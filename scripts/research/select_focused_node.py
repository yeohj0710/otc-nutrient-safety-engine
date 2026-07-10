#!/usr/bin/env python3
"""Select the focused synthesis node only after all prespecified scores exist."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


NODES = {"K1", "K2", "K3", "K4", "K5"}
CRITERIA = ["direct_primary_studies", "compatibility", "full_text_availability", "incremental_value", "rule_translatability"]


def select(rows: list[dict[str, str]]) -> dict[str, object]:
    errors: list[str] = []
    scores: dict[str, dict[str, int]] = {}
    for line, row in enumerate(rows, start=2):
        node = (row.get("clinical_node_id") or "").strip()
        if node not in NODES or node in scores:
            errors.append(f"invalid_or_duplicate_node:line_{line}")
            continue
        node_scores: dict[str, int] = {}
        for criterion in CRITERIA:
            try:
                value = int(row.get(criterion, ""))
            except ValueError:
                errors.append(f"missing_score:{node}:{criterion}")
                continue
            if value not in {0, 1, 2}:
                errors.append(f"score_out_of_range:{node}:{criterion}")
            node_scores[criterion] = value
        if not (row.get("reviewer_ids") or "").strip():
            errors.append(f"missing_reviewer:{node}")
        scores[node] = node_scores
    if set(scores) != NODES:
        errors.append("all_five_nodes_must_be_scored")
    totals = {node: sum(values.values()) for node, values in scores.items()}
    highest = max(totals.values()) if totals and not errors else None
    winners = sorted(node for node, total in totals.items() if total == highest) if highest is not None else []
    selected = winners[0] if len(winners) == 1 else None
    if len(winners) > 1:
        errors.append("tie_requires_prespecified_human_adjudication")
    return {"selected_node": selected, "totals": totals, "scores": scores, "validation_errors": errors, "pass": selected is not None and not errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("score_csv")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with Path(args.score_csv).open(encoding="utf-8-sig", newline="") as handle:
        result = select(list(csv.DictReader(handle)))
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
