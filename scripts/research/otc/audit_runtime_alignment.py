from __future__ import annotations

import csv
import json
import re
from pathlib import Path

try:
    from scripts.research.otc.build_runtime import runtime_amount
except ModuleNotFoundError:  # Direct script execution from the repository root.
    from build_runtime import runtime_amount


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "audit" / "runtime_research_alignment.json"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def short_product_name(name: str) -> str:
    return re.sub(r"\([^()]+\)$", "", name).strip()


def display_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def audit() -> dict:
    products = rows(OTC / "normalized" / "product_master.csv")
    joins = rows(OTC / "normalized" / "product_ingredient.csv")
    exclusions = rows(OTC / "normalized" / "analysis_exclusions.csv")
    constraints = [
        row for row in rows(OTC / "normalized" / "administration_constraints.csv")
        if row["record_status"] == "verified_from_authorization_source"
    ]
    runtime = json.loads((ROOT / "src" / "generated" / "otc-runtime.json").read_text(encoding="utf-8"))

    analysis_products = [row for row in products if row["analysis_status"] == "included"]
    analysis_product_ids = {row["product_id"] for row in analysis_products}
    products_by_id = {row["product_id"]: row for row in products}
    analysis_variant_rows = [row for row in joins if row["product_id"] in analysis_product_ids]
    selected_joins = [row for row in joins if row["selected_for_calculation"] == "true"]
    runtime_products = runtime.get("products", [])
    runtime_by_id = {row["productId"]: row for row in runtime_products}

    errors: list[dict[str, str]] = []
    if set(runtime_by_id) != analysis_product_ids:
        errors.append({
            "code": "PRODUCT_SET_MISMATCH",
            "detail": f"analysis={sorted(analysis_product_ids)} runtime={sorted(runtime_by_id)}",
        })

    selected_by_key = {(row["product_id"], row["ingredient_id"]): row for row in selected_joins}
    runtime_by_key = {
        (product["productId"], ingredient["ingredientId"]): ingredient
        for product in runtime_products
        for ingredient in product["ingredients"]
    }
    if set(selected_by_key) != set(runtime_by_key):
        errors.append({
            "code": "PRODUCT_INGREDIENT_SET_MISMATCH",
            "detail": f"selected={len(selected_by_key)} runtime={len(runtime_by_key)}",
        })

    declared_unit_conversions = []
    for key, join in selected_by_key.items():
        runtime_ingredient = runtime_by_key.get(key)
        if not runtime_ingredient:
            continue
        expected_amount, expected_unit, _ = runtime_amount(join)
        if float(runtime_ingredient["amountPerUnit"]) != expected_amount or runtime_ingredient["unit"] != expected_unit:
            errors.append({
                "code": "AMOUNT_UNIT_MISMATCH",
                "detail": f"{key}: expected={expected_amount}{expected_unit} runtime={runtime_ingredient['amountPerUnit']}{runtime_ingredient['unit']}",
            })
        evidence = runtime_ingredient.get("evidence", {})
        if not evidence.get("sourceId") or not evidence.get("locator") or not evidence.get("url"):
            errors.append({"code": "INGREDIENT_EVIDENCE_MISSING", "detail": str(key)})
        compact_basis = join["unit_basis"].replace(" ", "")
        if "100mL" in compact_basis or "100밀리리터" in compact_basis:
            product = products_by_id[join["product_id"]]
            declared_unit_conversions.append({
                "item_sequence": product["item_sequence"],
                "product_name": short_product_name(product["product_name"]),
                "source": f"{display_number(float(join['amount_per_unit']))} {join['amount_unit']}/100 mL",
                "runtime": f"{display_number(expected_amount)} {expected_unit}/mL",
            })

    source_constraints_by_id = {row["constraint_id"]: row for row in constraints}
    runtime_constraints_by_id = {
        constraint["constraintId"]: constraint
        for product in runtime_products
        for constraint in product["administrationConstraints"]
    }
    if set(source_constraints_by_id) != set(runtime_constraints_by_id):
        errors.append({
            "code": "ADMINISTRATION_CONSTRAINT_SET_MISMATCH",
            "detail": f"source={len(source_constraints_by_id)} runtime={len(runtime_constraints_by_id)}",
        })
    for constraint_id, source in source_constraints_by_id.items():
        current = runtime_constraints_by_id.get(constraint_id)
        if not current:
            continue
        expected_ingredient = source["ingredient_id"] or None
        current_ingredient = current.get("ingredientId")
        matches = (
            current["type"] == source["constraint_type"]
            and float(current["value"]) == float(source["value"])
            and current["valueUnit"] == source["value_unit"]
            and current_ingredient == expected_ingredient
            and current["evidence"]["sourceId"] == source["source_id"]
            and current["evidence"]["locator"] == source["source_locator"]
            and current["evidence"]["url"] == source["source_url"]
            and bool(source["source_sha256"])
        )
        if not matches:
            errors.append({"code": "ADMINISTRATION_CONSTRAINT_MISMATCH", "detail": constraint_id})

    excluded_product_ids = {row["product_id"] for row in exclusions}
    runtime_candidate_ids = {row["candidateId"] for row in runtime.get("officialCandidates", [])}
    excluded_product_leaks = sorted(
        excluded_product_ids & set(runtime_by_id)
        | {row["product_id"] for row in products if row["candidate_id"] in runtime_candidate_ids and row["product_id"] in excluded_product_ids}
    )
    if excluded_product_leaks:
        errors.append({"code": "EXCLUDED_PRODUCT_RUNTIME_LEAK", "detail": ",".join(excluded_product_leaks)})

    counts = {
        "analysis_products": len(analysis_products),
        "runtime_products": len(runtime_products),
        "analysis_product_ingredient_variant_rows": len(analysis_variant_rows),
        "selected_product_ingredient_bindings": len(selected_joins),
        "runtime_product_ingredient_bindings": len(runtime_by_key),
        "analysis_unique_ingredients": len({row["ingredient_id"] for row in selected_joins}),
        "runtime_unique_ingredients": len({key[1] for key in runtime_by_key}),
        "verified_administration_constraints": len(constraints),
        "runtime_administration_constraints": len(runtime_constraints_by_id),
    }
    return {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "scope": "analysis_dataset_to_site_runtime",
        "valid": not errors,
        "counts": counts,
        "declared_unit_conversions": sorted(declared_unit_conversions, key=lambda row: row["item_sequence"]),
        "excluded_product_leaks": excluded_product_leaks,
        "errors": errors,
    }


def write(result: dict) -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUTPUT


def main() -> int:
    result = audit()
    write(result)
    print(json.dumps({"valid": result["valid"], **result["counts"]}, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
