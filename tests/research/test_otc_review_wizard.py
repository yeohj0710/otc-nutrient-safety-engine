import json
import re
from pathlib import Path

from scripts.research.otc.build_review_wizard import OUTPUT, build_html, build_payload, main


def test_payload_has_no_prefilled_human_identity_or_decisions() -> None:
    payload = build_payload()
    assert payload["reviewer"] == {"reviewer_id": "", "reviewer_role": "", "reviewed_at": ""}
    assert payload["human_decisions"] == {}
    assert len(payload["sections"]["official_candidates"]) == 13
    assert len(payload["sections"]["draft_rules"]) == 16
    assert len(payload["sections"]["independent_scenarios"]) == 13


def test_html_contains_import_export_and_unchecked_review_controls() -> None:
    html = build_html(build_payload())
    assert "검토 결과 JSON 저장" in html
    assert "기존 결과 불러오기" in html
    assert not re.search(r"<input[^>]+\schecked(?:\s|=|>)", html)
    assert "human_decisions_prefilled" not in html
    source = re.search(r'<script id="sourcePayload" type="application/json">(.*?)</script>', html, re.S)
    assert source
    payload = json.loads(source.group(1))
    assert payload["human_decisions"] == {}


def test_builder_writes_manifest_with_zero_prefill() -> None:
    assert main() == 0
    manifest = json.loads((OUTPUT.parent / "review_manifest.json").read_text(encoding="utf-8"))
    assert OUTPUT.exists()
    assert manifest["human_decisions_prefilled"] == 0
    assert manifest["independent_codex_recommendations_prefilled"] == 13
    assert manifest["counts"] == {
        "official_candidates": 13,
            "normalization_exceptions": 0,
            "normalization_reference": 31,
        "draft_rules": 16,
        "official_evidence_candidates": 360,
        "rule_evidence_shortlist": 48,
        "runtime_rule_bindings": 13,
        "independent_scenarios": 13,
    }
