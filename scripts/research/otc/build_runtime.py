from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"

CLASS_NAMES = {
    "OTC-CLASS-ANALGESIC": "해열진통제",
    "OTC-CLASS-COLD": "종합감기약",
    "OTC-CLASS-GI": "위장관 일반의약품",
    "OTC-CLASS-TOPICAL": "외용 소염진통제",
    "OTC-CLASS-ANTIHISTAMINE": "항히스타민제",
}

ADMINISTRATION_CONSTRAINT_TYPES = {
    "maximum_units_per_dose",
    "maximum_doses_per_day",
    "maximum_daily_ingredient_amount",
    "minimum_interval_hours",
}

CONSTRAINT_RULE_TYPES = {
    "maximum_units_per_dose": "max_daily_dose",
    "maximum_doses_per_day": "max_daily_dose",
    "maximum_daily_ingredient_amount": "max_daily_dose",
    "minimum_interval_hours": "minimum_interval",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def runtime_amount(join: dict[str, str]) -> tuple[float, str, str]:
    amount = float(join["amount_per_unit"])
    unit = join["amount_unit"]
    basis = join["unit_basis"].replace(" ", "")
    if "100mL" in basis or "100밀리리터" in basis:
        if unit == "g":
            return amount * 1000 / 100, "mg", "mL"
        if unit == "mg":
            return amount / 100, "mg", "mL"
    if "1병" in basis:
        return amount, unit, "병"
    if "1매" in basis:
        return amount, unit, "매"
    if "1캡슐" in basis:
        return amount, unit, "캡슐"
    return amount, unit, "정"


def build() -> dict:
    products = rows(OTC / "normalized" / "product_master.csv")
    ingredients = {row["ingredient_id"]: row for row in rows(OTC / "normalized" / "ingredient_master.csv")}
    joins = rows(OTC / "normalized" / "product_ingredient.csv")
    candidate_rows = rows(OTC / "selection" / "official_designation_candidates.csv")
    candidate_rows += rows(OTC / "selection" / "rule_coverage_candidates.csv")
    candidates = {row["candidate_id"]: row for row in candidate_rows}
    rules = rows(OTC / "rules" / "rules.csv")
    released_rules = [rule for rule in rules if rule["status"] == "released"]
    released_rule_ids = {rule["rule_id"] for rule in released_rules}
    rule_types_by_id = {rule["rule_id"]: rule["rule_type"] for rule in released_rules}
    bindings = [
        row for row in rows(OTC / "rules" / "runtime_rule_bindings.csv")
        if row["rule_id"] in released_rule_ids and row["supports_release"] == "true"
    ]
    bindings_by_item: dict[str, list[dict[str, str]]] = {}
    for binding in bindings:
        bindings_by_item.setdefault(binding["item_sequence"], []).append(binding)

    dosage_pdf_hashes = {
        row["item_sequence"]: row["pdf_sha256"]
        for row in rows(OTC / "extracted" / "nedrug" / "page_manifest.csv")
        if row["document_type"] == "UD" and row["page"] == "1"
    }
    constraint_rows = [
        row for row in rows(OTC / "normalized" / "administration_constraints.csv")
        if row["record_status"] == "verified_from_authorization_source"
    ]
    constraints_by_item: dict[str, list[dict[str, str]]] = {}
    for row in constraint_rows:
        if row["constraint_type"] not in ADMINISTRATION_CONSTRAINT_TYPES:
            raise ValueError(f"unsupported administration constraint: {row['constraint_type']}")
        if float(row["value"]) <= 0:
            raise ValueError(f"administration constraint must be positive: {row['constraint_id']}")
        if dosage_pdf_hashes.get(row["item_sequence"]) != row["source_sha256"]:
            raise ValueError(f"administration constraint source hash mismatch: {row['constraint_id']}")
        constraints_by_item.setdefault(row["item_sequence"], []).append(row)

    by_product: dict[str, list[dict[str, str]]] = {}
    for join in joins:
        if join["selected_for_calculation"] == "true":
            by_product.setdefault(join["product_id"], []).append(join)

    runtime_products = []
    unresolved = []
    for product in products:
        candidate = candidates[product["candidate_id"]]
        class_name = CLASS_NAMES.get(candidate["class_id"], candidate["class_id"])
        if product.get("analysis_status") == "excluded":
            continue
        if product["record_status"] != "verified_from_source":
            unresolved.append({
                "candidateId": product["candidate_id"], "productName": product["product_name"],
                "className": class_name, "status": "withdrawn",
            })
            continue
        if product["calculation_ready"] != "true":
            unresolved.append({
                "candidateId": product["candidate_id"], "productName": product["product_name"],
                "className": class_name, "status": "package_variant_unresolved",
            })
            continue
        product_ingredients = []
        product_bindings = bindings_by_item.get(product["item_sequence"], [])
        product_constraints = constraints_by_item.get(product["item_sequence"], [])
        product_flags = sorted({flag for binding in product_bindings for flag in binding["flags"].split(";") if flag})
        dose_unit_label = "정"
        for join in by_product.get(product["product_id"], []):
            ingredient = ingredients[join["ingredient_id"]]
            amount, amount_unit, dose_unit_label = runtime_amount(join)
            ingredient_bindings = [binding for binding in product_bindings if binding["ingredient_id"] == join["ingredient_id"]]
            ingredient_row = {
                "ingredientId": join["ingredient_id"], "nameKo": join["ingredient_name_normalized"],
                "amountPerUnit": amount, "unit": amount_unit,
                "pharmacologicClasses": [value for value in ingredient["pharmacologic_classes"].split(";") if value and value != "unclassified"],
                "flags": sorted({flag for binding in ingredient_bindings for flag in binding["flags"].split(";") if flag}),
                "evidence": {
                    "sourceId": product["source_id"], "locator": join["source_locator"],
                    "url": product["authorization_document_url"],
                },
            }
            max_daily = [float(binding["max_daily_amount"]) for binding in ingredient_bindings if binding["max_daily_amount"]]
            intervals = [float(binding["minimum_interval_hours"]) for binding in ingredient_bindings if binding["minimum_interval_hours"]]
            if max_daily:
                ingredient_row["maxDailyAmount"] = min(max_daily)
            if intervals:
                ingredient_row["minimumIntervalHours"] = max(intervals)
            product_ingredients.append(ingredient_row)
        product_ingredient_ids = {row["ingredientId"] for row in product_ingredients}
        for constraint in product_constraints:
            if constraint["ingredient_id"] and constraint["ingredient_id"] not in product_ingredient_ids:
                raise ValueError(f"constraint ingredient is not in product: {constraint['constraint_id']}")
        supported_rule_types = {
            rule_types_by_id[binding["rule_id"]]
            for binding in product_bindings
            if binding["rule_id"] in rule_types_by_id
        }
        supported_rule_types.update(
            CONSTRAINT_RULE_TYPES[constraint["constraint_type"]]
            for constraint in product_constraints
        )
        runtime_product = {
            "productId": product["product_id"], "itemSequence": product["item_sequence"],
            "productName": product["product_name"], "classification": "일반의약품",
            "authorizationStatus": "active", "doseUnitLabel": dose_unit_label,
            "ingredients": product_ingredients, "flags": product_flags,
            "supportedRuleTypes": sorted(supported_rule_types),
            "administrationConstraints": [
                {
                    "constraintId": constraint["constraint_id"],
                    "type": constraint["constraint_type"],
                    "value": float(constraint["value"]),
                    "valueUnit": constraint["value_unit"],
                    **({"ingredientId": constraint["ingredient_id"]} if constraint["ingredient_id"] else {}),
                    "derivationMethod": constraint["derivation_method"],
                    "evidence": {
                        "sourceId": constraint["source_id"],
                        "locator": constraint["source_locator"],
                        "url": constraint["source_url"],
                    },
                }
                for constraint in product_constraints
            ],
            "evidence": {
                "sourceId": product["source_id"], "locator": product["source_locator"],
                "url": product["authorization_document_url"],
            },
        }
        minimum_ages = [float(binding["minimum_age_years"]) for binding in product_bindings if binding["minimum_age_years"]]
        maximum_days = [float(binding["maximum_continuous_days"]) for binding in product_bindings if binding["maximum_continuous_days"]]
        if minimum_ages:
            runtime_product["minimumAgeYears"] = max(minimum_ages)
        if maximum_days:
            runtime_product["maximumContinuousDays"] = min(maximum_days)
        runtime_products.append(runtime_product)
    return {
        "schemaVersion": "2.0.0", "generatedAt": date.today().isoformat(),
        "researchDirection": "korean_otc_product_safety", "releaseReady": False,
        "rulesReleased": len(released_rules), "releasedRuleTypes": [rule["rule_type"] for rule in released_rules],
        "urgentReferralBindings": [
            {"itemSequence": binding["item_sequence"], "terms": [term for term in binding.get("red_flag_terms", "").split(";") if term]}
            for binding in bindings if binding.get("red_flag_terms")
        ],
        "products": runtime_products,
        "officialCandidates": unresolved,
    }


def main() -> int:
    runtime = build()
    target = ROOT / "src" / "generated" / "otc-runtime.json"
    target.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"products={len(runtime['products'])} unresolved={len(runtime['officialCandidates'])} released_rules={runtime['rulesReleased']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
