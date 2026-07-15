from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
BINDING_FREE_TYPES = {"duplicate_ingredient", "duplicate_pharmacologic_class"}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, records: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def assess(otc: Path = OTC) -> dict[str, object]:
    rules = read(otc / "rules" / "rules.csv")
    reviews_path = otc / "review" / "expert_rule_review.csv"
    reviews = {row["rule_id"]: row for row in read(reviews_path)} if reviews_path.exists() else {}
    shortlist = read(otc / "rules" / "rule_evidence_shortlist.csv")
    primary = {row["rule_id"]: row for row in shortlist if row["recommendation"] == "recommended_primary"}
    bindings = read(otc / "rules" / "runtime_rule_bindings.csv")
    bindings_by_rule: dict[str, list[dict[str, str]]] = {}
    for row in bindings:
        bindings_by_rule.setdefault(row["rule_id"], []).append(row)

    eligible: list[str] = []
    blocked: dict[str, list[str]] = {}
    for rule in rules:
        reasons: list[str] = []
        review = reviews.get(rule["rule_id"])
        evidence = primary.get(rule["rule_id"])
        if rule["status"] != "draft":
            reasons.append("rule_not_draft")
        if not review or review.get("decision") != "approve" or review.get("reviewer_role") != "pharmacist_expert":
            reasons.append("pharmacist_approval_missing")
        if not evidence or not evidence.get("source_id") or not evidence.get("source_locator") or not evidence.get("evidence_text"):
            reasons.append("recommended_primary_evidence_missing")
        elif rule.get("source_id") != evidence["source_id"] or not rule.get("source_locator", "").endswith(evidence["source_locator"]):
            reasons.append("rule_evidence_locator_mismatch")
        if rule["rule_type"] not in BINDING_FREE_TYPES and not bindings_by_rule.get(rule["rule_id"]):
            reasons.append("runtime_binding_missing")
        if reasons:
            blocked[rule["rule_id"]] = reasons
        else:
            eligible.append(rule["rule_id"])
    return {"eligible_rule_ids": eligible, "blocked": blocked, "rules_total": len(rules)}


def promote(otc: Path = OTC, *, apply: bool = False) -> dict[str, object]:
    assessment = assess(otc)
    eligible = set(assessment["eligible_rule_ids"])
    result = {**assessment, "applied": False, "promoted": 0}
    if not apply or not eligible:
        return result

    rules_path = otc / "rules" / "rules.csv"
    shortlist_path = otc / "rules" / "rule_evidence_shortlist.csv"
    bindings_path = otc / "rules" / "runtime_rule_bindings.csv"
    paths = [rules_path, shortlist_path, bindings_path]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = otc / "etc" / "promotion_backups" / stamp
    backup.mkdir(parents=True, exist_ok=False)
    for path in paths:
        shutil.copy2(path, backup / path.name)

    rules = read(rules_path)
    shortlist = read(shortlist_path)
    bindings = read(bindings_path)
    for row in rules:
        if row["rule_id"] in eligible:
            row["status"] = "released"
    for row in shortlist:
        if row["rule_id"] in eligible and row["recommendation"] == "recommended_primary":
            row["review_status"] = "human_expert_verified"
            row["supports_release"] = "true"
    for row in bindings:
        if row["rule_id"] in eligible:
            row["binding_status"] = "human_expert_verified"
            row["supports_release"] = "true"
    write(rules_path, rules)
    write(shortlist_path, shortlist)
    write(bindings_path, bindings)
    result.update({"applied": True, "promoted": len(eligible), "backup": str(backup)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or explicitly promote pharmacist-approved OTC rules")
    parser.add_argument("--apply", action="store_true", help="write eligible promotions; default is a read-only assessment")
    args = parser.parse_args()
    result = promote(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
