#!/usr/bin/env python3
"""Build a five-node evidence map from verified extraction and GRADE rows."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


NODES = ["K1", "K2", "K3", "K4", "K5"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(extractions: list[dict[str, str]], grade_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    verified = [row for row in extractions if (row.get("verification_status") or "").strip().lower() == "verified"]
    by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in verified:
        node = (row.get("clinical_node_id") or "").strip()
        if node in NODES:
            by_node[node].append(row)
    grade_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in grade_rows:
        node = (row.get("clinical_node_id") or "").strip()
        if node in NODES:
            grade_by_node[node].append(row)

    result: list[dict[str, str]] = []
    for node in NODES:
        rows = by_node[node]
        study_ids = {(row.get("study_family_id") or "").strip() for row in rows if (row.get("study_family_id") or "").strip()}
        report_ids = {(row.get("report_id") or "").strip() for row in rows if (row.get("report_id") or "").strip()}
        outcomes = {(row.get("outcome_id") or "").strip() for row in rows if (row.get("outcome_id") or "").strip()}
        designs = Counter((row.get("study_design") or "not_reported").strip() for row in rows)
        certainty = Counter((row.get("final_certainty") or "not_graded").strip() for row in grade_by_node[node])
        analyzable = [row for row in rows if all((row.get(field) or "").strip() for field in ("effect_measure", "effect_value", "outcome_id"))]
        result.append(
            {
                "clinical_node_id": node,
                "verified_study_count": str(len(study_ids)),
                "verified_report_count": str(len(report_ids)),
                "outcome_count": str(len(outcomes)),
                "design_counts_json": json.dumps(dict(sorted(designs.items())), ensure_ascii=False),
                "grade_counts_json": json.dumps(dict(sorted(certainty.items())), ensure_ascii=False),
                "effect_rows_with_measure": str(len(analyzable)),
                "meta_analysis_candidate": str(len(study_ids) >= 3 and len(analyzable) >= 3).lower(),
                "synthesis_status": "ready_for_compatibility_review" if rows else "no_verified_extraction",
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extraction", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = build(read_csv(Path(args.extraction)), read_csv(Path(args.grade)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
