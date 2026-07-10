#!/usr/bin/env python3
"""Fail-closed release validator for the redesigned research repository.

The validator checks existence, identity, search reconciliation, final screening,
AI metrics, evidence provenance, scenario validation, and thesis claim support.
It is intentionally conservative: missing or malformed evidence is a failure.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

REQUIRED = [
    "protocol/protocol.md",
    "protocol/protocol.sha256",
    "search/search_run_log.csv",
    "screening/title_abstract.csv",
    "screening/full_text.csv",
    "screening/prisma_counts.json",
    "extraction/extraction.csv",
    "risk_of_bias/assessments.csv",
    "synthesis/grade.csv",
    "ai_eval/screening_metrics.json",
    "ai_eval/extraction_metrics.json",
    "synthesis/evidence_map.csv",
    "rules/rules.jsonl",
    "validation/scenario_metrics.json",
    "validation/content_validity.json",
    "thesis/metrics_manifest.json",
    "thesis/claim_ledger.csv",
]
BAD_PATTERNS = [r"\bTBD\b", r"추후\s*확인", r"후속\s*확인", r"미수행"]
FINAL_DECISIONS = {"include", "exclude"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_root", nargs="?", default="research_v2")
    parser.add_argument("--thresholds", default=None)
    parser.add_argument("--out", default="release_validation.json")
    args = parser.parse_args()

    root = Path(args.research_root)
    threshold_path = Path(args.thresholds) if args.thresholds else root / "config" / "quality_thresholds.json"
    thresholds = {
        "screening_recall_point_estimate_min": 0.95,
        "extraction_required_field_accuracy_min": 0.90,
        "provenance_completeness_required": 1.0,
        "scenario_hazard_sensitivity_point_estimate_min": 0.95,
        "sentinel_critical_false_negative_max": 0,
        "minimum_validation_scenarios": 100,
        "minimum_screening_gold_items": 300,
        "minimum_screening_gold_positive": 60,
    }
    if threshold_path.exists():
        thresholds.update(load_json(threshold_path))

    failures: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED:
        if not (root / relative).exists():
            failures.append(f"missing:{relative}")

    identity = root / "audit" / "repo_identity.json"
    if not identity.exists():
        failures.append("missing:audit/repo_identity.json")
    else:
        obj = load_json(identity)
        if obj.get("student_name") != "권혁찬" or str(obj.get("student_id")) != "2021194024":
            failures.append("identity_mismatch")
        if not obj.get("pass"):
            failures.append("gate0_identity_check_failed")

    # Active release files must not contain Yeo identity markers; governance and
    # legacy/audit records may document the package correction.
    identity_exceptions = {
        root / "project_identity.json",
        root / "config" / "project_identity.json",
        root / "protocol" / "reference" / "reference_manifest.json",
    }
    governance_files = {"DECISIONS.md", "CHANGELOG_RESEARCH.md", "HUMAN_ACTION_REQUIRED.md"}
    for path in root.rglob("*"):
        if path in identity_exceptions:
            continue
        if path.name in governance_files:
            continue
        if not path.is_file() or any(part in {"legacy_untrusted", "audit"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".md", ".txt", ".csv", ".json", ".jsonl", ".ts", ".tsx", ".js"}:
            continue
        try:
            if path.stat().st_size > 20_000_000:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        if "여형준" in text or "2020194025" in text:
            failures.append(f"yeo_marker:{path.relative_to(root)}")
        if path.name in {"protocol.md", "thesis.md", "thesis.txt"}:
            for pattern in BAD_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    failures.append(f"placeholder:{path.relative_to(root)}:{pattern}")

    search_log = root / "search" / "search_run_log.csv"
    if search_log.exists():
        rows = read_csv(search_log)
        if not rows:
            failures.append("empty_search_run_log")
        for index, row in enumerate(rows, start=2):
            status = (row.get("status") or "").strip().lower()
            hit = as_int(row.get("hit_count"))
            exported = as_int(row.get("exported_count"))
            imported = as_int(row.get("imported_count"))
            if status not in {"complete", "completed"}:
                failures.append(f"search_not_complete:line_{index}")
            if hit is None or exported is None or imported is None:
                failures.append(f"search_count_missing_or_invalid:line_{index}")
            elif exported != imported:
                failures.append(f"search_export_import_mismatch:line_{index}")
            if not (row.get("raw_file_sha256") or "").strip():
                failures.append(f"search_raw_hash_missing:line_{index}")
            limits = (row.get("limits") or "").lower()
            if "top" in limits or "relevance" in limits or "first page" in limits:
                failures.append(f"top_n_or_relevance_limit_detected:line_{index}")

    ta_path = root / "screening" / "title_abstract.csv"
    if ta_path.exists():
        ta_rows = read_csv(ta_path)
        unresolved = [
            row.get("record_id", "")
            for row in ta_rows
            if (row.get("adjudicated_decision") or row.get("decision") or "").strip().lower()
            not in FINAL_DECISIONS
        ]
        if unresolved:
            failures.append(f"unresolved_title_abstract_decisions:{len(unresolved)}")

    ft_path = root / "screening" / "full_text.csv"
    if ft_path.exists():
        ft_rows = read_csv(ft_path)
        unresolved = [
            row.get("report_id", "")
            for row in ft_rows
            if (row.get("adjudicated_decision") or row.get("decision") or "").strip().lower()
            not in FINAL_DECISIONS
        ]
        if unresolved:
            failures.append(f"unresolved_full_text_decisions:{len(unresolved)}")
        missing_reason = [
            row.get("report_id", "")
            for row in ft_rows
            if (row.get("adjudicated_decision") or row.get("decision") or "").strip().lower() == "exclude"
            and not (row.get("primary_exclusion_reason") or "").strip()
        ]
        if missing_reason:
            failures.append(f"full_text_exclusion_reason_missing:{len(missing_reason)}")

    prisma_path = root / "screening" / "prisma_counts.json"
    if prisma_path.exists():
        prisma = load_json(prisma_path)
        if not prisma.get("pass", not prisma.get("validation_errors")):
            failures.append("prisma_arithmetic_failed")
        if prisma.get("validation_errors"):
            failures.append("prisma_validation_errors_present")

    screening_metrics = root / "ai_eval" / "screening_metrics.json"
    if screening_metrics.exists():
        metrics = load_json(screening_metrics)
        sensitivity = as_float(metrics.get("sensitivity", metrics.get("recall")))
        n_evaluated = as_int(metrics.get("n_evaluated", metrics.get("n"))) or 0
        positives = as_int(metrics.get("gold_positive_count")) or 0
        if n_evaluated < int(thresholds["minimum_screening_gold_items"]):
            failures.append(f"screening_gold_too_small:{n_evaluated}")
        if positives < int(thresholds["minimum_screening_gold_positive"]):
            failures.append(f"screening_gold_positive_too_small:{positives}")
        if sensitivity is None or sensitivity < float(thresholds["screening_recall_point_estimate_min"]):
            failures.append(f"screening_recall_below_threshold:{sensitivity}")
        if not metrics.get("sensitivity_ci95"):
            failures.append("screening_recall_ci_missing")

    extraction_metrics = root / "ai_eval" / "extraction_metrics.json"
    if extraction_metrics.exists():
        metrics = load_json(extraction_metrics)
        accuracy = as_float(
            metrics.get("required_field_accuracy", metrics.get("strict_required_field_accuracy"))
        )
        if accuracy is None or accuracy < float(thresholds["extraction_required_field_accuracy_min"]):
            failures.append(f"extraction_accuracy_below_threshold:{accuracy}")
        if as_float(metrics.get("unsupported_extraction_rate")) is None:
            failures.append("unsupported_extraction_rate_missing")
        if as_float(metrics.get("locator_accuracy")) is None:
            failures.append("locator_accuracy_missing")

    quote_ids: set[str] = set()
    quotes_path = root / "extraction" / "source_quotes.csv"
    if quotes_path.exists():
        for row in read_csv(quotes_path):
            quote_id = (row.get("quote_id") or "").strip()
            if quote_id:
                quote_ids.add(quote_id)

    rules_path = root / "rules" / "rules.jsonl"
    released_rule_count = 0
    if rules_path.exists():
        seen_rule_ids: set[str] = set()
        with rules_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    rule = json.loads(line)
                except json.JSONDecodeError:
                    failures.append(f"invalid_rule_json:line_{line_number}")
                    continue
                rule_id = str(rule.get("rule_id", "")).strip()
                if not rule_id:
                    failures.append(f"rule_id_missing:line_{line_number}")
                elif rule_id in seen_rule_ids:
                    failures.append(f"duplicate_rule_id:{rule_id}")
                seen_rule_ids.add(rule_id)
                if rule.get("status") == "released":
                    released_rule_count += 1
                    if rule.get("action_class") == "safe":
                        failures.append(f"forbidden_safe_action:{rule_id}")
                    for field in (
                        "clinical_node_id",
                        "ingredient_id",
                        "outcome_id",
                        "action_class",
                        "severity",
                        "message_short",
                        "uncertainty_statement",
                        "certainty_grade",
                    ):
                        if not rule.get(field):
                            failures.append(f"released_rule_missing_{field}:{rule_id}")
                    evidence_ids = rule.get("evidence_ids") or []
                    source_quote_ids = rule.get("source_quote_ids") or []
                    reviewers = rule.get("reviewer_ids") or []
                    if not evidence_ids:
                        failures.append(f"released_rule_without_evidence:{rule_id}")
                    if not source_quote_ids:
                        failures.append(f"released_rule_without_source_quote:{rule_id}")
                    elif quote_ids and any(qid not in quote_ids for qid in source_quote_ids):
                        failures.append(f"released_rule_unknown_source_quote:{rule_id}")
                    if not reviewers:
                        failures.append(f"released_rule_without_reviewer:{rule_id}")
        if released_rule_count == 0:
            failures.append("no_released_rules")

    scenario_metrics = root / "validation" / "scenario_metrics.json"
    if scenario_metrics.exists():
        metrics = load_json(scenario_metrics)
        n_scenarios = as_int(metrics.get("n_scenarios")) or 0
        sensitivity = as_float(metrics.get("hazard_sensitivity"))
        critical_fn = as_int(metrics.get("critical_false_negative_count"))
        provenance = as_float(metrics.get("provenance_completeness"))
        if n_scenarios < int(thresholds["minimum_validation_scenarios"]):
            failures.append(f"too_few_validation_scenarios:{n_scenarios}")
        if sensitivity is None or sensitivity < float(
            thresholds["scenario_hazard_sensitivity_point_estimate_min"]
        ):
            failures.append(f"scenario_sensitivity_below_threshold:{sensitivity}")
        if not metrics.get("hazard_sensitivity_ci95"):
            failures.append("scenario_sensitivity_ci_missing")
        if critical_fn is None or critical_fn > int(thresholds["sentinel_critical_false_negative_max"]):
            failures.append(f"critical_false_negative_present:{critical_fn}")
        if provenance is None or provenance < float(thresholds["provenance_completeness_required"]):
            failures.append(f"provenance_incomplete:{provenance}")

    claim_ledger = root / "thesis" / "claim_ledger.csv"
    if claim_ledger.exists():
        rows = read_csv(claim_ledger)
        if not rows:
            failures.append("empty_claim_ledger")
        for index, row in enumerate(rows, start=2):
            claim_type = (row.get("claim_type") or "").strip().lower()
            if (row.get("status") or "").strip().lower() != "verified":
                failures.append(f"unverified_claim:line_{index}")
            if claim_type == "numeric" and (
                not (row.get("metric_id") or "").strip()
                or not (row.get("analysis_script") or "").strip()
            ):
                failures.append(f"numeric_claim_without_metric_provenance:line_{index}")
            if claim_type in {"literature", "clinical"} and (
                not (row.get("source_id") or "").strip()
                or not (row.get("source_locator") or "").strip()
            ):
                failures.append(f"literature_claim_without_locator:line_{index}")

    result = {
        "pass": not failures,
        "research_root": str(root),
        "thresholds": thresholds,
        "released_rule_count": released_rule_count,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
