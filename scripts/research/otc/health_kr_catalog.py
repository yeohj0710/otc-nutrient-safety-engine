from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


ALLOWED_MATCH_STATUSES = {
    "confirmed",
    "review_required",
    "not_found",
    "not_applicable",
}

HEALTH_KR_GENERAL_OTC_DRUG_CLASS_CODE = "2"
AGE_THRESHOLD_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>개월|세)\s*미만")

RESEARCH_REQUIRED_FIELDS = (
    "official_product_key",
    "official_item_seq",
    "official_item_name",
    "official_manufacturer",
    "official_source_type",
    "official_source_url",
    "official_category",
    "official_dosage_form",
    "official_route",
    "official_storage",
    "official_efficacy",
    "official_dosage",
    "official_precautions",
    "official_active_ingredients",
)


def normalize_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def health_kr_raw(record: dict[str, Any]) -> dict[str, Any]:
    additional = record.get("official_additional_data")
    if not isinstance(additional, dict):
        return {}
    raw = additional.get("health_kr_raw")
    return raw if isinstance(raw, dict) else {}


def ingredient_details(record: dict[str, Any]) -> list[dict[str, Any]]:
    details = health_kr_raw(record).get("ingredient_details", [])
    if not isinstance(details, list):
        return []
    return [row for row in details if isinstance(row, dict)]


def ingredient_codes(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(row.get("ingredient_code", "")).strip()
                for row in ingredient_details(record)
                if str(row.get("ingredient_code", "")).strip()
            }
        )
    )


def stable_official_key(record: dict[str, Any]) -> str:
    product_key = str(record.get("official_product_key", "")).strip()
    if not product_key:
        return ""
    domain = str(record.get("official_domain", "")).strip() or "health.kr"
    return f"{domain}:{product_key}"


def missing_stable_identity_fields(record: dict[str, Any]) -> list[str]:
    required = (
        "official_product_key",
        "official_item_seq",
        "official_source_type",
        "official_source_url",
    )
    return [field for field in required if not nonempty(record.get(field))]


def validate_records(records: list[dict[str, Any]]) -> dict[str, int]:
    if not isinstance(records, list):
        raise ValueError("catalog_schema_invalid:root_list_required")
    seen: set[str] = set()
    confirmed = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"catalog_schema_invalid:row_object_required:{index}")
        source_id = str(record.get("id") or record.get("document_id") or "").strip()
        if not source_id:
            raise ValueError(f"catalog_schema_invalid:missing_source_id:{index}")
        if source_id in seen:
            raise ValueError(f"catalog_duplicate_source_id:{source_id}")
        seen.add(source_id)
        status = str(record.get("official_match_status", "")).strip()
        if status not in ALLOWED_MATCH_STATUSES:
            raise ValueError(f"catalog_schema_invalid:official_match_status:{source_id}:{status}")
        if status != "confirmed":
            continue
        confirmed += 1
        missing_identity = missing_stable_identity_fields(record)
        if missing_identity:
            raise ValueError(
                f"confirmed_missing_stable_identity:{source_id}:{','.join(missing_identity)}"
            )
        source_url = str(record.get("official_source_url", ""))
        parsed = urlparse(source_url)
        source_code = parse_qs(parsed.query).get("drug_cd", [""])[0]
        if parsed.hostname not in {"health.kr", "www.health.kr"}:
            raise ValueError(f"confirmed_source_domain_invalid:{source_id}")
        raw_code = str(health_kr_raw(record).get("drug_code", "")).strip()
        product_key = str(record.get("official_product_key", "")).strip()
        item_sequence = str(record.get("official_item_seq", "")).strip()
        if not source_code or not raw_code:
            raise ValueError(f"confirmed_source_identifier_missing:{source_id}")
        if len({product_key, item_sequence, source_code, raw_code}) != 1:
            raise ValueError(f"confirmed_source_identifier_mismatch:{source_id}")
        evidence = record.get("official_section_evidence")
        if not isinstance(evidence, dict) or not evidence.get("detail_page_verified"):
            raise ValueError(f"confirmed_source_evidence_missing:{source_id}")
        codes = ingredient_codes(record)
        if not codes:
            raise ValueError(f"confirmed_missing_ingredient_code:{source_id}")
    return {"record_count": len(records), "unique_source_ids": len(seen), "confirmed": confirmed}


