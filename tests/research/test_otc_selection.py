import csv
from pathlib import Path

from scripts.research.otc.validate_selection import validate


ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "research_v3" / "otc" / "selection"


def read_rows(name: str):
    with (SELECTION / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_selection_sources_and_rationales_are_complete() -> None:
    assert validate(SELECTION) == {"sources": 6, "classes": 5, "official_candidates": 13}


def test_initial_candidates_are_not_mislabeled_as_sales_ranking_or_verified_products() -> None:
    candidates = read_rows("official_designation_candidates.csv")
    assert all(row["candidate_status"] == "official_designation_candidate" for row in candidates)
    assert all("판매량" not in row["candidate_status"] for row in candidates)
    assert all("item_sequence" not in row for row in candidates)


def test_all_required_initial_classes_are_explicit() -> None:
    classes = {row["class_id"]: row for row in read_rows("included_classes.csv")}
    assert set(classes) == {
        "OTC-CLASS-ANALGESIC",
        "OTC-CLASS-COLD",
        "OTC-CLASS-ANTIHISTAMINE",
        "OTC-CLASS-COUGH-DECONGESTANT",
        "OTC-CLASS-GI",
    }
    assert classes["OTC-CLASS-ANTIHISTAMINE"]["scope_status"] == "pending_authorization_evidence"
