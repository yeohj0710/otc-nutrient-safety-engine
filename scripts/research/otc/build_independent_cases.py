from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATION = ROOT / "research_v3" / "otc" / "validation"
CASES = VALIDATION / "independent_cases"
INDEX = VALIDATION / "independent_scenarios.csv"


EMPTY_PROFILE = {
    "ageYears": None,
    "pregnant": False,
    "lactating": False,
    "liverDisease": False,
    "kidneyDisease": False,
    "giBleedingOrUlcer": False,
    "hypertensionOrCardiovascularDisease": False,
    "willDrive": False,
    "alcohol": False,
    "medications": [],
    "redFlagSymptoms": [],
}


def selected(item_sequence: str, units: float, doses: float, **extra: object) -> dict[str, object]:
    value: dict[str, object] = {
        "inputType": "verified_product",
        "itemSequence": item_sequence,
        "unitsPerDose": units,
        "dosesPerDay": doses,
    }
    value.update(extra)
    return value


def query(product_name: str) -> dict[str, object]:
    return {"inputType": "product_search_query", "productNameQuery": product_name}


def case(family: str, critical: bool, products: list[dict[str, object]], **profile: object) -> dict[str, object]:
    user_profile = dict(EMPTY_PROFILE)
    user_profile.update(profile)
    return {
        "schemaVersion": "1.0.0",
        "scenarioFamily": family,
        "critical": critical,
        "productInputs": products,
        "userProfile": user_profile,
        "referenceLabel": None,
        "prediction": None,
        "reviewStatus": "awaiting_independent_human_label",
    }


CASES_BY_ID = {
    "IND-OTC-001": case("duplicate_acetaminophen", True, [selected("202106092", 1, 3), selected("196800036", 1, 3)]),
    "IND-OTC-002": case("duplicate_nsaid", True, [selected("198601920", 10, 3), selected("201110646", 1, 3)]),
    "IND-OTC-003": case("duplicate_nsaid", True, [selected("198601920", 10, 3), selected("197500016", 1, 2)]),
    "IND-OTC-004": case("duplicate_antihistamine", True, [selected("196800036", 1, 3), selected("200610765", 1, 1)]),
    "IND-OTC-005": case("sedation_driving", True, [selected("196800036", 1, 3)], willDrive=True),
    "IND-OTC-006": case("nsaid_anticoagulant", True, [selected("198601920", 10, 3)], medications=["와파린"]),
    "IND-OTC-007": case("decongestant_hypertension", True, [selected("196800036", 1, 3)], hypertensionOrCardiovascularDisease=True),
    "IND-OTC-008": case("acetaminophen_liver", True, [selected("202106092", 2, 4)], liverDisease=True),
    "IND-OTC-009": case("nsaid_kidney", True, [selected("198601920", 10, 3)], kidneyDisease=True),
    "IND-OTC-010": case("pediatric_adult_product", True, [selected("202106092", 1, 3)], ageYears=10),
    "IND-OTC-011": case("minimum_interval", True, [selected("202106092", 1, 3, hoursSincePreviousDose=2)]),
    "IND-OTC-012": case("normal_use", False, [selected("202106092", 1, 3)], ageYears=30),
    "IND-OTC-013": case("unsupported_product", False, [query("지원 목록에 없는 임의 일반의약품")]),
}


def build() -> dict[str, int]:
    CASES.mkdir(parents=True, exist_ok=True)
    with INDEX.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    for row in rows:
        scenario_id = row["scenario_id"]
        payload = {"scenarioId": scenario_id, **CASES_BY_ID[scenario_id]}
        target = CASES / f"{scenario_id}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        row["case_payload_ref"] = target.relative_to(VALIDATION).as_posix()
        row["status"] = "case_prepared_awaiting_independent_human_label"
    with INDEX.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {"cases": len(rows), "human_labels": 0, "predictions": 0}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
