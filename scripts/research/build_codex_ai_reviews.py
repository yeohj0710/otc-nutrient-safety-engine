from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REVIEWER = "codex_ai"
STATUS = "ai_reviewed_not_human"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def review_full_queue(source: Path, output: Path) -> dict[str, object]:
    mapping = {
        "priority_include_candidate": "ai_include_candidate",
        "retain_uncertain": "ai_uncertain",
        "explicit_exclude_candidate": "ai_exclude_candidate",
    }
    rows = []
    for source_row in read_csv(source):
        proposal = source_row["computational_proposal"]
        rows.append({
            "record_id": source_row["record_id"],
            "pmid": source_row["pmid"],
            "clinical_node_candidates": source_row["clinical_node_candidates"],
            "ai_decision": mapping.get(proposal, "ai_uncertain"),
            "ai_confidence_basis": f"score={source_row['computational_score']}; proposal={proposal}",
            "ai_rationale": source_row["computational_rationale"],
            "exclusion_flags": source_row["explicit_exclusion_flags"],
            "reviewer_id": REVIEWER,
            "review_status": STATUS,
            "human_confirmation_required": "true",
        })
    fields = list(rows[0]) if rows else ["record_id"]
    write_csv(output, fields, rows)
    counts = Counter(row["ai_decision"] for row in rows)
    return {"rows": len(rows), "counts": dict(counts), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def review_priority(source: Path, output: Path) -> dict[str, object]:
    rows = []
    for source_row in read_csv(source):
        score = int(source_row.get("score") or 0)
        has_outcome = bool(source_row.get("outcome_signals", "").strip())
        decision = "ai_include_for_full_text" if score >= 6 and has_outcome else "ai_uncertain"
        rows.append({
            "evidence_candidate_id": source_row["evidence_candidate_id"],
            "clinical_node_id": source_row["clinical_node_id"],
            "pmid": source_row["pmid"],
            "title": source_row["title"],
            "ai_title_abstract_decision": decision,
            "ai_reason": f"score={score}; outcome_signals={source_row.get('outcome_signals', '') or 'none'}",
            "full_text_retrieval_recommended": "true" if decision == "ai_include_for_full_text" else "manual_check",
            "reviewer_id": REVIEWER,
            "review_status": STATUS,
            "human_confirmation_required": "true",
        })
    fields = list(rows[0]) if rows else ["evidence_candidate_id"]
    write_csv(output, fields, rows)
    counts = Counter(row["ai_title_abstract_decision"] for row in rows)
    return {"rows": len(rows), "counts": dict(counts), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def review_rules(source: Path, output: Path) -> dict[str, object]:
    rows = []
    for source_row in read_csv(source):
        required = ["threshold_value", "threshold_unit", "conditions_json", "message_ko", "next_action_ko", "source_id", "locator"]
        missing = [field for field in required if not source_row.get(field, "").strip()]
        rows.append({
            "review_item_id": source_row["review_item_id"],
            "rule_id": source_row["rule_id"],
            "ai_structural_decision": "ai_structurally_complete" if not missing else "ai_revision_required",
            "missing_fields": ";".join(missing),
            "source_locator_present": str(bool(source_row.get("source_id") and source_row.get("locator"))).lower(),
            "expert_approval_granted": "false",
            "reviewer_id": REVIEWER,
            "review_status": STATUS,
            "human_confirmation_required": "true",
        })
    fields = list(rows[0]) if rows else ["review_item_id"]
    write_csv(output, fields, rows)
    return {"rows": len(rows), "structurally_complete": sum(row["ai_structural_decision"] == "ai_structurally_complete" for row in rows), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def review_queries(query_dir: Path, output: Path) -> dict[str, object]:
    rows = []
    for path in sorted(query_dir.glob("K*.txt")):
        text = path.read_text(encoding="utf-8")
        checks = {
            "balanced_parentheses": text.count("(") == text.count(")"),
            "mesh_present": "[Mesh]" in text,
            "title_abstract_terms_present": "[tiab]" in text,
            "three_or_more_concept_blocks": text.upper().count("\nAND\n") >= 2,
            "date_or_language_limit_absent": not any(token in text.lower() for token in ("[dp]", "english[lang]", "humans[mesh]")),
        }
        rows.append({
            "strategy_id": path.stem,
            **{key: str(value).lower() for key, value in checks.items()},
            "ai_decision": "ai_structural_pass" if all(checks.values()) else "ai_revision_required",
            "reviewer_id": REVIEWER,
            "review_status": STATUS,
            "human_press_review_completed": "false",
        })
    fields = list(rows[0]) if rows else ["strategy_id"]
    write_csv(output, fields, rows)
    return {"rows": len(rows), "structural_pass": sum(row["ai_decision"] == "ai_structural_pass" for row in rows), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--query-dir", type=Path, default=Path("research_v2/search/pubmed_queries"))
    args = parser.parse_args()
    out = args.root / "ai_review"
    report = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviewer_id": REVIEWER,
        "review_status": STATUS,
        "human_review_completed": 0,
        "expert_approval_completed": 0,
        "performance_claim_allowed": False,
        "release_ready": False,
        "title_abstract_full_queue": review_full_queue(args.root / "screening/review_packets/title_abstract_full_queue.csv", out / "title_abstract_ai_review.csv"),
        "priority_packet": review_priority(args.root / "screening/review_packets/priority_118_review_packet.csv", out / "priority_118_ai_review.csv"),
        "draft_rules": review_rules(args.root / "rules/expert_rule_review_packet.csv", out / "draft_rule_ai_review.csv"),
        "search_strategies": review_queries(args.query_dir, out / "search_strategy_ai_review.csv"),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "ai_review_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
