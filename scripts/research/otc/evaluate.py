from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Iterable


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate_rows(rows: Iterable[dict[str, str]]) -> dict:
    rows = list(rows)
    labeled = [row for row in rows if row.get("human_reference_label") in {"0", "1"} and row.get("prediction") in {"0", "1"}]
    if not labeled:
        return {
            "status": "not_evaluated_missing_independent_human_labels",
            "scenarios_total": len(rows),
            "scenarios_evaluated": 0,
            "performance_claim_allowed": False,
        }
    tp = sum(row["human_reference_label"] == "1" and row["prediction"] == "1" for row in labeled)
    tn = sum(row["human_reference_label"] == "0" and row["prediction"] == "0" for row in labeled)
    fp = sum(row["human_reference_label"] == "0" and row["prediction"] == "1" for row in labeled)
    fn = sum(row["human_reference_label"] == "1" and row["prediction"] == "0" for row in labeled)
    critical_fn = sum(row["human_reference_label"] == "1" and row["prediction"] == "0" and row.get("critical", "").lower() == "true" for row in labeled)
    blinded = all(row.get("independent_blinding", "true").lower() == "true" for row in labeled)
    sensitivity_den = tp + fn
    specificity_den = tn + fp
    accuracy_num = tp + tn
    return {
        "status": "evaluated_independent_human_labels" if blinded else "evaluated_codex_prefilled_external_human_confirmation",
        "review_method": "independent_blind_human_adjudication" if blinded else "codex_prefilled_external_human_confirmation",
        "independent_blinding": blinded,
        "scenarios_total": len(rows),
        "scenarios_evaluated": len(labeled),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "sensitivity": {"value": ratio(tp, sensitivity_den), "ci95": wilson(tp, sensitivity_den)},
        "specificity": {"value": ratio(tn, specificity_den), "ci95": wilson(tn, specificity_den)},
        "positive_predictive_value": {"value": ratio(tp, tp + fp), "ci95": wilson(tp, tp + fp)},
        "negative_predictive_value": {"value": ratio(tn, tn + fn), "ci95": wilson(tn, tn + fn)},
        "accuracy": {"value": ratio(accuracy_num, len(labeled)), "ci95": wilson(accuracy_num, len(labeled))},
        "critical_false_negatives": critical_fn,
        "performance_claim_allowed": len(labeled) == len(rows) and blinded,
    }


def evaluate_file(path: Path, output: Path | None = None) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        result = evaluate_rows(csv.DictReader(handle))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate independently labeled OTC safety scenarios")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_file(args.input, args.output), ensure_ascii=False))
