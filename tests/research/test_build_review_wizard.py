from pathlib import Path


def test_review_wizard_has_no_automatic_decisions_or_scenario_answer_leaks() -> None:
    output = Path(__file__).parents[2] / "research_v3" / "human_review_minimal" / "연구_승인_마법사.html"
    text = output.read_text(encoding="utf-8")
    assert '"ai_baseline"' not in text
    assert "DATA.ai_baseline" not in text
    assert "kwon_research_review_v4_fulltext" in text
    assert 'id="nextReviewerBtn"' in text
    assert text.count('"reviewer_role": "지도교수"') == 4
    assert '"id": "fulltext"' in text
    assert '"title": "전문 검토"' in text
    assert "정답 위험 규칙 ID" not in text
    assert "중대 시나리오" not in text
    assert "예상되는 규칙 ID" not in text
    assert "엔진 예측·개발 정답·critical 분류는 표시하지 않습니다." in text
