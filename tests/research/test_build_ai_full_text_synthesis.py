from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.research.build_ai_full_text_synthesis import run


FIELDS = [
    "evidence_candidate_id", "parent_candidate_id", "pmid", "pmcid", "clinical_node_id", "ingredient", "title",
    "source_path", "source_sha256", "section_title", "locator", "evidence_text", "signal_types", "dose_mentions",
    "population_mentions", "duration_mentions", "design_signals", "ai_relevance_score", "reviewer_id", "review_status",
    "human_verification_required",
]


def make_root(tmp_path: Path, candidate_status: str = "ai_extracted_not_human_verified") -> Path:
    root = tmp_path / "research_v3"
    (root / "extraction").mkdir(parents=True)
    (root / "rules").mkdir()
    with (root / "extraction" / "ai_full_text_evidence_candidates.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader()
        writer.writerow({"evidence_candidate_id": "AI-1", "pmid": "1", "pmcid": "PMC1", "clinical_node_id": "K2",
                         "ingredient": "vitamin B6", "source_sha256": "abc", "locator": "PMC1, Safety, P1",
                         "signal_types": "neuropathy;safety", "dose_mentions": "50 mg", "population_mentions": "adult",
                         "duration_mentions": "12 weeks", "ai_relevance_score": "9", "review_status": candidate_status})
    with (root / "rules" / "rules.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rule_id", "ingredient_id", "review_status"]); writer.writeheader()
        writer.writerow({"rule_id": "R-B6", "ingredient_id": "vitamin_b6", "review_status": "draft"})
    return root


def test_builds_non_threshold_ai_links(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    report = run(root)
    links = list(csv.DictReader((root / "extraction" / "ai_draft_rule_evidence_links.csv").open(encoding="utf-8-sig")))
    assert report["candidate_rule_links"] == 1
    assert report["released_rules_created"] == 0
    assert links[0]["supports_threshold_claim"] == "false"
    assert links[0]["link_status"] == "ai_candidate_link_not_expert_verified"


def test_rejects_non_ai_candidate_status(tmp_path: Path) -> None:
    root = make_root(tmp_path, "human_verified")
    with pytest.raises(ValueError, match="unexpected candidate status"):
        run(root)
