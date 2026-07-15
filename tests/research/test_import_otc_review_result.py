import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "otc" / "import_review_result.py"
SPEC = importlib.util.spec_from_file_location("import_otc_review_result", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, fields: list[str], records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def fixture(tmp_path: Path) -> Path:
    write(tmp_path / "rules/rules.csv", ["rule_id"], [{"rule_id": "R1"}])
    write(tmp_path / "selection/official_designation_candidates.csv", ["candidate_id"], [{"candidate_id": "C1"}])
    fields = ["scenario_id", "human_reference_label", "human_reviewer_id", "human_reviewed_at", "prediction", "status"]
    write(tmp_path / "validation/independent_scenarios.csv", fields, [{"scenario_id": "S1", "human_reference_label": "", "human_reviewer_id": "", "human_reviewed_at": "", "prediction": "", "status": "awaiting"}])
    write(tmp_path / "validation/normalization_reference.csv", ["ingredient_id", "system_normalized_name", "human_reference_name", "human_reviewer_id", "human_reviewed_at", "status"], [{"ingredient_id": "I1", "system_normalized_name": "아세트아미노펜", "human_reference_name": "", "human_reviewer_id": "", "human_reviewed_at": "", "status": "awaiting"}])
    return tmp_path


def review(role: str, decisions: dict) -> dict:
    return {
        "research_direction": "korean_otc_product_safety",
        "reviewer": {"reviewer_id": "human-1", "reviewer_role": role, "reviewed_at": "2026-07-14T00:00:00Z"},
        "human_decisions": decisions,
    }


def test_expert_review_is_recorded_without_rule_promotion(tmp_path: Path) -> None:
    result = MODULE.import_result(review("pharmacist_expert", {"draft_rules:R1": {"decision": "approve", "comment": "확인"}}), fixture(tmp_path))
    assert result == {"rule_reviews": 1, "candidate_reviews": 0, "scenario_labels": 0, "scenario_uncertain": 0, "rules_promoted": 0, "normalization_labels": 0}
    recorded = list(csv.DictReader((tmp_path / "review/expert_rule_review.csv").open(encoding="utf-8-sig")))
    assert recorded[0]["supports_release"] == "false"
    assert recorded[0]["review_status"] == "human_expert_recorded_not_promoted"


def test_independent_label_is_locked_but_prediction_remains_hidden(tmp_path: Path) -> None:
    MODULE.import_result(review("independent_scenario_reviewer", {"independent_scenarios:S1": {"decision": "1", "comment": ""}}), fixture(tmp_path))
    recorded = list(csv.DictReader((tmp_path / "validation/independent_scenarios.csv").open(encoding="utf-8-sig")))
    assert recorded[0]["human_reference_label"] == "1"
    assert recorded[0]["prediction"] == ""
    assert recorded[0]["status"] == "human_label_locked_awaiting_prediction"


def test_role_mismatch_is_rejected_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reviewer_role_mismatch"):
        MODULE.import_result(review("pharmacist_expert", {"independent_scenarios:S1": {"decision": "1"}}), fixture(tmp_path))


def test_separate_expert_imports_preserve_prior_records(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    write(otc / "rules/rules.csv", ["rule_id"], [{"rule_id": "R1"}, {"rule_id": "R2"}])
    MODULE.import_result(review("pharmacist_expert", {"draft_rules:R1": {"decision": "approve"}}), otc)
    MODULE.import_result(review("pharmacist_expert", {"draft_rules:R2": {"decision": "revise"}}), otc)
    recorded = list(csv.DictReader((otc / "review/expert_rule_review.csv").open(encoding="utf-8-sig")))
    assert [(row["rule_id"], row["decision"]) for row in recorded] == [("R1", "approve"), ("R2", "revise")]


def test_locked_independent_label_cannot_be_changed(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    MODULE.import_result(review("independent_scenario_reviewer", {"independent_scenarios:S1": {"decision": "1"}}), otc)
    with pytest.raises(ValueError, match="scenario_label_already_locked:S1"):
        MODULE.import_result(review("independent_scenario_reviewer", {"independent_scenarios:S1": {"decision": "0"}}), otc)
    recorded = list(csv.DictReader((otc / "validation/independent_scenarios.csv").open(encoding="utf-8-sig")))
    assert recorded[0]["human_reference_label"] == "1"


def test_normalization_reference_is_human_labeled_and_locked(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    result = MODULE.import_result(review("normalization_reviewer", {"normalization_reference:I1": {"decision": "correct"}}), otc)
    assert result["normalization_labels"] == 1
    recorded = list(csv.DictReader((otc / "validation/normalization_reference.csv").open(encoding="utf-8-sig")))
    assert recorded[0]["human_reference_name"] == "아세트아미노펜"
    with pytest.raises(ValueError, match="normalization_reference_already_locked:I1"):
        MODULE.import_result(review("normalization_reviewer", {"normalization_reference:I1": {"decision": "incorrect", "comment": "다른 이름"}}), otc)
