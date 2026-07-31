import copy
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from scripts.research.otc.build_runtime import (
    build,
    evidence_source_version,
    validate_active_rule_applicability,
    verified_source_documents,
)


ROOT = Path(__file__).resolve().parents[2]
APPLICABILITY = ROOT / "research_v51" / "evidence" / "active_rule_applicability.csv"
PAGE_MANIFEST = ROOT / "research_v3" / "otc" / "extracted" / "nedrug" / "page_manifest.csv"
ADMIN_CONSTRAINTS = (
    ROOT / "research_v3" / "otc" / "normalized" / "administration_constraints.csv"
)


def csv_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_exposes_rule_id_centered_applicability():
    runtime = build()
    policies = {row["ruleId"]: row for row in runtime["releasedRules"]}

    assert len(policies) == runtime["rulesReleased"] == 15
    assert runtime["authorizationConstraintsCount"] == 32
    assert all(
        row["lineageStatus"] == "mapped_from_v50_released_rule"
        for row in policies.values()
    )
    assert {
        rule_id: policy["applicability"] for rule_id, policy in policies.items()
    } == {
        "OTC-RULE-001": {"ingredientIds": ["ING-acetaminophen"]},
        "OTC-RULE-002": {
            "pharmacologicClasses": ["NSAID"],
            "requiredAnchorIngredientIds": ["ING-ibuprofen"],
        },
        "OTC-RULE-003": {
            "productItemSequences": ["202106092"],
            "ingredientIds": ["ING-acetaminophen"],
            "administrationConstraintTypes": [
                "maximum_daily_ingredient_amount"
            ],
            "minimumAgeYears": 12,
        },
        "OTC-RULE-004": {
            "productItemSequences": ["202106092"],
            "ingredientIds": ["ING-acetaminophen"],
            "administrationConstraintTypes": ["minimum_interval_hours"],
            "minimumAgeYears": 12,
        },
        "OTC-RULE-005": {"productItemSequences": ["202106092"]},
        "OTC-RULE-006": {
            "productItemSequences": ["198601920"],
            "pregnancyTrimesters": [3],
            "lactationSupported": False,
        },
        "OTC-RULE-007": {
            "productItemSequences": ["202106092"],
            "ingredientIds": ["ING-acetaminophen"],
        },
        "OTC-RULE-008": {"productItemSequences": ["198601920"]},
        "OTC-RULE-009": {"productItemSequences": ["198601920"]},
        "OTC-RULE-010": {"productItemSequences": ["196800036"]},
        "OTC-RULE-011": {
            "productItemSequences": ["202106092"],
            "ingredientIds": ["ING-acetaminophen"],
        },
        "OTC-RULE-012": {
            "productItemSequences": ["198601920"],
            "medicationTerms": [
                "warfarin",
                "와파린",
                "coumarin",
                "쿠마린",
                "쿠마린계 항응고제",
            ],
        },
        "OTC-RULE-013": {
            "productItemSequences": ["196800036"],
            "medicationTerms": ["sedative", "진정제", "수면제"],
        },
        "OTC-RULE-014": {"productItemSequences": ["196800036"]},
        "OTC-RULE-016": {
            "productItemSequences": ["202106092"],
            "urgentTerms": [
                "호흡곤란",
                "온몸이 붉어짐",
                "혈관부기",
                "두드러기",
                "천식발작",
                "얼굴부기",
                "저혈압",
                "쇽",
                "스티븐스-존슨",
                "스티븐스 존슨",
                "독성표피괴사",
                "리엘 증후군",
            ],
        },
    }


