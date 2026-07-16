from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.research.otc.health_kr_catalog import (
        ALLOWED_MATCH_STATUSES,
        SafetyProfile,
        classify_product,
        dur_minimum_age_years,
        flatten_text,
        health_kr_raw,
        ingredient_codes,
        ingredient_form_group_id,
        nonempty,
        research_use_status,
        safety_exclusion_reasons,
        search_research_candidates,
        stable_official_key,
        validate_records,
    )
except ModuleNotFoundError:  # Direct script execution from the repository root.
    from health_kr_catalog import (  # type: ignore
        ALLOWED_MATCH_STATUSES,
        SafetyProfile,
        classify_product,
        dur_minimum_age_years,
        flatten_text,
        health_kr_raw,
        ingredient_codes,
        ingredient_form_group_id,
        nonempty,
        research_use_status,
        safety_exclusion_reasons,
        search_research_candidates,
        stable_official_key,
        validate_records,
    )


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
DEFAULT_CATALOG_ROOT = Path(r"C:\dev\pharmacy-product-catalog")

STATUS_INDEX_FIELDS = [
    "catalog_source_id",
    "document_id",
    "official_match_status",
    "official_product_key",
    "official_item_seq",
    "stable_official_key",
    "research_use_status",
    "mfds_promotion_evidence_complete",
    "runtime_promotion_allowed",
    "exclusion_reason",
]

CANDIDATE_FIELDS = [
    "catalog_source_id",
    "official_product_key",
    "official_item_seq",
    "stable_official_key",
    "official_item_name",
    "official_manufacturer",
    "official_source_type",
    "official_source_url",
    "official_category",
    "research_classification",
    "official_dosage_form",
    "official_route",
    "official_atc_code",
    "official_kpic_atc",
    "ingredient_form_group_id",
    "ingredient_count",
    "has_efficacy",
    "has_dosage",
    "has_precautions",
    "has_interactions",
    "has_dur_age",
    "has_dur_pregnancy",
    "has_dur_contraindications",
    "research_search_usable",
    "deterministic_screening_eligible",
    "clinical_ranking_uses_price",
    "mfds_promotion_evidence_complete",
    "runtime_promotion_allowed",
]

GROUP_FIELDS = [
    "ingredient_form_group_id",
    "ingredient_codes",
    "official_dosage_form",
    "research_classifications",
    "official_product_count",
    "retail_sku_count",
    "official_product_keys",
]

CONFLICT_FIELDS = [
    "catalog_source_id",
    "stable_official_key",
    "official_item_seq",
    "official_source_url",
    "conflict_count",
    "conflict_reasons",
]

EXPECTED_EXISTING_RESEARCH_BOUNDARY = {
    "product_master_records": 16,
    "analysis_products": 13,
    "runtime_products": 13,
    "runtime_unique_ingredients": 28,
    "runtime_product_ingredient_bindings": 47,
    "runtime_administration_constraints": 32,
    "rules_total": 16,
    "rules_released": 15,
    "complete": False,
    "release_ready": False,
    "independent_blinding": False,
    "performance_claim_allowed": False,
}

CSV_PROJECTION_FIELDS = (
    "id",
    "document_id",
    "name",
    "official_match_status",
    "official_product_key",
    "official_item_seq",
    "official_source_url",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_json_bytes(payload: bytes, source: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"source_json_invalid:{source}") from exc
    if not isinstance(value, list):
        raise ValueError(f"source_json_root_invalid:{source}")
    return value


def read_csv_bytes(payload: bytes, source: Path) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"source_csv_invalid:{source}") from exc
    previous_limit = csv.field_size_limit()
    try:
        csv.field_size_limit(2_147_483_647)
        return list(csv.DictReader(io.StringIO(text, newline="")))
    finally:
        csv.field_size_limit(previous_limit)


def validate_source_trio(
    records: list[dict[str, Any]],
    csv_rows: list[dict[str, str]],
    queue_payload: bytes,
    public_payload: bytes,
) -> None:
    if queue_payload != public_payload:
        raise ValueError("public_sync_mismatch")
    if len(records) != len(csv_rows):
        raise ValueError("catalog_json_csv_count_mismatch")
    for index, (record, csv_row) in enumerate(zip(records, csv_rows)):
        for field in CSV_PROJECTION_FIELDS:
            if str(record.get(field, "")) != str(csv_row.get(field, "")):
                raise ValueError(f"catalog_json_csv_projection_mismatch:{index}:{field}")


