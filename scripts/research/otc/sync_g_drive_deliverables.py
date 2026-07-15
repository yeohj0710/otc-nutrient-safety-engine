from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
AUDIT = OTC / "audit" / "g_drive_working_sync_verification.json"
G_ROOT = Path(r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_pairs() -> list[tuple[Path, Path]]:
    return [
        (
            ROOT / "research_v3" / "thesis" / "권혁찬_졸업논문_최종본.docx",
            G_ROOT / "01_논문_최종본" / "권혁찬_졸업논문_최종본.docx",
        ),
        (
            ROOT / "research_v3" / "thesis" / "권혁찬_졸업논문_최종본.pdf",
            G_ROOT / "01_논문_최종본" / "권혁찬_졸업논문_최종본.pdf",
        ),
        (
            ROOT / "research_v3" / "protocol" / "권혁찬_OTC_연구계획서_최종본.docx",
            G_ROOT / "02_연구계획서_최종본" / "권혁찬_OTC_연구계획서_최종본.docx",
        ),
        (
            ROOT / "research_v3" / "protocol" / "권혁찬_OTC_연구계획서_최종본.pdf",
            G_ROOT / "02_연구계획서_최종본" / "권혁찬_OTC_연구계획서_최종본.pdf",
        ),
    ]


def supplemental_pairs() -> list[tuple[Path, Path]]:
    destination = G_ROOT / "07_OTC_작업본_외부검토패키지" / "03_보고서_및_검증"
    return [
        (ROOT / "research_v3" / "reports" / "GATE_0_10_REPORT.md", destination / "GATE_0_10_REPORT.md"),
        (OTC / "audit" / "completion_audit.json", destination / "completion_audit.json"),
        (OTC / "audit" / "document_visual_qa.json", destination / "document_visual_qa.json"),
        (OTC / "audit" / "production_deployment_receipt.json", destination / "production_deployment_receipt.json"),
        (OTC / "audit" / "runtime_research_alignment.json", destination / "runtime_research_alignment.json"),
        (OTC / "audit" / "software_validation.json", destination / "software_validation.json"),
    ]


def load_existing_pairs() -> list[tuple[Path, Path]]:
    if not AUDIT.exists():
        return []
    previous = json.loads(AUDIT.read_text(encoding="utf-8-sig"))
    pairs: list[tuple[Path, Path]] = []
    for item in previous.get("files", []):
        source = Path(item["source"])
        destination = Path(item["destination"])
        if source.exists() and destination not in {target for _, target in canonical_pairs()}:
            pairs.append((source, destination))
    return pairs


def main() -> int:
    pairs = load_existing_pairs() + supplemental_pairs() + canonical_pairs()
    deduplicated: dict[str, tuple[Path, Path]] = {str(destination).casefold(): (source, destination) for source, destination in pairs}
    files: list[dict[str, object]] = []
    for source, destination in deduplicated.values():
        if not source.is_file():
            files.append({"source": str(source), "destination": str(destination), "match": False, "error": "source_missing"})
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        source_hash = digest(source)
        destination_hash = digest(destination)
        files.append(
            {
                "source": str(source),
                "destination": str(destination),
                "source_sha256": source_hash,
                "destination_sha256": destination_hash,
                "match": source_hash == destination_hash,
            }
        )
    valid = bool(files) and all(item.get("match") is True for item in files)
    report = {
        "schema_version": "2.0.0",
        "research_direction": "korean_otc_product_safety",
        "scope": "working_review_package_and_canonical_final_documents",
        "synced_at": datetime.now().astimezone().isoformat(),
        "destination": str(G_ROOT),
        "canonical_final_documents_synced": all(
            any(Path(item["destination"]) == destination and item.get("match") is True for item in files)
            for _, destination in canonical_pairs()
        ),
        "file_count": len(files),
        "files": files,
        "valid": valid,
    }
    AUDIT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid": valid, "file_count": len(files), "canonical_final_documents_synced": report["canonical_final_documents_synced"]}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
