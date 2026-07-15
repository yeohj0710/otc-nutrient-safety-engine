from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
VALID_TYPES = {
    "duplicate_ingredient", "duplicate_pharmacologic_class", "max_daily_dose", "minimum_interval",
    "age_restriction", "pregnancy_lactation", "hepatic_disease", "renal_disease", "gi_bleeding_ulcer",
    "sedation_driving", "alcohol", "anticoagulant_antiplatelet", "sedative_medication",
    "decongestant_hypertension", "maximum_duration", "urgent_referral",
}


def validate(path: Path = RULES) -> dict[str, int | float | None]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors = []
    ids = set()
    for row in rows:
        if row["rule_id"] in ids:
            errors.append(f"duplicate_id:{row['rule_id']}")
        ids.add(row["rule_id"])
        if row["rule_type"] not in VALID_TYPES:
            errors.append(f"invalid_type:{row['rule_id']}")
        if row["status"] == "released" and (not row["source_id"].strip() or not row["source_locator"].strip()):
            errors.append(f"released_without_source_locator:{row['rule_id']}")
    if errors:
        raise ValueError(";".join(errors))
    released = [row for row in rows if row["status"] == "released"]
    linked = [row for row in released if row["source_id"].strip() and row["source_locator"].strip()]
    return {
        "rules_total": len(rows),
        "rules_draft": sum(row["status"] == "draft" for row in rows),
        "rules_released": len(released),
        "released_source_locator_rate": len(linked) / len(released) if released else None,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False))
