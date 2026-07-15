import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    path = ROOT / "scripts/research/otc" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module)
    return module


def test_active_otc_identity_has_no_cross_student_contamination() -> None:
    result = load("audit_active_identity").audit()
    assert result["valid"] is True
    assert result["cross_student_findings"] == []
    assert result["inspected_files"] > 20


def test_completion_audit_keeps_human_and_promotion_requirements_incomplete() -> None:
    result = load("audit_completion").audit()
    assert result["complete"] is False
    assert "independent_evaluation_complete" in result["incomplete_requirements"]
    assert "ingredient_normalization_accuracy_reported" not in result["incomplete_requirements"]
    assert next(item for item in result["requirements"] if item["requirement"] == "ingredient_normalization_accuracy_reported")["status"] == "achieved"
    assert "preview_browser_verified" not in result["incomplete_requirements"]
    assert "g_drive_working_package_synced" not in result["incomplete_requirements"]
    assert "canonical_promotion" not in result["incomplete_requirements"]
    assert next(item for item in result["requirements"] if item["requirement"] == "canonical_promotion")["status"] == "achieved"
    assert next(item for item in result["requirements"] if item["requirement"] == "no_cross_student_contamination")["status"] == "achieved"
