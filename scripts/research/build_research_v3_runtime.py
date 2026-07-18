from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(root: Path) -> dict[str, object]:
    rules = rows(root / "rules" / "rules.csv")
    return {
        "schemaVersion": "1.0.0",
        "lineage": "research_v3",
        "releaseStatus": "draft_not_for_clinical_use",
        "claimBoundary": "KDRI threshold developer prototype; no expert review or independent evaluation",
        "rules": [
            {
                "id": row["rule_id"],
                "ingredientId": row["ingredient_id"],
                "conditions": json.loads(row["conditions_json"]),
                "exceptions": json.loads(row["exceptions_json"]),
                "decisionLevel": row["decision_level"],
                "messageKo": row["message_ko"],
                "nextActionKo": row["next_action_ko"],
                "sourceId": row["source_id"],
                "locator": row["locator"],
                "reviewStatus": row["review_status"],
                "version": row["version"],
            }
            for row in rules
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--output", type=Path, default=Path("src/generated/research-v3-runtime.json"))
    args = parser.parse_args()
    payload = build(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
