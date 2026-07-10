from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "validate_human_adjudication.py"
SPEC = importlib.util.spec_from_file_location("validate_human_adjudication", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_screening_requires_two_reviewers_and_adjudicator() -> None:
    rows = [
        {"record_id": "R1", "reviewer_id": "A", "decision": "include", "adjudicated_decision": "include", "adjudicator_id": "C"},
        {"record_id": "R1", "reviewer_id": "B", "decision": "exclude", "adjudicated_decision": "include", "adjudicator_id": "C"},
    ]
    assert MODULE.validate_screening(rows, "record_id") == []
    errors = MODULE.validate_screening(rows[:1], "record_id")
    assert "fewer_than_two_reviewers:R1" in errors


def test_extraction_requires_distinct_verifier_and_locator() -> None:
    valid = {"extraction_id": "E1", "extractor_id": "A", "verifier_id": "B", "verification_status": "verified", "report_id": "P1", "clinical_node_id": "K1", "outcome_id": "O1", "locator": "p. 3 Table 1", "supporting_quote": "verified paraphrase"}
    assert MODULE.validate_extraction([valid]) == []
    invalid = {**valid, "verifier_id": "A", "locator": ""}
    errors = MODULE.validate_extraction([invalid])
    assert "invalid_independent_verification:E1" in errors
    assert "missing_locator:E1" in errors


def test_grade_requires_two_human_reviewers() -> None:
    row = {"clinical_node_id": "K1", "outcome_id": "O1", "final_certainty": "low", "rationale": "downgraded for imprecision", "reviewer_ids": "A;B"}
    assert MODULE.validate_grade([row]) == []
    row["reviewer_ids"] = "A"
    assert "fewer_than_two_grade_reviewers:K1:O1" in MODULE.validate_grade([row])
