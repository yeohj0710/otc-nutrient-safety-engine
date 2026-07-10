from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("execution_package/scripts/check_project_identity.py").resolve()


def run_gate(root: Path, config: dict[str, object]) -> tuple[int, dict[str, object]]:
    research = root / "research_v2"
    (research / "config").mkdir(parents=True)
    (research / "audit").mkdir(parents=True)
    (research / "config" / "project_identity.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    (research / "project_identity.json").write_text(
        json.dumps({**config, "mode": "kwon_primary_research"}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    report = json.loads(
        (research / "audit" / "repo_identity.json").read_text(encoding="utf-8")
    )
    return result.returncode, report


def kwon_config() -> dict[str, object]:
    return {
        "student_name": "권혁찬",
        "student_id": "2021194024",
        "recommended_repo": "otc-nutrient-safety-engine",
        "study_slug": "kwon-high-dose-otc-nutrient-safety",
        "title_ko": (
            "일반의약품형 고함량 영양성분의 함량 기준 안전성 평가와 "
            "근거 추적형 조회 도구의 개발 및 검증"
        ),
        "title_en": (
            "Dose-based safety evaluation of high-dose nutrient ingredients and "
            "development and validation of a traceable query tool"
        ),
    }


def initialize_repo(root: Path) -> None:
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "remote",
            "add",
            "origin",
            "https://github.com/example/otc-nutrient-safety-engine.git",
        ],
        check=True,
    )


def test_gate_accepts_kwon_repo_identity(tmp_path: Path) -> None:
    initialize_repo(tmp_path)

    code, report = run_gate(tmp_path, kwon_config())

    assert code == 0
    assert report["pass"] is True


def test_gate_rejects_yeo_identity_leak(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text(
        "여형준 2020194025", encoding="utf-8"
    )

    code, report = run_gate(tmp_path, kwon_config())

    assert code == 1
    assert "yeo_markers_in_active_paths" in report["failures"]


def test_gate_allows_yeo_parent_folder_in_reference_provenance(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    reference = tmp_path / "research_v2" / "protocol" / "reference"
    reference.mkdir(parents=True)
    (reference / "reference_manifest.json").write_text(
        json.dumps(
            {
                "source_path": (
                    "G:\\내 드라이브\\여형준님\\24 전공심화실습(1)"
                    "\\권혁찬\\연구계획서_권혁찬_260618.pdf"
                )
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    code, report = run_gate(tmp_path, kwon_config())

    assert code == 0
    assert report["pass"] is True
