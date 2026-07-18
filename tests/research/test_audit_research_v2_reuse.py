from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "audit_research_v2_reuse.py"
SPEC = importlib.util.spec_from_file_location("audit_research_v2_reuse", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_empty_rows_are_templates() -> None:
    assert MODULE.classify("full_text_screening", []) == (
        "template_only",
        "헤더만 존재하거나 행이 없음",
    )


def test_rules_never_become_released_by_inventory() -> None:
    status, reason = MODULE.classify("rules", [{"status": "draft_ai"}])
    assert status == "draft_only"
    assert "released 0개" in reason


def test_source_quotes_require_locator() -> None:
    status, _ = MODULE.classify(
        "source_quotes",
        [{"source_url": "https://example.test", "locator": "", "quote": "text"}],
    )
    assert status == "not_reusable"
