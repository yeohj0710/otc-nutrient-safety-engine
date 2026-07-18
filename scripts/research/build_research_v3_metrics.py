from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(root: Path) -> dict[str, object]:
    provisional = root / "search" / "provisional_pubmed_20260710"
    search_runs = csv_rows(provisional / "search_run_log.csv")
    records = csv_rows(provisional / "normalized" / "records.csv")
    dedup = csv_rows(provisional / "dedup_log.csv")
    title_abstract = csv_rows(root / "screening" / "title_abstract.csv")
    full_text = csv_rows(root / "screening" / "full_text.csv")
    evidence = csv_rows(root / "extraction" / "evidence.csv")
    rules = csv_rows(root / "rules" / "rules.csv")
    development = csv_rows(root / "validation" / "development_scenarios.csv")
    independent = csv_rows(root / "validation" / "independent_scenarios.csv")
    sources = json.loads((root / "sources" / "source_registry.json").read_text(encoding="utf-8"))["sources"]
    fetch = json.loads((root / "sources" / "fetch_manifest_20260713.json").read_text(encoding="utf-8"))
    candidates = csv_rows(root / "sources" / "normative_candidates.csv")
    review_packet = json.loads((root / "screening" / "review_packets" / "review_packet_manifest.json").read_text(encoding="utf-8"))
    search_peer_review = csv_rows(provisional / "peer_review.csv")
    completed_search_reviews = [row for row in search_peer_review if row["status"] == "completed"]
    released = [row for row in rules if row["review_status"] == "released"]
    released_linked = [row for row in released if row["source_id"] and row["locator"]]
    development_results = json.loads((root / "validation" / "development_results.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "audit" / "software_quality_report.json").read_text(encoding="utf-8"))
    ai_review = json.loads((root / "ai_review" / "ai_review_report.json").read_text(encoding="utf-8"))
    approval_report_path = root / "approvals" / "approval_import_report.json"
    approval_report = json.loads(approval_report_path.read_text(encoding="utf-8")) if approval_report_path.exists() else {}
    retrieval_summary_path = root / "full_text" / "retrieval_summary.json"
    retrieval_summary = json.loads(retrieval_summary_path.read_text(encoding="utf-8")) if retrieval_summary_path.exists() else {}
    extraction_report_path = root / "extraction" / "ai_full_text_extraction_report.json"
    extraction_report = json.loads(extraction_report_path.read_text(encoding="utf-8")) if extraction_report_path.exists() else {}
    synthesis_report_path = root / "extraction" / "ai_full_text_synthesis_report.json"
    synthesis_report = json.loads(synthesis_report_path.read_text(encoding="utf-8")) if synthesis_report_path.exists() else {}
    quantitative_report_path = root / "extraction" / "quantitative_effects_report.json"
    quantitative_report = json.loads(quantitative_report_path.read_text(encoding="utf-8")) if quantitative_report_path.exists() else {}
    independent_report_path = root / "validation" / "independent_evaluation.json"
    independent_report = json.loads(independent_report_path.read_text(encoding="utf-8")) if independent_report_path.exists() else {}

    evaluated = bool(independent)
    priority_rows = review_packet["priority_packet"]["rows"]
    full_queue_rows = review_packet["full_queue"]["rows"]
    title_abstract_count = len(title_abstract)
    title_abstract_status = (
        "completed"
        if title_abstract_count >= full_queue_rows
        else ("partially_reviewed" if title_abstract_count else "prepared_not_reviewed")
    )
    priority_review_status = (
        "completed"
        if title_abstract_count >= priority_rows
        else ("partially_reviewed" if title_abstract_count else "prepared_not_reviewed")
    )
    release_blockers = []
    if not approval_report.get("advisor_approval_complete"):
        release_blockers.append("research_direction_advisor_confirmation")
    if len(completed_search_reviews) < len(search_peer_review):
        release_blockers.append("search_strategy_peer_review")
    if not full_text:
        release_blockers.append("human_screening_and_full_text_review")
    if approval_report.get("human_expert_rule_approval_count", 0) < len(rules):
        release_blockers.append("expert_rule_review")
    if approval_report.get("independent_human_scenario_count", 0) == 0:
        release_blockers.append("independent_scenario_evaluation")
    return {
        "schema_version": "1.0.0",
        "lineage": "research_v3",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "claim_boundary": "evidence_bound_high_dose_nutrient_safety_rules_and_research_prototype",
        "metrics": {
            "search_runs": {"status": "provisional", "value": len(search_runs)},
            "search_occurrences": {"status": "provisional", "value": len(records)},
            "unique_pmids": {
                "status": "provisional",
                "value": len({row["pmid"] for row in records if row["pmid"]}),
            },
            "dedup_candidates": {"status": "provisional_unadjudicated", "value": len(dedup)},
            "search_strategy_review_packet": {
                "status": "completed" if len(completed_search_reviews) == len(search_peer_review) else ("prepared_not_reviewed" if not completed_search_reviews else "partially_reviewed"),
                "value": len(search_peer_review),
                "strategies": len({row["strategy_id"] for row in search_peer_review}),
                "human_decisions_prefilled": sum(bool(row["rating"] or row["comment"]) for row in search_peer_review),
            },
            "completed_search_strategy_reviews": {"status": "evaluated", "value": len(completed_search_reviews)},
            "advisor_approvals": {
                "status": "completed" if approval_report.get("advisor_approval_complete") else "not_completed",
                "value": approval_report.get("advisor_approval_count", 0),
                "reviewer": approval_report.get("advisor_name"),
            },
            "human_title_abstract_decisions": {"status": "evaluated", "value": len(title_abstract)},
            "codex_ai_title_abstract_reviews": {
                "status": "ai_reviewed_not_human",
                "value": ai_review["title_abstract_full_queue"]["rows"],
                "human_review_completed": approval_report.get("human_literature_review_count", 0),
            },
            "title_abstract_review_queue": {
                "status": title_abstract_status,
                "value": full_queue_rows,
                "human_decisions_completed": title_abstract_count,
                "human_decisions_prefilled": review_packet["full_queue"]["human_decisions_prefilled"],
            },
            "priority_review_packet": {
                "status": priority_review_status,
                "value": priority_rows,
                "human_decisions_completed": min(title_abstract_count, priority_rows),
                "human_decisions_prefilled": review_packet["priority_packet"]["human_decisions_prefilled"],
            },
            "human_full_text_decisions": {"status": "evaluated", "value": len(full_text)},
            "priority_full_text_retrieved": {
                "status": "human_review_completed" if full_text else "retrieved_not_human_reviewed",
                "value": retrieval_summary.get("retrieved_open_access_xml", 0) + retrieval_summary.get("retrieved_public_pmc_html", 0),
                "requested": retrieval_summary.get("requested", 0),
                "retrieval_failed": retrieval_summary.get("retrieval_failed", 0),
                "no_pmc_open_access_identifier": retrieval_summary.get("no_pmc_open_access_identifier", 0),
                "human_full_text_reviews": len(full_text),
            },
            "codex_ai_full_text_evidence_candidates": {
                "status": "human_verified" if evidence else "ai_extracted_not_human_verified",
                "value": extraction_report.get("ai_evidence_candidates", 0),
                "unique_sources_verified": extraction_report.get("unique_sources_verified", 0),
                "articles_with_candidates": extraction_report.get("articles_with_candidates", 0),
                "human_verified_candidates": sum(row.get("review_status") == "verified" for row in evidence),
            },
            "codex_ai_draft_rule_evidence_links": {
                "status": "ai_candidate_link_not_expert_verified",
                "value": synthesis_report.get("candidate_rule_links", 0),
                "draft_rules_linked": synthesis_report.get("draft_rules_linked", 0),
                "released_rules_created": synthesis_report.get("released_rules_created", 0),
                "expert_verified_links": synthesis_report.get("expert_verified_links", 0),
            },
            "codex_ai_priority_reviews": {
                "status": "ai_reviewed_not_human",
                "value": ai_review["priority_packet"]["rows"],
                "human_review_completed": approval_report.get("human_literature_review_count", 0),
            },
            "evidence_extractions": {"status": "evaluated", "value": len(evidence)},
            "reported_quantitative_statistics": {
                "status": "codex_structured_not_independently_verified",
                "value": quantitative_report.get("reported_statistics", 0),
                "evidence_rows": quantitative_report.get("rows_with_reported_statistics", 0),
                "relative_effect_measures": quantitative_report.get("counts_by_type", {}).get("relative_effect_measure", 0),
                "synthesis_eligible": 0,
            },
            "registered_official_sources": {"status": "evaluated", "value": len(sources)},
            "fetched_official_sources": {
                "status": "evaluated",
                "value": fetch["summary"]["fetched"],
                "denominator": fetch["summary"]["total"],
            },
            "normative_candidates": {"status": "not_expert_reviewed", "value": len(candidates)},
            "rules_total": {"status": "evaluated", "value": len(rules)},
            "codex_ai_rule_structural_reviews": {
                "status": "ai_reviewed_not_expert",
                "value": ai_review["draft_rules"]["rows"],
                "structurally_complete": ai_review["draft_rules"]["structurally_complete"],
                "expert_approval_completed": approval_report.get("human_expert_rule_approval_count", 0),
            },
            "codex_ai_search_strategy_reviews": {
                "status": "ai_reviewed_not_press_peer_review",
                "value": ai_review["search_strategies"]["rows"],
                "structural_pass": ai_review["search_strategies"]["structural_pass"],
                "human_press_review_completed": approval_report.get("human_press_review_count", 0),
            },
            "rules_released": {"status": "evaluated", "value": len(released)},
            "released_source_locator_rate": {
                "status": "not_evaluated" if not released else "evaluated",
                "value": None if not released else len(released_linked) / len(released),
                "numerator": len(released_linked),
                "denominator": len(released),
            },
            "development_scenarios": {"status": "evaluated", "value": len(development)},
            "development_scenarios_passed": {
                "status": "evaluated_non_independent",
                "value": development_results["passed"],
                "denominator": development_results["scenario_count"],
                "performance_claim_allowed": development_results["performance_claim_allowed"],
            },
            "independent_scenarios": {"status": "evaluated", "value": len(independent)},
            "sensitivity": {"status": "evaluated" if independent_report.get("status") == "evaluated" else "not_evaluated", "value": independent_report.get("metrics", {}).get("sensitivity", {}).get("value"), "ci95": independent_report.get("metrics", {}).get("sensitivity", {}).get("ci95_wilson")},
            "specificity": {"status": "evaluated" if independent_report.get("status") == "evaluated" else "not_evaluated", "value": independent_report.get("metrics", {}).get("specificity", {}).get("value"), "ci95": independent_report.get("metrics", {}).get("specificity", {}).get("ci95_wilson")},
            "accuracy": {"status": "evaluated" if independent_report.get("status") == "evaluated" else "not_evaluated", "value": independent_report.get("metrics", {}).get("accuracy", {}).get("value"), "ci95": independent_report.get("metrics", {}).get("accuracy", {}).get("ci95_wilson")},
            "critical_false_negatives": {"status": "evaluated" if independent_report.get("status") == "evaluated" else "not_evaluated", "value": independent_report.get("metrics", {}).get("confusion_matrix", {}).get("critical_false_negative")},
            "research_tests_passed": {"status": "evaluated", "value": quality["summary"]["research_tests_passed"]},
            "app_tests_passed": {"status": "evaluated", "value": quality["summary"]["app_tests_passed"]},
            "static_paths_generated": {"status": "evaluated", "value": quality["summary"]["static_paths_generated"]},
            "lint_typecheck_build_passed": {"status": "evaluated", "value": quality["summary"]["all_exit_codes_zero"]},
        },
        "release_ready": False,
        "release_blockers": release_blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output else root / "metrics_manifest.json"
    report = build(root)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
