from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "validation" / "normalization_reference.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build() -> list[dict[str, str]]:
    ingredients = rows(OTC / "normalized" / "ingredient_master.csv")
    joins = rows(OTC / "normalized" / "product_ingredient.csv")
    existing = {row["ingredient_id"]: row for row in rows(OUTPUT)} if OUTPUT.exists() else {}
    raw_by_id: dict[str, set[str]] = {}
    for row in joins:
        raw_by_id.setdefault(row["ingredient_id"], set()).add(row["ingredient_name_raw"])
    result = []
    for ingredient in ingredients:
        prior = existing.get(ingredient["ingredient_id"], {})
        result.append({
            "ingredient_id": ingredient["ingredient_id"],
            "raw_names": ";".join(sorted(raw_by_id.get(ingredient["ingredient_id"], set()))),
            "system_normalized_name": ingredient["preferred_name_ko"],
            "human_reference_name": prior.get("human_reference_name", ""),
            "human_reviewer_id": prior.get("human_reviewer_id", ""),
            "human_reviewed_at": prior.get("human_reviewed_at", ""),
            "status": prior.get("status", "awaiting_independent_normalization_review"),
        })
    return result


def main() -> int:
    records = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    print(f"normalization_reference_rows={len(records)} human_reviewed={sum(bool(row['human_reference_name']) for row in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
