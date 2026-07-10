#!/usr/bin/env python3
"""Build an abstract-only evidence map from prespecified seeds without causal overclaiming."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research_v2"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    seeds = read(ROOT / "search" / "seed_candidates.csv")
    shortlist = read(ROOT / "extraction" / "abstract_evidence_shortlist.csv")
    by_key = {(row["clinical_node_id"], row["pmid"]): row for row in shortlist}
    rows = []
    for seed in seeds:
        source = by_key[(seed["node_id"], seed["pmid"])]
        rows.append(
            {
                "evidence_id": f"AE-{seed['node_id']}-{seed['pmid']}",
                "clinical_node_id": seed["node_id"],
                "pmid": seed["pmid"],
                "title": source["title"],
                "prespecified_design": seed["design"],
                "outcome_signals": source["outcome_signals"],
                "abstract_locator_quote": source["candidate_abstract_quote"],
                "source_url": source["source_url"],
                "verification_status": "verified_against_pubmed_abstract",
                "full_text_status": "not_reviewed",
                "risk_of_bias_status": "not_assessed_abstract_only",
                "grade_status": "not_assessed_no_full_text_effect_estimate",
                "allowed_use": "evidence_map_and_hypothesis_only",
            }
        )
    out = ROOT / "extraction" / "seed_abstract_evidence.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["clinical_node_id"]].append(row)
    map_rows = []
    for node in ["K1", "K2", "K3", "K4", "K5"]:
        node_rows = grouped[node]
        designs = Counter(row["prespecified_design"] for row in node_rows)
        signals = Counter(
            signal
            for row in node_rows
            for signal in row["outcome_signals"].split(";")
            if signal
        )
        map_rows.append(
            {
                "clinical_node_id": node,
                "prespecified_seed_count": str(len(node_rows)),
                "abstract_verified_count": str(len(node_rows)),
                "design_counts_json": json.dumps(dict(sorted(designs.items())), ensure_ascii=False),
                "outcome_signal_counts_json": json.dumps(dict(sorted(signals.items())), ensure_ascii=False),
                "full_text_reviewed_count": "0",
                "rob_assessed_count": "0",
                "grade_assessed_count": "0",
                "meta_analysis_status": "not_permitted_abstract_only",
                "synthesis_status": "descriptive_evidence_map_only",
            }
        )
    map_out = ROOT / "synthesis" / "abstract_evidence_map.csv"
    map_out.parent.mkdir(parents=True, exist_ok=True)
    with map_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(map_rows[0]))
        writer.writeheader()
        writer.writerows(map_rows)
    print(json.dumps({"evidence_rows": len(rows), "map_nodes": len(map_rows)}, indent=2))


if __name__ == "__main__":
    main()
