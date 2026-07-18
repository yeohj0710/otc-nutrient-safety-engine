from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "scenario_id", "scenario_type", "input_json", "gold_hazards_json", "critical",
    "adjudicator_id", "adjudicated_at", "locked_before_test", "notes",
}
PREDICTION_REQUIRED_COLUMNS = {"scenario_id", "predicted_hazards_json"}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def safe_div(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def load_rows(path: Path, required_columns: set[str] = REQUIRED_COLUMNS) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = required_columns - fields
        if missing:
            raise ValueError(f"missing columns: {sorted(missing)}")
        return list(reader)


def validate_locked_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    sid = row.get("scenario_id") or "<blank>"
    if not row.get("input_json"):
        errors.append(f"{sid}: input_json missing")
    if not row.get("gold_hazards_json"):
        errors.append(f"{sid}: gold_hazards_json missing")
    if row.get("locked_before_test", "").lower() != "true":
        errors.append(f"{sid}: locked_before_test must be true")
    if not row.get("adjudicator_id") or not row.get("adjudicated_at"):
        errors.append(f"{sid}: independent adjudication metadata missing")
    for field in ("input_json", "gold_hazards_json"):
        if row.get(field):
            try:
                json.loads(row[field])
            except json.JSONDecodeError:
                errors.append(f"{sid}: {field} invalid JSON")
    return errors


def confusion(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "critical_false_negative": 0}
    for row in rows:
        gold = set(row["gold_hazards"])
        predicted = set(row["predicted_hazards"])
        counts["tp"] += len(gold & predicted)
        counts["fn"] += len(gold - predicted)
        counts["fp"] += len(predicted - gold)
        if not gold and not predicted:
            counts["tn"] += 1
        if row["critical"] and gold - predicted:
            counts["critical_false_negative"] += 1
    return counts


def calculate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    c = confusion(rows)
    sensitivity_n, sensitivity_d = c["tp"], c["tp"] + c["fn"]
    specificity_n, specificity_d = c["tn"], c["tn"] + c["fp"]
    ppv_n, ppv_d = c["tp"], c["tp"] + c["fp"]
    npv_n, npv_d = c["tn"], c["tn"] + c["fn"]
    exact_n = sum(set(row["gold_hazards"]) == set(row["predicted_hazards"]) for row in rows)
    accuracy_n, accuracy_d = exact_n, len(rows)
    return {
        "confusion_matrix": c,
        "sensitivity": {"value": safe_div(sensitivity_n, sensitivity_d), "ci95_wilson": wilson(sensitivity_n, sensitivity_d)},
        "specificity": {"value": safe_div(specificity_n, specificity_d), "ci95_wilson": wilson(specificity_n, specificity_d)},
        "positive_predictive_value": {"value": safe_div(ppv_n, ppv_d), "ci95_wilson": wilson(ppv_n, ppv_d)},
        "negative_predictive_value": {"value": safe_div(npv_n, npv_d), "ci95_wilson": wilson(npv_n, npv_d)},
        "accuracy": {"value": safe_div(accuracy_n, accuracy_d), "ci95_wilson": wilson(accuracy_n, accuracy_d)},
        "exact_hazard_set_accuracy": {"value": safe_div(exact_n, len(rows)), "ci95_wilson": wilson(exact_n, len(rows))},
    }


def run(scenarios: Path, predictions: Path | None) -> dict[str, Any]:
    rows = load_rows(scenarios)
    if not rows:
        return {
            "schema_version": "1.0.0", "status": "not_evaluated", "scenario_count": 0,
            "reason": "No independently adjudicated and pre-locked scenarios are available.",
            "performance_claim_allowed": False, "metrics": None,
        }
    errors = [error for row in rows for error in validate_locked_row(row)]
    if errors:
        return {"schema_version": "1.0.0", "status": "invalid", "errors": errors, "performance_claim_allowed": False}
    if predictions is None or not predictions.exists():
        return {
            "schema_version": "1.0.0", "status": "awaiting_predictions", "scenario_count": len(rows),
            "reason": "Gold labels are locked; prediction file is absent.", "performance_claim_allowed": False,
        }
    prediction_rows = load_rows(predictions, PREDICTION_REQUIRED_COLUMNS)
    predicted: dict[str, list[str]] = {}
    for row in prediction_rows:
        sid = row["scenario_id"]
        if sid in predicted:
            errors.append(f"{sid}: duplicate prediction")
            continue
        try:
            value = json.loads(row["predicted_hazards_json"])
        except json.JSONDecodeError:
            errors.append(f"{sid}: predicted_hazards_json invalid JSON")
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{sid}: predicted_hazards_json must be a JSON string array")
            continue
        predicted[sid] = value
    evaluated = []
    for row in rows:
        sid = row["scenario_id"]
        if sid not in predicted:
            errors.append(f"{sid}: prediction missing")
            continue
        evaluated.append({
            "scenario_id": sid,
            "gold_hazards": json.loads(row["gold_hazards_json"]),
            "predicted_hazards": predicted[sid],
            "critical": row["critical"].lower() == "true",
        })
    if errors:
        return {"schema_version": "1.0.0", "status": "invalid", "errors": errors, "performance_claim_allowed": False}
    return {
        "schema_version": "1.0.0", "status": "evaluated", "scenario_count": len(evaluated),
        "metrics": calculate(evaluated), "performance_claim_allowed": True, "rows": evaluated,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.scenarios, args.predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] in {"not_evaluated", "awaiting_predictions", "evaluated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
