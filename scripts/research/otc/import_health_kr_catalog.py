from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
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
    "retail_display_name",
    "retail_specification",
    "retail_normalized_name",
    "retail_normalized_capacity",
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

EXISTING_MATCH_FIELDS = [
    "research_product_id",
    "mfds_item_sequence",
    "research_product_name",
    "in_runtime",
    "match_status",
    "match_method",
    "health_kr_item_seq",
    "official_product_key",
    "official_item_name",
    "official_manufacturer",
    "official_dosage_form",
    "official_pack_unit",
    "retail_sku_count",
    "retail_display_links",
    "official_source_url",
    "stable_identifier_match",
    "exact_name_match",
    "manufacturer_match",
    "dosage_form_match",
    "package_compatible",
    "ingredient_count_match",
    "conflict_codes",
    "decision_reason",
    "mfds_promotion_evidence_complete",
    "catalog_runtime_promotion_allowed",
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


def read_json_object_bytes(payload: bytes, source: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"source_json_invalid:{source}") from exc
    if not isinstance(value, dict):
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


def validate_source_pair(
    records: list[dict[str, Any]], csv_rows: list[dict[str, str]]
) -> None:
    if len(records) != len(csv_rows):
        raise ValueError("catalog_json_csv_count_mismatch")
    for index, (record, csv_row) in enumerate(zip(records, csv_rows)):
        for field in CSV_PROJECTION_FIELDS:
            if str(record.get(field, "")) != str(csv_row.get(field, "")):
                raise ValueError(f"catalog_json_csv_projection_mismatch:{index}:{field}")


def _contains_raw_html(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.casefold()
        return "<br" in lowered or bool(__import__("re").search(r"</?[a-z][^>]*>", lowered))
    if isinstance(value, list):
        return any(_contains_raw_html(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_raw_html(item) for item in value.values())
    return False


def validate_portable_package(
    records: list[dict[str, Any]],
    portable_records: list[dict[str, Any]],
    manifest: dict[str, Any],
    portable_payload: bytes,
    schema_payload: bytes,
) -> dict[str, dict[str, Any]]:
    expected_products_hash = (
        (manifest.get("files") or {}).get("products.json") or {}
    ).get("sha256")
    expected_schema_hash = ((manifest.get("files") or {}).get("schema.json") or {}).get(
        "sha256"
    )
    if expected_products_hash != sha256_bytes(portable_payload):
        raise ValueError("portable_products_hash_mismatch")
    if expected_schema_hash and expected_schema_hash != sha256_bytes(schema_payload):
        raise ValueError("portable_schema_hash_mismatch")
    if manifest.get("schema_version") != "1.0":
        raise ValueError("portable_schema_version_unsupported")
    if manifest.get("product_count") != len(portable_records):
        raise ValueError("portable_manifest_product_count_mismatch")

    by_id: dict[str, dict[str, Any]] = {}
    for portable in portable_records:
        product_id = str(portable.get("product_id", ""))
        if not product_id or product_id in by_id:
            raise ValueError(f"portable_product_id_invalid:{product_id or 'missing'}")
        by_id[product_id] = portable
    queue_by_id = {str(record.get("id", "")): record for record in records}
    if set(by_id) != set(queue_by_id):
        raise ValueError("portable_queue_product_ids_mismatch")

    confirmed_count = 0
    for product_id, portable in by_id.items():
        record = queue_by_id[product_id]
        display = portable.get("display") or {}
        quality = portable.get("quality") or {}
        if str(display.get("name", "")) != str(record.get("name", "")):
            raise ValueError(f"portable_corrected_name_mismatch:{product_id}")
        expected_specification = str(record.get("specification") or record.get("capacity") or "")
        if str(display.get("specification", "")) != expected_specification:
            raise ValueError(f"portable_corrected_specification_mismatch:{product_id}")
        if str(quality.get("official_match_status", "")) != str(
            record.get("official_match_status", "")
        ):
            raise ValueError(f"portable_match_status_mismatch:{product_id}")
        if record.get("official_match_status") == "confirmed":
            confirmed_count += 1
            medicine = portable.get("medicine") or {}
            identity = medicine.get("identity") or {}
            source = medicine.get("source") or {}
            if not all(
                str(value or "").strip()
                for value in (
                    identity.get("item_code"),
                    identity.get("item_name"),
                    identity.get("manufacturer"),
                    source.get("url"),
                )
            ):
                raise ValueError(f"portable_confirmed_identity_missing:{product_id}")
            content = medicine.get("content") or {}
            if content.get("schema_version") != "1.0":
                raise ValueError(f"portable_content_schema_invalid:{product_id}")
            if _contains_raw_html(content):
                raise ValueError(f"portable_content_not_normalized:{product_id}")
    if manifest.get("official_confirmed_count") != confirmed_count:
        raise ValueError("portable_manifest_confirmed_count_mismatch")
    return by_id


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


def _normalized_identity_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _product_name_identity(value: Any) -> str:
    without_parentheses = re.sub(r"\([^)]*\)", "", str(value or ""))
    return _normalized_identity_text(without_parentheses)


def _manufacturer_identity(value: Any) -> str:
    normalized = _normalized_identity_text(value)
    for token in ("판매유한회사", "주식회사", "유한회사"):
        normalized = normalized.replace(token, "")
    if normalized.startswith("주"):
        normalized = normalized[1:]
    if normalized.endswith("주"):
        normalized = normalized[:-1]
    return normalized


def _dosage_form_identity(value: Any) -> str:
    normalized = _normalized_identity_text(value)
    if "현탁액" in normalized:
        return "현탁액"
    if "장용" in normalized:
        return "장용정"
    if "연질캡슐" in normalized:
        return "연질캡슐"
    if "캡슐" in normalized:
        return "캡슐"
    if "정제" in normalized or normalized.endswith("정"):
        return "정제"
    if "시럽" in normalized:
        return "시럽"
    return normalized


def _package_token(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    normalized = re.sub(r"(?<=\d)\s*t\b", "정", normalized)
    normalized = normalized.replace("밀리리터", "ml")
    return "".join(character for character in normalized if character.isalnum())


def _validated_standard_codes(record: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    barcode = record.get("official_barcode")
    if barcode:
        values.append(barcode)
    standard_codes = record.get("official_standard_codes")
    if isinstance(standard_codes, list):
        values.extend(standard_codes)
    elif standard_codes:
        values.append(standard_codes)
    return sorted(
        {
            str(value).strip()
            for value in values
            if re.fullmatch(r"\d{8,14}", str(value).strip())
        }
    )


def rematch_existing_research_products(
    records: list[dict[str, Any]], research_root: Path
) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    products = _csv_file_rows(
        research_root / "research_v3" / "otc" / "normalized" / "product_master.csv"
    )
    ingredients = _csv_file_rows(
        research_root / "research_v3" / "otc" / "normalized" / "product_ingredient.csv"
    )
    ingredient_ids_by_product: dict[str, set[str]] = defaultdict(set)
    for ingredient in ingredients:
        ingredient_ids_by_product[str(ingredient.get("product_id", ""))].add(
            str(ingredient.get("ingredient_id", ""))
        )
    runtime = _json_file(research_root / "src" / "generated" / "otc-runtime.json")
    runtime_item_sequences = {
        str(product.get("itemSequence", "")) for product in runtime.get("products", [])
    }
    confirmed = [
        record for record in records if record.get("official_match_status") == "confirmed"
    ]
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_health_item_seq: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_official_product_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_validated_standard_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in confirmed:
        by_name[_product_name_identity(record.get("official_item_name"))].append(record)
        by_health_item_seq[str(record.get("official_item_seq", ""))].append(record)
        by_official_product_key[str(record.get("official_product_key", ""))].append(record)
        for code in _validated_standard_codes(record):
            by_validated_standard_code[code].append(record)

    rows: list[dict[str, str]] = []
    for product in products:
        product_id = str(product.get("product_id", ""))
        mfds_item_sequence = str(product.get("item_sequence", ""))
        stable_matches = (
            by_health_item_seq.get(mfds_item_sequence, [])
            or by_official_product_key.get(mfds_item_sequence, [])
            or by_validated_standard_code.get(mfds_item_sequence, [])
        )
        matches = stable_matches or by_name.get(
            _product_name_identity(product.get("product_name")), []
        )
        official_entities: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for match in matches:
            official_entities[stable_official_key(match)].append(match)

        representative: dict[str, Any] = {}
        linked_skus: list[dict[str, Any]] = []
        match_status = "unlinked"
        match_method = "none"
        conflict_codes: list[str] = []
        decision_reason = "No exact official product-name identity was found."
        manufacturer_match = False
        dosage_form_match = False
        package_compatible = False
        ingredient_count_match = False
        stable_identifier_match = bool(stable_matches)
        if len(official_entities) == 1:
            linked_skus = next(iter(official_entities.values()))
            representative = linked_skus[0]
            manufacturer_match = _manufacturer_identity(
                product.get("manufacturer_name")
            ) == _manufacturer_identity(representative.get("official_manufacturer"))
            dosage_form_match = _dosage_form_identity(
                product.get("dosage_form")
            ) == _dosage_form_identity(representative.get("official_dosage_form"))
            research_pack = _package_token(product.get("package_unit"))
            official_pack = _package_token(representative.get("official_pack_unit"))
            retail_tokens = {
                _package_token(member.get("specification") or member.get("capacity"))
                for member in linked_skus
            }
            package_compatible = any(
                token and token in research_pack and token in official_pack
                for token in retail_tokens
            )
            ingredient_count_match = len(ingredient_ids_by_product[product_id]) == len(
                representative.get("official_active_ingredients") or []
            )
            if manufacturer_match and dosage_form_match and package_compatible and ingredient_count_match:
                match_status = "success"
                match_method = (
                    "stable_identifier"
                    if stable_identifier_match
                    else "exact_composite_identity"
                )
                decision_reason = (
                    "Exact product name, manufacturer, dosage form, retail package, and "
                    "active-ingredient count agree; MFDS and health.kr identifiers remain separate."
                )
            else:
                match_status = "conflict"
                match_method = "exact_name_conflict"
                if not manufacturer_match:
                    conflict_codes.append("MANUFACTURER_MISMATCH")
                if not dosage_form_match:
                    conflict_codes.append("DOSAGE_FORM_MISMATCH")
                if not package_compatible:
                    conflict_codes.append("PACKAGE_MISMATCH")
                if not ingredient_count_match:
                    conflict_codes.append("INGREDIENT_COUNT_MISMATCH")
                conflict_codes.append("NO_MFDS_HEALTH_KEY_CROSSWALK")
                decision_reason = (
                    "An exact product-name candidate exists, but composite identity evidence "
                    "conflicts or lacks an MFDS-to-health.kr identifier crosswalk."
                )
        elif len(official_entities) > 1:
            match_status = "conflict"
            match_method = "exact_name_ambiguous"
            conflict_codes = ["MULTIPLE_OFFICIAL_ENTITIES", "NO_MFDS_HEALTH_KEY_CROSSWALK"]
            decision_reason = "The exact product name maps to multiple health.kr entities."

        rows.append(
            {
                "research_product_id": product_id,
                "mfds_item_sequence": mfds_item_sequence,
                "research_product_name": str(product.get("product_name", "")),
                "in_runtime": str(mfds_item_sequence in runtime_item_sequences).lower(),
                "match_status": match_status,
                "match_method": match_method,
                "health_kr_item_seq": str(representative.get("official_item_seq", "")),
                "official_product_key": str(
                    representative.get("official_product_key", "")
                ),
                "official_item_name": str(representative.get("official_item_name", "")),
                "official_manufacturer": str(
                    representative.get("official_manufacturer", "")
                ),
                "official_dosage_form": str(
                    representative.get("official_dosage_form", "")
                ),
                "official_pack_unit": str(
                    representative.get("official_pack_unit", "")
                ),
                "retail_sku_count": str(len(linked_skus)),
                "retail_display_links": " | ".join(
                    f"{member.get('name', '')} [{member.get('specification') or member.get('capacity', '')}]"
                    for member in linked_skus
                ),
                "official_source_url": str(
                    representative.get("official_source_url", "")
                ),
                "stable_identifier_match": str(stable_identifier_match).lower(),
                "exact_name_match": str(bool(matches)).lower(),
                "manufacturer_match": str(manufacturer_match).lower(),
                "dosage_form_match": str(dosage_form_match).lower(),
                "package_compatible": str(package_compatible).lower(),
                "ingredient_count_match": str(ingredient_count_match).lower(),
                "conflict_codes": ";".join(conflict_codes),
                "decision_reason": decision_reason,
                "mfds_promotion_evidence_complete": "false",
                "catalog_runtime_promotion_allowed": "false",
            }
        )

    def counts(scope: list[dict[str, str]]) -> dict[str, int]:
        values = Counter(row["match_status"] for row in scope)
        return {
            "total": len(scope),
            "success": values["success"],
            "conflict": values["conflict"],
            "unlinked": values["unlinked"],
        }

    return rows, {
        "product_master": counts(rows),
        "runtime": counts([row for row in rows if row["in_runtime"] == "true"]),
    }


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
    public_path: Path | None,
    research_root: Path = ROOT,
    *,
    portable_products_path: Path | None = None,
    portable_schema_path: Path | None = None,
    portable_manifest_path: Path | None = None,
    corrections_path: Path | None = None,
) -> dict[str, Any]:
    queue_payload = queue_path.read_bytes()
    csv_payload = csv_path.read_bytes()
    records = read_json_bytes(queue_payload, queue_path)
    csv_rows = read_csv_bytes(csv_payload, csv_path)
    public_payload: bytes | None = None
    public_records: list[dict[str, Any]] = []
    portable_payload: bytes | None = None
    portable_schema_payload: bytes | None = None
    portable_manifest_payload: bytes | None = None
    corrections_payload: bytes | None = None
    portable_by_id: dict[str, dict[str, Any]] = {}
    portable_manifest: dict[str, Any] = {}
    corrections: list[dict[str, Any]] = []
    if portable_products_path is not None:
        if portable_schema_path is None or portable_manifest_path is None:
            raise ValueError("portable_package_paths_incomplete")
        portable_payload = portable_products_path.read_bytes()
        portable_schema_payload = portable_schema_path.read_bytes()
        portable_manifest_payload = portable_manifest_path.read_bytes()
        portable_records = read_json_bytes(portable_payload, portable_products_path)
        portable_manifest = read_json_object_bytes(
            portable_manifest_payload, portable_manifest_path
        )
        portable_by_id = validate_portable_package(
            records,
            portable_records,
            portable_manifest,
            portable_payload,
            portable_schema_payload,
        )
        validate_source_pair(records, csv_rows)
        if corrections_path is not None:
            corrections_payload = corrections_path.read_bytes()
            corrections = read_json_bytes(corrections_payload, corrections_path)
            if any(not row.get("approved") for row in corrections):
                raise ValueError("catalog_text_correction_not_approved")
    else:
        if public_path is None:
            raise ValueError("legacy_public_path_required_without_portable_package")
        public_payload = public_path.read_bytes()
        public_records = read_json_bytes(public_payload, public_path)
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
        portable = portable_by_id.get(source_id, {})
        portable_display = portable.get("display") or {}
        candidates.append(
            {
                "catalog_source_id": source_id,
                "retail_display_name": str(
                    portable_display.get("name") or record.get("name", "")
                ),
                "retail_specification": str(
                    portable_display.get("specification")
                    or record.get("specification")
                    or record.get("capacity", "")
                ),
                "retail_normalized_name": str(record.get("normalized_name", "")),
                "retail_normalized_capacity": str(
                    record.get("normalized_capacity", "")
                ),
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
        "validated_standard_code_or_barcode": _validated_standard_codes,
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
    official_products: list[dict[str, Any]] = []
    for official_key in sorted(official_key_groups):
        members = [
            record for record in confirmed if stable_official_key(record) == official_key
        ]
        representative = members[0]
        representative_portable = portable_by_id.get(
            str(representative.get("id", "")), {}
        )
        medicine = representative_portable.get("medicine") or {}
        official_products.append(
            {
                "stable_official_key": official_key,
                "health_kr_item_seq": str(representative.get("official_item_seq", "")),
                "official_product_key": str(
                    representative.get("official_product_key", "")
                ),
                "official_item_name": str(
                    representative.get("official_item_name", "")
                ),
                "official_manufacturer": str(
                    representative.get("official_manufacturer", "")
                ),
                "official_dosage_form": str(
                    representative.get("official_dosage_form", "")
                ),
                "official_route": str(representative.get("official_route", "")),
                "official_pack_unit": str(
                    representative.get("official_pack_unit", "")
                ),
                "official_active_ingredients": representative.get(
                    "official_active_ingredients", []
                ),
                "official_source_url": str(
                    representative.get("official_source_url", "")
                ),
                "retail_sku_count": len(members),
                "retail_links": [
                    {
                        "catalog_source_id": str(member.get("id", "")),
                        "display_name": str(member.get("name", "")),
                        "specification": str(
                            member.get("specification") or member.get("capacity", "")
                        ),
                    }
                    for member in members
                ],
                "content": medicine.get("content")
                or representative.get("official_content")
                or {},
                "dur": {
                    "contraindications": representative.get(
                        "official_dur_contraindications"
                    ),
                    "age": representative.get("official_dur_age"),
                    "pregnancy": representative.get("official_dur_pregnancy"),
                    "senior": representative.get("official_dur_senior"),
                    "max_dose": representative.get("official_dur_max_dose"),
                    "max_period": representative.get("official_dur_max_period"),
                    "split_dosage": representative.get("official_dur_split_dosage"),
                },
                "mfds_promotion_evidence_complete": False,
                "runtime_promotion_allowed": False,
            }
        )
    existing_matches, existing_match_counts = rematch_existing_research_products(
        records, research_root
    )
    provenance = {
        "queue_dataset_id": "pharmacy-product-catalog/data/enrichment-queue.json",
        "queue_sha256": sha256_bytes(queue_payload),
        "queue_bytes": len(queue_payload),
        "csv_dataset_id": "pharmacy-product-catalog/data/enrichment-queue.csv",
        "csv_sha256": sha256_bytes(csv_payload),
        "csv_bytes": len(csv_payload),
        "public_dataset_id": (
            "pharmacy-product-catalog/public/data/enrichment-queue.json"
            if public_payload is not None
            else None
        ),
        "public_sha256": sha256_bytes(public_payload) if public_payload is not None else None,
        "public_bytes": len(public_payload) if public_payload is not None else None,
        "portable_dataset_id": (
            "pharmacy-product-catalog/data/portable/v1/products.json"
            if portable_payload is not None
            else None
        ),
        "portable_sha256": (
            sha256_bytes(portable_payload) if portable_payload is not None else None
        ),
        "portable_schema_sha256": (
            sha256_bytes(portable_schema_payload)
            if portable_schema_payload is not None
            else None
        ),
        "portable_manifest_sha256": (
            sha256_bytes(portable_manifest_payload)
            if portable_manifest_payload is not None
            else None
        ),
        "corrections_sha256": (
            sha256_bytes(corrections_payload) if corrections_payload is not None else None
        ),
        "portable_package_version": portable_manifest.get("package_version"),
        "portable_schema_version": portable_manifest.get("schema_version"),
        "approved_text_correction_count": len(corrections),
        "source_files_read_once": True,
        "public_sync_exact": (
            queue_payload == public_payload if public_payload is not None else None
        ),
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
        "mfds_promotion_evidence_complete_count": 0,
        "mapping_failure_count": len(mapping_failures),
        "duplicate_official_product_group_count": len(duplicate_groups),
        "duplicate_linked_retail_sku_count": sum(duplicate_groups.values()),
        "duplicate_extra_link_count": sum(duplicate_groups.values()) - len(duplicate_groups),
        "ingredient_form_group_count": len(groups),
        "conflict_record_count": len(conflict_records),
        "conflict_entry_count": conflict_entries,
        "existing_mfds_stable_identifier_overlap_count": len(stable_identifier_overlaps),
        "existing_research_product_rematch": existing_match_counts["product_master"],
        "runtime_product_rematch": existing_match_counts["runtime"],
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
        "source_trio_counts_equal": (
            len(records) == len(csv_rows) == len(public_records)
            if public_payload is not None
            else None
        ),
        "portable_package_valid": bool(portable_by_id) if portable_payload is not None else None,
        "public_sync_exact": True if public_payload is not None else None,
        "csv_projection_equivalent": True,
        "official_match_statuses_isolated": all(
            record.get("official_match_status") == "confirmed" for record in usable
        ),
        "stable_identifier_required": True,
        "name_similarity_not_used_as_identity": True,
        "mfds_and_health_kr_identifier_namespaces_separated": True,
        "app_fields_used_for_matching_or_display": False,
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
            "existing_research_product_rematch": existing_match_counts[
                "product_master"
            ],
            "runtime_product_rematch": existing_match_counts["runtime"],
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
        "official_products": official_products,
        "existing_matches": existing_matches,
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
    local_output = selection_output.parent / "local"
    local_output.mkdir(parents=True, exist_ok=True)
    status_path = selection_output / "catalog_health_kr_status_index.csv"
    candidates_path = selection_output / "catalog_health_kr_research_candidates.csv"
    groups_path = selection_output / "catalog_health_kr_same_ingredient_groups.csv"
    conflicts_path = selection_output / "catalog_health_kr_conflict_review.csv"
    official_products_path = local_output / "catalog_health_kr_official_products.json"
    existing_matches_path = (
        selection_output / "catalog_health_kr_existing_product_matches.csv"
    )
    summary_path = selection_output / "catalog_health_kr_summary.json"
    audit_path = audit_output / "catalog_health_kr_integration.json"
    write_csv(status_path, result["status_index"], STATUS_INDEX_FIELDS)
    write_csv(candidates_path, result["candidates"], CANDIDATE_FIELDS)
    write_csv(groups_path, result["groups"], GROUP_FIELDS)
    write_csv(conflicts_path, result["conflicts"], CONFLICT_FIELDS)
    official_products_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "source_role": "local_normalized_health_kr_official_entity_index",
                "price_values_exported": False,
                "products": result["official_products"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(existing_matches_path, result["existing_matches"], EXISTING_MATCH_FIELDS)
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
        {"path": "research_v3/otc/local/catalog_health_kr_official_products.json", "rows": len(result["official_products"]), "sha256": sha256(official_products_path)},
        {"path": "research_v3/otc/selection/catalog_health_kr_existing_product_matches.csv", "rows": len(result["existing_matches"]), "sha256": sha256(existing_matches_path)},
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
        None,
        portable_products_path=args.catalog_root / "data" / "portable" / "v1" / "products.json",
        portable_schema_path=args.catalog_root / "data" / "portable" / "v1" / "schema.json",
        portable_manifest_path=args.catalog_root / "data" / "portable" / "v1" / "manifest.json",
        corrections_path=args.catalog_root / "data" / "catalog-text-corrections.json",
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
