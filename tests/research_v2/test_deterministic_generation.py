from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "src" / "generated" / "literature-candidates.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_literature_candidate_generation_is_deterministic() -> None:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    assert npm is not None

    subprocess.run(
        [npm, "run", "prepare:knowledge"], cwd=REPO_ROOT, check=True, capture_output=True
    )
    first = file_hash(OUTPUT)
    subprocess.run(
        [npm, "run", "prepare:knowledge"], cwd=REPO_ROOT, check=True, capture_output=True
    )
    second = file_hash(OUTPUT)

    assert first == second


def test_literature_candidates_use_active_project_identity() -> None:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    assert npm is not None

    subprocess.run(
        [npm, "run", "prepare:knowledge"], cwd=REPO_ROOT, check=True, capture_output=True
    )
    generated = json.loads(OUTPUT.read_text(encoding="utf-8"))
    identity = json.loads(
        (REPO_ROOT / "research_v2" / "project_identity.json").read_text(
            encoding="utf-8"
        )
    )

    assert generated["summary"]["studyLabel"] == identity["student_name"] == "권혁찬"
    assert generated["summary"]["studyId"] == identity["study_slug"]
    assert "여형준" not in OUTPUT.read_text(encoding="utf-8")
