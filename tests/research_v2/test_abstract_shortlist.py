from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "build_abstract_evidence_shortlist.py"
SPEC = importlib.util.spec_from_file_location("build_abstract_evidence_shortlist", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_shortlist_keeps_seed_and_top_scored_candidate() -> None:
    screening = [
        {"pmid": "1", "clinical_node_candidates": "K1", "proposal": "retain_uncertain", "abstract": "Hypercalcemia was reported.", "matched_outcome_terms": "hypercalcemia", "matched_design_terms": "", "score": "1", "year": "2020", "title": "Seed"},
        {"pmid": "2", "clinical_node_candidates": "K1", "proposal": "priority_include_candidate", "abstract": "Adult trial. Hypercalcemia was reported.", "matched_outcome_terms": "hypercalcemia", "matched_design_terms": "trial", "score": "8", "year": "2024", "title": "Top"},
    ]
    seeds = [{"node_id": "K1", "pmid": "1"}]
    rows = MODULE.build(screening, seeds, 1)
    assert {(row["pmid"], row["selection_basis"]) for row in rows} == {("1", "prespecified_seed"), ("2", "top_score_recent")}
    assert rows[0]["verification_status"] == "agent_review_required"


def test_candidate_quote_requires_outcome_sentence() -> None:
    row = {"abstract": "Background sentence. Hypercalcemia occurred in two participants.", "matched_outcome_terms": "hypercalcemia"}
    assert MODULE.candidate_quote(row) == "Hypercalcemia occurred in two participants."
