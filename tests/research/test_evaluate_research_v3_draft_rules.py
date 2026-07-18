from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "evaluate_research_v3_draft_rules.py"
SPEC = importlib.util.spec_from_file_location("evaluate_research_v3_draft_rules", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_all_development_scenarios_pass_without_performance_claim() -> None:
    root = Path(__file__).parents[2] / "research_v3"
    report = MODULE.run(root)
    assert report["scenario_count"] == 12
    assert report["passed"] == 12
    assert report["failed"] == 0
    assert report["performance_claim_allowed"] is False


def test_calcium_profile_is_age_and_sex_specific() -> None:
    root = Path(__file__).parents[2] / "research_v3"
    rules = MODULE.csv_rows(root / "rules" / "rules.csv")
    assert MODULE.evaluate(rules, {
        "age": 25,
        "sex": "male",
        "ingredient": "calcium",
        "daily_total_mg": 2800,
    }) == []
    assert MODULE.evaluate(rules, {
        "age": 35,
        "sex": "female",
        "ingredient": "calcium",
        "daily_total_mg": 2800,
    }) == ["V3-DRAFT-KDRI-CA-UL"]