def exclusion_reason(record: dict[str, Any], status: str) -> str:
    if status == "research_search_usable":
        return ""
    if status == "excluded_unconfirmed":
        return f"official_match_status:{record.get('official_match_status', '')}"
    return status


def missingness(
    confirmed: list[dict[str, Any]],
    accessors: dict[str, Callable[[dict[str, Any]], Any]],
) -> dict[str, dict[str, float | int]]:
    denominator = len(confirmed)
    result: dict[str, dict[str, float | int]] = {}
    for field, accessor in accessors.items():
        present = sum(nonempty(accessor(record)) for record in confirmed)
        missing = denominator - present
        result[field] = {
            "present": present,
            "missing": missing,
            "denominator": denominator,
            "missing_rate": round(missing / denominator, 6) if denominator else 0.0,
        }
    return result


def _csv_file_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def existing_research_invariants(root: Path) -> dict[str, Any]:
    otc = root / "research_v3" / "otc"
    products = _csv_file_rows(otc / "normalized" / "product_master.csv")
    rules = _csv_file_rows(otc / "rules" / "rules.csv")
    runtime = _json_file(root / "src" / "generated" / "otc-runtime.json")
    alignment = _json_file(otc / "audit" / "runtime_research_alignment.json")
    completion = _json_file(otc / "audit" / "completion_audit.json")
    independent = _json_file(otc / "validation" / "independent_evaluation.json")
    runtime_products = runtime.get("products", [])
    runtime_bindings = [
        ingredient
        for product in runtime_products
        for ingredient in product.get("ingredients", [])
    ]
    observed = {
        "product_master_records": len(products),
        "analysis_products": sum(row.get("analysis_status") == "included" for row in products),
        "runtime_products": len(runtime_products),
        "runtime_unique_ingredients": len(
            {row.get("ingredientId") for row in runtime_bindings if row.get("ingredientId")}
        ),
        "runtime_product_ingredient_bindings": len(runtime_bindings),
        "runtime_administration_constraints": sum(
            len(product.get("administrationConstraints", [])) for product in runtime_products
        ),
        "rules_total": len(rules),
        "rules_released": sum(row.get("status") == "released" for row in rules),
        "complete": completion.get("complete"),
        "release_ready": completion.get("release_ready"),
        "independent_blinding": independent.get("independent_blinding"),
        "performance_claim_allowed": independent.get("performance_claim_allowed"),
    }
    mismatches = {
        key: {"expected": expected, "observed": observed.get(key)}
        for key, expected in EXPECTED_EXISTING_RESEARCH_BOUNDARY.items()
        if observed.get(key) != expected
    }
    if alignment.get("valid") is not True:
        mismatches["runtime_research_alignment"] = {
            "expected": True,
            "observed": alignment.get("valid"),
        }
    return {
        "valid": not mismatches,
        "expected": EXPECTED_EXISTING_RESEARCH_BOUNDARY,
        "observed": observed,
        "runtime_research_alignment_valid": alignment.get("valid") is True,
        "mismatches": mismatches,
    }


def _first_flattened_value(value: Any) -> str:
    flattened = " ".join(flatten_text(value).split())
    return flattened[:500]


