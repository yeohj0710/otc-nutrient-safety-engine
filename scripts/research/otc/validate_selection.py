from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SELECTION = ROOT / "research_v3" / "otc" / "selection"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(selection_dir: Path = SELECTION) -> dict[str, int]:
    sources = rows(selection_dir / "source_evidence.csv")
    classes = rows(selection_dir / "included_classes.csv")
    candidates = rows(selection_dir / "official_designation_candidates.csv")
    source_ids = {row["source_id"] for row in sources}
    errors = []
    for row in classes:
        refs = set(filter(None, row["source_ids"].split(";")))
        if not refs or not refs <= source_ids:
            errors.append(f"class_source:{row['class_id']}")
        if not row["rationale"].strip():
            errors.append(f"class_rationale:{row['class_id']}")
    for row in candidates:
        if row["designation_source_id"] not in source_ids:
            errors.append(f"candidate_source:{row['candidate_id']}")
        if row["candidate_status"] != "official_designation_candidate":
            errors.append(f"candidate_status:{row['candidate_id']}")
    protocol = (selection_dir / "selection_protocol.md").read_text(encoding="utf-8")
    if "판매량 상위" not in protocol or "표현하지 않는다" not in protocol:
        errors.append("unsupported_sales_rank_boundary")
    if errors:
        raise ValueError(";".join(errors))
    return {"sources": len(sources), "classes": len(classes), "official_candidates": len(candidates)}


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False))
