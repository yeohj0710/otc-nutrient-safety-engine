#!/usr/bin/env python3
"""Fail-closed checks for human screening, extraction, RoB, and GRADE inputs."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


FINAL = {"include", "exclude"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def reviewers(value: str | None) -> set[str]:
    return {part.strip() for part in str(value or "").replace(",", ";").split(";") if part.strip()}


def validate_screening(rows: list[dict[str, str]], id_field: str) -> list[str]:
    errors: list[str] = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        item_id = (row.get(id_field) or "").strip()
        if not item_id:
            errors.append(f"blank_{id_field}:line_{line}")
            continue
        grouped[item_id].append(row)
    for item_id, item_rows in grouped.items():
        human_reviewers = {(row.get("reviewer_id") or "").strip() for row in item_rows if (row.get("reviewer_id") or "").strip()}
        final_values = {(row.get("adjudicated_decision") or "").strip().lower() for row in item_rows if (row.get("adjudicated_decision") or "").strip()}
        if len(human_reviewers) < 2:
            errors.append(f"fewer_than_two_reviewers:{item_id}")
        if len(final_values) != 1 or not final_values.issubset(FINAL):
            errors.append(f"missing_or_conflicting_adjudication:{item_id}")
        adjudicators = {(row.get("adjudicator_id") or "").strip() for row in item_rows if (row.get("adjudicator_id") or "").strip()}
        if not adjudicators:
            errors.append(f"missing_adjudicator:{item_id}")
    if not grouped:
        errors.append("no_screening_rows")
    return errors


def validate_extraction(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for line, row in enumerate(rows, start=2):
        item_id = (row.get("extraction_id") or f"line_{line}").strip()
        extractor = (row.get("extractor_id") or "").strip()
        verifier = (row.get("verifier_id") or "").strip()
        if not extractor or not verifier or extractor == verifier:
            errors.append(f"invalid_independent_verification:{item_id}")
        if (row.get("verification_status") or "").strip().lower() != "verified":
            errors.append(f"not_verified:{item_id}")
        for field in ("report_id", "clinical_node_id", "outcome_id", "locator", "supporting_quote"):
            if not (row.get(field) or "").strip():
                errors.append(f"missing_{field}:{item_id}")
    if not rows:
        errors.append("no_extraction_rows")
    return errors


def validate_rob(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for line, row in enumerate(rows, start=2):
        item_id = (row.get("assessment_id") or f"line_{line}").strip()
        first = (row.get("reviewer_id") or "").strip()
        second = (row.get("second_reviewer_id") or "").strip()
        if not first or not second or first == second:
            errors.append(f"invalid_rob_reviewers:{item_id}")
        for field in ("tool", "domain", "supporting_rationale", "locator", "adjudicated_judgement"):
            if not (row.get(field) or "").strip():
                errors.append(f"missing_{field}:{item_id}")
    if not rows:
        errors.append("no_rob_rows")
    return errors


def validate_grade(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for line, row in enumerate(rows, start=2):
        item_id = f"{row.get('clinical_node_id', '')}:{row.get('outcome_id', '')}" or f"line_{line}"
        if len(reviewers(row.get("reviewer_ids"))) < 2:
            errors.append(f"fewer_than_two_grade_reviewers:{item_id}")
        for field in ("clinical_node_id", "outcome_id", "final_certainty", "rationale"):
            if not (row.get(field) or "").strip():
                errors.append(f"missing_{field}:{item_id}")
    if not rows:
        errors.append("no_grade_rows")
    return errors


def validate_root(root: Path) -> dict[str, Any]:
    checks = {
        "title_abstract": validate_screening(read_csv(root / "screening" / "title_abstract.csv"), "record_id"),
        "full_text": validate_screening(read_csv(root / "screening" / "full_text.csv"), "report_id"),
        "extraction": validate_extraction(read_csv(root / "extraction" / "extraction.csv")),
        "risk_of_bias": validate_rob(read_csv(root / "risk_of_bias" / "assessments.csv")),
        "grade": validate_grade(read_csv(root / "synthesis" / "grade.csv")),
    }
    return {
        "checks": {name: {"pass": not errors, "errors": errors} for name, errors in checks.items()},
        "pass": all(not errors for errors in checks.values()),
        "note": "Only completed independent human decisions can satisfy these checks.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_root", nargs="?", default="research_v2")
    parser.add_argument("--out", default="human_adjudication_readiness.json")
    args = parser.parse_args()
    result = validate_root(Path(args.research_root))
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
