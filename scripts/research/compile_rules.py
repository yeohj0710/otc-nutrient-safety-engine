#!/usr/bin/env python3
"""Compile only human-reviewed released rule rows into schema-ready JSONL."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


NODES = {"K1", "K2", "K3", "K4", "K5"}


def parts(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").replace(",", ";").split(";") if part.strip()]


def parse_json(row: dict[str, str], field: str, expected: type, nullable: bool = False) -> Any:
    raw = (row.get(field) or "").strip()
    if nullable and not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, expected):
        raise ValueError(f"{field} must be {expected.__name__}")
    return value


def compile_rows(rows: list[dict[str, str]], quote_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    compiled: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        if (row.get("status") or "").strip() != "released":
            continue
        rule_id = (row.get("rule_id") or "").strip()
        if not rule_id or rule_id in seen:
            errors.append(f"blank_or_duplicate_rule_id:line_{line}")
            continue
        seen.add(rule_id)
        node = (row.get("clinical_node_id") or "").strip()
        if node not in NODES:
            errors.append(f"invalid_clinical_node:{rule_id}")
        evidence_ids = parts(row.get("evidence_ids"))
        source_quote_ids = parts(row.get("source_quote_ids"))
        reviewer_ids = parts(row.get("reviewer_ids"))
        if not evidence_ids:
            errors.append(f"missing_evidence:{rule_id}")
        if not source_quote_ids or any(item not in quote_ids for item in source_quote_ids):
            errors.append(f"missing_or_unknown_source_quote:{rule_id}")
        if len(set(reviewer_ids)) < 2:
            errors.append(f"fewer_than_two_rule_reviewers:{rule_id}")
        try:
            rule = {
                "rule_id": rule_id,
                "clinical_node_id": node,
                "ingredient_id": (row.get("ingredient_id") or "").strip(),
                "population_criteria": parse_json(row, "population_criteria_json", dict),
                "medication_criteria": parse_json(row, "medication_criteria_json", dict),
                "dose": parse_json(row, "dose_json", dict, nullable=True),
                "duration": parse_json(row, "duration_json", dict, nullable=True),
                "outcome_id": (row.get("outcome_id") or "").strip(),
                "action_class": (row.get("action_class") or "").strip(),
                "severity": (row.get("severity") or "").strip(),
                "message_short": (row.get("message_short") or "").strip(),
                "message_explanation": (row.get("message_explanation") or "").strip(),
                "questions_to_ask": parse_json(row, "questions_to_ask_json", list),
                "uncertainty_statement": (row.get("uncertainty_statement") or "").strip(),
                "certainty_grade": (row.get("certainty_grade") or "").strip(),
                "jurisdiction": parse_json(row, "jurisdiction_json", list),
                "evidence_ids": evidence_ids,
                "source_quote_ids": source_quote_ids,
                "reviewer_ids": reviewer_ids,
                "status": "released",
                "valid_from": (row.get("valid_from") or "").strip(),
                "review_due": (row.get("review_due") or "").strip(),
            }
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_json_field:{rule_id}:{exc}")
            continue
        for field in ("ingredient_id", "outcome_id", "action_class", "severity", "message_short", "message_explanation", "uncertainty_statement", "certainty_grade", "valid_from", "review_due"):
            if not rule[field]:
                errors.append(f"missing_{field}:{rule_id}")
        compiled.append(rule)
    if not compiled:
        errors.append("no_released_rules")
    return compiled, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--quotes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    with Path(args.trace).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with Path(args.quotes).open(encoding="utf-8-sig", newline="") as handle:
        quote_ids = {(row.get("quote_id") or "").strip() for row in csv.DictReader(handle) if (row.get("quote_id") or "").strip()}
    compiled, errors = compile_rows(rows, quote_ids)
    report = {"released_rule_count": len(compiled), "errors": errors, "pass": bool(compiled) and not errors}
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["pass"]:
        Path(args.out).write_text("".join(json.dumps(rule, ensure_ascii=False) + "\n" for rule in compiled), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