def test_runtime_pins_all_released_rule_types_and_scope_labels():
    runtime = build()
    policies = {row["ruleId"]: row for row in runtime["releasedRules"]}

    assert {
        rule_id: {
            "ruleType": policy["ruleType"],
            "scope": policy["scope"],
        }
        for rule_id, policy in policies.items()
    } == {
        "OTC-RULE-001": {
            "ruleType": "duplicate_ingredient",
            "scope": "acetaminophen_containing_selected_products",
        },
        "OTC-RULE-002": {
            "ruleType": "duplicate_pharmacologic_class",
            "scope": "ibuprofen_and_other_NSAIDs",
        },
        "OTC-RULE-003": {
            "ruleType": "max_daily_dose",
            "scope": "acetaminophen_tylenol500_age_12_plus",
        },
        "OTC-RULE-004": {
            "ruleType": "minimum_interval",
            "scope": "tylenol500_age_12_plus",
        },
        "OTC-RULE-005": {
            "ruleType": "age_restriction",
            "scope": "tylenol500_minimum_age_12",
        },
        "OTC-RULE-006": {
            "ruleType": "pregnancy_lactation",
            "scope": "ibuprofen_pregnancy_lactation",
        },
        "OTC-RULE-007": {
            "ruleType": "hepatic_disease",
            "scope": "acetaminophen_liver_disease",
        },
        "OTC-RULE-008": {
            "ruleType": "renal_disease",
            "scope": "ibuprofen_kidney_disease",
        },
        "OTC-RULE-009": {
            "ruleType": "gi_bleeding_ulcer",
            "scope": "ibuprofen_gi_bleeding_or_ulcer",
        },
        "OTC-RULE-010": {
            "ruleType": "sedation_driving",
            "scope": "pancol_a_driving",
        },
        "OTC-RULE-011": {
            "ruleType": "alcohol",
            "scope": "acetaminophen_regular_alcohol_use",
        },
        "OTC-RULE-012": {
            "ruleType": "anticoagulant_antiplatelet",
            "scope": "ibuprofen_warfarin_or_coumarin_anticoagulant",
        },
        "OTC-RULE-013": {
            "ruleType": "sedative_medication",
            "scope": "pancol_a_sedative_or_overlapping_cold_medicine",
        },
        "OTC-RULE-014": {
            "ruleType": "decongestant_hypertension",
            "scope": "pancol_a_phenylephrine_hypertension",
        },
        "OTC-RULE-016": {
            "ruleType": "urgent_referral",
            "scope": "tylenol500_stop_and_consult_symptoms",
        },
    }


def test_runtime_rule_evidence_keeps_multiple_same_type_rules_possible():
    runtime = build()
    assert all(len(rule["evidence"]) == 1 for rule in runtime["releasedRules"])
    assert all(
        evidence["ruleId"] == rule["ruleId"]
        for rule in runtime["releasedRules"]
        for evidence in rule["evidence"]
    )
    assert len(runtime["ruleEvidenceByType"]) == 15


def test_every_released_rule_evidence_has_a_verified_snapshot_version():
    runtime = build()
    manifest = csv_rows(PAGE_MANIFEST)
    documents = {}
    for row in manifest:
        key = (row["item_sequence"], row["document_type"])
        document = documents.setdefault(
            key,
            {
                "hash": row["pdf_sha256"],
                "path": row["pdf_path"],
                "pages": set(),
            },
        )
        assert document["hash"] == row["pdf_sha256"]
        assert document["path"] == row["pdf_path"]
        document["pages"].add(int(row["page"]))

    evidence_rows = [
        evidence
        for policy in runtime["releasedRules"]
        for evidence in policy["evidence"]
    ]
    assert len(evidence_rows) == 15
    for evidence in evidence_rows:
        path_parts = [
            part for part in urlparse(evidence["url"]).path.split("/") if part
        ]
        item_sequence, document_type = path_parts[-2:]
        document = documents[(item_sequence, document_type)]
        assert evidence["sourceVersion"] == f"sha256:{document['hash']}"
        assert binary_sha256(ROOT / document["path"]) == document["hash"]
        page_match = re.search(r" PDF p\.(\d+)(?:,|$)", evidence["locator"])
        assert page_match is not None
        assert int(page_match.group(1)) in document["pages"]


def test_rule016_uses_the_reviewed_locator_and_snapshot_version():
    runtime = build()
    rule = next(
        policy for policy in runtime["releasedRules"] if policy["ruleId"] == "OTC-RULE-016"
    )
    evidence = rule["evidence"][0]

    assert evidence["locator"] == "사용상의주의사항 PDF p.2, 문단 12-19"
    assert evidence["sourceVersion"] == (
        "sha256:0c8ea0d7eb164b27673fc8549c42a06d874fdfa26047db8d0681b3a2f79c9442"
    )
    range_match = re.fullmatch(
        r"사용상의주의사항 PDF p\.(\d+), 문단 (\d+)-(\d+)",
        evidence["locator"],
    )
    assert range_match is not None
    page, first_paragraph, last_paragraph = map(int, range_match.groups())
    assert page == 2
    assert 1 <= first_paragraph <= last_paragraph
    page_manifest = next(
        row
        for row in csv_rows(PAGE_MANIFEST)
        if row["item_sequence"] == "202106092"
        and row["document_type"] == "NB"
        and row["page"] == "2"
    )
    assert page_manifest["page_text_sha256"] == (
        "ca432bb358666a3b1abb16796c7b9a37e5b721fab299b2862ccfc9732b131d2e"
    )


