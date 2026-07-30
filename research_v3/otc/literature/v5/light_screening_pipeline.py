"""Materialize and audit the deterministic v5 classifier layer.

This module does not perform agent inference.  It prepares evidence batches,
validates classifier projections, and materializes the immutable 43,207-row
classifier layer.  Semantic edge-case adjudication is maintained separately by
``adjudication_pipeline_v50.py`` and may override only the final projection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
EVIDENCE = V5 / "evidence_map.csv"
SCREEN = V5 / "screening"
PROMPT = V5 / "prompts" / "frozen_light_screening_prompt.md"
BATCHES = SCREEN / "batches"
OUTPUTS = SCREEN / "agent_outputs"
CHECKPOINTS = SCREEN / "checkpoints.jsonl"
CLASSIFIER_DECISIONS_CSV = SCREEN / "classifier_decisions.csv"
PROGRESS = ROOT / "research_v3" / "logs" / "v50_progress.json"
ORDER = [
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
]
DECISIONS = {"retain", "deprioritize", "uncertain"}
REASONS = {
    "population", "exposure", "outcome", "human_signal", "design_signal",
    "animal_term_present", "insufficient_abstract", "off_topic",
}
CONFIDENCE = {"high", "medium", "low"}
BASES = {"abstract", "title_only"}
DECISION_FIELDS = [
    "record_id", "question_id", "decision", "reason_codes", "confidence", "evidence_basis"
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def materialize_decisions() -> dict:
    """Create the deterministic CSV projection without changing append-only checkpoints."""
    rows = [
        json.loads(line)
        for line in CHECKPOINTS.read_text(encoding="utf-8").splitlines()
        if line
    ]
    keys = [(row["record_id"], row["question_id"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("checkpoints contain duplicate screening units")
    rows.sort(key=lambda row: (ORDER.index(row["question_id"]), row["record_id"]))
    with CLASSIFIER_DECISIONS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_FIELDS)
        writer.writeheader()
        for row in rows:
            projected = {field: row[field] for field in DECISION_FIELDS}
            projected["reason_codes"] = ";".join(projected["reason_codes"])
            writer.writerow(projected)
    return {
        "path": CLASSIFIER_DECISIONS_CSV.relative_to(ROOT).as_posix(),
        "rows": len(rows),
        "sha256": sha256(CLASSIFIER_DECISIONS_CSV),
    }


def memberships(question_id: str) -> list[dict]:
    rows: list[dict] = []
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if question_id not in row["question_ids"].split(";"):
                continue
            rows.append({
                "record_id": row["record_id"],
                "question_id": question_id,
                "title": row["title"],
                "abstract": row["abstract"],
                "publication_types": row["publication_types"],
                "mesh_terms": row["mesh_terms"],
            })
    return rows


def prepare(question_id: str, batch_size: int) -> dict:
    if question_id not in ORDER:
        raise SystemExit(f"unknown question: {question_id}")
    rows = memberships(question_id)
    target = BATCHES / question_id
    target.mkdir(parents=True, exist_ok=True)
    OUTPUTS.joinpath(question_id).mkdir(parents=True, exist_ok=True)
    batches = []
    for index in range(0, len(rows), batch_size):
        chunk = rows[index:index + batch_size]
        batch_id = f"{question_id}-B{index // batch_size + 1:03d}"
        path = target / f"{batch_id}.jsonl"
        if not path.exists():
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                for row in chunk:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        batches.append({
            "batch_id": batch_id,
            "input_path": path.relative_to(ROOT).as_posix(),
            "output_path": (OUTPUTS / question_id / f"{batch_id}.jsonl").relative_to(ROOT).as_posix(),
            "row_count": len(chunk),
            "input_sha256": sha256(path),
        })
    manifest = {
        "question_id": question_id,
        "prepared_at_utc": now(),
        "batch_size": batch_size,
        "row_count": len(rows),
        "prompt_path": PROMPT.relative_to(ROOT).as_posix(),
        "prompt_sha256": sha256(PROMPT),
        "evidence_map_sha256": sha256(EVIDENCE),
        "batches": batches,
    }
    path = target / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def validate_output(batch: dict) -> list[dict]:
    input_path = ROOT / batch["input_path"]
    output_path = ROOT / batch["output_path"]
    inputs = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    outputs = [json.loads(line) for line in output_path.read_text(encoding="utf-8-sig").splitlines() if line]
    if len(outputs) != len(inputs):
        raise ValueError(f"{batch['batch_id']}: {len(outputs)} outputs != {len(inputs)} inputs")
    expected = [(x["record_id"], x["question_id"]) for x in inputs]
    actual = [(x.get("record_id"), x.get("question_id")) for x in outputs]
    if actual != expected:
        raise ValueError(f"{batch['batch_id']}: output keys/order differ from input")
    allowed = {"record_id", "question_id", "decision", "reason_codes", "confidence", "evidence_basis"}
    for row, source in zip(outputs, inputs):
        if set(row) != allowed:
            raise ValueError(f"{batch['batch_id']}/{row.get('record_id')}: fields differ")
        if row["decision"] not in DECISIONS or row["confidence"] not in CONFIDENCE:
            raise ValueError(f"{batch['batch_id']}/{row['record_id']}: invalid decision/confidence")
        if not isinstance(row["reason_codes"], list) or not row["reason_codes"] or not set(row["reason_codes"]) <= REASONS:
            raise ValueError(f"{batch['batch_id']}/{row['record_id']}: invalid reason_codes")
        expected_basis = "abstract" if source["abstract"].strip() else "title_only"
        if row["evidence_basis"] != expected_basis or (expected_basis == "title_only" and row["confidence"] != "low"):
            raise ValueError(f"{batch['batch_id']}/{row['record_id']}: invalid evidence basis/confidence")
    return outputs


def ingest(question_id: str) -> dict:
    manifest = json.loads((BATCHES / question_id / "manifest.json").read_text(encoding="utf-8"))
    existing_keys: set[tuple[str, str]] = set()
    if CHECKPOINTS.exists():
        for line in CHECKPOINTS.read_text(encoding="utf-8").splitlines():
            if line:
                row = json.loads(line)
                existing_keys.add((row["record_id"], row["question_id"]))
    all_rows: list[dict] = []
    commits = []
    for batch in manifest["batches"]:
        rows = validate_output(batch)
        all_rows.extend(rows)
        commits.append({
            "batch_id": batch["batch_id"],
            "execution_layer": "deterministic_text_classifier",
            "attribution_unsupported": True,
            "attribution_note": (
                "The classifier output schema contains no durable agent identity; "
                "legacy assigned_agent values are unsupported."
            ),
            "output_file_mtime_utc": datetime.fromtimestamp(
                (ROOT / batch["output_path"]).stat().st_mtime, timezone.utc
            ).isoformat(),
            "semantic_review_completed_at_utc": None,
            "completion_time_unsupported": True,
            "row_count": len(rows),
            "input_sha256": batch["input_sha256"],
            "output_sha256": sha256(ROOT / batch["output_path"]),
        })
    new_rows = [row for row in all_rows if (row["record_id"], row["question_id"]) not in existing_keys]
    SCREEN.mkdir(parents=True, exist_ok=True)
    with CHECKPOINTS.open("a", encoding="utf-8", newline="\n") as handle:
        for row in new_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    decisions_csv = materialize_decisions()
    counts = Counter(row["decision"] for row in all_rows)
    progress = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {
        "schema_version": "5.0.0", "phase": "C", "question_order": ORDER, "questions": {}
    }
    progress["updated_at_utc"] = now()
    progress["prompt_sha256"] = manifest["prompt_sha256"]
    progress["questions"][question_id] = {
        "expected": manifest["row_count"],
        "screened": len(all_rows),
        "coverage": len(all_rows) / manifest["row_count"] if manifest["row_count"] else 1.0,
        "decision_distribution": dict(sorted(counts.items())),
        "complete": len(all_rows) == manifest["row_count"],
        "batches": commits,
    }
    progress["classifier_questions_completed"] = sum(
        bool(progress["questions"].get(q, {}).get("complete")) for q in ORDER
    )
    progress["classifier_all_questions_complete"] = (
        progress["classifier_questions_completed"] == len(ORDER)
    )
    progress["classifier_current_question"] = (
        None if progress["classifier_all_questions_complete"] else question_id
    )
    progress["classifier_completed_rows"] = sum(
        int(progress["questions"].get(q, {}).get("screened", 0)) for q in ORDER
    )
    progress["classifier_total_rows"] = sum(
        int(progress["questions"].get(q, {}).get("expected", 0)) for q in ORDER
    )
    for q in ORDER:
        for batch in progress["questions"].get(q, {}).get("batches", []):
            legacy_agent = batch.pop("assigned_agent", None)
            if legacy_agent is not None:
                batch["legacy_claimed_assigned_agent"] = legacy_agent
            batch["execution_layer"] = "deterministic_text_classifier"
            batch["attribution_unsupported"] = True
            batch["attribution_note"] = (
                "The classifier output schema contains no durable agent identity."
            )
            legacy_time = batch.pop("completed_at_utc", None)
            if legacy_time is not None:
                batch["output_file_mtime_utc"] = legacy_time
            batch["semantic_review_completed_at_utc"] = None
            batch["completion_time_unsupported"] = True
    completed_times = [
        datetime.fromisoformat(batch["output_file_mtime_utc"])
        for q in ORDER
        for batch in progress["questions"].get(q, {}).get("batches", [])
        if batch.get("output_file_mtime_utc")
    ]
    progress["classifier_output_mtime_span_seconds"] = (
        (max(completed_times) - min(completed_times)).total_seconds() if completed_times else 0
    )
    progress["phase"] = "C_classifier_complete_semantic_adjudication_pending"
    progress["semantic_adjudication_status"] = "pending"
    progress["all_questions_complete"] = False
    progress["classifier_decisions_csv"] = decisions_csv
    for unsupported_key in (
        "questions_completed",
        "current_question",
        "completed_rows",
        "total_rows",
        "elapsed_time_seconds",
        "recent_30min_rows",
        "estimated_remaining_time_seconds",
        "decisions_csv",
    ):
        progress.pop(unsupported_key, None)
    progress["independent_blinding"] = False
    progress["release_ready"] = False
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"question_id": question_id, "appended": len(new_rows), **progress["questions"][question_id]}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--question-id", required=True, choices=ORDER)
    p.add_argument("--batch-size", type=int, default=240)
    i = sub.add_parser("ingest")
    i.add_argument("--question-id", required=True, choices=ORDER)
    args = parser.parse_args()
    result = prepare(args.question_id, args.batch_size) if args.command == "prepare" else ingest(args.question_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
