"""P3-A AI 참조표준 통계 함수 검증.

층화 가중, Rogan-Gladen 보정, 층화 부트스트랩 CI, 종합 라벨 규칙을 검증한다.
"""

import json
from pathlib import Path

import pytest

from tools.ai_reference_standard import (
    allocate_sample,
    cohen_kappa,
    derive_composite_label,
    majority_label,
    rogan_gladen,
    stratified_bootstrap,
    stratified_metrics,
    weighted_confusion,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "research_v3" / "measurement" / "screener_vs_ai_reference.json"


def _row(stratum: str, weight: float, screener: bool, reference: bool) -> dict:
    return {
        "stratum": stratum,
        "weight": weight,
        "screener_positive": screener,
        "reference_positive": reference,
    }


# --------------------------------------------------------------------------
# 종합 라벨 규칙
# --------------------------------------------------------------------------
def test_composite_label_rule_is_explicit_and_veto_driven() -> None:
    assert derive_composite_label({"P": "Y", "I": "Y", "C": "U", "O": "Y", "S": "Y"}) == "retain"
    # I·O 가 Y 여도 S=N 이면 deprioritize (동물·시험관 배제)
    assert (
        derive_composite_label({"P": "Y", "I": "Y", "C": "U", "O": "Y", "S": "N"}) == "deprioritize"
    )
    # 노출은 있으나 결과가 없으면 deprioritize
    assert (
        derive_composite_label({"P": "Y", "I": "Y", "C": "U", "O": "N", "S": "Y"}) == "deprioritize"
    )
    # I 또는 O 가 U 이면 uncertain
    assert derive_composite_label({"P": "U", "I": "Y", "C": "U", "O": "U", "S": "U"}) == "uncertain"
    assert derive_composite_label({"P": "U", "I": "U", "C": "U", "O": "Y", "S": "Y"}) == "uncertain"


def test_composite_label_ignores_comparator() -> None:
    base = {"P": "Y", "I": "Y", "O": "Y", "S": "Y"}
    labels = {derive_composite_label({**base, "C": value}) for value in ("Y", "N", "U")}
    assert labels == {"retain"}


def test_composite_label_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        derive_composite_label({"P": "Y", "I": "Y", "C": "U", "O": "Y", "S": "maybe"})


# --------------------------------------------------------------------------
# 층화 가중
# --------------------------------------------------------------------------
def test_weighted_confusion_applies_stratum_weights() -> None:
    rows = [
        _row("A", 10.0, True, True),
        _row("B", 2.0, True, False),
        _row("B", 2.0, False, True),
        _row("B", 2.0, False, False),
    ]
    counts = weighted_confusion(rows)
    assert counts == {"tp": 10.0, "fp": 2.0, "fn": 2.0, "tn": 2.0}


def test_stratified_metrics_differ_from_unweighted_average() -> None:
    """큰 층에서만 위음성이 나면 가중 민감도는 단순 평균보다 낮아야 한다."""
    rows = [_row("big", 100.0, False, True)] + [_row("small", 1.0, True, True) for _ in range(9)]
    metrics = stratified_metrics(rows)
    unweighted_sensitivity = 9 / 10
    assert metrics["sensitivity_vs_ai_reference"] == pytest.approx(9 / 109)
    assert metrics["sensitivity_vs_ai_reference"] < unweighted_sensitivity


def test_stratified_metrics_perfect_and_degenerate_cases() -> None:
    perfect = stratified_metrics([_row("A", 3.0, True, True), _row("A", 3.0, False, False)])
    assert perfect["sensitivity_vs_ai_reference"] == 1.0
    assert perfect["specificity_vs_ai_reference"] == 1.0
    assert perfect["f1_vs_ai_reference"] == 1.0
    assert perfect["agreement_vs_ai_reference"] == 1.0

    no_positive = stratified_metrics([_row("A", 1.0, False, False)])
    assert no_positive["sensitivity_vs_ai_reference"] is None
    assert no_positive["precision_vs_ai_reference"] is None
    assert no_positive["f1_vs_ai_reference"] is None


# --------------------------------------------------------------------------
# Rogan-Gladen
# --------------------------------------------------------------------------
def test_rogan_gladen_returns_apparent_prevalence_for_perfect_test() -> None:
    assert rogan_gladen(0.4, 1.0, 1.0) == pytest.approx(0.4)


def test_rogan_gladen_corrects_known_example() -> None:
    # (0.30 + 0.90 - 1) / (0.80 + 0.90 - 1) = 0.20 / 0.70
    assert rogan_gladen(0.30, 0.80, 0.90) == pytest.approx(0.2 / 0.7)


def test_rogan_gladen_clamps_and_guards_denominator() -> None:
    assert rogan_gladen(0.10, 0.80, 0.90) == 0.0  # 음수 결과는 0으로 절단
    assert rogan_gladen(0.95, 0.80, 0.90) == 1.0  # 1 초과는 1로 절단
    assert rogan_gladen(0.4, 0.5, 0.5) is None  # 민감도+특이도-1 <= 0 이면 정의되지 않음


# --------------------------------------------------------------------------
# 층화 부트스트랩
# --------------------------------------------------------------------------
def test_stratified_bootstrap_is_deterministic_for_a_fixed_seed() -> None:
    rows = [_row("A", 4.0, True, True), _row("A", 4.0, False, True)] + [
        _row("B", 1.0, False, False),
        _row("B", 1.0, True, False),
    ]
    first = stratified_bootstrap(rows, 0.4, replicates=200, seed=7)
    second = stratified_bootstrap(rows, 0.4, replicates=200, seed=7)
    assert first == second


def test_stratified_bootstrap_ci_brackets_point_estimate() -> None:
    rows = (
        [_row("A", 2.0, True, True) for _ in range(8)]
        + [_row("A", 2.0, False, True) for _ in range(2)]
        + [_row("B", 5.0, False, False) for _ in range(9)]
        + [_row("B", 5.0, True, False)]
    )
    metrics = stratified_metrics(rows)
    result = stratified_bootstrap(rows, 0.4, replicates=500, seed=11)
    low, high = result["sensitivity_ci95"]
    assert low <= metrics["sensitivity_vs_ai_reference"] <= high
    low, high = result["specificity_ci95"]
    assert low <= metrics["specificity_vs_ai_reference"] <= high
    assert result["replicates"] == 500


def test_stratified_bootstrap_resamples_within_strata_only() -> None:
    """한 층이 전부 양성이면 어떤 복제에서도 그 층은 양성만 나와야 한다."""
    rows = [_row("pos", 1.0, True, True) for _ in range(5)] + [
        _row("neg", 1.0, False, False) for _ in range(5)
    ]
    result = stratified_bootstrap(rows, 0.5, replicates=100, seed=3)
    assert result["sensitivity_ci95"] == [1.0, 1.0]
    assert result["specificity_ci95"] == [1.0, 1.0]


# --------------------------------------------------------------------------
# 보조 통계
# --------------------------------------------------------------------------
def test_wilson_interval_matches_known_values() -> None:
    # p=0.8, n=100, z=1.96 → (0.7112, 0.8666)
    low, high = wilson_interval(80, 100)
    assert low == pytest.approx(0.7112, abs=1e-3)
    assert high == pytest.approx(0.8666, abs=1e-3)
    assert wilson_interval(0, 0) is None


def test_cohen_kappa_perfect_and_chance() -> None:
    assert cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == pytest.approx(1.0)
    assert cohen_kappa(["a", "a", "b", "b"], ["b", "b", "a", "a"]) == pytest.approx(-1.0)


def test_majority_label_and_unresolved() -> None:
    assert majority_label(["retain", "retain", "deprioritize"]) == "retain"
    assert majority_label(["retain", "deprioritize", "uncertain"]) == "unresolved"


def test_allocate_sample_respects_floor_and_frame() -> None:
    frames = {"big": 1000, "small": 5, "mid": 100}
    allocation = allocate_sample(frames, 60, floor=20)
    assert sum(allocation.values()) == 60
    assert allocation["small"] == 5  # 프레임보다 크게 배정하지 않는다
    assert allocation["big"] >= 20
    assert allocation["mid"] >= 20


# --------------------------------------------------------------------------
# 산출물 정합성
# --------------------------------------------------------------------------
@pytest.mark.skipif(not OUTPUT.exists(), reason="P3-A 산출물이 아직 생성되지 않음")
def test_measurement_output_declares_ai_reference_and_no_human_claim() -> None:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert payload["ai_reference_standard"] is True
    assert payload["human_reference_standard"] is False
    assert payload["human_decisions"] == 0
    assert payload["local_language_model_used"] is False
    assert payload["external_llm_api_used"] is False
    for key in (
        "sensitivity_vs_ai_reference",
        "specificity_vs_ai_reference",
        "precision_vs_ai_reference",
        "f1_vs_ai_reference",
        "agreement_vs_ai_reference",
    ):
        assert key in payload["primary_analysis"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "independent_blinding\": true" not in serialized
    assert payload["corpus_prevalence"]["rogan_gladen_corrected_prevalence"] is not None
    assert payload["bootstrap"]["replicates"] == 10_000


@pytest.mark.skipif(not OUTPUT.exists(), reason="P3-A 산출물이 아직 생성되지 않음")
def test_measurement_output_metrics_recompute_from_per_record_rows() -> None:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    rows = [
        {
            "stratum": row["stratum"],
            "weight": row["weight"],
            "screener_positive": row["screener_decision"] == "retain",
            "reference_positive": row["ai_reference_label"] == "retain",
        }
        for row in payload["per_record"]
        if row["ai_reference_label"] in ("retain", "deprioritize")
    ]
    recomputed = stratified_metrics(rows)
    for key in (
        "sensitivity_vs_ai_reference",
        "specificity_vs_ai_reference",
        "precision_vs_ai_reference",
        "f1_vs_ai_reference",
        "agreement_vs_ai_reference",
    ):
        assert recomputed[key] == pytest.approx(payload["primary_analysis"][key])
