from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
DEFAULT_CATALOG_ROOT = Path(r"C:\dev\pharmacy-product-catalog")
DEFAULT_PRODUCT_MASTER = OTC / "normalized" / "product_master.csv"
DEFAULT_POLICY = OTC / "selection" / "catalog_screening_policy.json"
DEFAULT_SELECTION_OUTPUT = OTC / "selection"
DEFAULT_AUDIT_OUTPUT = OTC / "audit"

INTERSECTION_FIELDS = [
    "catalog_source_id",
    "catalog_name",
    "catalog_specification",
    "catalog_category",
    "catalog_normalized_name",
    "catalog_normalized_specification",
    "duplicate_group_id",
    "duplicate_group_size",
    "existing_product_id",
    "item_sequence",
    "existing_product_name",
    "match_method",
    "match_score",
    "match_margin",
    "source_enrichment_match_status",
    "mfds_promotion_evidence_complete",
    "review_status",
    "promotion_allowed",
]

CANDIDATE_FIELDS = [
    "catalog_source_id",
    "catalog_name",
    "catalog_specification",
    "catalog_category",
    "catalog_normalized_name",
    "catalog_normalized_specification",
    "duplicate_group_id",
    "duplicate_group_size",
    "screening_class",
    "screening_status",
    "candidate_reason",
    "source_enrichment_match_status",
    "mfds_promotion_evidence_complete",
    "required_next_step",
    "promotion_allowed",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    return read_csv_bytes(path.read_bytes())


def read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def official_aliases(name: str, suffixes: list[str]) -> set[str]:
    without_qualifier = re.sub(r"\([^)]*\)", "", name or "").strip()
    base = normalize_text(without_qualifier)
    aliases = {normalize_text(name), base}
    for suffix in sorted({normalize_text(value) for value in suffixes}, key=len, reverse=True):
        if suffix and base.endswith(suffix) and len(base) > len(suffix) + 1:
            aliases.add(base[: -len(suffix)])
    return {alias for alias in aliases if alias}


def validate_catalog(catalog: list[dict[str, Any]]) -> None:
    required = ("id", "name", "capacity", "category", "verification_status")
    seen: set[str] = set()
    for row in catalog:
        source_id = str(row.get("id", ""))
        for field in required:
            if field not in row or row[field] is None:
                raise ValueError(f"catalog_schema_invalid:{source_id or 'missing_id'}:{field}")
        if not source_id:
            raise ValueError("catalog_schema_invalid:missing_id:id")
        if source_id in seen:
            raise ValueError(f"catalog_duplicate_source_id:{source_id}")
        seen.add(source_id)


def validate_catalog_csv_equivalence(catalog: list[dict[str, Any]], catalog_csv_payload: bytes | None) -> bool | None:
    if catalog_csv_payload is None:
        return None
    csv_rows = read_csv_bytes(catalog_csv_payload)
    fields = ("id", "name", "capacity", "category")
    json_projection = [{field: str(row[field]) for field in fields} for row in catalog]
    csv_projection = [{field: str(row.get(field, "")) for field in fields} for row in csv_rows]
    if json_projection != csv_projection:
        raise ValueError("catalog_json_csv_mismatch")
    return True


def duplicate_metadata(
    catalog: list[dict[str, Any]], queue: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], int, int]:
    names: dict[str, list[str]] = defaultdict(list)
    for row in catalog:
        names[normalize_text(str(row["name"]))].append(str(row["id"]))
    expected_sizes = {
        source_id: len(group)
        for group in names.values()
        for source_id in group
    }
    queue_by_id = {str(row.get("id", "")): row for row in queue}
    if set(queue_by_id) != set(expected_sizes):
        raise ValueError("catalog_duplicate_metadata_mismatch")
    for source_id, expected_size in expected_sizes.items():
        try:
            recorded_size = int(queue_by_id[source_id].get("duplicate_group_size", 0))
        except (TypeError, ValueError):
            recorded_size = 0
        if recorded_size != expected_size:
            raise ValueError("catalog_duplicate_metadata_mismatch")
    duplicate_groups = [group for group in names.values() if len(group) > 1]
    metadata = {
        source_id: {
            "duplicate_group_id": str(queue_by_id[source_id].get("duplicate_group_id", "")),
            "duplicate_group_size": expected_sizes[source_id],
            "source_enrichment_match_status": str(
                queue_by_id[source_id].get("official_match_status", "pending")
            ),
        }
        for source_id in expected_sizes
    }
    return metadata, len(duplicate_groups), sum(len(group) for group in duplicate_groups)


