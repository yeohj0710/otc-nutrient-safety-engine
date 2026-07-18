from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "audit_research_v3_identity.py"
SPEC = importlib.util.spec_from_file_location("audit_research_v3_identity", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_forbidden_student_terms_are_explicit() -> None:
    assert "여형준" in MODULE.FORBIDDEN
    assert MODULE.EXPECTED["researcher"] == "권혁찬"
    assert MODULE.EXPECTED["student_id"] == "2021194024"


def test_sha256_is_uppercase(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("abc", encoding="utf-8")
    assert MODULE.sha256(source) == (
        "BA7816BF8F01CFEA414140DE5DAE2223"
        "B00361A396177A9CB410FF61F20015AD"
    )


def test_readable_text_handles_utf8_bom(tmp_path: Path) -> None:
    source = tmp_path / "record.csv"
    source.write_text("연구자,권혁찬\n", encoding="utf-8-sig")
    assert MODULE.readable_text(source) == "연구자,권혁찬\n"


def test_package_verification_report_is_audit_context() -> None:
    path = Path("02_핵심보고서/package_verification_report.json")
    assert MODULE.is_audit_evidence_path(path.as_posix(), path)
    ordinary = Path("02_핵심보고서/FINAL_RESEARCH_REPORT.md")
    assert not MODULE.is_audit_evidence_path(ordinary.as_posix(), ordinary)
