from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"


SECTION_ROLES = {
    "draft_rules": "pharmacist_expert",
    "independent_scenarios": "independent_scenario_reviewer",
    "official_candidates": "research_advisor",
    "normalization_reference": "normalization_reviewer",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, records: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def merge_existing(path: Path, records: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    merged = {row[key]: row for row in rows(path)} if path.exists() else {}
    merged.update({row[key]: row for row in records})
    return [merged[item_id] for item_id in sorted(merged)]


def import_result(data: dict, otc: Path = OTC) -> dict[str, int]:
    if data.get("research_direction") != "korean_otc_product_safety":
        raise ValueError("wrong_research_direction")
    reviewer = data.get("reviewer", {})
    reviewer_id = str(reviewer.get("reviewer_id", "")).strip()
    reviewer_role = str(reviewer.get("reviewer_role", "")).strip()
    reviewed_at = str(reviewer.get("reviewed_at", "")).strip()
    if not reviewer_id or not reviewed_at or reviewer_role not in set(SECTION_ROLES.values()):
        raise ValueError("invalid_reviewer_identity")

    current_rules = rows(otc / "rules" / "rules.csv")
    current_scenarios = rows(otc / "validation" / "independent_scenarios.csv")
    current_candidates = rows(otc / "selection" / "official_designation_candidates.csv")
    normalization_path = otc / "validation" / "normalization_reference.csv"
    current_normalization = rows(normalization_path) if normalization_path.exists() else []
    valid_ids = {
        "draft_rules": {row["rule_id"] for row in current_rules},
        "independent_scenarios": {row["scenario_id"] for row in current_scenarios},
        "official_candidates": {row["candidate_id"] for row in current_candidates},
        "normalization_reference": {row["ingredient_id"] for row in current_normalization},
    }

    parsed: list[tuple[str, str, dict]] = []
    for key, decision in data.get("human_decisions", {}).items():
        if ":" not in key or not isinstance(decision, dict):
            raise ValueError(f"invalid_decision_key:{key}")
        section, item_id = key.split(":", 1)
        if section not in SECTION_ROLES:
            continue
        if SECTION_ROLES[section] != reviewer_role:
            raise ValueError(f"reviewer_role_mismatch:{section}")
        if item_id not in valid_ids[section]:
            raise ValueError(f"unknown_item:{section}:{item_id}")
        parsed.append((section, item_id, decision))

    rule_reviews = []
    candidate_reviews = []
    scenario_decisions: dict[str, dict] = {}
    normalization_decisions: dict[str, dict] = {}
    for section, item_id, item in parsed:
        decision = str(item.get("decision", "")).strip()
        comment = str(item.get("comment", "")).strip()
        if section == "draft_rules":
            if decision not in {"approve", "revise", "reject"}:
                raise ValueError(f"invalid_rule_decision:{item_id}")
            rule_reviews.append({
                "rule_id": item_id, "decision": decision, "comment": comment,
                "reviewer_id": reviewer_id, "reviewer_role": reviewer_role,
                "reviewed_at": reviewed_at, "review_status": "human_expert_recorded_not_promoted",
                "supports_release": "false",
            })
        elif section == "official_candidates":
            if decision not in {"include_for_verification", "hold", "exclude"}:
                raise ValueError(f"invalid_candidate_decision:{item_id}")
            candidate_reviews.append({
                "candidate_id": item_id, "decision": decision, "comment": comment,
                "reviewer_id": reviewer_id, "reviewer_role": reviewer_role, "reviewed_at": reviewed_at,
            })
        elif section == "independent_scenarios":
            if decision not in {"0", "1", "uncertain"}:
                raise ValueError(f"invalid_scenario_decision:{item_id}")
            scenario_decisions[item_id] = {"decision": decision, "comment": comment}
        else:
            if decision not in {"correct", "incorrect", "uncertain"}:
                raise ValueError(f"invalid_normalization_decision:{item_id}")
            if decision == "incorrect" and not comment:
                raise ValueError(f"corrected_normalized_name_required:{item_id}")
            normalization_decisions[item_id] = {"decision": decision, "comment": comment}

    if reviewer_role == "pharmacist_expert":
        target = otc / "review" / "expert_rule_review.csv"
        write(target, merge_existing(target, rule_reviews, "rule_id"), [
            "rule_id", "decision", "comment", "reviewer_id", "reviewer_role", "reviewed_at", "review_status", "supports_release",
        ])
    elif reviewer_role == "research_advisor":
        target = otc / "review" / "candidate_review.csv"
        write(target, merge_existing(target, candidate_reviews, "candidate_id"), [
            "candidate_id", "decision", "comment", "reviewer_id", "reviewer_role", "reviewed_at",
        ])
    elif reviewer_role == "independent_scenario_reviewer":
        review_method = str(data.get("review_method", "independent_blind_human_adjudication")).strip()
        predictions_exposed = str(data.get("predictions_exposed", 0))
        independent_blinding = str(bool(data.get("independent_blinding", review_method == "independent_blind_human_adjudication"))).lower()
        scenario_by_id = {row["scenario_id"]: row for row in current_scenarios}
        for item_id, item in scenario_decisions.items():
            existing = scenario_by_id[item_id].get("human_reference_label", "")
            if existing and item["decision"] != existing:
                raise ValueError(f"scenario_label_already_locked:{item_id}")
        for row in current_scenarios:
            item = scenario_decisions.get(row["scenario_id"])
            if not item:
                continue
            if row.get("human_reference_label") == item["decision"]:
                continue
            if item["decision"] in {"0", "1"}:
                row["human_reference_label"] = item["decision"]
                row["human_reviewer_id"] = reviewer_id
                row["human_reviewed_at"] = reviewed_at
                row["review_method"] = review_method
                row["predictions_exposed"] = predictions_exposed
                row["independent_blinding"] = independent_blinding
                row["status"] = "human_label_locked_awaiting_prediction" if independent_blinding == "true" else "assisted_human_confirmation_awaiting_prediction"
            else:
                row["status"] = "human_uncertain_requires_adjudication"
        fields = list(current_scenarios[0])
        for field in ("review_method", "predictions_exposed", "independent_blinding"):
            if field not in fields:
                fields.append(field)
        write(otc / "validation" / "independent_scenarios.csv", current_scenarios, fields)
    else:
        for row in current_normalization:
            item = normalization_decisions.get(row["ingredient_id"])
            if not item:
                continue
            if row.get("human_reference_name"):
                proposed = row["system_normalized_name"] if item["decision"] == "correct" else item["comment"]
                if item["decision"] != "uncertain" and proposed != row["human_reference_name"]:
                    raise ValueError(f"normalization_reference_already_locked:{row['ingredient_id']}")
                continue
            if item["decision"] == "uncertain":
                row["status"] = "human_uncertain_requires_adjudication"
            else:
                row["human_reference_name"] = row["system_normalized_name"] if item["decision"] == "correct" else item["comment"]
                row["human_reviewer_id"] = reviewer_id
                row["human_reviewed_at"] = reviewed_at
                row["status"] = "human_reference_locked"
        write(normalization_path, current_normalization, list(current_normalization[0]))

    return {
        "rule_reviews": len(rule_reviews),
        "candidate_reviews": len(candidate_reviews),
        "scenario_labels": sum(item["decision"] in {"0", "1"} for item in scenario_decisions.values()),
        "scenario_uncertain": sum(item["decision"] == "uncertain" for item in scenario_decisions.values()),
        "rules_promoted": 0,
        "normalization_labels": sum(item["decision"] in {"correct", "incorrect"} for item in normalization_decisions.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a human OTC review result without promoting rules")
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    data = json.loads(args.result.read_text(encoding="utf-8"))
    print(json.dumps(import_result(data), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
