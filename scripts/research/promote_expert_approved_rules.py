from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


BOOLEAN_FIELDS = (
    "threshold_correct",
    "scope_correct",
    "conditions_correct",
    "exceptions_correct",
    "message_safe",
    "next_action_safe",
    "source_locator_verified",
)


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    if validation.get("release_ready") is not True or validation.get("errors"):
        raise SystemExit("expert review validation is not release-ready")

    rules, fields = read_rows(args.rules)
    packet, _ = read_rows(args.packet)
    reviews = {row["rule_id"]: row for row in packet}
    if len(rules) != len(reviews):
        raise SystemExit("rule/review count mismatch")

    promoted = 0
    for rule in rules:
        review = reviews.get(rule["rule_id"])
        if not review:
            raise SystemExit(f"review missing: {rule['rule_id']}")
        if review.get("overall_decision") != "approve":
            raise SystemExit(f"rule not approved: {rule['rule_id']}")
        if any(review.get(field, "").lower() != "true" for field in BOOLEAN_FIELDS):
            raise SystemExit(f"review checklist incomplete: {rule['rule_id']}")
        if not rule.get("evidence_quote") and review.get("evidence_quote"):
            rule["evidence_quote"] = review["evidence_quote"]
        if not all(rule.get(field) for field in ("source_id", "locator", "evidence_quote")):
            raise SystemExit(f"evidence binding incomplete: {rule['rule_id']}")
        if not review.get("reviewer_id") or not review.get("reviewed_at"):
            raise SystemExit(f"review identity/time missing: {rule['rule_id']}")
        rule.update(
            {
                "review_status": "released",
                "reviewer_id": review["reviewer_id"],
                "reviewed_at": review["reviewed_at"],
                "change_history": f"{rule.get('change_history', '')}; expert-approved release".strip("; "),
            }
        )
        promoted += 1

    with args.rules.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rules)
    print(json.dumps({"promoted": promoted, "review_status": "released"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
