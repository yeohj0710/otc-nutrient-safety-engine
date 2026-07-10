from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "execution_package" / "scripts" / "validate_release.py"


def run_validator(root: Path) -> dict[str, object]:
    out = root.parent / f"{root.name}-validation.json"
    subprocess.run(
        [sys.executable, str(VALIDATOR), str(root), "--out", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def initialize_identity(root: Path) -> None:
    audit = root / "audit"
    audit.mkdir(parents=True)
    (audit / "repo_identity.json").write_text(
        json.dumps(
            {
                "student_name": "권혁찬",
                "student_id": "2021194024",
                "pass": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_release_validator_allows_parent_folder_in_reference_provenance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "research_v2"
    initialize_identity(root)
    reference = root / "protocol" / "reference"
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

    result = run_validator(root)

    assert not any(
        str(item).startswith("yeo_marker:") for item in result["failures"]
    )


def test_release_validator_rejects_active_yeo_marker(tmp_path: Path) -> None:
    root = tmp_path / "research_v2"
    initialize_identity(root)
    active = root / "screening"
    active.mkdir()
    (active / "notes.md").write_text("여형준 2020194025", encoding="utf-8")

    result = run_validator(root)

    assert "yeo_marker:screening\\notes.md" in result["failures"]
