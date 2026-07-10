#!/usr/bin/env python3
"""Generate auditable PRISMA 2020 counts from record- and report-level logs.

This script distinguishes records, reports, and studies. It refuses to silently
mix database hit counts with a top-N import or incomplete adjudication.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

TRUE_VALUES = {"1", "true", "yes", "y"}
FINAL_DECISIONS = {"include", "exclude"}


def read_rows(path: str) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def final_decision(row: dict[str, str]) -> str:
    return (row.get("adjudicated_decision") or row.get("decision") or "").strip().lower()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True, help="Normalized record log")
    parser.add_argument("--ta", required=True, help="Title/abstract screening log")
    parser.add_argument("--ft", required=True, help="Full-text screening log")
    parser.add_argument("--retrieval", help="Optional full-text retrieval log")
    parser.add_argument("--out", default="prisma_counts.json")
    args = parser.parse_args()

    records = read_rows(args.records)
    ta_rows = read_rows(args.ta)
    ft_rows = read_rows(args.ft)
    retrieval_rows = read_rows(args.retrieval) if args.retrieval else []

    errors: list[str] = []
    warnings: list[str] = []

    record_ids = [row.get("record_id", "").strip() for row in records]
    if any(not value for value in record_ids):
        errors.append("records file contains blank record_id")
    duplicate_record_ids = [key for key, count in Counter(record_ids).items() if key and count > 1]
    if duplicate_record_ids:
        errors.append(f"duplicate record_id values in records file: {len(duplicate_record_ids)}")

    identified = len({value for value in record_ids if value})
    duplicates_removed = sum(truthy(row.get("is_duplicate")) for row in records)
    removed_before_screening = sum(
        truthy(row.get("removed_before_screening")) and not truthy(row.get("is_duplicate"))
        for row in records
    )
    expected_screened = identified - duplicates_removed - removed_before_screening

    ta_by_id: dict[str, str] = {}
    for row in ta_rows:
        record_id = row.get("record_id", "").strip()
        if not record_id:
            errors.append("title/abstract file contains blank record_id")
            continue
        decision = final_decision(row)
        if decision not in FINAL_DECISIONS:
            errors.append(f"title/abstract record lacks final include/exclude decision: {record_id}")
        previous = ta_by_id.get(record_id)
        if previous and previous != decision:
            errors.append(f"conflicting final title/abstract decisions: {record_id}")
        ta_by_id[record_id] = decision

    screened = len(ta_by_id)
    records_excluded = sum(value == "exclude" for value in ta_by_id.values())
    reports_sought = sum(value == "include" for value in ta_by_id.values())

    ft_by_report: dict[str, dict[str, str]] = {}
    for row in ft_rows:
        report_id = row.get("report_id", "").strip()
        if not report_id:
            errors.append("full-text file contains blank report_id")
            continue
        decision = final_decision(row)
        if decision and decision not in FINAL_DECISIONS:
            errors.append(f"invalid full-text final decision for {report_id}: {decision}")
        if report_id in ft_by_report and final_decision(ft_by_report[report_id]) != decision:
            errors.append(f"conflicting final full-text decisions: {report_id}")
        ft_by_report[report_id] = row

    assessed_rows = {
        report_id: row
        for report_id, row in ft_by_report.items()
        if final_decision(row) in FINAL_DECISIONS
    }
    reports_assessed = len(assessed_rows)
    reports_excluded = sum(final_decision(row) == "exclude" for row in assessed_rows.values())
    reports_included = sum(final_decision(row) == "include" for row in assessed_rows.values())

    not_retrieved_ids: set[str] = set()
    for row in retrieval_rows:
        report_id = row.get("report_id", "").strip()
        result = (row.get("result") or "").strip().lower()
        if report_id and result in {"not_retrieved", "unavailable", "failed", "not available"}:
            not_retrieved_ids.add(report_id)
    reports_not_retrieved = len(not_retrieved_ids)
    if not retrieval_rows:
        inferred = reports_sought - reports_assessed
        if inferred < 0:
            errors.append("full-text reports assessed exceeds reports sought")
            inferred = 0
        reports_not_retrieved = inferred
        warnings.append("reports_not_retrieved inferred because no retrieval log was supplied")

    included_study_families = {
        row.get("study_family_id", "").strip()
        for row in assessed_rows.values()
        if final_decision(row) == "include" and row.get("study_family_id", "").strip()
    }
    studies_included = len(included_study_families)
    if reports_included and not included_study_families:
        errors.append("included reports lack study_family_id values")

    exclusion_reasons = Counter(
        (row.get("primary_exclusion_reason") or "unspecified").strip()
        for row in assessed_rows.values()
        if final_decision(row) == "exclude"
    )

    if screened != expected_screened:
        errors.append(
            f"records_screened ({screened}) != identified - duplicates - other removals ({expected_screened})"
        )
    if reports_sought != reports_assessed + reports_not_retrieved:
        errors.append(
            "reports_sought does not equal reports_assessed + reports_not_retrieved"
        )
    if reports_assessed != reports_excluded + reports_included:
        errors.append("reports_assessed does not equal reports_excluded + reports_included")
    if reports_included < studies_included:
        errors.append("studies_included cannot exceed reports_included")

    result = {
        "records_identified": identified,
        "duplicate_records_removed": duplicates_removed,
        "other_records_removed_before_screening": removed_before_screening,
        "records_screened": screened,
        "records_excluded": records_excluded,
        "reports_sought_for_retrieval": reports_sought,
        "reports_not_retrieved": reports_not_retrieved,
        "reports_assessed_for_eligibility": reports_assessed,
        "reports_excluded": reports_excluded,
        "full_text_exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "reports_included": reports_included,
        "studies_included": studies_included,
        "validation_errors": errors,
        "warnings": warnings,
        "pass": not errors,
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
