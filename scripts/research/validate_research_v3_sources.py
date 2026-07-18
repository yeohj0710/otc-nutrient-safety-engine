from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(root: Path) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    registry = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
    registry_ids = {item["source_id"] for item in registry["sources"]}
    fetch = json.loads((root / "fetch_manifest_20260713.json").read_text(encoding="utf-8"))
    fetched_ids: set[str] = set()
    for record in fetch["records"]:
        if record["status"] != "fetched":
            warnings.append({"code": "SOURCE_FETCH_FAILED", "source_id": record["source_id"]})
            continue
        path = Path(record["path"])
        fetched_ids.add(record["source_id"])
        if not path.exists() or sha256(path) != record["sha256"]:
            errors.append({"code": "FETCH_INTEGRITY", "source_id": record["source_id"]})
        extension = path.suffix.lower()
        head = path.read_bytes()[:4]
        if extension == ".pdf" and head != b"%PDF":
            errors.append({"code": "PDF_MAGIC", "source_id": record["source_id"]})
        if extension == ".zip" and head[:2] != b"PK":
            errors.append({"code": "ZIP_MAGIC", "source_id": record["source_id"]})

    with (root / "normative_candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    for row in candidates:
        if row["source_id"] not in registry_ids:
            errors.append({"code": "UNKNOWN_SOURCE", "source_id": row["source_id"]})
        if not row["locator"].strip():
            errors.append({"code": "MISSING_LOCATOR", "source_id": row["source_id"]})
        if row["review_status"] == "released":
            errors.append({"code": "CANDIDATE_RELEASE_STATE", "source_id": row["source_id"]})

    archive = json.loads((root / "kdri_archive_contents_manifest.json").read_text(encoding="utf-8"))
    archive_root = root / "raw" / "20260713" / "KNS_KDRI_2025_BOOKS_CORRECTED_F4"
    for item in archive["files"]:
        path = archive_root / item["name"]
        if not path.exists() or path.stat().st_size != item["bytes"] or sha256(path).upper() != item["sha256"]:
            errors.append({"code": "KDRI_ARCHIVE_INTEGRITY", "path": item["name"]})

    return {
        "schema_version": "1.0.0",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "registered_sources": len(registry_ids),
            "fetched_sources": len(fetched_ids),
            "normative_candidates": len(candidates),
            "kdri_archive_files": len(archive["files"]),
        },
        "valid": not errors,
        "release_ready": not errors and not warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3/sources"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
