from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "build_search_strategy_peer_review_packet.py"
SPEC = importlib.util.spec_from_file_location("build_search_strategy_peer_review_packet", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_packet_has_all_strategies_and_no_prefilled_human_decisions() -> None:
    query_dir = Path(__file__).parents[2] / "research_v2" / "search" / "pubmed_queries"
    rows = MODULE.build(query_dir)
    assert len(rows) == 35
    assert {row["strategy_id"] for row in rows} == {"K1", "K2", "K3", "K4", "K5"}
    assert all(row["query_sha256"] for row in rows)
    assert all(row["status"] == "not_reviewed" for row in rows)
    assert all(not row["reviewer_id"] and not row["rating"] and not row["comment"] for row in rows)
