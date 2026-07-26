from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "screen_v40_literature_local.py"
SPEC = importlib.util.spec_from_file_location("screen_v40_literature_local", MODULE_PATH)
assert SPEC and SPEC.loader
screening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(screening)


def test_parse_model_output_accepts_only_declared_labels() -> None:
    result = screening.parse_model_output("retain|medium|직접 안전성 결과를 다룸", True)
    assert result == {
        "label": "retain",
        "confidence": "medium",
        "rationale": "직접 안전성 결과를 다룸",
        "parse_status": "parsed",
    }


def test_title_only_forces_low_confidence() -> None:
    result = screening.parse_model_output("DEPRIORITIZE|HIGH|질문과 무관", False)
    assert result["label"] == "deprioritize"
    assert result["confidence"] == "low"


def test_invalid_output_falls_back_to_uncertain() -> None:
    result = screening.parse_model_output("설명만 있는 출력", True)
    assert result["label"] == "uncertain"
    assert result["parse_status"] == "fallback_invalid_output"


def test_validate_coverage_reports_missing_and_rejects_duplicates() -> None:
    result = screening.validate_coverage(
        ["A", "B"], [{"record_id": "A"}]
    )
    assert result["coverage"] == 0.5
    assert result["missing_ids"] == ["B"]

    with pytest.raises(ValueError, match="duplicates"):
        screening.validate_coverage(
            ["A", "B"], [{"record_id": "A"}, {"record_id": "A"}]
        )
