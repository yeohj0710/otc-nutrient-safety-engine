from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SOURCES = {
    "NIH_ODS_VITAMIN_D_HP": ("VitaminD-HealthProfessional", "Office of Dietary Supplements - Vitamin D"),
    "NIH_ODS_CALCIUM_HP": ("Calcium-HealthProfessional", "Office of Dietary Supplements - Calcium"),
    "NIH_ODS_VITAMIN_B6_HP": ("VitaminB6-HealthProfessional", "Office of Dietary Supplements - Vitamin B6"),
    "NIH_ODS_MAGNESIUM_HP": ("Magnesium-HealthProfessional", "Office of Dietary Supplements - Magnesium"),
    "NIH_ODS_IRON_HP": ("Iron-HealthProfessional", "Office of Dietary Supplements - Iron"),
    "NIH_ODS_ZINC_HP": ("Zinc-HealthProfessional", "Office of Dietary Supplements - Zinc"),
}


def build(raw_root: Path) -> dict[str, object]:
    records = []
    for source_id, (slug, expected_title) in SOURCES.items():
        path = raw_root / f"{source_id}.web_text.md"
        data = path.read_bytes()
        text = data.decode("utf-8")
        source_url = f"http://ods.od.nih.gov/factsheets/{slug}/"
        valid = (
            f"Title: {expected_title}" in text
            and f"URL Source: {source_url}" in text
            and "## Table of Contents" in text
            and "Health Professional" in text
        )
        records.append(
            {
                "source_id": source_id,
                "official_url": source_url.replace("http://", "https://"),
                "local_path": path.as_posix(),
                "capture_method": "r.jina.ai read-only text proxy",
                "artifact_type": "derived_web_text_not_original_html",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "validation_passed": valid,
            }
        )
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim_boundary": "Text snapshots support reading and locator checks; they are not direct NIH HTML originals.",
        "records": records,
        "summary": {
            "total": len(records),
            "validated": sum(bool(record["validation_passed"]) for record in records),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.raw_root.resolve())
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["summary"]["validated"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