@pytest.mark.parametrize(
    ("source_url", "source_locator", "message"),
    [
        (
            "https://example.test/dsie/pdf/drb/202106092/NB",
            "사용상의주의사항 PDF p.2, 문단 12-19",
            "invalid MFDS evidence URL",
        ),
        (
            "https://nedrug.mfds.go.kr/wrong/202106092/NB",
            "사용상의주의사항 PDF p.2, 문단 12-19",
            "invalid MFDS evidence URL",
        ),
        (
            "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/NB",
            "사용상의주의사항 PDF p.99, 문단 12-19",
            "locator is outside protected manifest",
        ),
    ],
)
def test_evidence_source_version_rejects_unpinned_locations(
    source_url, source_locator, message
):
    evidence = {
        "rule_id": "OTC-RULE-016",
        "item_sequence": "202106092",
        "source_url": source_url,
        "source_locator": source_locator,
    }
    with pytest.raises(ValueError, match=message):
        evidence_source_version(evidence, verified_source_documents())


def test_administration_constraints_keep_their_verified_source_versions():
    runtime = build()
    expected_versions = {
        row["constraint_id"]: f"sha256:{row['source_sha256']}"
        for row in csv_rows(ADMIN_CONSTRAINTS)
        if row["record_status"] == "verified_from_authorization_source"
    }
    constraints = [
        constraint
        for product in runtime["products"]
        for constraint in product["administrationConstraints"]
    ]

    assert len(constraints) == runtime["authorizationConstraintsCount"] == 32
    assert all(
        constraint["evidence"]["sourceVersion"]
        == expected_versions[constraint["constraintId"]]
        for constraint in constraints
    )


def test_products_separate_released_bindings_from_authorization_checks():
    runtime = build()
    products = {product["itemSequence"]: product for product in runtime["products"]}

    assert products["201110646"]["supportedReleasedRuleIds"] == []
    assert "max_daily_dose" in products["201110646"]["supportedRuleTypes"]
    assert products["202106092"]["supportedReleasedRuleIds"] == [
        "OTC-RULE-003",
        "OTC-RULE-004",
        "OTC-RULE-005",
        "OTC-RULE-007",
        "OTC-RULE-011",
        "OTC-RULE-016",
    ]


@pytest.mark.parametrize(
    ("rule_id", "field", "value", "message"),
    [
        (
            "OTC-RULE-006",
            "productItemSequences",
            ["UNKNOWN-ITEM"],
            "unknown product items",
        ),
        (
            "OTC-RULE-001",
            "ingredientIds",
            ["ING-unknown"],
            "unknown ingredients",
        ),
        (
            "OTC-RULE-006",
            "pharmacologicClasses",
            ["unknown-class"],
            "unknown classes",
        ),
        (
            "OTC-RULE-002",
            "requiredAnchorIngredientIds",
            ["ING-unknown"],
            "unknown anchors",
        ),
    ],
)
def test_applicability_validator_rejects_unknown_references(
    rule_id, field, value, message
):
    runtime = build()
    policies = copy.deepcopy(runtime["releasedRules"])
    policy = next(policy for policy in policies if policy["ruleId"] == rule_id)
    policy["applicability"][field] = value

    with pytest.raises(ValueError, match=message):
        validate_active_rule_applicability(policies, runtime["products"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ingredientIds", ["ING-dexibuprofen"], "ingredient is outside product scope"),
        ("pharmacologicClasses", ["antihistamine"], "class is outside product scope"),
        (
            "requiredAnchorIngredientIds",
            ["ING-acetaminophen"],
            "anchor is outside product scope",
        ),
    ],
)
def test_applicability_validator_rejects_inconsistent_product_scope(
    field, value, message
):
    runtime = build()
    policies = copy.deepcopy(runtime["releasedRules"])
    policy = next(
        policy for policy in policies if policy["ruleId"] == "OTC-RULE-006"
    )
    policy["applicability"][field] = value

    with pytest.raises(ValueError, match=message):
        validate_active_rule_applicability(policies, runtime["products"])


def test_runtime_records_applicability_provenance_and_rebuilds_canonically():
    runtime = build()
    canonical_csv = (
        APPLICABILITY.read_text(encoding="utf-8-sig")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )
    assert runtime["ruleApplicabilityProvenance"] == {
        "path": "research_v51/evidence/active_rule_applicability.csv",
        "sha256": hashlib.sha256(canonical_csv).hexdigest(),
        "normalization": "utf8_lf",
        "lineageStatus": "mapped_from_v50_released_rule",
    }
    checked_in = json.loads(
        (ROOT / "src" / "generated" / "otc-runtime.json").read_text(encoding="utf-8")
    )
    assert {
        key: value for key, value in runtime.items() if key != "generatedAt"
    } == {
        key: value for key, value in checked_in.items() if key != "generatedAt"
    }
