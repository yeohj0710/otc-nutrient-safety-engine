from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "compute_extraction_metrics.py"
SPEC = importlib.util.spec_from_file_location("compute_extraction_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extraction_metrics_use_held_out_and_numeric_tolerance() -> None:
    rows = [
        {"item_id": "I1", "split": "held_out", "field_name": "dose", "required": "true", "numeric": "true", "numeric_tolerance": "0.1", "gold_value": "10", "predicted_value": "10.05", "gold_locator": "p3", "predicted_locator": "p3", "locator_match": "", "verifier_id": "V1"},
        {"item_id": "I1", "split": "held_out", "field_name": "unit", "required": "true", "numeric": "false", "gold_value": "mg", "predicted_value": "MG", "gold_locator": "p3", "predicted_locator": "p3", "locator_match": "true", "verifier_id": "V1"},
        {"item_id": "D1", "split": "development", "field_name": "dose", "required": "true", "numeric": "false", "gold_value": "1", "predicted_value": "wrong", "verifier_id": "V1"},
    ]
    result = MODULE.compute(rows)
    assert result["pass"] is True
    assert result["n_evaluated_fields"] == 2
    assert result["required_field_accuracy"] == 1.0
    assert result["locator_accuracy"] == 1.0


def test_extraction_metrics_measure_unsupported_and_omitted_values() -> None:
    rows = [
        {"item_id": "I1", "split": "held_out", "field_name": "funding", "required": "false", "gold_value": "", "predicted_value": "industry", "gold_locator": "", "predicted_locator": "p9", "locator_match": "false", "verifier_id": "V1"},
        {"item_id": "I1", "split": "held_out", "field_name": "duration", "required": "true", "gold_value": "12 weeks", "predicted_value": "", "gold_locator": "p4", "predicted_locator": "", "locator_match": "false", "verifier_id": "V1"},
    ]
    result = MODULE.compute(rows)
    assert result["unsupported_extraction_rate"] == 1.0
    assert result["omission_rate"] == 0.5
    assert result["required_field_accuracy"] == 0.0


def test_extraction_metrics_reject_missing_verifier() -> None:
    row = {"item_id": "I1", "split": "held_out", "field_name": "dose", "required": "true", "gold_value": "10", "predicted_value": "10", "verifier_id": ""}
    result = MODULE.compute([row])
    assert result["pass"] is False
    assert "missing_human_verifier:I1:dose" in result["validation_errors"]
