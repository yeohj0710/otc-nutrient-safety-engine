#!/usr/bin/env python3
"""Create an evidence freeze only when every prerequisite artifact is valid."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_JSON = [
    "screening/prisma_counts.json",
    "ai_eval/screening_metrics.json",
    "ai_eval/extraction_metrics.json",
    "synthesis/focused_node_decision.json",
    "synthesis/focused_results.json",
    "validation/scenario_metrics.json",
    "validation/content_validity.json",
]
REQUIRED_FILES = [
    "protocol/protocol.md",
    "protocol/protocol.sha256",
    "search/search_run_log.csv",
    "screening/title_abstract.csv",
    "screening/full_text.csv",
    "extraction/extraction.csv",
    "risk_of_bias/assessments.csv",
    "synthesis/grade.csv",
    "synthesis/evidence_map.csv",
    "rules/rules.jsonl",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nonempty_csv(path: Path) -> bool:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle), None) is not None


def validate(root: Path) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for relative in REQUIRED_FILES + REQUIRED_JSON:
        path = root / relative
        if not path.exists():
            errors.append(f"missing:{relative}")
            continue
        hashes[relative] = sha256(path)
        if path.suffix == ".csv" and not nonempty_csv(path):
            errors.append(f"empty:{relative}")
    for relative in REQUIRED_JSON:
        path = root / relative
        if not path.exists():
            continue
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("pass") is False:
            errors.append(f"failed:{relative}")
    rules = root / "rules" / "rules.jsonl"
    if rules.exists() and not rules.read_text(encoding="utf-8").strip():
        errors.append("empty:rules/rules.jsonl")
    return sorted(set(errors)), hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_root", nargs="?", default="research_v2")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--frozen-at", required=True, help="Approved UTC ISO-8601 timestamp")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    root = Path(args.research_root)
    errors, hashes = validate(root)
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result = {
        "status": "frozen" if not errors else "not_frozen",
        "pass": not errors,
        "dataset_version": args.dataset_version,
        "frozen_at": args.frozen_at,
        "source_commit": source_commit,
        "artifact_sha256": hashes,
        "errors": errors,
    }
    out = Path(args.out) if args.out else root / "audit" / "evidence_freeze.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
