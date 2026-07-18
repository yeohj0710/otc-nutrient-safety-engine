from pathlib import Path
from scripts.research.build_independent_scenario_review_html import build
def test_blind_html_has_twelve_unfilled_scenarios(tmp_path:Path):
    root=Path(__file__).parents[2];out=tmp_path/"review.html";r=build(root/"research_v3/human_review_minimal/05_독립시나리오_12건_확정.csv",out);text=out.read_text(encoding="utf-8")
    assert r["scenarios"]==12 and r["prefilled_gold_labels"]==0 and r["predictions_exposed"]==0
    assert "independent_human_scenario_adjudication" in text and "엔진 예측·개발 정답·critical 분류 비공개" in text
    assert "hazard_rule_id" not in text and "critical 사례 여부" not in text
