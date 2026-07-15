import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "research_v3" / "otc" / "schema"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def validate(name: str, instance: dict) -> None:
    validator = Draft202012Validator(load_schema(name))
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_product_schema_accepts_traceable_korean_otc_product() -> None:
    validate(
        "product.schema.json",
        {
            "product_id": "MFDS-200000001",
            "item_sequence": "200000001",
            "product_name": "검증용일반정",
            "manufacturer_name": "검증제약",
            "classification": "일반의약품",
            "authorization_status": "active",
            "dosage_form": "정제",
            "route": "경구",
            "active_ingredient_raw": "아세트아미노펜 500밀리그램",
            "dose_per_administration": "1정",
            "administrations_per_day": "3~4회",
            "max_daily_dose": "4000 mg",
            "minimum_dose_interval": "4시간",
            "age_restriction": "만 12세 이상",
            "indications": "해열 및 진통",
            "dosage_and_administration": "허가문서 원문",
            "warnings": "허가문서 원문",
            "contraindications": "허가문서 원문",
            "drug_interactions": "허가문서 원문",
            "pregnancy_lactation": "허가문서 원문",
            "hepatic_renal": "허가문서 원문",
            "authorization_document_url": "https://nedrug.mfds.go.kr/example",
            "source_id": "MFDS-NEDRUG-200000001",
            "source_locator": "용법용량; 사용상의주의사항",
            "retrieved_at": "2026-07-14",
            "source_sha256": "a" * 64,
            "record_status": "verified_from_source",
        },
    )


def test_compound_product_uses_multiple_join_rows() -> None:
    product_id = "MFDS-200000002"
    rows = [
        {
            "product_id": product_id,
            "ingredient_id": "ING-acetaminophen",
            "ingredient_name_raw": "아세트아미노펜",
            "ingredient_name_normalized": "acetaminophen",
            "amount_per_unit": 325,
            "amount_unit": "mg",
            "unit_basis": "1정",
            "source_id": "MFDS-NEDRUG-200000002",
            "source_locator": "원료약품 및 분량 > 1정 중",
            "normalization_status": "verified",
        },
        {
            "product_id": product_id,
            "ingredient_id": "ING-chlorpheniramine",
            "ingredient_name_raw": "클로르페니라민말레산염",
            "ingredient_name_normalized": "chlorpheniramine_maleate",
            "amount_per_unit": 2,
            "amount_unit": "mg",
            "unit_basis": "1정",
            "source_id": "MFDS-NEDRUG-200000002",
            "source_locator": "원료약품 및 분량 > 1정 중",
            "normalization_status": "verified",
        },
    ]
    for row in rows:
        validate("product_ingredient.schema.json", row)
    assert len({row["ingredient_id"] for row in rows}) == 2


def test_released_rule_requires_source_and_concrete_locator() -> None:
    schema = load_schema("rule.schema.json")
    validator = Draft202012Validator(schema)
    released_without_locator = {
        "rule_id": "OTC-RULE-001",
        "rule_type": "duplicate_ingredient",
        "status": "released",
        "severity": "high",
        "predicate": {"ingredient_id": "ING-acetaminophen"},
        "message_ko": "동일 성분 중복을 확인하세요.",
        "next_action_ko": "약사 또는 의사와 상담하세요.",
        "source_id": "MFDS-NEDRUG-200000001",
        "source_locator": "",
    }
    assert list(validator.iter_errors(released_without_locator))


def test_source_and_ingredient_schemas_require_provenance() -> None:
    validate(
        "ingredient.schema.json",
        {
            "ingredient_id": "ING-ibuprofen",
            "preferred_name_ko": "이부프로펜",
            "preferred_name_en": "ibuprofen",
            "normalized_key": "ibuprofen",
            "pharmacologic_classes": ["NSAID"],
            "source_id": "MFDS-NEDRUG-200000003",
            "source_locator": "원료약품 및 분량",
            "status": "verified",
        },
    )
    validate(
        "source.schema.json",
        {
            "source_id": "MFDS-NEDRUG-200000003",
            "authority": "식품의약품안전처",
            "title": "검증용 제품 허가사항",
            "source_type": "authorization_document",
            "url": "https://nedrug.mfds.go.kr/example",
            "retrieved_at": "2026-07-14",
            "sha256": "b" * 64,
            "local_snapshot": "research_v3/otc/raw/MFDS-NEDRUG-200000003.json",
            "status": "retrieved",
        },
    )
