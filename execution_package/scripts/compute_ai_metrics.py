#!/usr/bin/env python3
"""Compute screening metrics with explicit handling of 'uncertain' predictions.

For screening safety, predictions configured as positive are treated as requiring
human review. The script never treats an unknown label as a negative by default.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    denominator = 1 + (z * z / n)
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--gold", default="gold_label")
    parser.add_argument("--pred", default="prediction")
    parser.add_argument("--gold-positive", default="include")
    parser.add_argument(
        "--prediction-positive-values",
        default="include,uncertain",
        help="Comma-separated predictions that trigger human review",
    )
    parser.add_argument("--split-column", default=None)
    parser.add_argument("--split-value", default=None)
    parser.add_argument("--out", default="ai_metrics.json")
    args = parser.parse_args()

    with Path(args.csv_path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if args.split_column and args.split_value is not None:
        rows = [row for row in rows if row.get(args.split_column) == args.split_value]

    positive_predictions = {
        value.strip() for value in args.prediction_positive_values.split(",") if value.strip()
    }
    if not positive_predictions:
        raise SystemExit("At least one prediction-positive value is required")

    tp = fp = tn = fn = 0
    excluded_unknown = 0
    gold_positive_count = 0
    for line_number, row in enumerate(rows, start=2):
        if args.gold not in row or args.pred not in row:
            raise SystemExit(f"Missing required columns: {args.gold}, {args.pred}")
        gold_value = (row.get(args.gold) or "").strip()
        pred_value = (row.get(args.pred) or "").strip()
        if not gold_value or not pred_value:
            excluded_unknown += 1
            continue
        gold_positive = gold_value == args.gold_positive
        pred_positive = pred_value in positive_predictions
        gold_positive_count += int(gold_positive)
        tp += int(gold_positive and pred_positive)
        fn += int(gold_positive and not pred_positive)
        fp += int((not gold_positive) and pred_positive)
        tn += int((not gold_positive) and (not pred_positive))

    n = tp + fp + tn + fn
    sensitivity = safe_div(tp, tp + fn)
    specificity = safe_div(tn, tn + fp)
    precision = safe_div(tp, tp + fp)
    npv = safe_div(tn, tn + fn)
    f1 = safe_div(2 * tp, 2 * tp + fp + fn)
    accuracy = safe_div(tp + tn, n)
    balanced_accuracy = (
        (sensitivity + specificity) / 2
        if sensitivity is not None and specificity is not None
        else None
    )
    review_fraction = safe_div(tp + fp, n)
    workload_saved_fraction = 1 - review_fraction if review_fraction is not None else None

    result = {
        "n_input_rows": len(rows),
        "n_evaluated": n,
        "n_rows_with_missing_label": excluded_unknown,
        "gold_positive_count": gold_positive_count,
        "prediction_positive_values": sorted(positive_predictions),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "sensitivity": sensitivity,
        "sensitivity_ci95": wilson(tp, tp + fn),
        "specificity": specificity,
        "specificity_ci95": wilson(tn, tn + fp),
        "precision": precision,
        "precision_ci95": wilson(tp, tp + fp),
        "npv": npv,
        "npv_ci95": wilson(tn, tn + fn),
        "f1": f1,
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "human_review_fraction": review_fraction,
        "workload_saved_fraction_at_observed_recall": workload_saved_fraction,
        "interpretation_note": (
            "Predictions listed as positive are queued for human review; this is not an auto-exclusion policy."
        ),
    }
    Path(args.out).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
