from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "freeze_evidence.py"
SPEC = importlib.util.spec_from_file_location("freeze_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def populate(root: Path) -> None:
    for relative in MODULE.REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("a,b\n1,2\n" if path.suffix == ".csv" else "content\n", encoding="utf-8")
    for relative in MODULE.REQUIRED_JSON:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pass": True}), encoding="utf-8")


def test_evidence_freeze_rejects_missing_artifacts(tmp_path: Path) -> None:
    errors, _hashes = MODULE.validate(tmp_path)
    assert "missing:protocol/protocol.md" in errors
    assert "missing:validation/scenario_metrics.json" in errors


def test_evidence_freeze_hashes_complete_valid_inputs(tmp_path: Path) -> None:
    populate(tmp_path)
    errors, hashes = MODULE.validate(tmp_path)
    assert errors == []
    assert set(hashes) == set(MODULE.REQUIRED_FILES + MODULE.REQUIRED_JSON)


def test_evidence_freeze_rejects_failed_metric(tmp_path: Path) -> None:
    populate(tmp_path)
    path = tmp_path / "validation" / "scenario_metrics.json"
    path.write_text(json.dumps({"pass": False}), encoding="utf-8")
    errors, _hashes = MODULE.validate(tmp_path)
    assert "failed:validation/scenario_metrics.json" in errors
