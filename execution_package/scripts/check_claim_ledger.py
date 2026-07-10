#!/usr/bin/env python3
"""Audit thesis claims against source and metric provenance fields."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger")
    parser.add_argument("--out", default="claim_ledger_audit.json")
    args = parser.parse_args()

    with Path(args.ledger).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    issues: list[dict[str, object]] = []
    ids = [(row.get("claim_id") or "").strip() for row in rows]
    duplicate_ids = {value for value, count in Counter(ids).items() if value and count > 1}

    for line_number, row in enumerate(rows, start=2):
        claim_id = (row.get("claim_id") or "").strip()
        claim_type = (row.get("claim_type") or "").strip().lower()
        status = (row.get("status") or "").strip().lower()
        if not claim_id:
            issues.append({"line": line_number, "issue": "missing claim_id"})
        elif claim_id in duplicate_ids:
            issues.append({"line": line_number, "claim_id": claim_id, "issue": "duplicate claim_id"})
        if not (row.get("claim_text") or "").strip():
            issues.append({"line": line_number, "claim_id": claim_id, "issue": "missing claim_text"})
        if claim_type == "numeric" and (
            not (row.get("metric_id") or "").strip()
            or not (row.get("analysis_script") or "").strip()
        ):
            issues.append(
                {
                    "line": line_number,
                    "claim_id": claim_id,
                    "issue": "numeric claim lacks metric_id or analysis_script",
                }
            )
        if claim_type in {"literature", "clinical"} and (
            not (row.get("source_id") or "").strip()
            or not (row.get("source_locator") or "").strip()
        ):
            issues.append(
                {
                    "line": line_number,
                    "claim_id": claim_id,
                    "issue": "literature/clinical claim lacks source_id or source_locator",
                }
            )
        if claim_type == "interpretive" and not (row.get("certainty_or_limitation") or "").strip():
            issues.append(
                {
                    "line": line_number,
                    "claim_id": claim_id,
                    "issue": "interpretive claim lacks limitation/uncertainty statement",
                }
            )
        if not (row.get("verified_by") or "").strip():
            issues.append({"line": line_number, "claim_id": claim_id, "issue": "missing verifier"})
        if status != "verified":
            issues.append({"line": line_number, "claim_id": claim_id, "issue": "claim not verified"})

    result = {
        "rows": len(rows),
        "unique_claim_ids": len({value for value in ids if value}),
        "issues": issues,
        "pass": not issues,
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
