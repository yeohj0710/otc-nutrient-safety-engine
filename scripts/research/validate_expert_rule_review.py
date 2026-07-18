from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

BOOLEAN_FIELDS = (
    "threshold_correct", "scope_correct", "conditions_correct", "exceptions_correct", "message_safe",
    "next_action_safe", "source_locator_verified",
)
DECISIONS = {"approve", "revise", "reject"}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(path: Path) -> dict[str, object]:
    data = rows(path)
    errors: list[dict[str, str]] = []
    completed = 0
    approved = 0
    for row in data:
        item = row.get("review_item_id", "<blank>")
        decision = row.get("overall_decision", "").strip().lower()
        if not decision:
            continue
        completed += 1
        if decision not in DECISIONS:
            errors.append({"code": "INVALID_DECISION", "item": item})
            continue
        missing = [field for field in (*BOOLEAN_FIELDS, "reviewer_id", "reviewer_role", "reviewed_at") if not row.get(field, "").strip()]
        if missing:
            errors.append({"code": "REVIEW_PROVENANCE_MISSING", "item": item, "fields": ",".join(missing)})
        invalid_boolean = [field for field in BOOLEAN_FIELDS if row.get(field, "").strip().lower() not in {"true", "false"}]
        if invalid_boolean:
            errors.append({"code": "INVALID_BOOLEAN", "item": item, "fields": ",".join(invalid_boolean)})
        if decision == "approve":
            if any(row[field].strip().lower() != "true" for field in BOOLEAN_FIELDS):
                errors.append({"code": "APPROVAL_WITH_FAILED_CHECK", "item": item})
            if not row.get("evidence_quote", "").strip():
                errors.append({"code": "APPROVAL_WITHOUT_EVIDENCE_QUOTE", "item": item})
            else:
                approved += 1
        if decision in {"revise", "reject"} and not row.get("required_revision", "").strip():
            errors.append({"code": "REVISION_REASON_MISSING", "item": item})
    return {
        "schema_version": "1.0.0", "items": len(data), "completed": completed, "approved": approved,
        "errors": errors, "valid": not errors, "all_reviewed": bool(data) and completed == len(data),
        "release_candidate_count": approved if not errors else 0,
        "release_ready": not errors and completed == len(data) and approved == len(data),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.packet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
