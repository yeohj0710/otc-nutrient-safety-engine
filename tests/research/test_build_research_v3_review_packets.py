from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "build_research_v3_review_packets.py"
SPEC = importlib.util.spec_from_file_location("build_research_v3_review_packets", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_packets_cover_all_unique_records_and_leave_decisions_blank(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    report = MODULE.build(
        root / "research_v2" / "screening" / "computational_screening.csv",
        root / "research_v2" / "extraction" / "abstract_evidence_shortlist.csv",
        tmp_path,
    )
    assert report["full_queue"]["rows"] == 15890
    assert report["full_queue"]["human_decisions_prefilled"] == 0
    assert report["priority_packet"]["rows"] == 118
    assert report["priority_packet"]["human_decisions_prefilled"] == 0
    with (tmp_path / "title_abstract_full_queue.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len({row["record_id"] for row in rows}) == 15890
    assert all(not row["human_decision"] for row in rows)
