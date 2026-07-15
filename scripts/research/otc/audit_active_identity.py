from __future__ import annotations

import json
import re
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
EXPECTED_RESEARCHER = "권혁찬"
EXPECTED_STUDENT_ID = "2021194024"
FORBIDDEN = ("여형준", "항응고제 복용자 중심 연구", "신장 관련 고위험군 중심 연구")
TEXT_SUFFIXES = {".md", ".csv", ".json", ".html"}


def docx_text(path: Path) -> str:
    with ZipFile(path) as archive:
        return "\n".join(
            re.sub(r"<[^>]+>", "", archive.read(name).decode("utf-8", errors="ignore"))
            for name in archive.namelist() if name == "word/document.xml"
        )


def active_files() -> list[Path]:
    files = [
        ROOT / "research_v3/thesis/otc_thesis_working.md",
        ROOT / "research_v3/thesis/권혁찬_졸업논문_OTC_작업본.docx",
        ROOT / "research_v3/protocol/otc_research_plan_working.md",
        ROOT / "research_v3/protocol/권혁찬_OTC_연구계획서_작업본.docx",
        ROOT / "research_v3/reports/FINAL_RESEARCH_REPORT.md",
    ]
    for path in OTC.rglob("*"):
        relative_parts = {part.lower() for part in path.relative_to(OTC).parts}
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not relative_parts.intersection({"raw", "extracted", "etc", "audit"}):
            files.append(path)
    return sorted(set(files))


def audit() -> dict[str, object]:
    contamination = []
    identity_documents = {}
    files = active_files()
    for path in files:
        text = docx_text(path) if path.suffix.lower() == ".docx" else path.read_text(encoding="utf-8-sig", errors="replace")
        relative = path.relative_to(ROOT).as_posix()
        for term in FORBIDDEN:
            if term in text:
                contamination.append({"path": relative, "term": term})
        if path.name in {"otc_thesis_working.md", "FINAL_RESEARCH_REPORT.md", "권혁찬_졸업논문_OTC_작업본.docx"}:
            identity_documents[relative] = {"researcher_present": EXPECTED_RESEARCHER in text, "student_id_present": EXPECTED_STUDENT_ID in text}
    valid_identity = bool(identity_documents) and all(item["researcher_present"] and item["student_id_present"] for item in identity_documents.values())
    return {
        "schema_version": "1.0.0",
        "scope": "active_otc_authored_and_structured_outputs_excluding_official_raw_text_audit_and_legacy",
        "expected_identity": {"researcher": EXPECTED_RESEARCHER, "student_id": EXPECTED_STUDENT_ID},
        "inspected_files": len(files),
        "identity_documents": identity_documents,
        "cross_student_findings": contamination,
        "valid": valid_identity and not contamination,
    }


def main() -> int:
    result = audit()
    target = OTC / "audit" / "active_identity_audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid": result["valid"], "inspected_files": result["inspected_files"], "findings": len(result["cross_student_findings"])}, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