def build_safety_evaluation(records: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [record for record in records if research_use_status(record) == "research_search_usable"]
    if not usable:
        return {
            "valid": False,
            "error": "no_research_search_usable_records",
            "performance_claim_allowed": False,
        }
    query = str(usable[0].get("official_item_name", ""))
    baseline = search_research_candidates(usable[:100], query, SafetyProfile())
    price_changed = deepcopy(usable[:100])
    for index, record in enumerate(price_changed):
        record["price"] = str((index + 1) * 999999)
        record["displayed_price_krw"] = (index + 1) * 999999
    repriced = search_research_candidates(price_changed, query, SafetyProfile())
    baseline_keys = [row["stableOfficialKey"] for row in baseline["candidates"]]
    repriced_keys = [row["stableOfficialKey"] for row in repriced["candidates"]]
    red_flag = search_research_candidates(
        usable[:100], query, SafetyProfile(red_flags=("sentinel_red_flag",))
    )

    pregnancy_rows = [row for row in usable if nonempty(row.get("official_dur_pregnancy"))]
    age_rows = [row for row in usable if nonempty(row.get("official_dur_age"))]
    senior_rows = [row for row in usable if nonempty(row.get("official_dur_senior"))]
    contraindication_rows = [
        row for row in usable if nonempty(row.get("official_dur_contraindications"))
    ]
    interaction_rows = [row for row in usable if nonempty(row.get("official_interactions"))]

    pregnancy_passed = sum(
        "dur_pregnancy" in safety_exclusion_reasons(row, SafetyProfile(pregnant=True))
        for row in pregnancy_rows
    )
    age_passed = 0
    for row in age_rows:
        threshold = dur_minimum_age_years(row.get("official_dur_age"))
        test_age = max(0.0, threshold - (1 / 365)) if threshold is not None else 0.0
        reasons = safety_exclusion_reasons(row, SafetyProfile(age_years=test_age))
        if "dur_age" in reasons or "dur_age_unparsed" in reasons:
            age_passed += 1
    senior_passed = sum(
        "dur_senior" in safety_exclusion_reasons(row, SafetyProfile(age_years=70))
        for row in senior_rows
    )
    contraindication_passed = 0
    for row in contraindication_rows:
        term = str(row.get("official_dur_contraindications", ""))
        if safety_exclusion_reasons(row, SafetyProfile(conditions=(term,))):
            contraindication_passed += 1
    interaction_passed = 0
    for row in interaction_rows:
        term = _first_flattened_value(row.get("official_interactions"))
        if term and safety_exclusion_reasons(row, SafetyProfile(medications=(term,))):
            interaction_passed += 1

    checks = {
        "confirmed_status_isolation": all(
            row.get("official_match_status") == "confirmed" for row in usable
        ),
        "price_does_not_change_clinical_ranking": baseline_keys == repriced_keys,
        "red_flag_returns_zero_candidates": red_flag["candidates"] == [],
        "red_flag_referral_preserved": red_flag["disposition"]
        == "refer_to_pharmacist_or_clinician",
        "pregnancy_dur_exclusion": pregnancy_passed == len(pregnancy_rows),
        "age_dur_exclusion": age_passed == len(age_rows),
        "senior_dur_exclusion": senior_passed == len(senior_rows),
        "contraindication_exclusion": contraindication_passed
        == len(contraindication_rows),
        "interaction_exclusion": interaction_passed == len(interaction_rows),
    }
    return {
        "valid": all(checks.values()),
        "decision_mode": "deterministic",
        "scope": "catalog_research_candidate_screening_not_clinical_performance",
        "performance_claim_allowed": False,
        "checks": checks,
        "cases": {
            "pregnancy_dur": len(pregnancy_rows),
            "age_dur": len(age_rows),
            "senior_dur": len(senior_rows),
            "contraindications": len(contraindication_rows),
            "interactions": len(interaction_rows),
            "red_flags": 1,
            "price_invariance": 1,
        },
    }


def build_import(
    queue_path: Path,
    csv_path: Path,
    public_path: Path,
    research_root: Path = ROOT,
) -> dict[str, Any]:
    queue_payload = queue_path.read_bytes()
    csv_payload = csv_path.read_bytes()
    public_payload = public_path.read_bytes()
    records = read_json_bytes(queue_payload, queue_path)
    public_records = read_json_bytes(public_payload, public_path)
    csv_rows = read_csv_bytes(csv_payload, csv_path)
    validate_source_trio(records, csv_rows, queue_payload, public_payload)
    if len(public_records) != len(records):
        raise ValueError("public_sync_count_mismatch")
    validation_counts = validate_records(records)
    research_invariants = existing_research_invariants(research_root)

    status_counts = Counter(str(record.get("official_match_status", "")) for record in records)
    status_counts_full = {
        status: status_counts.get(status, 0) for status in sorted(ALLOWED_MATCH_STATUSES)
    }
    confirmed = [record for record in records if record.get("official_match_status") == "confirmed"]
    usable = [record for record in confirmed if research_use_status(record) == "research_search_usable"]
    mapping_failures = [
        record
        for record in confirmed
        if not stable_official_key(record)
        or not record.get("official_item_seq")
        or not record.get("official_source_url")
    ]

    status_index: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []
    for record in records:
        use_status = research_use_status(record)
        source_id = str(record.get("id") or record.get("document_id") or "")
        status_index.append(
            {
                "catalog_source_id": source_id,
                "document_id": str(record.get("document_id", "")),
                "official_match_status": str(record.get("official_match_status", "")),
                "official_product_key": str(record.get("official_product_key", "")),
                "official_item_seq": str(record.get("official_item_seq", "")),
                "stable_official_key": stable_official_key(record),
                "research_use_status": use_status,
                "mfds_promotion_evidence_complete": "false",
                "runtime_promotion_allowed": "false",
                "exclusion_reason": exclusion_reason(record, use_status),
            }
        )
        if use_status != "research_search_usable":
            continue
        candidates.append(
            {
                "catalog_source_id": source_id,
                "official_product_key": str(record.get("official_product_key", "")),
                "official_item_seq": str(record.get("official_item_seq", "")),
                "stable_official_key": stable_official_key(record),
                "official_item_name": str(record.get("official_item_name", "")),
                "official_manufacturer": str(record.get("official_manufacturer", "")),
                "official_source_type": str(record.get("official_source_type", "")),
                "official_source_url": str(record.get("official_source_url", "")),
                "official_category": str(record.get("official_category", "")),
                "research_classification": classify_product(record),
                "official_dosage_form": str(record.get("official_dosage_form", "")),
                "official_route": str(record.get("official_route", "")),
                "official_atc_code": str(record.get("official_atc_code", "")),
                "official_kpic_atc": str(record.get("official_kpic_atc", "")),
                "ingredient_form_group_id": ingredient_form_group_id(record),
                "ingredient_count": str(len(ingredient_codes(record))),
                "has_efficacy": str(nonempty(record.get("official_efficacy"))).lower(),
                "has_dosage": str(nonempty(record.get("official_dosage"))).lower(),
                "has_precautions": str(nonempty(record.get("official_precautions"))).lower(),
                "has_interactions": str(nonempty(record.get("official_interactions"))).lower(),
                "has_dur_age": str(nonempty(record.get("official_dur_age"))).lower(),
                "has_dur_pregnancy": str(nonempty(record.get("official_dur_pregnancy"))).lower(),
                "has_dur_contraindications": str(
                    nonempty(record.get("official_dur_contraindications"))
                ).lower(),
                "research_search_usable": "true",
                "deterministic_screening_eligible": "true",
                "clinical_ranking_uses_price": "false",
                "mfds_promotion_evidence_complete": "false",
                "runtime_promotion_allowed": "false",
            }
        )

    group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in usable:
        group_members[ingredient_form_group_id(record)].append(record)
    groups: list[dict[str, str]] = []
    for group_id, members in group_members.items():
        stable_keys = sorted({stable_official_key(record) for record in members})
        groups.append(
            {
                "ingredient_form_group_id": group_id,
                "ingredient_codes": ";".join(ingredient_codes(members[0])),
                "official_dosage_form": str(members[0].get("official_dosage_form", "")),
                "research_classifications": ";".join(
                    sorted({classify_product(record) for record in members})
                ),
                "official_product_count": str(len(stable_keys)),
                "retail_sku_count": str(len(members)),
                "official_product_keys": ";".join(stable_keys),
            }
        )

    official_key_groups = Counter(stable_official_key(record) for record in confirmed)
    duplicate_groups = {key: count for key, count in official_key_groups.items() if count > 1}
    conflict_records = [
        record
        for record in confirmed
        if nonempty((record.get("official_section_evidence") or {}).get("conflicts", []))
    ]
    conflict_entries = sum(
        len((record.get("official_section_evidence") or {}).get("conflicts", []))
        for record in conflict_records
    )
    conflicts = [
        {
            "catalog_source_id": str(record.get("id") or record.get("document_id") or ""),
            "stable_official_key": stable_official_key(record),
            "official_item_seq": str(record.get("official_item_seq", "")),
            "official_source_url": str(record.get("official_source_url", "")),
            "conflict_count": str(
                len((record.get("official_section_evidence") or {}).get("conflicts", []))
            ),
            "conflict_reasons": " | ".join(
                str(value)
                for value in (record.get("official_section_evidence") or {}).get(
                    "conflicts", []
                )
            ),
        }
        for record in conflict_records
    ]

    existing_item_sequences = {
        row["item_sequence"]
        for row in _csv_file_rows(
            research_root / "research_v3" / "otc" / "normalized" / "product_master.csv"
        )
        if row.get("item_sequence")
    }
    stable_identifier_overlaps = [
        record
        for record in usable
        if str(record.get("official_item_seq", "")) in existing_item_sequences
    ]

    field_accessors: dict[str, Callable[[dict[str, Any]], Any]] = {
        "retail_price": lambda row: row.get("price") or row.get("displayed_price_krw"),
        "retail_specification": lambda row: row.get("capacity") or row.get("specification"),
        "official_product_key": lambda row: row.get("official_product_key"),
        "official_item_seq": lambda row: row.get("official_item_seq"),
        "standard_code_or_barcode": lambda row: row.get("official_standard_codes")
        or row.get("official_barcode"),
        "efficacy": lambda row: row.get("official_efficacy"),
        "dosage": lambda row: row.get("official_dosage"),
        "active_ingredients": lambda row: row.get("official_active_ingredients"),
        "dosage_form": lambda row: row.get("official_dosage_form"),
        "route": lambda row: row.get("official_route"),
        "atc_code": lambda row: row.get("official_atc_code"),
        "kpic_atc": lambda row: row.get("official_kpic_atc"),
        "storage": lambda row: row.get("official_storage"),
        "valid_term": lambda row: row.get("official_valid_term"),
        "insurance": lambda row: row.get("official_insurance"),
        "precautions": lambda row: row.get("official_precautions"),
        "professional_precautions": lambda row: row.get("official_professional_precautions"),
        "interactions": lambda row: row.get("official_interactions"),
        "dur_contraindications": lambda row: row.get("official_dur_contraindications"),
        "dur_age": lambda row: row.get("official_dur_age"),
        "dur_pregnancy": lambda row: row.get("official_dur_pregnancy"),
        "dur_senior": lambda row: row.get("official_dur_senior"),
        "dur_max_dose": lambda row: row.get("official_dur_max_dose"),
        "dur_max_period": lambda row: row.get("official_dur_max_period"),
        "dur_split_dosage": lambda row: row.get("official_dur_split_dosage"),
        "medication_guide": lambda row: row.get("official_medication_guide"),
        "same_ingredient_products": lambda row: row.get("official_same_ingredient_products"),
    }
    classification_counts = Counter(classify_product(record) for record in usable)
    safety_evaluation = build_safety_evaluation(records)
    provenance = {
        "queue_dataset_id": "pharmacy-product-catalog/data/enrichment-queue.json",
        "queue_sha256": sha256_bytes(queue_payload),
        "queue_bytes": len(queue_payload),
        "csv_dataset_id": "pharmacy-product-catalog/data/enrichment-queue.csv",
        "csv_sha256": sha256_bytes(csv_payload),
        "csv_bytes": len(csv_payload),
        "public_dataset_id": "pharmacy-product-catalog/public/data/enrichment-queue.json",
        "public_sha256": sha256_bytes(public_payload),
        "public_bytes": len(public_payload),
        "source_files_read_once": True,
        "public_sync_exact": queue_payload == public_payload,
        "csv_projection_equivalent": True,
    }
    summary = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_role": "private_health_kr_linked_sales_sku_research_input",
        "source_record_count": len(records),
        "normal_import_count": validation_counts["record_count"],
        "status_counts": status_counts_full,
        "confirmed_count": len(confirmed),
        "confirmed_unique_official_product_count": len(official_key_groups),
        "research_search_usable_count": len(usable),
        "research_search_usable_unique_official_product_count": len(
            {stable_official_key(record) for record in usable}
        ),
        "deterministic_screening_eligible_count": len(usable),
        "runtime_promotion_allowed_count": 0,
        "mapping_failure_count": len(mapping_failures),
        "duplicate_official_product_group_count": len(duplicate_groups),
        "duplicate_linked_retail_sku_count": sum(duplicate_groups.values()),
        "duplicate_extra_link_count": sum(duplicate_groups.values()) - len(duplicate_groups),
        "ingredient_form_group_count": len(groups),
        "conflict_record_count": len(conflict_records),
        "conflict_entry_count": conflict_entries,
        "existing_mfds_stable_identifier_overlap_count": len(stable_identifier_overlaps),
        "classification_counts": dict(sorted(classification_counts.items())),
        "missingness_confirmed": missingness(confirmed, field_accessors),
        "candidate_rows_are_clinical_recommendations": False,
        "source_enrichment_status_is_not_mfds_promotion_evidence": True,
        "full_source_records_exported": False,
        "price_values_exported": False,
        "clinical_ranking_uses_price": False,
        "provenance": provenance,
    }
    audit = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "valid": safety_evaluation.get("valid", False) and research_invariants["valid"],
        "source_schema_valid": True,
        "source_ids_unique": validation_counts["unique_source_ids"] == len(records),
        "source_trio_counts_equal": len(records) == len(csv_rows) == len(public_records),
        "public_sync_exact": True,
        "csv_projection_equivalent": True,
        "official_match_statuses_isolated": all(
            record.get("official_match_status") == "confirmed" for record in usable
        ),
        "stable_identifier_required": True,
        "name_similarity_not_used_as_identity": True,
        "ingredient_groups_use_stable_codes_and_dosage_form": True,
        "full_source_records_copied": False,
        "price_values_copied": False,
        "price_used_for_clinical_ranking": False,
        "existing_research_invariants": research_invariants,
        "catalog_runtime_promotion_attempted": any(
            row["runtime_promotion_allowed"] != "false" for row in status_index
        ),
        "release_ready_changed": False,
        "safety_evaluation": safety_evaluation,
        "counts": {
            "source_records": len(records),
            "confirmed": len(confirmed),
            "research_search_usable": len(usable),
            "runtime_promotion_allowed": 0,
            "mapping_failures": len(mapping_failures),
            "conflicts": conflict_entries,
        },
        "provenance": provenance,
    }
    status_index.sort(key=lambda row: row["catalog_source_id"])
    candidates.sort(key=lambda row: (row["stable_official_key"], row["catalog_source_id"]))
    groups.sort(key=lambda row: row["ingredient_form_group_id"])
    conflicts.sort(key=lambda row: row["catalog_source_id"])
    return {
        "summary": summary,
        "audit": audit,
        "status_index": status_index,
        "candidates": candidates,
        "groups": groups,
        "conflicts": conflicts,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_import(
    result: dict[str, Any],
    selection_output: Path,
    audit_output: Path,
) -> None:
    selection_output.mkdir(parents=True, exist_ok=True)
    audit_output.mkdir(parents=True, exist_ok=True)
    status_path = selection_output / "catalog_health_kr_status_index.csv"
    candidates_path = selection_output / "catalog_health_kr_research_candidates.csv"
    groups_path = selection_output / "catalog_health_kr_same_ingredient_groups.csv"
    conflicts_path = selection_output / "catalog_health_kr_conflict_review.csv"
    summary_path = selection_output / "catalog_health_kr_summary.json"
    audit_path = audit_output / "catalog_health_kr_integration.json"
    write_csv(status_path, result["status_index"], STATUS_INDEX_FIELDS)
    write_csv(candidates_path, result["candidates"], CANDIDATE_FIELDS)
    write_csv(groups_path, result["groups"], GROUP_FIELDS)
    write_csv(conflicts_path, result["conflicts"], CONFLICT_FIELDS)
    summary_path.write_text(
        json.dumps(result["summary"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit = dict(result["audit"])
    audit["outputs"] = [
        {"path": "research_v3/otc/selection/catalog_health_kr_status_index.csv", "rows": len(result["status_index"]), "sha256": sha256(status_path)},
        {"path": "research_v3/otc/selection/catalog_health_kr_research_candidates.csv", "rows": len(result["candidates"]), "sha256": sha256(candidates_path)},
        {"path": "research_v3/otc/selection/catalog_health_kr_same_ingredient_groups.csv", "rows": len(result["groups"]), "sha256": sha256(groups_path)},
        {"path": "research_v3/otc/selection/catalog_health_kr_conflict_review.csv", "rows": len(result["conflicts"]), "sha256": sha256(conflicts_path)},
        {"path": "research_v3/otc/selection/catalog_health_kr_summary.json", "rows": 1, "sha256": sha256(summary_path)},
    ]
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import health.kr-linked pharmacy catalog records into the private OTC research candidate layer."
    )
    parser.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG_ROOT)
    parser.add_argument("--selection-output", type=Path, default=OTC / "selection")
    parser.add_argument("--audit-output", type=Path, default=OTC / "audit")
    args = parser.parse_args()
    result = build_import(
        args.catalog_root / "data" / "enrichment-queue.json",
        args.catalog_root / "data" / "enrichment-queue.csv",
        args.catalog_root / "public" / "data" / "enrichment-queue.json",
    )
    write_import(result, args.selection_output, args.audit_output)
    summary = result["summary"]
    print(
        json.dumps(
            {
                "source_records": summary["source_record_count"],
                "confirmed": summary["confirmed_count"],
                "research_search_usable": summary["research_search_usable_count"],
                "review_required": summary["status_counts"]["review_required"],
                "not_found": summary["status_counts"]["not_found"],
                "not_applicable": summary["status_counts"]["not_applicable"],
                "runtime_promotion_allowed": summary["runtime_promotion_allowed_count"],
                "mapping_failures": summary["mapping_failure_count"],
                "conflicts": summary["conflict_entry_count"],
                "valid": result["audit"]["valid"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["audit"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