def research_use_status(record: dict[str, Any]) -> str:
    if record.get("official_match_status") != "confirmed":
        return "excluded_unconfirmed"
    if missing_stable_identity_fields(record):
        return "excluded_mapping_failure"
    if (
        str(health_kr_raw(record).get("drug_cls", "")).strip()
        != HEALTH_KR_GENERAL_OTC_DRUG_CLASS_CODE
    ):
        return "excluded_not_general_otc"
    if record.get("official_content_status") != "complete":
        return "excluded_incomplete_content"
    if any(not nonempty(record.get(field)) for field in RESEARCH_REQUIRED_FIELDS):
        return "excluded_missing_required_field"
    if not ingredient_codes(record):
        return "excluded_missing_ingredient_code"
    return "research_search_usable"


def ingredient_form_group_id(record: dict[str, Any]) -> str:
    codes = ingredient_codes(record)
    dosage_form = normalize_text(record.get("official_dosage_form"))
    if not codes or not dosage_form:
        return ""
    payload = "|".join((*codes, dosage_form)).encode("utf-8")
    return f"HKG-{hashlib.sha256(payload).hexdigest()[:20]}"


def classify_product(record: dict[str, Any]) -> str:
    text = normalize_text(
        " ".join(
            str(record.get(field, ""))
            for field in (
                "official_category",
                "official_atc_code",
                "official_kpic_atc",
                "official_efficacy",
                "official_dosage_form",
            )
        )
    )
    rules = (
        ("analgesic_antiinflammatory", ("해열", "진통", "소염", "nsaid")),
        ("cold_respiratory", ("감기", "진해", "거담", "비충혈", "호흡")),
        ("antihistamine", ("항히스타민", "알레르")),
        ("gastrointestinal", ("소화", "제산", "하제", "완장", "지사", "정장", "위장")),
        ("anthelmintic", ("구충",)),
        ("motion_sickness", ("멀미",)),
        ("topical_or_local", ("외용", "피부", "안과", "이비", "치과", "구강", "점안")),
    )
    for classification, tokens in rules:
        if any(normalize_text(token) in text for token in tokens):
            return classification
    return "other_otc"


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return " ".join(flatten_text(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class SafetyProfile:
    age_years: float | None = None
    pregnant: bool = False
    lactating: bool = False
    conditions: tuple[str, ...] = ()
    medications: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()


def _matching_terms(terms: tuple[str, ...], source_text: str) -> list[str]:
    normalized_source = normalize_text(source_text)
    matches: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        if len(normalized_term) >= 2 and normalized_term in normalized_source:
            matches.append(term)
    return matches


def dur_minimum_age_years(value: Any) -> float | None:
    thresholds: list[float] = []
    for match in AGE_THRESHOLD_PATTERN.finditer(str(value or "")):
        threshold = float(match.group("value"))
        if match.group("unit") == "개월":
            threshold /= 12
        thresholds.append(threshold)
    return max(thresholds) if thresholds else None


def safety_exclusion_reasons(record: dict[str, Any], profile: SafetyProfile) -> list[str]:
    reasons: list[str] = []
    if profile.pregnant and nonempty(record.get("official_dur_pregnancy")):
        reasons.append("dur_pregnancy")
    lactation_text = " ".join(
        str(record.get(field, ""))
        for field in (
            "official_precautions",
            "official_medication_guide",
            "official_patient_guidance",
        )
    )
    if profile.lactating and "수유" in lactation_text:
        reasons.append("lactation_precaution")
    if profile.age_years is not None and nonempty(record.get("official_dur_age")):
        minimum_age = dur_minimum_age_years(record.get("official_dur_age"))
        if minimum_age is None:
            reasons.append("dur_age_unparsed")
        elif profile.age_years < minimum_age:
            reasons.append("dur_age")
    if profile.age_years is not None and profile.age_years >= 65 and nonempty(record.get("official_dur_senior")):
        reasons.append("dur_senior")
    contraindication_text = " ".join(
        str(record.get(field, ""))
        for field in ("official_dur_contraindications", "official_precautions")
    )
    reasons.extend(
        f"contraindication:{term}"
        for term in _matching_terms(profile.conditions, contraindication_text)
    )
    interaction_text = " ".join(
        (
            flatten_text(record.get("official_interactions")),
            str(record.get("official_dur_contraindications", "")),
            str(record.get("official_precautions", "")),
        )
    )
    reasons.extend(
        f"interaction:{term}"
        for term in _matching_terms(profile.medications, interaction_text)
    )
    return list(dict.fromkeys(reasons))


def clinical_match_score(record: dict[str, Any], query: str) -> int:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return 0
    names = [record.get("official_item_name", ""), record.get("name", "")]
    normalized_names = [normalize_text(value) for value in names]
    if normalized_query in normalized_names:
        return 120
    if any(normalized_query in value for value in normalized_names):
        return 100
    fields = (
        (record.get("official_active_ingredients", []), 80),
        (record.get("official_efficacy", ""), 60),
        (record.get("official_category", ""), 50),
        (record.get("official_dosage_form", ""), 40),
        (f"{record.get('official_atc_code', '')} {record.get('official_kpic_atc', '')}", 30),
    )
    for value, score in fields:
        if normalized_query in normalize_text(flatten_text(value)):
            return score
    return 0


def search_research_candidates(
    records: list[dict[str, Any]],
    query: str,
    profile: SafetyProfile,
    limit: int = 50,
) -> dict[str, Any]:
    if profile.red_flags:
        return {
            "query": query,
            "candidates": [],
            "excludedCount": 0,
            "disposition": "refer_to_pharmacist_or_clinician",
            "decisionMode": "deterministic",
            "priceUsedForClinicalRanking": False,
        }
    matched: list[tuple[int, str, str, dict[str, Any]]] = []
    excluded = 0
    for record in records:
        if research_use_status(record) != "research_search_usable":
            continue
        score = clinical_match_score(record, query)
        if score <= 0:
            continue
        reasons = safety_exclusion_reasons(record, profile)
        if reasons:
            excluded += 1
            continue
        stable_key = stable_official_key(record)
        source_id = str(record.get("id") or record.get("document_id") or "")
        matched.append((score, stable_key, source_id, record))
    matched.sort(key=lambda item: (-item[0], item[1], item[2]))

    collapsed: dict[str, dict[str, Any]] = {}
    for score, stable_key, source_id, record in matched:
        current = collapsed.get(stable_key)
        if current is not None:
            current["catalogSourceIds"].append(source_id)
            continue
        collapsed[stable_key] = {
            "stableOfficialKey": stable_key,
            "officialProductKey": str(record.get("official_product_key", "")),
            "officialItemSequence": str(record.get("official_item_seq", "")),
            "productName": str(record.get("official_item_name", "")),
            "manufacturer": str(record.get("official_manufacturer", "")),
            "classification": classify_product(record),
            "dosageForm": str(record.get("official_dosage_form", "")),
            "route": str(record.get("official_route", "")),
            "ingredientFormGroupId": ingredient_form_group_id(record),
            "score": score,
            "catalogSourceIds": [source_id],
            "sourceUrl": str(record.get("official_source_url", "")),
            "runtimePromotionAllowed": False,
        }
    candidates = list(collapsed.values())[: max(0, limit)]
    return {
        "query": query,
        "candidates": candidates,
        "excludedCount": excluded,
        "disposition": "research_candidates_not_clinical_recommendations",
        "decisionMode": "deterministic",
        "priceUsedForClinicalRanking": False,
    }
