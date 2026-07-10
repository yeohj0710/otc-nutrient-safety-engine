from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = REPO_ROOT / "research_v2"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_protocol_and_search_preflight_cover_all_five_nodes() -> None:
    eligibility = json.loads(
        (RESEARCH_ROOT / "protocol" / "eligibility.json").read_text(encoding="utf-8")
    )
    strategies = read_csv(RESEARCH_ROOT / "search" / "search_strategies.csv")
    seeds = read_csv(RESEARCH_ROOT / "search" / "seed_candidates.csv")

    expected_nodes = {"K1", "K2", "K3", "K4", "K5"}
    assert {node["node_id"] for node in eligibility["nodes"]} == expected_nodes
    assert {row["node_id"] for row in strategies} == expected_nodes
    assert {row["node_id"] for row in seeds} == expected_nodes
    assert len(strategies) == 5
    assert len(seeds) == 22
    assert Counter(row["node_id"] for row in seeds) == {
        "K1": 5,
        "K2": 4,
        "K3": 4,
        "K4": 5,
        "K5": 4,
    }


def test_preflight_query_hashes_and_limits_are_consistent() -> None:
    report = json.loads(
        (RESEARCH_ROOT / "search" / "preflight_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "preflight_ready_not_executed"
    assert report["search_limits"]["top_n_allowed_for_gate2"] is False
    assert report["environment"]["final_search_executed"] is False
    assert report["human_dependencies"] == ["H-001", "H-002", "H-003", "H-007"]

    for query in report["queries"]:
        path = REPO_ROOT / query["path"]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == query["sha256"]
        assert query["parentheses_balanced"] is True


def test_ai_prompt_manifest_is_frozen_without_claiming_a_model_run() -> None:
    manifest = json.loads(
        (RESEARCH_ROOT / "ai_eval" / "prompt_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "prompts_frozen_model_not_selected"
    assert manifest["held_out_tuning_prohibited"] is True
    assert manifest["run_executed"] is False
    assert manifest["model"] is None
    for prompt in manifest["prompts"]:
        path = REPO_ROOT / prompt["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == prompt["sha256"]
