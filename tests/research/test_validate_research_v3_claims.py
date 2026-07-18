from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "validate_research_v3_claims.py"
SPEC = importlib.util.spec_from_file_location("validate_research_v3_claims", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_current_report_and_thesis_match_manifest() -> None:
    root = Path(__file__).parents[2] / "research_v3"
    report = MODULE.validate(
        root / "metrics_manifest.json",
        [root / "reports" / "FINAL_RESEARCH_REPORT.md", root / "thesis" / "otc_thesis_working.md"],
    )
    assert report["valid"] is True
