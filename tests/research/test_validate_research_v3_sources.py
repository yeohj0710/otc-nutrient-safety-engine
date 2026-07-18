from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "validate_research_v3_sources.py"
SPEC = importlib.util.spec_from_file_location("validate_research_v3_sources", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_current_sources_have_integrity_but_fetch_warnings() -> None:
    root = Path(__file__).parents[2] / "research_v3" / "sources"
    report = MODULE.validate(root)
    assert report["valid"] is True
    assert report["release_ready"] is False
    assert report["counts"]["normative_candidates"] >= 14
    assert {item["source_id"] for item in report["warnings"]} == {
        "NIH_ODS_VITAMIN_D_HP",
        "NIH_ODS_CALCIUM_HP",
        "NIH_ODS_VITAMIN_B6_HP",
        "NIH_ODS_MAGNESIUM_HP",
        "NIH_ODS_IRON_HP",
        "NIH_ODS_ZINC_HP",
    }
