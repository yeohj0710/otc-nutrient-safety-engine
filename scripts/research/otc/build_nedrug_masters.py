from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
PRODUCTS = OTC / "normalized" / "products.json"
ALIASES = OTC / "normalization" / "ingredient_aliases.csv"
OUT = OTC / "normalized"

UNIT_MAP = {"밀리그램": "mg", "그램": "g", "마이크로그램": "mcg", "밀리리터": "mL", "mL": "mL"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def canonical_raw_name(name: str) -> str:
    # Source qualifiers describe particle form, not a distinct active ingredient.
    return re.sub(r"\((?:미분화)\)$", "", name).strip()


def candidate_id(name: str) -> str:
    return "ING-mf-src-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def basis_variant(basis: str) -> str:
    match = re.search(r"-\s*(내수용|수출용I{1,2})\s*$", basis)
    if match:
        return match.group(1)
    match = re.search(r"-\s*\((\d+)\)", basis)
    return f"규격-{match.group(1)}" if match else "단일기준"


def build() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    aliases = {row["raw_name"]: row for row in read_csv(ALIASES)}
    product_rows, ingredient_rows, joins, exclusions = [], {}, [], []
    for product in products:
        verified = product["status"] == "verified_from_source"
        variants = {basis_variant(x["quantity_basis"] or "") for x in product["ingredients"]}
        calculation_ready = verified and (len(variants) == 1 or variants == {"내수용", "수출용I", "수출용II"})
        if product["candidate_id"] == "SAFE-OTC-13":
            calculation_ready = False
        selected_variant = "내수용" if "내수용" in variants else (next(iter(variants)) if len(variants) == 1 else "")
        if calculation_ready:
            analysis_status = "included"
            analysis_exclusion_reason = ""
        elif product["candidate_id"] == "SAFE-OTC-13" and verified:
            analysis_status = "excluded"
            analysis_exclusion_reason = "ambiguous_authorized_package_size"
        else:
            analysis_status = "ineligible"
            analysis_exclusion_reason = "withdrawn_authorization"
        product_row = {
            "candidate_id": product["candidate_id"], "product_id": product["product_id"],
            "item_sequence": product["item_seq"], "product_name": product["product_name"],
            "manufacturer_name": product["company_name"], "classification": product["otc_classification"],
            "authorization_status": product["authorization_status"], "dosage_form": product["dosage_form"] or "",
            "package_unit": product["package_unit"] or "", "authorization_document_url": product["detail_url"],
            "source_id": product["source_id"], "source_locator": product["source_locator"],
            "retrieved_at": product["retrieved_at_utc"][:10], "source_sha256": product["raw_sha256"],
            "record_status": product["status"], "calculation_ready": str(calculation_ready).lower(),
            "selected_ingredient_variant": selected_variant,
            "calculation_blocker": "" if calculation_ready else ("withdrawn authorization" if not verified else "package-size variant unresolved"),
            "analysis_status": analysis_status,
            "analysis_exclusion_reason": analysis_exclusion_reason,
        }
        product_rows.append(product_row)
        if analysis_status == "excluded":
            exclusions.append({
                "candidate_id": product["candidate_id"],
                "product_id": product["product_id"],
                "item_sequence": product["item_seq"],
                "product_name": product["product_name"],
                "exclusion_stage": "analysis_and_runtime",
                "exclusion_reason": analysis_exclusion_reason,
                "source_id": product["source_id"],
                "source_locator": product["source_locator"],
                "source_sha256": product["raw_sha256"],
                "source_records_preserved": "true",
            })
        if not verified:
            continue
        for source in product["ingredients"]:
            raw_name = canonical_raw_name(source["source_name"])
            alias = aliases.get(raw_name)
            ingredient_id = alias["ingredient_id"] if alias else candidate_id(raw_name)
            normalized_name = alias["preferred_name_ko"] if alias else raw_name
            status = "verified" if alias else "candidate"
            ingredient_rows.setdefault(ingredient_id, {
                "ingredient_id": ingredient_id, "preferred_name_ko": normalized_name,
                "preferred_name_en": alias["preferred_name_en"] if alias else raw_name,
                "normalized_key": alias["normalized_key"] if alias else ingredient_id.removeprefix("ING-").replace("-", "_"),
                "pharmacologic_classes": alias["pharmacologic_classes"] if alias else "unclassified",
                "source_id": product["source_id"], "source_locator": source["source_locator"], "status": status,
            })
            variant = basis_variant(source["quantity_basis"] or "")
            joins.append({
                "product_id": product["product_id"], "ingredient_id": ingredient_id,
                "ingredient_name_raw": source["source_name"], "ingredient_name_normalized": normalized_name,
                "amount_per_unit": source["quantity"], "amount_unit": UNIT_MAP.get(source["unit"], source["unit"]),
                "unit_basis": source["quantity_basis"], "variant": variant,
                "selected_for_calculation": str(calculation_ready and variant == selected_variant).lower(),
                "source_id": product["source_id"], "source_locator": source["source_locator"],
                "normalization_status": status,
            })
    return product_rows, sorted(ingredient_rows.values(), key=lambda x: x["ingredient_id"]), joins, exclusions


def main() -> int:
    products, ingredients, joins, exclusions = build()
    write_csv(OUT / "product_master.csv", products, list(products[0]))
    write_csv(OUT / "ingredient_master.csv", ingredients, list(ingredients[0]))
    write_csv(OUT / "product_ingredient.csv", joins, list(joins[0]))
    write_csv(
        OUT / "analysis_exclusions.csv",
        exclusions,
        [
            "candidate_id", "product_id", "item_sequence", "product_name",
            "exclusion_stage", "exclusion_reason", "source_id", "source_locator",
            "source_sha256", "source_records_preserved",
        ],
    )
    print(f"products={len(products)} active={sum(x['record_status'] == 'verified_from_source' for x in products)} calculation_ready={sum(x['calculation_ready'] == 'true' for x in products)}")
    print(f"ingredients={len(ingredients)} joins={len(joins)} analysis_exclusions={len(exclusions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
