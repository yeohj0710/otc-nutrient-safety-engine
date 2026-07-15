from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
MODE = "codex_recommendations_confirmed_by_human_not_blinded_independent_review"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(data: dict, otc: Path = OTC) -> dict[str, object]:
    if data.get("research_direction") != "korean_otc_product_safety":
        raise ValueError("wrong_research_direction")
    if data.get("reviewer_id") != "FINAL-DECISION-001" or data.get("review_mode") != MODE or not data.get("approved_at"):
        raise ValueError("invalid_final_decision_identity")

    rules = rows(otc / "rules" / "rules.csv")
    scenarios = rows(otc / "validation" / "independent_scenarios.csv")
    expected_rules = {
        row["rule_id"]: "revise" if row["rule_id"] == "OTC-RULE-015" else "approve"
        for row in rules
    }
    expected_scenarios = {
        row["scenario_id"]: "0" if row["scenario_family"] in {"normal_use", "unsupported_product"} else "1"
        for row in scenarios
    }
    received_rules = {key: value.get("decision") for key, value in data.get("rule_decisions", {}).items()}
    received_scenarios = {key: value.get("decision") for key, value in data.get("scenario_decisions", {}).items()}
    if received_rules != expected_rules:
        raise ValueError("rule_decisions_do_not_match_presented_final_draft")
    if received_scenarios != expected_scenarios:
        raise ValueError("scenario_decisions_do_not_match_presented_final_draft")
    return {
        "confirmed_rule_recommendations": len(received_rules),
        "confirmed_scenario_recommendations": len(received_scenarios),
        "counts_as_pharmacist_expert_review": False,
        "counts_as_blinded_independent_scenario_labeling": False,
    }


def import_confirmation(source: Path, otc: Path = OTC) -> dict[str, object]:
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    result = validate(data, otc)
    submissions = otc / "review" / "submissions"
    submissions.mkdir(parents=True, exist_ok=True)
    target = submissions / "final_decision_confirmation.json"
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = otc / "etc" / "review_submission_backups" / f"final_decision_confirmation_before_{stamp}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
    target.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest().upper()
    receipt = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "reviewer_id": data["reviewer_id"],
        "approved_at": data["approved_at"],
        "submission": target.relative_to(ROOT).as_posix(),
        "submission_sha256": digest,
        **result,
        "review_mode": MODE,
        "status": "final_decision_confirmation_recorded",
    }
    receipt_path = otc / "review" / "final_decision_confirmation_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and record the non-blinded final decision confirmation")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(import_confirmation(args.source), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
