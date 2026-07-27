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


def test_completion_audit_completes_via_ai_evaluation_but_never_releases() -> None:
    """P3-B 이후 완료 조건은 AI 맹검 평가로 충족된다. 사람 블라인드와 배포 승인은 별개다."""
    result = load("audit_completion").audit()
    assert result["complete"] is True
    assert result["incomplete_requirements"] == []
    assert "independent_evaluation_ai_complete" not in result["incomplete_requirements"]

    flags = result["status_flags"]
    assert flags["independent_evaluation_ai_complete"]["value"] is True
    assert flags["independent_blinding_ai"]["value"] is True
    assert flags["performance_claim_allowed"]["value"] is True
    # 사람 블라인드 평가는 수행되지 않았고 배포도 허용되지 않는다.
    assert flags["independent_blinding"]["value"] is False
    assert flags["release_ready"]["value"] is False
    assert result["release_ready"] is False
    # 모든 플래그에 근거 파일 경로가 붙어 있어야 한다.
    for name, flag in flags.items():
        assert flag["evidence"], name


def test_completion_audit_keeps_other_requirements_achieved() -> None:
    result = load("audit_completion").audit()
    assert "ingredient_normalization_accuracy_reported" not in result["incomplete_requirements"]
    assert next(item for item in result["requirements"] if item["requirement"] == "ingredient_normalization_accuracy_reported")["status"] == "achieved"
    assert "preview_browser_verified" not in result["incomplete_requirements"]
    assert "g_drive_working_package_synced" not in result["incomplete_requirements"]
    assert "canonical_promotion" not in result["incomplete_requirements"]
    assert next(item for item in result["requirements"] if item["requirement"] == "canonical_promotion")["status"] == "achieved"
    assert next(item for item in result["requirements"] if item["requirement"] == "no_cross_student_contamination")["status"] == "achieved"
