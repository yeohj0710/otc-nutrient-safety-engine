#!/usr/bin/env python3
"""Create a deterministic abstract-evidence shortlist without calling it full-text review."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


NODES = ["K1", "K2", "K3", "K4", "K5"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if item.strip()]


def candidate_quote(row: dict[str, str]) -> str:
    outcomes = [value for value in row.get("matched_outcome_terms", "").split(";") if value]
    for sentence in sentences(row.get("abstract", "")):
        lowered = sentence.casefold()
        if any(term in lowered for term in outcomes):
            return sentence[:1000]
    return ""


def build(screening: list[dict[str, str]], seed_rows: list[dict[str, str]], per_node: int) -> list[dict[str, str]]:
    by_pmid = {row["pmid"]: row for row in screening}
    selected: dict[tuple[str, str], dict[str, str]] = {}
    seed_map = defaultdict(list)
    for seed in seed_rows:
        seed_map[seed["node_id"]].append(seed["pmid"])
    for node in NODES:
        for pmid in seed_map[node]:
            if pmid in by_pmid:
                selected[(node, pmid)] = {"basis": "prespecified_seed", **by_pmid[pmid]}
        candidates = [
            row for row in screening
            if node in row["clinical_node_candidates"].split(";")
            and row["proposal"] == "priority_include_candidate"
            and row.get("abstract", "").strip()
        ]
        candidates.sort(key=lambda row: (-int(row["score"]), -int(row["year"] or 0), row["pmid"]))
        for row in candidates[:per_node]:
            selected.setdefault((node, row["pmid"]), {"basis": "top_score_recent", **row})
    result = []
    for (node, pmid), row in sorted(selected.items()):
        result.append(
            {
                "evidence_candidate_id": f"EV-{node}-{pmid}",
                "clinical_node_id": node,
                "pmid": pmid,
                "selection_basis": row["basis"],
                "score": row["score"],
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "design_signals": row.get("matched_design_terms", ""),
                "outcome_signals": row.get("matched_outcome_terms", ""),
                "candidate_abstract_quote": candidate_quote(row),
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source_locator": "PubMed abstract",
                "verification_status": "agent_review_required",
                "full_text_status": "not_assessed",
                "limitations": "abstract-only candidate; not a verified effect estimate",
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", default="research_v2")
    parser.add_argument("--per-node", type=int, default=20)
    args = parser.parse_args()
    root = Path(args.research_root)
    rows = build(
        read_csv(root / "screening" / "computational_screening.csv"),
        read_csv(root / "search" / "seed_candidates.csv"),
        args.per_node,
    )
    out = root / "extraction" / "abstract_evidence_shortlist.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "count": len(rows),
        "node_counts": dict(sorted(Counter(row["clinical_node_id"] for row in rows).items())),
        "seed_count": sum(row["selection_basis"] == "prespecified_seed" for row in rows),
        "verification_status": "agent_review_required",
    }
    (root / "extraction" / "abstract_evidence_shortlist_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
