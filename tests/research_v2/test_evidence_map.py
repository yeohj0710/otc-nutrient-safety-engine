from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / "research" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAP = load("build_evidence_map", "build_evidence_map.py")
SELECT = load("select_focused_node", "select_focused_node.py")


def test_evidence_map_always_contains_five_nodes_and_verified_only() -> None:
    extractions = [
        {"clinical_node_id": "K1", "verification_status": "verified", "study_family_id": "S1", "report_id": "R1", "outcome_id": "O1", "study_design": "rct", "effect_measure": "RR", "effect_value": "1.2"},
        {"clinical_node_id": "K2", "verification_status": "unverified", "study_family_id": "S2", "report_id": "R2", "outcome_id": "O2"},
    ]
    rows = MAP.build(extractions, [])
    assert [row["clinical_node_id"] for row in rows] == ["K1", "K2", "K3", "K4", "K5"]
    assert rows[0]["verified_study_count"] == "1"
    assert rows[1]["verified_study_count"] == "0"


def test_focused_node_selection_requires_all_nodes_and_unique_winner() -> None:
    rows = []
    for index, node in enumerate(("K1", "K2", "K3", "K4", "K5"), start=1):
        score = "2" if node == "K3" else "1"
        rows.append({"clinical_node_id": node, **{criterion: score for criterion in SELECT.CRITERIA}, "reviewer_ids": "A;B"})
    result = SELECT.select(rows)
    assert result["pass"] is True
    assert result["selected_node"] == "K3"
    assert SELECT.select(rows[:4])["pass"] is False


def test_focused_node_tie_fails_closed() -> None:
    rows = [{"clinical_node_id": node, **{criterion: "1" for criterion in SELECT.CRITERIA}, "reviewer_ids": "A;B"} for node in ("K1", "K2", "K3", "K4", "K5")]
    result = SELECT.select(rows)
    assert result["pass"] is False
    assert "tie_requires_prespecified_human_adjudication" in result["validation_errors"]
