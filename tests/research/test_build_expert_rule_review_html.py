from __future__ import annotations

import json
from pathlib import Path

from scripts.research.build_expert_rule_review_html import build


def test_real_packet_embeds_six_rules_and_sixty_candidates(tmp_path: Path) -> None:
    root = Path(__file__).parents[2] / "research_v3"
    output = tmp_path / "expert.html"
    report = build(root, output)
    html = output.read_text(encoding="utf-8")
    assert report["rules"] == 6
    assert report["evidence_candidates"] == 60
    assert report["prefilled_decisions"] == 0
    assert "human_expert_rule_review" in html
    assert "AI 후보·사람 미검증" in html
    assert '"prefilled_decisions": 0' in html
    manifest = json.loads((tmp_path / "expert_rule_review_html_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == report["sha256"]
