#!/usr/bin/env python3
"""Build the reduced-scope metrics manifest, preserving unavailable metrics explicitly."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research_v2"


def metric(value, denominator, source, status="evaluated", note=""):
    return {"status": status, "value": value, "denominator": denominator, "ci95": None, "source_artifact": source, "note": note}


def main() -> None:
    screening = json.loads((ROOT / "screening" / "computational_screening_summary.json").read_text(encoding="utf-8"))
    seeds = json.loads((ROOT / "search" / "seed_recall_summary.json").read_text(encoding="utf-8"))
    shortlist = json.loads((ROOT / "extraction" / "abstract_evidence_shortlist_summary.json").read_text(encoding="utf-8"))
    result = {
        "schema_version": "1.0.0-feasibility",
        "claim_boundary": "pubmed_single_reviewer_feasibility",
        "metrics": {
            "pubmed_occurrences": metric(screening["identified_occurrences"], None, "screening/computational_screening_summary.json"),
            "unique_records": metric(screening["unique_records"], None, "screening/computational_screening_summary.json"),
            "duplicates_removed": metric(screening["duplicates_removed"], screening["identified_occurrences"], "screening/computational_screening_summary.json"),
            "prespecified_seed_recall": metric(seeds["recall"], seeds["total"], "search/seed_recall_summary.json", note="descriptive query check; not AI held-out screening recall"),
            "abstract_candidates": metric(shortlist["count"], screening["unique_records"], "extraction/abstract_evidence_shortlist_summary.json"),
            "abstract_verified_seeds": metric(seeds["retrieved"], seeds["total"], "extraction/seed_abstract_evidence.csv"),
            "released_rules": metric(0, 5, "rules/compile_report.json", note="five draft_ai rules; none released"),
            "ai_screening_heldout_recall": metric(None, None, None, "not_evaluated", "no independent human gold set"),
            "scenario_hazard_sensitivity": metric(None, None, None, "not_evaluated", "no independent expert-rated scenarios"),
            "critical_false_negatives": metric(None, None, None, "not_evaluated", "no independent sentinel set"),
            "expert_content_validity": metric(None, None, None, "not_evaluated", "no expert panel"),
        },
    }
    out = ROOT / "thesis" / "metrics_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
