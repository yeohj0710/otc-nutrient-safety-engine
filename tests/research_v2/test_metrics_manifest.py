from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "build_metrics_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_metrics_manifest", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def valid_root(root: Path) -> None:
    write_json(root, "audit/evidence_freeze.json", {"status": "frozen", "pass": True, "dataset_version": "v1", "frozen_at": "2026-07-10T00:00:00Z", "source_commit": "abc"})
    write_json(root, "screening/prisma_counts.json", {"pass": True, "records_identified": 400, "studies_included": 20, "reports_included": 22})
    write_json(root, "ai_eval/screening_metrics.json", {"pass": True, "sensitivity": 0.96, "sensitivity_ci95": [0.90, 0.99], "gold_positive_count": 60})
    write_json(root, "ai_eval/extraction_metrics.json", {"pass": True, "required_field_accuracy": 0.92, "required_field_count": 200})
    write_json(root, "validation/scenario_metrics.json", {"pass": True, "hazard_sensitivity": 0.96, "hazard_sensitivity_ci95": [0.91, 0.99], "n_scenarios": 100, "critical_false_negative_count": 0, "provenance_completeness": 1.0})
    write_json(root, "validation/content_validity.json", {"pass": True, "s_cvi_ave": 0.91, "n_experts": 3})


def test_metrics_manifest_requires_evidence_freeze(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="evidence_freeze"):
        MODULE.build(tmp_path)


def test_metrics_manifest_uses_only_machine_sources(tmp_path: Path) -> None:
    valid_root(tmp_path)
    result = MODULE.build(tmp_path)
    assert result["generated_at"] == "2026-07-10T00:00:00Z"
    assert result["metrics"]["ai_screening_recall"]["value"] == 0.96
    assert result["metrics"]["scenario_critical_false_negative"]["value"] == 0


def test_metrics_manifest_rejects_failed_source(tmp_path: Path) -> None:
    valid_root(tmp_path)
    write_json(tmp_path, "validation/scenario_metrics.json", {"pass": False})
    with pytest.raises(ValueError, match="failed validation"):
        MODULE.build(tmp_path)
