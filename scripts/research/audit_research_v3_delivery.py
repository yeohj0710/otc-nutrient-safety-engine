from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_ROOT = {
    "00_먼저_읽기.md", "01_논문", "02_핵심보고서", "03_연구데이터_research_v3",
    "04_재현코드", "05_웹사이트", "06_레퍼런스", "etc",
}
REQUIRED_REPORTS = {
    "FINAL_RESEARCH_REPORT.md", "GATE_0_10_REPORT.md", "HUMAN_ACTION_REQUIRED.md", "metrics_manifest.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    present = {item.name for item in root.iterdir() if item.name.lower() != "desktop.ini"}
    for name in sorted(REQUIRED_ROOT - present):
        errors.append({"code": "MISSING_ROOT_ITEM", "path": name})
    active_v2 = [item.name for item in root.iterdir() if "research_v2" in item.name.lower()]
    for name in active_v2:
        errors.append({"code": "ACTIVE_RESEARCH_V2_AT_ROOT", "path": name})
    reports = root / "02_핵심보고서"
    if reports.exists():
        for name in sorted(REQUIRED_REPORTS - {item.name for item in reports.iterdir()}):
            errors.append({"code": "MISSING_CORE_REPORT", "path": f"02_핵심보고서/{name}"})
    thesis = root / "01_논문"
    expected_docx = thesis / "권혁찬_졸업논문_최종본.docx"
    expected_pdf = thesis / "권혁찬_졸업논문_최종본.pdf"
    for path in (expected_docx, expected_pdf):
        if not path.exists():
            errors.append({"code": "CANONICAL_FINAL_THESIS_MISSING", "path": str(path.relative_to(root))})
    visible_theses = [item for item in thesis.glob("권혁찬_졸업논문_*") if item.suffix.lower() in {".docx", ".pdf"}]
    noncanonical = [item for item in visible_theses if item not in {expected_docx, expected_pdf}]
    for path in noncanonical:
        warnings.append({"code": "VISIBLE_NONCANONICAL_THESIS", "path": str(path.relative_to(root))})
    metrics_paths = [
        root / "02_핵심보고서" / "metrics_manifest.json",
        root / "03_연구데이터_research_v3" / "metrics_manifest.json",
    ]
    existing_metrics = [path for path in metrics_paths if path.exists()]
    hashes = {str(path.relative_to(root)): sha256(path) for path in existing_metrics}
    if len(set(hashes.values())) > 1:
        errors.append({"code": "METRICS_HASH_MISMATCH", "path": json.dumps(hashes, ensure_ascii=False)})
    legacy = root / "etc" / "영양성분_구방향_20260713" / "research_v2"
    if not legacy.exists():
        errors.append({"code": "LEGACY_ISOLATION_MISSING", "path": str(legacy.relative_to(root))})
    return {
        "schema_version": "1.0.0", "root": str(root), "errors": errors, "warnings": warnings,
        "metrics_sha256": hashes, "valid": not errors,
        "release_ready": not errors and not warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
