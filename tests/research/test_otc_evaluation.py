import csv
from pathlib import Path

from scripts.research.otc.evaluate import evaluate_file, evaluate_rows, wilson


ROOT = Path(__file__).resolve().parents[2]
INDEPENDENT = ROOT / "research_v3" / "otc" / "validation" / "independent_scenarios.csv"
DEVELOPMENT = ROOT / "research_v3" / "otc" / "validation" / "development_scenarios.csv"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_development_and_independent_ids_are_disjoint_and_cover_required_families() -> None:
    development = read_rows(DEVELOPMENT)
    independent = read_rows(INDEPENDENT)
    assert len(development) == len(independent) == 13
    assert {row["scenario_id"] for row in development}.isdisjoint(row["scenario_id"] for row in independent)
    assert {row["scenario_family"] for row in development} == {row["scenario_family"] for row in independent}


def test_empty_human_labels_refuse_performance_claims(tmp_path: Path) -> None:
    result = evaluate_rows([
        {"human_reference_label": "", "prediction": "1", "critical": "true"},
        {"human_reference_label": "", "prediction": "0", "critical": "false"},
    ])
    assert result["status"] == "not_evaluated_missing_independent_human_labels"
    assert result["scenarios_evaluated"] == 0
    assert result["performance_claim_allowed"] is False


def test_codex_prefilled_external_confirmation_is_reported_but_not_claimed_independent() -> None:
    result = evaluate_rows([
        {"human_reference_label": "1", "prediction": "1", "critical": "true", "independent_blinding": "false"},
        {"human_reference_label": "0", "prediction": "0", "critical": "false", "independent_blinding": "false"},
    ])
    assert result["status"] == "evaluated_codex_prefilled_external_human_confirmation"
    assert result["scenarios_evaluated"] == 2
    assert result["performance_claim_allowed"] is False


def test_metrics_and_critical_false_negative_are_computed_from_labels() -> None:
    rows = [
        {"human_reference_label": "1", "prediction": "1", "critical": "true"},
        {"human_reference_label": "1", "prediction": "0", "critical": "true"},
        {"human_reference_label": "0", "prediction": "0", "critical": "false"},
        {"human_reference_label": "0", "prediction": "1", "critical": "false"},
    ]
    result = evaluate_rows(rows)
    assert result["confusion_matrix"] == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}
    assert result["sensitivity"]["value"] == result["specificity"]["value"] == 0.5
    assert result["positive_predictive_value"]["value"] == result["negative_predictive_value"]["value"] == 0.5
    assert result["accuracy"]["value"] == 0.5
    assert result["critical_false_negatives"] == 1
    assert result["performance_claim_allowed"] is True
    assert wilson(1, 2) == result["sensitivity"]["ci95"]
