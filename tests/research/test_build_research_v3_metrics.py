from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "build_research_v3_metrics.py"
SPEC = importlib.util.spec_from_file_location("build_research_v3_metrics", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_manifest_is_derived_and_does_not_invent_evaluation() -> None:
    root = Path(__file__).parents[2] / "research_v3"
    report = MODULE.build(root)
    metrics = report["metrics"]
    assert metrics["search_occurrences"]["value"] == 16194
    assert metrics["unique_pmids"]["value"] == 15890
    assert metrics["dedup_candidates"]["value"] == 304
    assert metrics["search_strategy_review_packet"]["value"] == 35
    assert metrics["search_strategy_review_packet"]["strategies"] == 5
    assert metrics["search_strategy_review_packet"]["human_decisions_prefilled"] == 35
    assert metrics["completed_search_strategy_reviews"]["value"] == 35
    assert metrics["advisor_approvals"]["value"] == 4
    assert metrics["advisor_approvals"]["status"] == "completed"
    assert "research_direction_advisor_confirmation" not in report["release_blockers"]
    assert metrics["human_full_text_decisions"]["value"] == 63
    assert metrics["evidence_extractions"]["value"] == 326
    assert metrics["reported_quantitative_statistics"]["value"] == 124
    assert metrics["reported_quantitative_statistics"]["evidence_rows"] == 57
    assert metrics["reported_quantitative_statistics"]["relative_effect_measures"] == 20
    assert metrics["reported_quantitative_statistics"]["synthesis_eligible"] == 0
    assert metrics["codex_ai_full_text_evidence_candidates"]["human_verified_candidates"] == 326
    assert metrics["title_abstract_review_queue"]["value"] == 15890
    assert metrics["title_abstract_review_queue"]["status"] == "partially_reviewed"
    assert metrics["title_abstract_review_queue"]["human_decisions_completed"] == 118
    assert metrics["title_abstract_review_queue"]["human_decisions_prefilled"] == 0
    assert metrics["priority_review_packet"]["status"] == "completed"
    assert metrics["priority_review_packet"]["human_decisions_completed"] == 118
    assert metrics["rules_released"]["value"] == 6
    assert metrics["rules_total"]["value"] == 6
    assert metrics["sensitivity"]["value"] == 1.0
    assert metrics["critical_false_negatives"]["value"] == 0
    assert metrics["development_scenarios"]["value"] == 12
    assert metrics["development_scenarios_passed"]["value"] == 12
    assert metrics["development_scenarios_passed"]["performance_claim_allowed"] is False
    assert metrics["research_tests_passed"]["status"] == "evaluated"
    assert metrics["app_tests_passed"]["status"] == "evaluated"
    assert metrics["lint_typecheck_build_passed"]["status"] == "evaluated"
