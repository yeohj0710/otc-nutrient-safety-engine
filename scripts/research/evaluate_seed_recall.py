#!/usr/bin/env python3
"""Evaluate prespecified PMID seed recall against active normalized exports."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research_v2"


def main() -> None:
    with (ROOT / "search" / "seed_candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
        seeds = list(csv.DictReader(handle))
    retrieved: dict[str, set[str]] = {}
    for node in sorted({row["node_id"] for row in seeds}):
        with (ROOT / "search" / "normalized" / f"{node}_pubmed_records.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            retrieved[node] = {row["pmid"] for row in csv.DictReader(handle)}
    rows = []
    for seed in seeds:
        hit = seed["pmid"] in retrieved[seed["node_id"]]
        rows.append(
            {
                "seed_id": seed["seed_id"],
                "node_id": seed["node_id"],
                "pmid": seed["pmid"],
                "retrieved": str(hit).lower(),
                "search_version": "0.2" if seed["node_id"] != "K1" else "0.1",
                "assessment": "pass" if hit else "search_revision_required",
            }
        )
    path = ROOT / "search" / "seed_recall.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["node_id"] for row in rows if row["retrieved"] == "true")
    summary = {
        "retrieved": sum(row["retrieved"] == "true" for row in rows),
        "total": len(rows),
        "recall": sum(row["retrieved"] == "true" for row in rows) / len(rows),
        "node_retrieved": dict(sorted(counts.items())),
        "gate": "pass" if all(row["retrieved"] == "true" for row in rows) else "fail",
    }
    (ROOT / "search" / "seed_recall_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
