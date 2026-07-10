#!/usr/bin/env python3
"""Compute independent scenario and expert content-validity metrics.

The module only analyzes completed human gold labels. It never imputes missing
reviewer decisions or converts AI output into a gold standard.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TRUE = {"1", "true", "yes", "y"}
NO_HAZARD = {"", "0", "false", "no", "none", "no_hazard", "not_detected"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_div(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def is_hazard(value: str | None) -> bool:
    return str(value or "").strip().lower() not in NO_HAZARD


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUE


def macro_f1(gold: list[str], predicted: list[str]) -> float | None:
    labels = sorted(set(gold) | set(predicted))
    if not labels:
        return None
    scores: list[float] = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        scores.append(safe_div(2 * tp, 2 * tp + fp + fn) or 0.0)
    return sum(scores) / len(scores)


def compute_scenario_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    evaluated: list[dict[str, str]] = []
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        scenario_id = (row.get("scenario_id") or "").strip()
        if not scenario_id:
            errors.append(f"blank_scenario_id:line_{line}")
            continue
        if scenario_id in seen:
            errors.append(f"duplicate_scenario_id:{scenario_id}")
        seen.add(scenario_id)
        required = ("split", "gold_hazard", "gold_action_class", "predicted_hazard", "predicted_action_class")
        missing = [field for field in required if not (row.get(field) or "").strip()]
        if missing:
            errors.append(f"missing_fields:{scenario_id}:{','.join(missing)}")
            continue
        if not (row.get("reviewer_ids") or "").strip():
            errors.append(f"missing_human_reviewers:{scenario_id}")
            continue
        evaluated.append(row)

    tp = fp = tn = fn = 0
    for row in evaluated:
        gold_positive = is_hazard(row["gold_hazard"])
        pred_positive = is_hazard(row["predicted_hazard"])
        tp += int(gold_positive and pred_positive)
        fn += int(gold_positive and not pred_positive)
        fp += int(not gold_positive and pred_positive)
        tn += int(not gold_positive and not pred_positive)

    gold_actions = [row["gold_action_class"].strip() for row in evaluated]
    pred_actions = [row["predicted_action_class"].strip() for row in evaluated]
    critical_fn = sum(
        truthy(row.get("critical_false_negative"))
        or (is_hazard(row["gold_hazard"]) and not is_hazard(row["predicted_hazard"]))
        for row in evaluated
    )
    provenance_complete = sum(truthy(row.get("provenance_complete")) for row in evaluated)
    sensitivity = safe_div(tp, tp + fn)
    specificity = safe_div(tn, tn + fp)
    return {
        "n_input_rows": len(rows),
        "n_scenarios": len(evaluated),
        "split_counts": dict(sorted(Counter(row["split"] for row in evaluated).items())),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "hazard_sensitivity": sensitivity,
        "hazard_sensitivity_ci95": wilson(tp, tp + fn),
        "hazard_specificity": specificity,
        "hazard_specificity_ci95": wilson(tn, tn + fp),
        "action_accuracy": safe_div(sum(g == p for g, p in zip(gold_actions, pred_actions, strict=True)), len(evaluated)),
        "action_macro_f1": macro_f1(gold_actions, pred_actions),
        "critical_false_negative_count": critical_fn,
        "false_reassurance_count": sum(truthy(row.get("false_reassurance")) for row in evaluated),
        "provenance_completeness": safe_div(provenance_complete, len(evaluated)),
        "validation_errors": errors,
        "pass": not errors,
    }


def compute_content_validity(rows: list[dict[str, str]]) -> dict[str, Any]:
    domains = ["relevance_1_4", "accuracy_1_4", "clarity_1_4", "scope_1_4", "message_strength_1_4", "traceability_1_4"]
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    scores: dict[tuple[str, str], list[int]] = defaultdict(list)
    experts: set[str] = set()
    for line, row in enumerate(rows, start=2):
        round_id = (row.get("round") or "").strip()
        expert = (row.get("expert_id") or "").strip()
        rule = (row.get("rule_id") or "").strip()
        if not round_id or not expert or not rule:
            errors.append(f"missing_identity:line_{line}")
            continue
        key = (round_id, expert, rule)
        if key in seen:
            errors.append(f"duplicate_rating:{round_id}:{expert}:{rule}")
        seen.add(key)
        experts.add(expert)
        for domain in domains:
            try:
                score = int(row.get(domain, ""))
            except ValueError:
                errors.append(f"invalid_rating:{rule}:{expert}:{domain}")
                continue
            if score not in {1, 2, 3, 4}:
                errors.append(f"rating_out_of_range:{rule}:{expert}:{domain}")
                continue
            scores[(rule, domain)].append(score)

    item_domain_cvi = {
        f"{rule}:{domain}": safe_div(sum(score >= 3 for score in values), len(values))
        for (rule, domain), values in sorted(scores.items())
    }
    values = [value for value in item_domain_cvi.values() if value is not None]
    rules = sorted({rule for rule, _domain in scores})
    per_rule = {
        rule: safe_div(
            sum(score >= 3 for (item, _domain), ratings in scores.items() if item == rule for score in ratings),
            sum(len(ratings) for (item, _domain), ratings in scores.items() if item == rule),
        )
        for rule in rules
    }
    return {
        "n_rows": len(rows),
        "n_experts": len(experts),
        "n_rules": len(rules),
        "threshold_rating": 3,
        "item_domain_cvi": item_domain_cvi,
        "rule_cvi_average": per_rule,
        "s_cvi_ave": safe_div(sum(values), len(values)),
        "validation_errors": errors,
        "pass": bool(rows) and not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("scenario", "content-validity"):
        sub = subparsers.add_parser(command)
        sub.add_argument("csv_path")
        sub.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = read_csv(Path(args.csv_path))
    result = compute_scenario_metrics(rows) if args.command == "scenario" else compute_content_validity(rows)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
