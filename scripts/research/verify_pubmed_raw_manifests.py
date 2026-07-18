from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(raw_root: Path) -> dict[str, object]:
    manifests = sorted(raw_root.rglob("raw_manifest.json"))
    runs: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_failures: list[dict[str, str]] = []
        for item in manifest.get("raw_files", []):
            path = manifest_path.parent / item["path"]
            if not path.exists():
                run_failures.append({"path": str(path), "error": "missing"})
                continue
            actual_size = path.stat().st_size
            actual_hash = sha256(path)
            if actual_size != item["size"] or actual_hash != item["sha256"]:
                run_failures.append({
                    "path": str(path),
                    "error": "integrity_mismatch",
                    "expected_sha256": item["sha256"],
                    "actual_sha256": actual_hash,
                })
        failures.extend(run_failures)
        runs.append({
            "node_id": manifest.get("node_id"),
            "manifest_path": str(manifest_path),
            "hit_count": manifest.get("hit_count"),
            "exported_count": manifest.get("exported_count"),
            "imported_count": manifest.get("imported_count"),
            "raw_file_count": len(manifest.get("raw_files", [])),
            "failures": len(run_failures),
        })
    return {
        "schema_version": "1.0.0",
        "manifest_count": len(manifests),
        "runs": runs,
        "failures": failures,
        "valid": bool(manifests) and not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.raw_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
