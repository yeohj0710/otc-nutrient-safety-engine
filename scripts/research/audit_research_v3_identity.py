from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


EXPECTED = {
    "researcher": "권혁찬",
    "student_id": "2021194024",
    "protocol_sha256": "21FC2B391868EC5F337B8327F1A82108BBED6F097D32CE7E9F33CE3DE7879AA5",
    "protocol_title": "일반의약품형 고함량 영양성분의 함량 기준 안전성 평가와 개인맞춤 조회 도구 구축",
}

FORBIDDEN = (
    "여형준",
    "항응고제 복용자 중심 연구",
    "신장 관련 고위험군 중심 연구",
)

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".ts", ".tsx", ".py"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def docx_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not re.fullmatch(r"word/(document|header\d*|footer\d*)\.xml", name):
                continue
            root = ElementTree.fromstring(archive.read(name))
            texts.extend(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    return "\n".join(texts)


def readable_text(path: Path) -> str | None:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    if path.suffix.lower() in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    return None


def is_audit_evidence_path(relative: str, path: Path) -> bool:
    normalized = f"/{relative.lower()}/"
    name = path.name.casefold()
    return (
        "/audit/" in normalized
        or normalized.startswith("/04_재현코드/")
        or name == "reproduce.md"
        or name.endswith("verification_report.json")
        or name.endswith("audit_report.json")
    )


def audit(protocol: Path, delivery_root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    actual_hash = sha256(protocol)
    checks.append({
        "check": "protocol_sha256",
        "status": "pass" if actual_hash == EXPECTED["protocol_sha256"] else "fail",
        "expected": EXPECTED["protocol_sha256"],
        "actual": actual_hash,
    })

    protocol_text = docx_text(protocol)
    checks.append({
        "check": "protocol_title",
        "status": "pass" if EXPECTED["protocol_title"] in protocol_text else "fail",
        "expected": EXPECTED["protocol_title"],
    })
    checks.append({
        "check": "protocol_researcher",
        "status": "pass" if EXPECTED["researcher"] in protocol_text else "fail",
        "expected": EXPECTED["researcher"],
    })
    checks.append({
        "check": "protocol_student_id",
        "status": "pass" if EXPECTED["student_id"] in protocol_text else "human_action_required",
        "expected": EXPECTED["student_id"],
        "actual": "present" if EXPECTED["student_id"] in protocol_text else "absent_or_blank",
    })

    contamination: list[dict[str, str]] = []
    audit_context_mentions: list[dict[str, str]] = []
    old_lineage_mentions: list[str] = []
    inspected = 0
    for path in sorted(delivery_root.rglob("*")):
        if not path.is_file() or "etc" in {part.lower() for part in path.parts}:
            continue
        text = readable_text(path)
        if text is None:
            continue
        inspected += 1
        relative = path.relative_to(delivery_root).as_posix()
        is_audit_evidence = is_audit_evidence_path(relative, path)
        for term in FORBIDDEN:
            if term in text:
                finding = {"path": relative, "term": term}
                if is_audit_evidence:
                    audit_context_mentions.append(finding)
                else:
                    contamination.append(finding)
        if "research_v2" in text:
            old_lineage_mentions.append(relative)

    checks.append({
        "check": "cross_student_contamination",
        "status": "pass" if not contamination else "fail",
        "findings": contamination,
        "audit_context_mentions_excluded": audit_context_mentions,
    })
    checks.append({
        "check": "old_lineage_mentions",
        "status": "pass",
        "findings": sorted(set(old_lineage_mentions)),
        "interpretation": "provenance references are allowed; active research lineage is checked separately",
    })

    failed = [item for item in checks if item["status"] == "fail"]
    human = [item for item in checks if item["status"] in {"human_action_required", "review_required"}]
    return {
        "schema_version": "1.0.0",
        "expected_identity": EXPECTED,
        "protocol": str(protocol),
        "delivery_root": str(delivery_root),
        "inspected_text_files": inspected,
        "checks": checks,
        "summary": {
            "failed": len(failed),
            "human_or_review_required": len(human),
            "release_ready": not failed and not human,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--delivery-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit(args.protocol.resolve(), args.delivery_root.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
