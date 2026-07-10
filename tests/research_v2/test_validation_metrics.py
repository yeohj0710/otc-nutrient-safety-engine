from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "validation_metrics.py"
SPEC = importlib.util.spec_from_file_location("validation_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_scenario_metrics_report_sensitivity_ci_and_critical_fn() -> None:
    rows = [
        {"scenario_id": "S1", "split": "held_out", "gold_hazard": "hazard", "gold_action_class": "avoid", "predicted_hazard": "hazard", "predicted_action_class": "avoid", "reviewer_ids": "R1;R2", "critical_false_negative": "false", "false_reassurance": "false", "provenance_complete": "true"},
        {"scenario_id": "S2", "split": "held_out", "gold_hazard": "hazard", "gold_action_class": "refer", "predicted_hazard": "no_hazard", "predicted_action_class": "monitor", "reviewer_ids": "R1;R2", "critical_false_negative": "true", "false_reassurance": "true", "provenance_complete": "false"},
        {"scenario_id": "S3", "split": "held_out", "gold_hazard": "no_hazard", "gold_action_class": "monitor", "predicted_hazard": "no_hazard", "predicted_action_class": "monitor", "reviewer_ids": "R1;R2", "critical_false_negative": "false", "false_reassurance": "false", "provenance_complete": "true"},
    ]
    result = MODULE.compute_scenario_metrics(rows)
    assert result["pass"] is True
    assert result["hazard_sensitivity"] == 0.5
    assert result["hazard_sensitivity_ci95"] is not None
    assert result["critical_false_negative_count"] == 1
    assert result["provenance_completeness"] == 2 / 3


def test_scenario_metrics_refuse_missing_human_gold_provenance() -> None:
    rows = [{"scenario_id": "S1", "split": "held_out", "gold_hazard": "hazard", "gold_action_class": "avoid", "predicted_hazard": "hazard", "predicted_action_class": "avoid", "reviewer_ids": ""}]
    result = MODULE.compute_scenario_metrics(rows)
    assert result["pass"] is False
    assert result["n_scenarios"] == 0
    assert "missing_human_reviewers:S1" in result["validation_errors"]


def test_content_validity_computes_item_and_scale_cvi() -> None:
    rows = []
    for expert, score in (("E1", "4"), ("E2", "3"), ("E3", "2")):
        rows.append({"round": "1", "expert_id": expert, "rule_id": "R1", **{domain: score for domain in ("relevance_1_4", "accuracy_1_4", "clarity_1_4", "scope_1_4", "message_strength_1_4", "traceability_1_4")}})
    result = MODULE.compute_content_validity(rows)
    assert result["pass"] is True
    assert result["n_experts"] == 3
    assert result["item_domain_cvi"]["R1:accuracy_1_4"] == 2 / 3
    assert result["s_cvi_ave"] == 2 / 3
