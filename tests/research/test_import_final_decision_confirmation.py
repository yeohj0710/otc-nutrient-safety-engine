import json
from pathlib import Path

import pytest

from scripts.research.otc.import_final_decision_confirmation import validate


ROOT = Path(__file__).resolve().parents[2]
OTC = ROOT / "research_v3" / "otc"


def presented_confirmation() -> dict:
    rules = {}
    for line in (OTC / "rules" / "rules.csv").read_text(encoding="utf-8-sig").splitlines()[1:]:
        rule_id = line.split(",", 1)[0]
        rules[rule_id] = {"decision": "revise" if rule_id == "OTC-RULE-015" else "approve"}
    scenarios = {}
    for line in (OTC / "validation" / "independent_scenarios.csv").read_text(encoding="utf-8-sig").splitlines()[1:]:
        scenario_id, family = line.split(",", 2)[:2]
        scenarios[scenario_id] = {"decision": "0" if family in {"normal_use", "unsupported_product"} else "1"}
    return {
        "research_direction": "korean_otc_product_safety",
        "reviewer_id": "FINAL-DECISION-001",
        "review_mode": "codex_recommendations_confirmed_by_human_not_blinded_independent_review",
        "approved_at": "2026-07-14T00:00:00Z",
        "rule_decisions": rules,
        "scenario_decisions": scenarios,
    }


def test_final_decision_confirmation_validates_without_upgrading_review_status():
    result = validate(presented_confirmation())
    assert result["confirmed_rule_recommendations"] == 16
    assert result["confirmed_scenario_recommendations"] == 13
    assert result["counts_as_pharmacist_expert_review"] is False
    assert result["counts_as_blinded_independent_scenario_labeling"] is False


def test_final_decision_confirmation_rejects_changed_presented_decision():
    data = presented_confirmation()
    data["scenario_decisions"]["IND-OTC-001"]["decision"] = "0"
    with pytest.raises(ValueError, match="scenario_decisions_do_not_match"):
        validate(data)
