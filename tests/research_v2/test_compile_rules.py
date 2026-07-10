from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "compile_rules.py"
SPEC = importlib.util.spec_from_file_location("compile_rules", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_row() -> dict[str, str]:
    return {
        "rule_id": "RULE-K1-001", "clinical_node_id": "K1", "ingredient_id": "vitamin_d", "population_criteria_json": "{}", "medication_criteria_json": "{}", "dose_json": "{}", "duration_json": "", "outcome_id": "hypercalcemia", "action_class": "monitor_or_discuss", "severity": "moderate", "message_short": "검토 필요", "message_explanation": "용량과 위험요인을 확인한다.", "questions_to_ask_json": '["용량은 얼마인가요?"]', "uncertainty_statement": "근거 확실성은 낮다.", "certainty_grade": "low", "jurisdiction_json": '["KR"]', "evidence_ids": "E1", "source_quote_ids": "Q1", "reviewer_ids": "A;B", "status": "released", "valid_from": "2026-07-10", "review_due": "2027-07-10"
    }


def test_compile_released_rule_with_two_reviewers_and_known_quote() -> None:
    rules, errors = MODULE.compile_rows([valid_row()], {"Q1"})
    assert errors == []
    assert rules[0]["clinical_node_id"] == "K1"
    assert rules[0]["questions_to_ask"] == ["용량은 얼마인가요?"]
    schema = json.loads(
        (REPO_ROOT / "execution_package" / "schemas" / "rule.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(Draft202012Validator(schema).iter_errors(rules[0])) == []


def test_compile_ignores_draft_and_fails_if_no_released_rules() -> None:
    row = valid_row()
    row["status"] = "draft_human"
    rules, errors = MODULE.compile_rows([row], {"Q1"})
    assert rules == []
    assert errors == ["no_released_rules"]


def test_compile_rejects_unknown_quote_and_single_reviewer() -> None:
    row = valid_row()
    row["reviewer_ids"] = "A"
    _rules, errors = MODULE.compile_rows([row], set())
    assert "missing_or_unknown_source_quote:RULE-K1-001" in errors
    assert "fewer_than_two_rule_reviewers:RULE-K1-001" in errors
