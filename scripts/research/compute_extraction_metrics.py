#!/usr/bin/env python3
"""Evaluate AI extraction on a human-verified held-out field-level gold set."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TRUE = {"1", "true", "yes", "y"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUE


def normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def safe_div(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def field_match(row: dict[str, str]) -> bool:
    gold = normalize(row.get("gold_value"))
    predicted = normalize(row.get("predicted_value"))
    if truthy(row.get("numeric")) and gold and predicted:
        try:
            tolerance = float(row.get("numeric_tolerance") or "0")
            return abs(float(gold) - float(predicted)) <= tolerance
        except ValueError:
            return False
    return gold == predicted


def compute(rows: list[dict[str, str]], split: str = "held_out") -> dict[str, Any]:
    selected = [row for row in rows if (row.get("split") or "").strip() == split]
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    evaluated: list[dict[str, str]] = []
    for line, row in enumerate(selected, start=2):
        item_id = (row.get("item_id") or "").strip()
        field = (row.get("field_name") or "").strip()
        if not item_id or not field:
            errors.append(f"missing_identity:line_{line}")
            continue
        key = (item_id, field)
        if key in seen:
            errors.append(f"duplicate_field:{item_id}:{field}")
        seen.add(key)
        if not (row.get("verifier_id") or "").strip():
            errors.append(f"missing_human_verifier:{item_id}:{field}")
            continue
        evaluated.append(row)

    required = [row for row in evaluated if truthy(row.get("required"))]
    required_correct = sum(field_match(row) for row in required)
    supported_predictions = [row for row in evaluated if normalize(row.get("predicted_value"))]
    unsupported = sum(
        bool(not normalize(row.get("gold_value")) and normalize(row.get("predicted_value")))
        for row in evaluated
    )
    omissions = sum(
        bool(normalize(row.get("gold_value")) and not normalize(row.get("predicted_value")))
        for row in evaluated
    )
    locator_rows = [row for row in evaluated if normalize(row.get("predicted_value"))]
    locator_correct = sum(
        bool(
            truthy(row.get("locator_match"))
            or (
                normalize(row.get("gold_locator"))
                and normalize(row.get("gold_locator")) == normalize(row.get("predicted_locator"))
            )
        )
        for row in locator_rows
    )
    per_field: dict[str, list[bool]] = defaultdict(list)
    for row in evaluated:
        per_field[row["field_name"]].append(field_match(row))
    return {
        "split": split,
        "n_input_rows": len(rows),
        "n_evaluated_fields": len(evaluated),
        "n_items": len({row["item_id"] for row in evaluated}),
        "required_field_count": len(required),
        "required_field_accuracy": safe_div(required_correct, len(required)),
        "field_accuracy": safe_div(sum(field_match(row) for row in evaluated), len(evaluated)),
        "locator_accuracy": safe_div(locator_correct, len(locator_rows)),
        "unsupported_extraction_rate": safe_div(unsupported, len(supported_predictions)),
        "omission_rate": safe_div(omissions, len(evaluated)),
        "field_counts": dict(sorted(Counter(row["field_name"] for row in evaluated).items())),
        "per_field_accuracy": {
            field: safe_div(sum(matches), len(matches)) for field, matches in sorted(per_field.items())
        },
        "validation_errors": errors,
        "pass": bool(evaluated) and not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--split", default="held_out")
    parser.add_argument("--out", default="extraction_metrics.json")
    args = parser.parse_args()
    result = compute(read_csv(Path(args.csv_path)), args.split)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
