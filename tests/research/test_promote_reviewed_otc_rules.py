import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "otc" / "promote_reviewed_rules.py"
SPEC = importlib.util.spec_from_file_location("promote_reviewed_otc_rules", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def write(path: Path, fields: list[str], records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def fixture(tmp_path: Path, rule_type: str = "max_daily_dose", with_binding: bool = True) -> Path:
    otc = tmp_path / "otc"
    write(otc / "rules/rules.csv", ["rule_id", "rule_type", "status", "source_id", "source_locator"], [{"rule_id": "R1", "rule_type": rule_type, "status": "draft", "source_id": "MFDS", "source_locator": "제품 · PDF p.1, 문단 2"}])
    write(otc / "review/expert_rule_review.csv", ["rule_id", "decision", "reviewer_role"], [{"rule_id": "R1", "decision": "approve", "reviewer_role": "pharmacist_expert"}])
    write(otc / "rules/rule_evidence_shortlist.csv", ["rule_id", "recommendation", "source_id", "source_locator", "evidence_text", "review_status", "supports_release"], [{"rule_id": "R1", "recommendation": "recommended_primary", "source_id": "MFDS", "source_locator": "PDF p.1, 문단 2", "evidence_text": "근거", "review_status": "candidate", "supports_release": "false"}])
    bindings = [{"rule_id": "R1", "binding_status": "candidate", "supports_release": "false"}] if with_binding else []
    write(otc / "rules/runtime_rule_bindings.csv", ["rule_id", "binding_status", "supports_release"], bindings)
    return otc


def test_default_assessment_never_mutates(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    before = (otc / "rules/rules.csv").read_bytes()
    result = MODULE.promote(otc)
    assert result["eligible_rule_ids"] == ["R1"] and result["applied"] is False
    assert (otc / "rules/rules.csv").read_bytes() == before


def test_binding_dependent_rule_cannot_release_without_binding(tmp_path: Path) -> None:
    result = MODULE.promote(fixture(tmp_path, with_binding=False), apply=True)
    assert "runtime_binding_missing" in result["blocked"]["R1"]
    assert result["promoted"] == 0


def test_evidence_locator_mismatch_blocks_release(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    records = list(csv.DictReader((otc / "rules/rules.csv").open(encoding="utf-8-sig")))
    records[0]["source_locator"] = "다른 위치"
    write(otc / "rules/rules.csv", list(records[0]), records)
    assert "rule_evidence_locator_mismatch" in MODULE.assess(otc)["blocked"]["R1"]


def test_apply_releases_only_eligible_rows_and_creates_backup(tmp_path: Path) -> None:
    otc = fixture(tmp_path)
    result = MODULE.promote(otc, apply=True)
    assert result["promoted"] == 1 and result["applied"] is True
    assert Path(result["backup"]).is_dir()
    assert list(csv.DictReader((otc / "rules/rules.csv").open(encoding="utf-8-sig")))[0]["status"] == "released"
    assert list(csv.DictReader((otc / "rules/runtime_rule_bindings.csv").open(encoding="utf-8-sig")))[0]["supports_release"] == "true"


def test_duplicate_rule_is_binding_free(tmp_path: Path) -> None:
    result = MODULE.promote(fixture(tmp_path, rule_type="duplicate_ingredient", with_binding=False))
    assert result["eligible_rule_ids"] == ["R1"]
