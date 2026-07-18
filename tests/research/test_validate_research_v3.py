from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "validate_research_v3.py"
SPEC = importlib.util.spec_from_file_location("validate_research_v3", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_current_v3_is_structurally_valid_but_not_release_ready() -> None:
    root = Path(__file__).parents[2] / "research_v3"
    report = MODULE.validate(root)
    assert report["valid"] is True
    assert report["release_ready"] is False
    assert any(warning["code"] == "RELEASE_GOVERNANCE_PENDING" for warning in report["warnings"])
    assert report["counts"]["rules_total"] == 6
    assert report["counts"]["rules_released"] == 6
    assert report["counts"]["development_scenarios"] == 12
    assert {item["code"] for item in report["warnings"]} == {"RELEASE_GOVERNANCE_PENDING"}
