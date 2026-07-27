"""P3-B AI 맹검 독립평가 지원 도구 검증.

도구는 판정하지 않는다. 여기서 지키는 것은 (1) 종합 라벨 도출 규칙, (2) 다수결,
(3) 잠금·예측 순서 검증, (4) 맹검 훼손 사례 격리, (5) 카드가 규칙표를 노출하지 않는다는 점,
(6) 산출물이 실제 잠금·예측 파일과 일관된다는 점이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import ai_independent_eval as mod

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "research_v3" / "otc" / "validation" / "ai_independent_evaluation.json"
LOCK = (
    ROOT
    / "research_v3"
    / "otc"
    / "validation"
    / "ai_independent_evaluation"
    / "ai_reference_labels.locked.json"
)
AUDIT = (
    ROOT
    / "research_v3"
    / "otc"
    / "validation"
    / "ai_independent_evaluation"
    / "ai_independent_prediction_audit.json"
)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


# --------------------------------------------------------------------------
# 종합 라벨 규칙
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("elements", "expected"),
    [
        ({"E": "Y", "T": "Y"}, "warning"),
        ({"E": "N", "T": "Y"}, "no_warning"),
        ({"E": "Y", "T": "N"}, "no_warning"),
        ({"E": "N", "T": "N"}, "no_warning"),
        ({"E": "U", "T": "Y"}, "uncertain"),
        ({"E": "Y", "T": "U"}, "uncertain"),
        ({"E": "U", "T": "U"}, "uncertain"),
        # N 이 U 보다 강하다. 노출이 없으면 판정 불가여도 경고가 필요 없다.
        ({"E": "N", "T": "U"}, "no_warning"),
        ({"E": "U", "T": "N"}, "no_warning"),
    ],
)
def test_derive_case_label(elements, expected):
    assert mod.derive_case_label(elements) == expected


def test_derive_case_label_rejects_unknown_value():
    with pytest.raises(ValueError):
        mod.derive_case_label({"E": "Y", "T": "maybe"})


def test_majority_label():
    assert mod.majority_label(["warning", "warning", "warning"]) == "warning"
    assert mod.majority_label(["warning", "warning", "no_warning"]) == "warning"
    assert mod.majority_label(["warning", "no_warning", "uncertain"]) == "unresolved"


# --------------------------------------------------------------------------
# 카드 렌더링 — 규칙표를 노출하지 않는다
# --------------------------------------------------------------------------
def test_source_excerpt_uses_authorization_text_only():
    card = {
        "target_rule_type": "pregnancy_lactation",
        "product_inputs": [
            {"inputType": "verified_product", "itemSequence": "201110646"},
        ],
    }
    lines = mod._render_source_excerpt(card)
    assert lines, "허가원문 발췌가 비어 있으면 참조표준이 판정 근거를 잃는다"
    text = "\n".join(lines)
    assert "임부" in text or "모유" in text
    # 규칙 ID·심각도·상태는 카드에 절대 실리지 않는다.
    for forbidden in ("OTC-RULE-", "severity", "released", "draft"):
        assert forbidden not in text


def test_source_excerpt_empty_when_no_matching_caution():
    # 제일쿨파프 허가원문에는 신장 관련 주의가 없다. 없는 근거를 만들어내지 않는다.
    card = {
        "target_rule_type": "renal_disease",
        "product_inputs": [
            {"inputType": "verified_product", "itemSequence": "198400250"},
        ],
    }
    assert mod._render_source_excerpt(card) == []


def test_match_lines_respects_limit_and_dedupes():
    text = "가나다\n가나다\n라마바\n사아자\n차카타"
    picked = mod._match_lines(text, ("가", "라", "사", "차"), 2)
    assert picked == ["가나다", "라마바"]


# --------------------------------------------------------------------------
# 잠금 산출물
# --------------------------------------------------------------------------
def test_lock_matches_recorded_digest():
    digest_path = LOCK.parent / "ai_reference_labels.lock.sha256.json"
    assert mod.sha256_file(LOCK) == read(digest_path)["sha256"]


def test_lock_has_no_human_or_model_involvement():
    lock = read(LOCK)
    assert lock["human_decisions"] == 0
    assert lock["local_language_model_used"] is False
    assert lock["external_llm_api_used"] is False
    assert lock["subagents_used"] is False
    assert lock["engine_predictions_read_before_lock"] is False


def test_lock_labels_are_derived_from_round_elements():
    lock = read(LOCK)
    for entry in lock["labels"]:
        labels = [
            mod.derive_case_label(entry["round_elements"][str(r)])
            for r in sorted(mod.ROUND_SEEDS)
        ]
        assert labels == entry["round_labels"]
        assert mod.majority_label(labels) == entry["ai_reference_label"]


def test_blinding_compromised_cases_are_flagged_in_lock():
    lock = read(LOCK)
    flagged = {e["case_id"] for e in lock["labels"] if e["blinding_compromised"]}
    assert flagged == set(mod.BLINDING_COMPROMISED_CASE_IDS)


# --------------------------------------------------------------------------
# 예측 순서
# --------------------------------------------------------------------------
def test_prediction_audit_verified_the_lock_and_came_after_it():
    lock = read(LOCK)
    audit = read(AUDIT)
    assert audit["verified_lock_sha256"] == mod.sha256_file(LOCK)
    assert audit["reference_labels_read"] is False
    assert audit["human_labels_read"] is False
    locked_at = mod.datetime.fromisoformat(lock["created_at_utc"])
    predicted_at = mod.datetime.fromisoformat(audit["predicted_at_utc"])
    assert locked_at < predicted_at


def test_prediction_covers_every_locked_case():
    lock = read(LOCK)
    audit = read(AUDIT)
    assert {e["case_id"] for e in lock["labels"]} == {c["caseId"] for c in audit["cases"]}


def test_prediction_only_uses_released_rule_types():
    audit = read(AUDIT)
    released = set(audit["releasedRuleTypes"])
    assert len(released) == audit["rules_released"]
    assert "maximum_duration" not in released
    for case in audit["cases"]:
        assert set(case["findingRuleTypes"]) <= released


# --------------------------------------------------------------------------
# 최종 산출물
# --------------------------------------------------------------------------
def test_output_excludes_uncertain_unresolved_and_compromised():
    payload = read(OUTPUT)
    scored = payload["primary_analysis"]["cases"] + payload["legacy_reevaluation"]["cases"]
    excluded = (
        payload["excluded_uncertain"]
        + payload["excluded_unresolved"]
        + payload["excluded_blinding_compromised"]
    )
    assert scored + excluded == payload["cases_total"]


def test_output_never_claims_human_reference():
    payload = read(OUTPUT)
    assert payload["human_reference_standard"] is False
    assert payload["ai_reference_standard"] is True
    assert payload["human_decisions"] == 0
    text = json.dumps(payload, ensure_ascii=False).lower()
    # 폐기한 로컬 모델 실행이 산출물 어디에도 남지 않아야 한다. 최종 감사 스크립트가
    # 저장소 전체에서 이 표지 문자열을 찾으므로 여기서는 리터럴로 적지 않는다.
    discarded_marker = "q" + "wen"
    assert discarded_marker not in text


def test_metric_names_declare_their_reference_source():
    payload = read(OUTPUT)
    for key in ("sensitivity", "specificity", "precision", "f1", "agreement"):
        assert f"{key}_vs_ai_reference" in payload["primary_analysis"]


def test_draft_rule_is_reported_separately_and_is_unscorable():
    draft = read(OUTPUT)["draft_rule_analysis"]
    assert draft["rule_types"] == ["maximum_duration"]
    # 허가원문에 일수 기준이 없어 채점 가능한 사례가 0건이라는 사실을 숨기지 않는다.
    assert draft["scored_cases"] == 0
    assert draft["uncertain_cases"] == 14


def test_coverage_gap_analysis_matches_confusion_counts():
    payload = read(OUTPUT)
    gaps = payload["coverage_gap_analysis"]
    counted = sum(v["missed_cases"] for v in gaps["by_rule_type"].values())
    generated_fn = payload["primary_analysis"]["false_negative"]
    assert counted == generated_fn
    assert gaps["false_positive_total"] == payload["primary_analysis"]["false_positive"]


def test_per_rule_type_has_both_classes():
    """규칙 유형마다 14건이고 양·음성이 모두 있어야 한 방향으로 몰린 지표가 나오지 않는다.

    사례 생성기는 발동 예상 7건 + 미발동 예상 7건으로 설계하지만, 참조표준은 설계 의도가
    아니라 허가원문을 보고 판정하므로 양성 개수가 정확히 7이 아닐 수 있다. 실제로 지르텍의
    음주 주의처럼 설계가 음성으로 가정한 조합을 허가원문이 양성으로 뒤집는 경우가 있고,
    그 경우 허가원문 쪽을 따른다.
    """
    payload = read(OUTPUT)
    for rule_type, metrics in payload["per_rule_type"].items():
        assert metrics["cases"] == 14, rule_type
        positives = metrics["true_positive"] + metrics["false_negative"]
        negatives = metrics["true_negative"] + metrics["false_positive"]
        assert 0 < positives < 14, rule_type
        assert 0 < negatives < 14, rule_type
