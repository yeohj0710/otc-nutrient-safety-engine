#!/usr/bin/env python3
"""Validate the hand-authored v5.1 shortlist semantic triage without writing it."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHORTLIST = ROOT / "research_v3" / "otc" / "rules" / "rule_evidence_shortlist.csv"
TARGET_TRIAGE = ROOT / "research_v51" / "review" / "shortlist_semantic_triage.csv"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
PRODUCTS = ROOT / "research_v3" / "otc" / "normalized" / "product_master.csv"

SOURCE_REVIEW_STATUS = "codex_recommended_not_expert_verified"
FIELDS = (
    "evidence_candidate_id",
    "rule_id",
    "rule_type",
    "product_name",
    "item_sequence",
    "current_scope",
    "semantic_relation",
    "recommended_status",
    "proposed_trigger",
    "expected_decision_ko",
    "decision_reason_ko",
    "expert_question_ko",
)
ALLOWED_RELATIONS = {
    "direct_same_scope",
    "potential_product_extension",
    "wrong_scope",
    "duplicate_context",
}
ALLOWED_STATUSES = {"provisional", "rejected", "needs_expert_review"}
EXPECTED_RELATION_COUNTS = {
    "direct_same_scope": 3,
    "potential_product_extension": 16,
    "wrong_scope": 9,
    "duplicate_context": 5,
}
EXPECTED_STATUS_COUNTS = {
    "provisional": 2,
    "needs_expert_review": 17,
    "rejected": 14,
}
FORBIDDEN_CLAIMS = (
    re.compile(r"human[_ ]?expert[_ ]?verified", re.IGNORECASE),
    re.compile(r"verified_primary", re.IGNORECASE),
    re.compile(r"supports[_ ]?release\s*=\s*true", re.IGNORECASE),
    re.compile(r"release[_ ]?ready\s*=\s*true", re.IGNORECASE),
    re.compile(r"전문가\s*검토\s*완료"),
    re.compile(r"사람\s*검토\s*완료"),
    re.compile(r"운영\s*활성화"),
    re.compile(r"운영\s*규칙으로\s*활성"),
)


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = tuple(reader.fieldnames or ())
        return headers, list(reader)


def duplicate_values(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count != 1)


def unique_index(
    rows: list[dict[str, str]], key: str, label: str, errors: list[str]
) -> dict[str, dict[str, str]]:
    duplicates = duplicate_values([row.get(key, "") for row in rows])
    if duplicates:
        errors.append(f"{label}_DUPLICATE_KEYS key={key} values={'|'.join(duplicates)}")
    return {row.get(key, ""): row for row in rows}


def validate(
    *,
    source_path: Path = SOURCE_SHORTLIST,
    target_path: Path = TARGET_TRIAGE,
    rules_path: Path = RULES,
    products_path: Path = PRODUCTS,
) -> dict[str, Any]:
    """Return a read-only validation report for the manual triage artifact."""

    errors: list[str] = []
    for label, path in (
        ("source", source_path),
        ("target", target_path),
        ("rules", rules_path),
        ("products", products_path),
    ):
        if not path.is_file():
            errors.append(f"MISSING_FILE label={label} path={path}")
    if errors:
        return {"valid": False, "errors": errors}

    _, all_source_rows = read_csv(source_path)
    target_headers, target_rows = read_csv(target_path)
    _, rule_rows = read_csv(rules_path)
    _, product_rows = read_csv(products_path)
    source_rows = [
        row for row in all_source_rows if row["review_status"] == SOURCE_REVIEW_STATUS
    ]

    if target_headers != FIELDS:
        errors.append(
            "TARGET_FIELDS_MISMATCH "
            f"expected={'|'.join(FIELDS)} observed={'|'.join(target_headers)}"
        )
    if len(source_rows) != 33:
        errors.append(f"SOURCE_ROW_COUNT expected=33 observed={len(source_rows)}")
    if len(target_rows) != 33:
        errors.append(f"TARGET_ROW_COUNT expected=33 observed={len(target_rows)}")

    source_ids = [row["evidence_candidate_id"] for row in source_rows]
    target_ids = [row.get("evidence_candidate_id", "") for row in target_rows]
    source_duplicates = duplicate_values(source_ids)
    target_duplicates = duplicate_values(target_ids)
    if source_duplicates:
        errors.append(f"SOURCE_DUPLICATE_IDS values={'|'.join(source_duplicates)}")
    if target_duplicates:
        errors.append(f"TARGET_DUPLICATE_IDS values={'|'.join(target_duplicates)}")
    missing_ids = sorted(set(source_ids) - set(target_ids))
    extra_ids = sorted(set(target_ids) - set(source_ids))
    if missing_ids:
        errors.append(f"TARGET_MISSING_IDS values={'|'.join(missing_ids)}")
    if extra_ids:
        errors.append(f"TARGET_EXTRA_IDS values={'|'.join(extra_ids)}")

    source_by_id = unique_index(
        source_rows, "evidence_candidate_id", "SOURCE", errors
    )
    rules_by_id = unique_index(rule_rows, "rule_id", "RULES", errors)
    products_by_sequence = unique_index(
        product_rows, "item_sequence", "PRODUCTS", errors
    )

    source_field_map = {
        "rule_id": "rule_id",
        "rule_type": "rule_type",
        "product_name": "product_name",
        "item_sequence": "item_sequence",
        "current_scope": "scope",
    }
    for row_number, row in enumerate(target_rows, start=2):
        candidate_id = row.get("evidence_candidate_id", "")
        for field in FIELDS:
            if not row.get(field, "").strip():
                errors.append(
                    f"EMPTY_FIELD row={row_number} id={candidate_id} field={field}"
                )

        if row.get("semantic_relation") not in ALLOWED_RELATIONS:
            errors.append(
                "INVALID_SEMANTIC_RELATION "
                f"id={candidate_id} value={row.get('semantic_relation', '')}"
            )
        if row.get("recommended_status") not in ALLOWED_STATUSES:
            errors.append(
                "INVALID_RECOMMENDED_STATUS "
                f"id={candidate_id} value={row.get('recommended_status', '')}"
            )

        source = source_by_id.get(candidate_id)
        if source:
            for target_field, source_field in source_field_map.items():
                if row.get(target_field) != source.get(source_field):
                    errors.append(
                        "SOURCE_METADATA_MISMATCH "
                        f"id={candidate_id} field={target_field} "
                        f"expected={source.get(source_field, '')} "
                        f"observed={row.get(target_field, '')}"
                    )

        rule = rules_by_id.get(row.get("rule_id", ""))
        if rule is None:
            errors.append(
                f"RULE_NOT_FOUND id={candidate_id} rule_id={row.get('rule_id', '')}"
            )
        else:
            if row.get("rule_type") != rule.get("rule_type"):
                errors.append(
                    "RULE_TYPE_MISMATCH "
                    f"id={candidate_id} expected={rule.get('rule_type', '')} "
                    f"observed={row.get('rule_type', '')}"
                )
            if row.get("current_scope") != rule.get("scope"):
                errors.append(
                    "RULE_SCOPE_MISMATCH "
                    f"id={candidate_id} expected={rule.get('scope', '')} "
                    f"observed={row.get('current_scope', '')}"
                )

        product = products_by_sequence.get(row.get("item_sequence", ""))
        if product is None:
            errors.append(
                "PRODUCT_NOT_FOUND "
                f"id={candidate_id} item_sequence={row.get('item_sequence', '')}"
            )
        elif row.get("product_name") != product.get("product_name"):
            errors.append(
                "PRODUCT_NAME_MISMATCH "
                f"id={candidate_id} expected={product.get('product_name', '')} "
                f"observed={row.get('product_name', '')}"
            )

        joined_text = "\n".join(row.get(field, "") for field in FIELDS)
        for pattern in FORBIDDEN_CLAIMS:
            if pattern.search(joined_text):
                errors.append(
                    f"FORBIDDEN_REVIEW_OR_ACTIVATION_CLAIM id={candidate_id} "
                    f"pattern={pattern.pattern}"
                )

    relation_counts = dict(Counter(row.get("semantic_relation", "") for row in target_rows))
    status_counts = dict(Counter(row.get("recommended_status", "") for row in target_rows))
    if relation_counts != EXPECTED_RELATION_COUNTS:
        errors.append(
            "SEMANTIC_RELATION_COUNTS "
            f"expected={EXPECTED_RELATION_COUNTS} observed={relation_counts}"
        )
    if status_counts != EXPECTED_STATUS_COUNTS:
        errors.append(
            "RECOMMENDED_STATUS_COUNTS "
            f"expected={EXPECTED_STATUS_COUNTS} observed={status_counts}"
        )

    return {
        "valid": not errors,
        "errors": errors,
        "source_rows": len(source_rows),
        "target_rows": len(target_rows),
        "unique_target_ids": len(set(target_ids)),
        "semantic_relation_counts": relation_counts,
        "recommended_status_counts": status_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only validation for the manual v5.1 shortlist triage"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing manual artifact without writing or regenerating it",
    )
    args = parser.parse_args()
    if not args.check:
        parser.error("--check is required; this validator never regenerates judgments")

    report = validate()
    if not report["valid"]:
        for error in report["errors"]:
            print(error, file=sys.stderr)
        return 1
    print(
        "v5.1 shortlist triage valid: "
        f"source_rows={report['source_rows']} "
        f"target_rows={report['target_rows']} "
        f"unique_ids={report['unique_target_ids']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
