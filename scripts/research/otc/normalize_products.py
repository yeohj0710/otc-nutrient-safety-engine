from __future__ import annotations

import argparse
import csv
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scripts.research.otc.fetch_mfds_products import response_items


FIELD_SEPARATOR = re.compile(r"\s*\|\s*")
TAG = re.compile(r"<[^>]+>")
INGREDIENT_START = re.compile(r"(?:^|\|)\s*성분명\s*:\s*")
KNOWN_UNIT_MAP = {
    "밀리그램": "mg",
    "mg": "mg",
    "그램": "g",
    "g": "g",
    "마이크로그램": "mcg",
    "μg": "mcg",
    "㎍": "mcg",
    "밀리리터": "mL",
    "mL": "mL",
    "아이.유": "IU",
    "IU": "IU",
    "%": "%",
    "단위": "unit",
}


@dataclass(frozen=True)
class Alias:
    raw_name: str
    ingredient_id: str
    normalized_key: str
    preferred_name_ko: str
    preferred_name_en: str
    pharmacologic_classes: tuple[str, ...]
    status: str


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def first(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean_text(item.get(key))
        if value:
            return value
    return ""


def load_aliases(path: Path) -> dict[str, Alias]:
    aliases: dict[str, Alias] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            alias = Alias(
                raw_name=row["raw_name"].strip(),
                ingredient_id=row["ingredient_id"].strip(),
                normalized_key=row["normalized_key"].strip(),
                preferred_name_ko=row["preferred_name_ko"].strip(),
                preferred_name_en=row["preferred_name_en"].strip(),
                pharmacologic_classes=tuple(filter(None, row["pharmacologic_classes"].split(";"))),
                status=row["status"].strip(),
            )
            aliases[alias.raw_name.casefold()] = alias
    return aliases


def parse_material(material: str) -> tuple[str, list[dict[str, Any]]]:
    material = clean_text(material)
    total_match = re.search(r"총량\s*:\s*([^|]+)", material)
    unit_basis = total_match.group(1).strip() if total_match else ""
    starts = list(INGREDIENT_START.finditer(material))
    rows: list[dict[str, Any]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(material)
        block = material[match.end() : end].strip(" |")
        segments = FIELD_SEPARATOR.split(block)
        raw_name = segments[0].strip()
        fields: dict[str, str] = {}
        for segment in segments[1:]:
            if ":" not in segment:
                continue
            key, value = segment.split(":", 1)
            fields[key.strip()] = value.strip()
        amount_text = fields.get("분량", "").replace(",", "")
        try:
            amount = float(amount_text)
        except ValueError:
            amount = None
        unit_raw = fields.get("단위", "")
        rows.append(
            {
                "ingredient_name_raw": raw_name,
                "amount_per_unit": amount,
                "amount_unit": KNOWN_UNIT_MAP.get(unit_raw),
                "amount_unit_raw": unit_raw,
                "unit_basis": unit_basis,
            }
        )
    return unit_basis, rows


def normalize_item(item: dict[str, Any], aliases: dict[str, Alias], source_sha256: str, retrieved_at: str) -> dict[str, Any]:
    item_sequence = first(item, "ITEM_SEQ", "itemSeq")
    product_name = first(item, "ITEM_NAME", "itemName")
    classification = first(item, "ETC_OTC_CODE", "etcOtcCode")
    cancel_date = first(item, "CANCEL_DATE", "cancelDate")
    rejection_reasons = []
    if classification != "일반의약품":
        rejection_reasons.append("not_otc")
    if cancel_date:
        rejection_reasons.append("cancelled_or_withdrawn")
    if not item_sequence or not product_name:
        rejection_reasons.append("missing_identity")

    material = first(item, "MATERIAL_NAME", "materialName")
    unit_basis, parsed_ingredients = parse_material(material)
    normalized_ingredients = []
    ingredient_errors = []
    for parsed in parsed_ingredients:
        alias = aliases.get(parsed["ingredient_name_raw"].casefold())
        if alias is None or alias.status != "verified":
            ingredient_errors.append(f"unverified_ingredient:{parsed['ingredient_name_raw']}")
            continue
        if parsed["amount_per_unit"] is None or parsed["amount_unit"] is None or not parsed["unit_basis"]:
            ingredient_errors.append(f"incomplete_amount:{parsed['ingredient_name_raw']}")
            continue
        normalized_ingredients.append(
            {
                "product_id": f"MFDS-{item_sequence}",
                "ingredient_id": alias.ingredient_id,
                "ingredient_name_raw": parsed["ingredient_name_raw"],
                "ingredient_name_normalized": alias.normalized_key,
                "amount_per_unit": parsed["amount_per_unit"],
                "amount_unit": parsed["amount_unit"],
                "unit_basis": parsed["unit_basis"],
                "source_id": f"MFDS-NEDRUG-{item_sequence}",
                "source_locator": f"원료약품 및 분량 > {parsed['unit_basis']}",
                "normalization_status": "verified",
            }
        )
    if not normalized_ingredients:
        ingredient_errors.append("no_verified_ingredient_rows")

    source_id = f"MFDS-NEDRUG-{item_sequence}" if item_sequence else ""
    product = {
        "product_id": f"MFDS-{item_sequence}",
        "item_sequence": item_sequence,
        "product_name": product_name,
        "manufacturer_name": first(item, "ENTP_NAME", "entpName"),
        "classification": classification,
        "authorization_status": "cancelled" if cancel_date else "active",
        "dosage_form": first(item, "CHART", "FORM_CODE_NAME", "formCodeName"),
        "route": first(item, "ROUTE_NAME", "routeName"),
        "active_ingredient_raw": material,
        "dose_per_administration": first(item, "DOSE_PER_ADMIN", "dosePerAdmin"),
        "administrations_per_day": first(item, "ADMIN_PER_DAY", "adminPerDay"),
        "max_daily_dose": first(item, "MAX_DAILY_DOSE", "maxDailyDose"),
        "minimum_dose_interval": first(item, "MIN_DOSE_INTERVAL", "minDoseInterval"),
        "age_restriction": first(item, "AGE_RESTRICTION", "ageRestriction"),
        "indications": first(item, "EE_DOC_DATA", "efcyQesitm"),
        "dosage_and_administration": first(item, "UD_DOC_DATA", "useMethodQesitm"),
        "warnings": first(item, "NB_DOC_DATA", "atpnQesitm"),
        "contraindications": first(item, "CONTRAINDICATIONS", "contraindications"),
        "drug_interactions": first(item, "INTRC_QESITM", "intrcQesitm"),
        "pregnancy_lactation": first(item, "PREGNANCY_LACTATION", "pregnancyLactation"),
        "hepatic_renal": first(item, "HEPATIC_RENAL", "hepaticRenal"),
        "authorization_document_url": first(item, "ITEM_IMAGE", "authorizationDocumentUrl") or f"https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail?itemSeq={item_sequence}",
        "source_id": source_id,
        "source_locator": "품목허가사항; 원료약품 및 분량; 효능효과; 용법용량; 사용상의 주의사항",
        "retrieved_at": retrieved_at,
        "source_sha256": source_sha256,
        "record_status": "normalized",
    }
    return {
        "product": product,
        "ingredients": normalized_ingredients,
        "unit_basis": unit_basis,
        "rejection_reasons": rejection_reasons + ingredient_errors,
        "eligible": not rejection_reasons and not ingredient_errors,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_snapshots(snapshot_paths: Iterable[Path], aliases_path: Path, output_dir: Path, retrieved_at: str) -> dict[str, int]:
    aliases = load_aliases(aliases_path)
    products = []
    joins = []
    ingredient_master: dict[str, dict[str, Any]] = {}
    rejected = []
    for snapshot_path in snapshot_paths:
        raw = snapshot_path.read_bytes()
        from scripts.research.otc.hash_snapshot import sha256_bytes

        source_sha256 = sha256_bytes(raw)
        payload = json.loads(raw.decode("utf-8"))
        for item in response_items(payload):
            normalized = normalize_item(item, aliases, source_sha256, retrieved_at)
            if normalized["eligible"]:
                products.append(normalized["product"])
                joins.extend(normalized["ingredients"])
                for join in normalized["ingredients"]:
                    alias = next(value for value in aliases.values() if value.ingredient_id == join["ingredient_id"])
                    ingredient_master[alias.ingredient_id] = {
                        "ingredient_id": alias.ingredient_id,
                        "preferred_name_ko": alias.preferred_name_ko,
                        "preferred_name_en": alias.preferred_name_en,
                        "normalized_key": alias.normalized_key,
                        "pharmacologic_classes": ";".join(alias.pharmacologic_classes),
                        "source_id": join["source_id"],
                        "source_locator": join["source_locator"],
                        "status": "verified",
                    }
            else:
                rejected.append(
                    {
                        "item_sequence": normalized["product"]["item_sequence"],
                        "product_name": normalized["product"]["product_name"],
                        "reasons": ";".join(dict.fromkeys(normalized["rejection_reasons"])),
                        "source_sha256": source_sha256,
                    }
                )
    product_fields = list(products[0].keys()) if products else []
    join_fields = list(joins[0].keys()) if joins else []
    ingredient_rows = sorted(ingredient_master.values(), key=lambda row: row["ingredient_id"])
    ingredient_fields = list(ingredient_rows[0].keys()) if ingredient_rows else []
    write_csv(output_dir / "products.csv", products, product_fields)
    write_csv(output_dir / "product_ingredients.csv", joins, join_fields)
    write_csv(output_dir / "ingredients.csv", ingredient_rows, ingredient_fields)
    write_csv(output_dir / "rejected_rows.csv", rejected, ["item_sequence", "product_name", "reasons", "source_sha256"])
    report = {"products": len(products), "ingredients": len(ingredient_rows), "product_ingredients": len(joins), "rejected": len(rejected)}
    (output_dir / "normalization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize MFDS Korean OTC products")
    parser.add_argument("snapshots", nargs="+", type=Path)
    parser.add_argument("--aliases", type=Path, default=Path("research_v3/otc/normalization/ingredient_aliases.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("research_v3/otc/normalized"))
    parser.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()
    print(json.dumps(normalize_snapshots(args.snapshots, args.aliases, args.output_dir, args.retrieved_at), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
