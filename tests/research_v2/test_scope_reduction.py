from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "research_v2" / "protocol"


def test_scope_reduction_is_machine_readable_and_fail_closed() -> None:
    boundary = json.loads((ROOT / "claim_boundary.json").read_text(encoding="utf-8"))
    assert boundary["study_design"] == "pubmed_single_reviewer_feasibility"
    assert boundary["databases_in_scope"] == ["PubMed"]
    assert boundary["clinical_nodes"] == ["K1", "K2", "K3", "K4", "K5"]
    assert "complete_multidatabase_systematic_review" in boundary["prohibited_claims"]
    assert "clinical_sensitivity_or_specificity" in boundary["prohibited_claims"]
    assert "independent_scenario_clinical_sensitivity" in boundary["not_evaluated_metrics"]
    assert "research_prototype_not_for_clinical_use" in boundary["required_disclosures"]


def test_amendment_does_not_claim_human_approval() -> None:
    text = (ROOT / "amendment_001_pubmed_feasibility.md").read_text(encoding="utf-8")
    assert "사람 승인을 받은 것으로 기록하지 않는다" in text
    assert "체계적 문헌고찰 또는 임상적으로 검증된" in text
