from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def fetch(registry_path: Path, output_dir: Path, manifest_path: Path) -> dict[str, object]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for source in registry["sources"]:
        request = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "KwonHyukchanResearchV3/1.0 evidence-archiving"},
        )
        record: dict[str, object] = {"source_id": source["source_id"], "url": source["url"]}
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
                content_type = response.headers.get_content_type()
                suffix = source.get("output_extension") or (
                    ".pdf" if content_type == "application/pdf" else mimetypes.guess_extension(content_type) or ".bin"
                )
                if suffix in {".htm", ".shtml"}:
                    suffix = ".html"
                path = output_dir / f"{source['source_id']}{suffix}"
                path.write_bytes(payload)
                record.update({
                    "status": "fetched",
                    "final_url": response.geturl(),
                    "http_status": response.status,
                    "content_type": content_type,
                    "path": str(path),
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                })
        except Exception as exc:  # network failures are evidence, not silent omissions
            record.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        records.append(record)
    report = {
        "schema_version": "1.0.0",
        "fetched_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "records": records,
        "summary": {
            "total": len(records),
            "fetched": sum(item["status"] == "fetched" for item in records),
            "failed": sum(item["status"] == "failed" for item in records),
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    report = fetch(args.registry.resolve(), args.output_dir.resolve(), args.manifest.resolve())
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