def screening_class(category: str, policy: dict[str, Any]) -> str:
    if category in set(policy["category_indicates_non_otc"]):
        return "category_indicates_non_otc_do_not_promote"
    if category in set(policy["possible_otc_categories"]):
        return "possible_otc_category_requires_official_domain"
    return "unresolved_category_requires_official_domain"


def product_candidates(
    catalog_name: str,
    products: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[dict[str, Any] | None, str, float, float]:
    normalized_name = normalize_text(catalog_name)
    scored: list[tuple[float, dict[str, Any]]] = []
    for product in products:
        aliases = product["aliases"]
        score = max(SequenceMatcher(None, normalized_name, alias).ratio() for alias in aliases)
        scored.append((score, product))
    scored.sort(key=lambda item: (-item[0], item[1]["product_id"]))
    if not scored:
        return None, "", 0.0, 0.0
    best_score, best = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second_score
    if best_score == 1.0 and (len(scored) == 1 or second_score < 1.0):
        return best, "exact_normalized_alias", best_score, margin
    if (
        len(normalized_name) >= int(policy["minimum_fuzzy_name_length"])
        and best_score >= float(policy["fuzzy_match_threshold"])
        and margin >= float(policy["fuzzy_match_margin"])
    ):
        return best, "fuzzy_normalized_alias", best_score, margin
    return None, "", best_score, margin


def matched_form_token(name: str, specification: str, policy: dict[str, Any]) -> str:
    normalized_name = normalize_text(name)
    normalized_specification = normalize_text(specification)
    patterns = {
        normalize_text(token): values
        for token, values in policy.get("form_capacity_patterns", {}).items()
    }
    for token in sorted({normalize_text(value) for value in policy["candidate_form_tokens"]}, key=len, reverse=True):
        if not token or not normalized_name.endswith(token):
            continue
        if any(re.search(pattern, normalized_specification, flags=re.IGNORECASE) for pattern in patterns.get(token, [])):
            return token
    return ""


def build_bridge(
    catalog_path: Path,
    queue_path: Path,
    product_master_path: Path,
    policy_path: Path,
    official_summary_path: Path | None = None,
    catalog_csv_path: Path | None = None,
) -> dict[str, Any]:
    catalog_payload = catalog_path.read_bytes()
    queue_payload = queue_path.read_bytes()
    product_master_payload = product_master_path.read_bytes()
    policy_payload = policy_path.read_bytes()
    catalog_csv_payload = catalog_csv_path.read_bytes() if catalog_csv_path else None
    official_summary_payload = (
        official_summary_path.read_bytes()
        if official_summary_path and official_summary_path.exists()
        else None
    )
    catalog = json.loads(catalog_payload.decode("utf-8-sig"))
    queue = json.loads(queue_payload.decode("utf-8-sig"))
    policy = json.loads(policy_payload.decode("utf-8-sig"))
    if not isinstance(catalog, list) or not isinstance(queue, list):
        raise ValueError("catalog_schema_invalid:root:list_required")
    validate_catalog(catalog)
    catalog_csv_equivalent = validate_catalog_csv_equivalence(catalog, catalog_csv_payload)
    duplicate_by_id, duplicate_group_count, products_in_duplicate_groups = duplicate_metadata(catalog, queue)

    products = []
    for row in read_csv_bytes(product_master_payload):
        if row.get("analysis_status") != "included":
            continue
        products.append(
            {
                "product_id": row["product_id"],
                "item_sequence": row["item_sequence"],
                "product_name": row["product_name"],
                "aliases": official_aliases(row["product_name"], policy["official_form_suffixes"]),
            }
        )

    intersections: list[dict[str, str]] = []
    fuzzy_reviews: list[dict[str, str]] = []
    matched_candidate_ids: set[str] = set()
    for row in catalog:
        source_id = str(row["id"])
        matched, method, score, margin = product_candidates(str(row["name"]), products, policy)
        if not matched:
            continue
        source_meta = duplicate_by_id[source_id]
        match_row = {
                "catalog_source_id": source_id,
                "catalog_name": str(row["name"]),
                "catalog_specification": str(row["capacity"]),
                "catalog_category": str(row["category"]),
                "catalog_normalized_name": normalize_text(str(row["name"])),
                "catalog_normalized_specification": normalize_text(str(row["capacity"])),
                "duplicate_group_id": str(source_meta["duplicate_group_id"]),
                "duplicate_group_size": str(source_meta["duplicate_group_size"]),
                "existing_product_id": str(matched["product_id"]),
                "item_sequence": str(matched["item_sequence"]),
                "existing_product_name": str(matched["product_name"]),
                "match_method": method,
                "match_score": f"{score:.4f}",
                "match_margin": f"{margin:.4f}",
                "source_enrichment_match_status": str(
                    source_meta["source_enrichment_match_status"]
                ),
                "mfds_promotion_evidence_complete": "false",
                "review_status": "requires_official_match_review",
                "promotion_allowed": "false",
            }
        if method == "exact_normalized_alias":
            intersections.append(match_row)
        else:
            fuzzy_reviews.append(match_row)
        matched_candidate_ids.add(source_id)

    non_drug_tokens = [normalize_text(value) for value in policy["non_drug_name_tokens"]]
    candidates: list[dict[str, str]] = []
    classification_counts: Counter[str] = Counter()
    for row in catalog:
        source_id = str(row["id"])
        category = str(row["category"])
        normalized_name = normalize_text(str(row["name"]))
        classification = screening_class(category, policy)
        classification_counts[classification] += 1
        form_token = matched_form_token(str(row["name"]), str(row["capacity"]), policy)
        has_non_drug_token = any(token in normalized_name for token in non_drug_tokens if token)
        if (
            source_id in matched_candidate_ids
            or classification != "possible_otc_category_requires_official_domain"
            or not form_token
            or has_non_drug_token
        ):
            continue
        source_meta = duplicate_by_id[source_id]
        candidates.append(
            {
                "catalog_source_id": source_id,
                "catalog_name": str(row["name"]),
                "catalog_specification": str(row["capacity"]),
                "catalog_category": category,
                "catalog_normalized_name": normalized_name,
                "catalog_normalized_specification": normalize_text(str(row["capacity"])),
                "duplicate_group_id": str(source_meta["duplicate_group_id"]),
                "duplicate_group_size": str(source_meta["duplicate_group_size"]),
                "screening_class": classification,
                "screening_status": "candidate_requires_official_domain_and_item_match",
                "candidate_reason": f"catalog_category_terminal_form_and_compatible_specification:{form_token}",
                "source_enrichment_match_status": str(
                    source_meta["source_enrichment_match_status"]
                ),
                "mfds_promotion_evidence_complete": "false",
                "required_next_step": "classify_source_domain_then_match_mfds_item_sequence_and_authorization",
                "promotion_allowed": "false",
            }
        )

    intersections.sort(key=lambda row: (row["existing_product_id"], row["catalog_source_id"]))
    fuzzy_reviews.sort(key=lambda row: (-float(row["match_score"]), row["catalog_source_id"]))
    candidates.sort(key=lambda row: (row["catalog_category"], row["catalog_normalized_name"], row["catalog_source_id"]))
    official_summary: dict[str, Any] = {}
    if official_summary_payload is not None:
        official_summary = json.loads(official_summary_payload.decode("utf-8-sig"))

    verification_counts = Counter(str(row["verification_status"]) for row in catalog)
    source_enrichment_match_status_counts = Counter(
        str(metadata["source_enrichment_match_status"])
        for metadata in duplicate_by_id.values()
    )
    summary = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "source_role": "private_domestic_sales_sku_candidate_population_only",
        "source_product_count": len(catalog),
        "source_verification_status_counts": dict(sorted(verification_counts.items())),
        "source_enrichment_match_status_counts": dict(
            sorted(source_enrichment_match_status_counts.items())
        ),
        "duplicate_group_count": duplicate_group_count,
        "products_in_duplicate_groups": products_in_duplicate_groups,
        "existing_analysis_product_count": len(products),
        "exact_intersection_sku_count": len(intersections),
        "exact_intersection_existing_product_count": len({row["existing_product_id"] for row in intersections}),
        "fuzzy_review_sku_count": len(fuzzy_reviews),
        "additional_screening_candidate_sku_count": len(candidates),
        "additional_screening_candidate_name_count": len({row["catalog_normalized_name"] for row in candidates}),
        "screening_classification_counts": dict(sorted(classification_counts.items())),
        "official_enrichment_status": official_summary.get("status", "unknown"),
        "official_product_count": official_summary.get("official_product_count", 0),
        "processed_official_match_count": official_summary.get("processed_count", 0),
        "price_fields_exported": False,
        "full_source_records_exported": False,
        "product_master_modified": False,
        "runtime_modified": False,
        "candidate_rows_are_otc_products": False,
        "promotion_requirement": "MFDS source domain, item_sequence, authorization, ingredients, dosage, and DUR evidence must be confirmed before promotion",
        "provenance": {
            "catalog_dataset_id": "pharmacy-product-catalog/data/products.json",
            "catalog_sha256": sha256_bytes(catalog_payload),
            "duplicate_queue_dataset_id": "pharmacy-product-catalog/data/enrichment-queue.json",
            "duplicate_queue_sha256": sha256_bytes(queue_payload),
            "catalog_csv_dataset_id": "pharmacy-product-catalog/data/catalog.csv" if catalog_csv_path else None,
            "catalog_csv_sha256": sha256_bytes(catalog_csv_payload) if catalog_csv_payload is not None else None,
            "source_recorded_dates": sorted({str(row.get("recorded_at", "")) for row in catalog if row.get("recorded_at")}),
        },
    }
    audit = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "valid": True,
        "source_schema_valid": True,
        "source_ids_unique": True,
        "source_duplicate_metadata_matches": True,
        "source_enrichment_status_is_not_mfds_promotion_evidence": True,
        "catalog_csv_equivalent_to_json": catalog_csv_equivalent,
        "source_full_record_count": len(catalog),
        "source_full_records_copied": False,
        "price_fields_copied": False,
        "official_match_required_before_promotion": True,
        "fuzzy_reviews_separated_from_exact_intersection": True,
        "official_enrichment_status": summary["official_enrichment_status"],
        "product_master_unchanged_by_bridge": True,
        "runtime_unchanged_by_bridge": True,
        "release_ready_changed_by_bridge": False,
        "performance_claim_allowed_changed_by_bridge": False,
    }
    return {
        "summary": summary,
        "intersections": intersections,
        "fuzzy_reviews": fuzzy_reviews,
        "candidates": candidates,
        "audit": audit,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_bridge(result: dict[str, Any], selection_output: Path, audit_output: Path) -> None:
    selection_output.mkdir(parents=True, exist_ok=True)
    audit_output.mkdir(parents=True, exist_ok=True)
    intersection_path = selection_output / "catalog_existing_product_intersection.csv"
    fuzzy_path = selection_output / "catalog_fuzzy_match_review.csv"
    candidate_path = selection_output / "catalog_additional_otc_candidates.csv"
    summary_path = selection_output / "catalog_candidate_summary.json"
    write_csv(intersection_path, result["intersections"], INTERSECTION_FIELDS)
    write_csv(fuzzy_path, result["fuzzy_reviews"], INTERSECTION_FIELDS)
    write_csv(candidate_path, result["candidates"], CANDIDATE_FIELDS)
    summary_path.write_text(
        json.dumps(result["summary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit = dict(result["audit"])
    audit["outputs"] = [
        {"path": "research_v3/otc/selection/catalog_existing_product_intersection.csv", "rows": len(result["intersections"]), "sha256": sha256(intersection_path)},
        {"path": "research_v3/otc/selection/catalog_fuzzy_match_review.csv", "rows": len(result["fuzzy_reviews"]), "sha256": sha256(fuzzy_path)},
        {"path": "research_v3/otc/selection/catalog_additional_otc_candidates.csv", "rows": len(result["candidates"]), "sha256": sha256(candidate_path)},
        {"path": "research_v3/otc/selection/catalog_candidate_summary.json", "rows": 1, "sha256": sha256(summary_path)},
    ]
    (audit_output / "catalog_candidate_bridge.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build privacy-limited OTC candidates from a private pharmacy catalog.")
    parser.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG_ROOT)
    parser.add_argument("--product-master", type=Path, default=DEFAULT_PRODUCT_MASTER)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--selection-output", type=Path, default=DEFAULT_SELECTION_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    args = parser.parse_args()
    result = build_bridge(
        args.catalog_root / "data" / "products.json",
        args.catalog_root / "data" / "enrichment-queue.json",
        args.product_master,
        args.policy,
        args.catalog_root / "data" / "official-data-summary.json",
        args.catalog_root / "data" / "catalog.csv",
    )
    write_bridge(result, args.selection_output, args.audit_output)
    print(
        json.dumps(
            {
                "source_products": result["summary"]["source_product_count"],
                "duplicate_groups": result["summary"]["duplicate_group_count"],
                "products_in_duplicate_groups": result["summary"]["products_in_duplicate_groups"],
                "exact_intersection_skus": result["summary"]["exact_intersection_sku_count"],
                "exact_intersection_existing_products": result["summary"]["exact_intersection_existing_product_count"],
                "fuzzy_review_skus": result["summary"]["fuzzy_review_sku_count"],
                "additional_candidate_skus": result["summary"]["additional_screening_candidate_sku_count"],
                "additional_candidate_names": result["summary"]["additional_screening_candidate_name_count"],
                "official_enrichment_status": result["summary"]["official_enrichment_status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
