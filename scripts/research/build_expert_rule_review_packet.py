from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

FIELDS = [
    "review_item_id", "rule_id", "ingredient_id", "candidate_id", "jurisdiction", "population",
    "threshold_value", "threshold_unit", "threshold_type", "scope", "conditions_json", "exceptions_json",
    "decision_level", "message_ko", "next_action_ko", "source_id", "locator", "source_note",
    "source_file_sha256", "evidence_quote", "threshold_correct", "scope_correct", "conditions_correct",
    "exceptions_correct", "message_safe", "next_action_safe", "source_locator_verified", "overall_decision",
    "required_revision", "reviewer_id", "reviewer_role", "reviewed_at", "second_reviewer_id",
    "second_reviewed_at", "adjudication_status", "adjudicator_id", "adjudicated_at", "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(root: Path) -> list[dict[str, str]]:
    rules = read_csv(root / "rules" / "rules.csv")
    candidates = read_csv(root / "sources" / "normative_candidates.csv")
    kdri: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        if row["jurisdiction"] == "Republic of Korea":
            kdri.setdefault(row["ingredient_id"], []).append(row)
    registry = json.loads((root / "sources" / "source_registry.json").read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in registry["sources"]}
    fetch_manifest = json.loads((root / "sources" / "fetch_manifest_20260713.json").read_text(encoding="utf-8"))
    fetched = {row["source_id"]: row for row in fetch_manifest["records"] if row.get("status") == "fetched"}
    packet: list[dict[str, str]] = []
    for index, rule in enumerate(rules, 1):
        candidate_rows = kdri.get(rule["ingredient_id"], [])
        candidate = candidate_rows[0] if candidate_rows else {}
        joined = lambda field: "; ".join(row[field] for row in candidate_rows)
        source = sources.get(rule["source_id"], {})
        row = {field: "" for field in FIELDS}
        row.update({
            "review_item_id": f"ERR-{index:03d}", "rule_id": rule["rule_id"],
            "ingredient_id": rule["ingredient_id"], "candidate_id": joined("candidate_id"),
            "jurisdiction": candidate.get("jurisdiction", ""), "population": joined("population"),
            "threshold_value": joined("value"), "threshold_unit": joined("unit"),
            "threshold_type": candidate.get("threshold_type", ""), "scope": candidate.get("scope", ""),
            "conditions_json": rule["conditions_json"], "exceptions_json": rule["exceptions_json"],
            "decision_level": rule["decision_level"], "message_ko": rule["message_ko"],
            "next_action_ko": rule["next_action_ko"], "source_id": rule["source_id"],
            "locator": rule["locator"], "source_note": joined("source_note"),
            "source_file_sha256": fetched.get(rule["source_id"], {}).get("sha256", source.get("sha256", "")),
            "evidence_quote": rule["evidence_quote"],
        })
        packet.append(row)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(packet)
    print(f"expert review packet: {len(packet)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
