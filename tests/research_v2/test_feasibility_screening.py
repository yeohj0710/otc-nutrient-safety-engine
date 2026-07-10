from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "build_feasibility_screening.py"
SPEC = importlib.util.spec_from_file_location("build_feasibility_screening", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def record(pmid: str, node: str, title: str, abstract: str, doi: str = "") -> dict[str, str]:
    return {"pmid": pmid, "target_id": node, "search_run_id": f"run-{node}", "title": title, "abstract_or_summary": abstract, "year": "2024", "journal_or_source": "J", "doi": doi}


def test_cross_node_same_pmid_is_deduplicated() -> None:
    rows = {node: [] for node in MODULE.NODES}
    rows["K1"] = [record("1", "K1", "Trial", "Adult oral supplement adverse event")]
    rows["K4"] = [record("1", "K4", "Trial", "Adult oral supplement adverse event")]
    records, duplicates, screening = MODULE.consolidate(rows)
    assert len(records) == 2
    assert len(duplicates) == 1
    assert len(screening) == 1
    assert screening[0]["clinical_node_candidates"] == "K1;K4"


def test_explicit_animal_only_signal_can_be_exclusion_candidate() -> None:
    result = MODULE.screen_record(
        {"title": "Vitamin D toxicity in mice", "abstract_or_summary": "Animal study in mice."},
        ["K1"],
    )
    assert result["proposal"] == "explicit_exclude_candidate"
    assert "animal_only_signal" in result["explicit_exclusion_flags"]


def test_missing_information_is_retained_not_auto_excluded() -> None:
    result = MODULE.screen_record(
        {"title": "Vitamin B6 and neuropathy", "abstract_or_summary": "Association reported."},
        ["K2"],
    )
    assert result["proposal"] == "retain_uncertain"
    assert result["rationale"].startswith("insufficient explicit information")
