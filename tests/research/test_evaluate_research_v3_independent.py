from __future__ import annotations

import importlib.util
import csv
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "evaluate_research_v3_independent.py"
SPEC = importlib.util.spec_from_file_location("evaluate_research_v3_independent", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_completed_packet_without_predictions_awaits_predictions() -> None:
    scenarios = Path(__file__).parents[2] / "research_v3" / "validation" / "independent_scenarios.csv"
    report = MODULE.run(scenarios, None)
    assert report["status"] == "awaiting_predictions"
    assert report["scenario_count"] == 12
    assert report["performance_claim_allowed"] is False


def test_wilson_interval_and_confusion_metrics() -> None:
    rows = [
        {"gold_hazards": ["A"], "predicted_hazards": ["A"], "critical": True},
        {"gold_hazards": ["B"], "predicted_hazards": [], "critical": True},
        {"gold_hazards": [], "predicted_hazards": [], "critical": False},
        {"gold_hazards": [], "predicted_hazards": ["C"], "critical": False},
    ]
    metrics = MODULE.calculate(rows)
    assert metrics["confusion_matrix"] == {"tp": 1, "tn": 1, "fp": 1, "fn": 1, "critical_false_negative": 1}
    assert metrics["sensitivity"]["value"] == 0.5
    assert metrics["specificity"]["value"] == 0.5
    assert metrics["accuracy"]["value"] == 0.5
    low, high = metrics["accuracy"]["ci95_wilson"]
    assert 0 <= low < 0.5 < high <= 1


def test_prediction_file_has_separate_schema(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios.csv"
    predictions = tmp_path / "predictions.csv"
    with scenarios.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(MODULE.REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerow({
            "scenario_id": "IND-001",
            "scenario_type": "threshold_above",
            "input_json": "{}",
            "gold_hazards_json": '["RULE-1"]',
            "critical": "true",
            "adjudicator_id": "reviewer-1",
            "adjudicated_at": "2026-07-13T00:00:00Z",
            "locked_before_test": "true",
            "notes": "",
        })
    with predictions.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario_id", "predicted_hazards_json"])
        writer.writeheader()
        writer.writerow({"scenario_id": "IND-001", "predicted_hazards_json": '["RULE-1"]'})

    report = MODULE.run(scenarios, predictions)
    assert report["status"] == "evaluated"
    assert report["rows"][0]["predicted_hazards"] == ["RULE-1"]


def test_wrong_hazard_is_not_counted_as_correct_detection() -> None:
    metrics = MODULE.calculate([
        {"gold_hazards": ["RULE-A"], "predicted_hazards": ["RULE-B"], "critical": True},
    ])
    assert metrics["confusion_matrix"]["tp"] == 0
    assert metrics["confusion_matrix"]["fn"] == 1
    assert metrics["confusion_matrix"]["fp"] == 1
    assert metrics["confusion_matrix"]["critical_false_negative"] == 1
    assert metrics["exact_hazard_set_accuracy"]["value"] == 0.0


def test_duplicate_prediction_ids_are_rejected(tmp_path: Path) -> None:
    scenarios = tmp_path / "scenarios.csv"
    predictions = tmp_path / "predictions.csv"
    with scenarios.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(MODULE.REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerow({
            "scenario_id": "IND-001", "scenario_type": "test", "input_json": "{}",
            "gold_hazards_json": '[]', "critical": "false", "adjudicator_id": "reviewer-1",
            "adjudicated_at": "2026-07-13T00:00:00Z", "locked_before_test": "true", "notes": "",
        })
    with predictions.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario_id", "predicted_hazards_json"])
        writer.writeheader()
        writer.writerows([
            {"scenario_id": "IND-001", "predicted_hazards_json": "[]"},
            {"scenario_id": "IND-001", "predicted_hazards_json": "[]"},
        ])
    report = MODULE.run(scenarios, predictions)
    assert report["status"] == "invalid"
    assert "IND-001: duplicate prediction" in report["errors"]
