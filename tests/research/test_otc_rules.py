import csv
from pathlib import Path

import pytest

from scripts.research.otc.validate_rules import validate


ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"


def test_reviewed_rule_release_state_and_evidence_linkage() -> None:
    report = validate(RULES)
    assert report == {
        "rules_total": 16,
        "rules_draft": 1,
        "rules_released": 15,
        "released_source_locator_rate": 1.0,
    }


def test_validator_rejects_released_rule_without_source_locator(tmp_path: Path) -> None:
    with RULES.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["status"] = "released"
    rows[0]["source_locator"] = ""
    path = tmp_path / "rules.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="released_without_source_locator"):
        validate(path)
