from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


EXPECTED = {"approval": 4, "press": 35, "literature": 118, "rules": 6, "scenarios": 12, "fulltext": 63}
EXPECTED_ROLES = {"press": "검색전략 검토자", "literature": "문헌 검토자", "rules": "약사·전문가", "scenarios": "독립 평가자", "fulltext": "전문 검토자"}
RULE_IDS = {"vitamin_d": "V3-DRAFT-KDRI-VD-UL", "calcium": "V3-DRAFT-KDRI-CA-UL", "vitamin_b6": "V3-DRAFT-KDRI-B6-UL", "iron": "V3-DRAFT-KDRI-FE-UL", "magnesium": "V3-DRAFT-KDRI-MG-UL", "zinc": "V3-DRAFT-KDRI-ZN-UL"}
RULE_BOOLEAN_FIELDS = ("threshold_correct", "scope_correct", "conditions_correct", "exceptions_correct", "message_safe", "next_action_safe", "source_locator_verified")
HUMAN_REVIEW_KINDS = {"human_review", "human_confirmation_of_codex_recommendation"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    decisions = data.get("decisions", {})
    counts = Counter(key.split(":", 1)[0] for key in decisions)
    if dict(counts) != EXPECTED:
        raise SystemExit(f"unexpected decision counts: {dict(counts)}")
    if data.get("overall_status") != "completed":
        raise SystemExit("review wizard result is not completed")
    for key, value in decisions.items():
        section = key.split(":", 1)[0]
        if section in EXPECTED_ROLES and (value.get("review_kind") not in HUMAN_REVIEW_KINDS or value.get("reviewer_role") != EXPECTED_ROLES[section]):
            raise SystemExit(f"non-human or wrong-role decision: {key}")

    approval_rows = []
    for key, value in decisions.items():
        if not key.startswith("approval:"):
            continue
        if value.get("decision") != "approve":
            raise SystemExit(f"approval not granted: {key}")
        if not value.get("reviewer_id") or not value.get("reviewed_at"):
            raise SystemExit(f"approval identity/time missing: {key}")
        approval_rows.append(
            {
                "item_id": key.split(":", 1)[1],
                "decision": value["decision"],
                "reviewer_id": value["reviewer_id"],
                "reviewer_role": value.get("reviewer_role", ""),
                "reviewed_at": value["reviewed_at"],
                "note": value.get("note", ""),
            }
        )
    if len(approval_rows) != 4 or any(row["reviewer_role"] != "지도교수" for row in approval_rows):
        raise SystemExit("four advisor approvals were not found")

    out = args.root / "approvals"
    out.mkdir(parents=True, exist_ok=True)
    canonical = out / "review_wizard_result.json"
    canonical.write_bytes(raw)
    with (out / "advisor_approvals.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(approval_rows[0]))
        writer.writeheader()
        writer.writerows(sorted(approval_rows, key=lambda row: row["item_id"]))

    peer_review_path = args.root / "search" / "provisional_pubmed_20260710" / "peer_review.csv"
    with peer_review_path.open("r", encoding="utf-8-sig", newline="") as f:
        peer_rows = list(csv.DictReader(f))
    peer_fields = list(peer_rows[0])
    human_press_updates = 0
    for row in peer_rows:
        value = decisions.get(f"press:{row['review_id']}", {})
        if value.get("reviewer_id") and value.get("reviewer_id") != "codex_ai":
            row.update(
                {
                    "reviewer_id": value["reviewer_id"],
                    "review_date_utc": value.get("reviewed_at", ""),
                    "rating": value.get("rating", ""),
                    "comment": value.get("note", "") or "",
                    "resolution": "accepted_without_change" if value.get("rating") == "yes" else "requires_follow_up",
                    "status": "completed",
                }
            )
            human_press_updates += 1
    with peer_review_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=peer_fields)
        writer.writeheader()
        writer.writerows(peer_rows)

    literature_packet = args.root / "human_review_minimal" / "03_우선문헌_118건_검토.csv"
    with literature_packet.open("r", encoding="utf-8-sig", newline="") as f:
        literature_source = {row["evidence_candidate_id"]: row for row in csv.DictReader(f)}
    screening_fields = ["record_id", "decision", "reason_code", "reviewer_id", "reviewed_at", "source_locator", "notes"]
    screening_rows = []
    decision_map = {"include_candidate": "include", "uncertain": "uncertain", "exclude": "exclude"}
    for key, value in decisions.items():
        if not key.startswith("literature:"):
            continue
        item = key.split(":", 1)[1]
        if value.get("decision") not in decision_map or item not in literature_source:
            raise SystemExit(f"invalid literature decision: {key}")
        source = literature_source[item]
        screening_rows.append({"record_id": item, "decision": decision_map[value["decision"]], "reason_code": value.get("reason", "") or value["decision"].upper(), "reviewer_id": value["reviewer_id"], "reviewed_at": value["reviewed_at"], "source_locator": source.get("source_locator", ""), "notes": value.get("note", "")})
    screening_path = args.root / "screening" / "title_abstract.csv"
    screening_path.parent.mkdir(parents=True, exist_ok=True)
    with screening_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=screening_fields); writer.writeheader(); writer.writerows(sorted(screening_rows, key=lambda row: row["record_id"]))

    rule_path = args.root / "rules" / "expert_rule_review_packet.csv"
    with rule_path.open("r", encoding="utf-8-sig", newline="") as f:
        rule_rows = list(csv.DictReader(f)); rule_fields = list(rule_rows[0])
    for row in rule_rows:
        value = decisions.get(f"rules:{row['review_item_id']}", {})
        decision = value.get("decision")
        if decision not in {"approve", "revise", "reject"}:
            raise SystemExit(f"invalid rule decision: {row['review_item_id']}")
        passed = decision == "approve"
        row.update({field: str(passed).lower() for field in RULE_BOOLEAN_FIELDS})
        row.update({"overall_decision": decision, "required_revision": "" if passed else value.get("note", ""), "reviewer_id": value["reviewer_id"], "reviewer_role": value["reviewer_role"], "reviewed_at": value["reviewed_at"], "adjudication_status": "completed", "notes": value.get("note", "")})
    with rule_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rule_fields); writer.writeheader(); writer.writerows(rule_rows)

    scenario_source_path = args.root / "human_review_minimal" / "05_독립시나리오_12건_확정.csv"
    with scenario_source_path.open("r", encoding="utf-8-sig", newline="") as f:
        scenario_rows = list(csv.DictReader(f)); scenario_fields = list(scenario_rows[0])
    for row in scenario_rows:
        value = decisions.get(f"scenarios:{row['scenario_id']}", {})
        if value.get("label") not in {"warning", "no_warning"} or value.get("locked_before_test") is not True:
            raise SystemExit(f"invalid independent scenario decision: {row['scenario_id']}")
        ingredient = json.loads(row["input_json"])["ingredient"]
        gold = [RULE_IDS[ingredient]] if value["label"] == "warning" else []
        row.update({"gold_hazards_json": json.dumps(gold, ensure_ascii=False), "adjudicator_id": value["reviewer_id"], "adjudicated_at": value["reviewed_at"], "locked_before_test": "true", "notes": value.get("note", "")})
    scenario_path = args.root / "validation" / "independent_scenarios.csv"
    scenario_path.parent.mkdir(parents=True, exist_ok=True)
    with scenario_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=scenario_fields); writer.writeheader(); writer.writerows(scenario_rows)

    candidate_path = args.root / "extraction" / "ai_full_text_evidence_candidates.csv"
    with candidate_path.open("r", encoding="utf-8-sig", newline="") as f:
        candidate_rows = list(csv.DictReader(f))
    candidates_by_pmcid: dict[str, list[dict[str, str]]] = {}
    for row in candidate_rows:
        candidates_by_pmcid.setdefault(row["pmcid"], []).append(row)
    full_text_fields = ["record_id", "decision", "reason_code", "full_text_path", "reviewer_id", "reviewed_at", "locator", "notes"]
    full_text_rows = []
    evidence_fields = ["evidence_id", "record_id", "ingredient_id", "population", "exposure", "comparator", "outcome", "effect_value", "effect_unit", "source_id", "locator", "verbatim_quote", "review_status", "reviewer_id", "reviewed_at"]
    evidence_rows = []
    for key, value in decisions.items():
        if not key.startswith("fulltext:"):
            continue
        pmcid = key.split(":", 1)[1]
        candidates = candidates_by_pmcid.get(pmcid, [])
        if not candidates or value.get("decision") not in {"include", "exclude", "uncertain"}:
            raise SystemExit(f"invalid full-text decision: {key}")
        first = candidates[0]
        locator = value.get("locator", "") or "; ".join(dict.fromkeys(row["locator"] for row in candidates if row["locator"]))
        full_text_rows.append({
            "record_id": first["parent_candidate_id"],
            "decision": value["decision"],
            "reason_code": value.get("reason", "") or value["decision"].upper(),
            "full_text_path": first["source_path"],
            "reviewer_id": value["reviewer_id"],
            "reviewed_at": value["reviewed_at"],
            "locator": locator,
            "notes": value.get("note", ""),
        })
        if value["decision"] == "include":
            for candidate in candidates:
                exposure_parts = [candidate.get("dose_mentions", ""), candidate.get("duration_mentions", "")]
                evidence_rows.append({
                    "evidence_id": candidate["evidence_candidate_id"],
                    "record_id": candidate["parent_candidate_id"],
                    "ingredient_id": candidate["clinical_node_id"],
                    "population": candidate.get("population_mentions", ""),
                    "exposure": "; ".join(part for part in exposure_parts if part),
                    "comparator": "",
                    "outcome": candidate.get("signal_types", ""),
                    "effect_value": "",
                    "effect_unit": "",
                    "source_id": candidate["pmcid"],
                    "locator": candidate["locator"],
                    "verbatim_quote": candidate["evidence_text"],
                    "review_status": "verified",
                    "reviewer_id": value["reviewer_id"],
                    "reviewed_at": value["reviewed_at"],
                })
    full_text_path = args.root / "screening" / "full_text.csv"
    with full_text_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=full_text_fields); writer.writeheader(); writer.writerows(sorted(full_text_rows, key=lambda row: row["record_id"]))
    evidence_path = args.root / "extraction" / "evidence.csv"
    with evidence_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=evidence_fields); writer.writeheader(); writer.writerows(sorted(evidence_rows, key=lambda row: row["evidence_id"]))

    reviewer_summary = Counter()
    for key, value in decisions.items():
        section = key.split(":", 1)[0]
        reviewer_summary[(section, value.get("reviewer_id", ""), value.get("reviewer_role", ""), value.get("review_kind", ""))] += 1
    report = {
        "schema_version": "1.0.0",
        "source_path": str(args.input.resolve()),
        "source_sha256": sha256(args.input),
        "overall_status": data["overall_status"],
        "completed_at": data.get("completed_at"),
        "exported_at": data.get("exported_at"),
        "decision_counts": dict(counts),
        "advisor_approval_count": 4,
        "advisor_name": approval_rows[0]["reviewer_id"],
        "advisor_approval_complete": True,
        "human_press_review_count": human_press_updates,
        "human_title_abstract_decision_count": len(screening_rows),
        "human_full_text_decision_count": len(full_text_rows),
        "human_verified_evidence_candidate_count": len(evidence_rows),
        "human_expert_rule_approval_count": sum(1 for key, v in decisions.items() if key.startswith("rules:") and v.get("review_kind") in HUMAN_REVIEW_KINDS),
        "human_literature_review_count": sum(1 for key, v in decisions.items() if key.startswith("literature:") and v.get("review_kind") in HUMAN_REVIEW_KINDS),
        "independent_human_scenario_count": sum(1 for key, v in decisions.items() if key.startswith("scenarios:") and v.get("review_kind") in HUMAN_REVIEW_KINDS and v.get("locked_before_test") is True),
        "reviewer_summary": [
            {"section": k[0], "reviewer_id": k[1], "reviewer_role": k[2], "review_kind": k[3], "count": count}
            for k, count in sorted(reviewer_summary.items())
        ],
        "interpretation": "Advisor approvals and explicit human confirmations are accepted as human review. Codex recommendations remain separately identified by review_kind and prefill_source.",
    }
    report_path = out / "approval_import_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
