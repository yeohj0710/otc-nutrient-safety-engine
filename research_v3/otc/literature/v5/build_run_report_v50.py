"""Build the self-contained v5.0 literature-search run ledger.

The builder is intentionally read-only apart from the atomic write of
``research_v3/logs/v50_run_report.json``.  Phase A and B inputs are required;
Phase C, Phase D, and final-audit inputs are reported exactly as present so a
partial run remains resumable and is never described as complete.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
LOGS = ROOT / "research_v3" / "logs"
OUTPUT = LOGS / "v50_run_report.json"

PROBE = V5 / "probe_report.json"
QUERY_DEFINITIONS = V5 / "query_definitions.json"
INGREDIENT_MAPPINGS = V5 / "ingredient_mappings.json"
CORPUS_MANIFEST = V5 / "corpus_manifest.json"
EVIDENCE_MAP = V5 / "evidence_map.csv"
SCREENING_MANIFEST = V5 / "screening" / "screening_manifest.json"
SCREENING_PROGRESS = LOGS / "v50_progress.json"
SCREENING_BATCHES = V5 / "screening" / "batches.jsonl"
SCREENING_DECISIONS = V5 / "screening" / "decisions.csv"
SCREENING_CHECKPOINTS = V5 / "screening" / "checkpoints.jsonl"
PROMPT_LOCK = V5 / "screening" / "prompt_lock.json"
FROZEN_PROMPT = V5 / "screening" / "agent_screening_prompt_v50.frozen.md"
DOWNSTREAM_MANIFEST = V5 / "literature_link_manifest.json"
SUPPORTING_LITERATURE = V5 / "supporting_literature.csv"
BASELINE_AUDIT = LOGS / "v50_protected_baseline.json"
AMENDMENTS = ROOT / "research_v3" / "protocol" / "amendments.csv"
DECISIONS_LOG = LOGS / "DECISIONS_v50.md"
PROTOCOL = ROOT / "research_v3" / "protocol" / "protocol-v5.0-mecir-search.md"

QUESTION_ORDER = (
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{repo_relative(path)}:{line_number}: JSON object required")
            rows.append(value)
    return rows


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def file_record(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": repo_relative(path), "exists": path.is_file()}
    if path.is_file():
        result.update({"bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return result


def atomic_write_json(path: Path, payload: Any) -> None:
    if path.resolve() != OUTPUT.resolve():
        raise RuntimeError(f"refusing unexpected write target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_reason_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item)]
    return [part.strip() for part in re.split(r"[;,|]", text) if part.strip()]


def count_distribution(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "")) for row in rows if row.get(key, "")).items()))


def source_registry(paths: Iterable[Path]) -> list[dict[str, Any]]:
    seen: set[Path] = set()
    records: list[dict[str, Any]] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            records.append(file_record(path))
    return records


def build_phase_a(
    probe: dict[str, Any], queries: dict[str, Any], mappings: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[str]]:
    query_by_id = {item["question_id"]: item for item in queries.get("questions", [])}
    mapping_rows = mappings.get("mappings", [])
    mapping_by_id = {item["ingredient_id"]: item for item in mapping_rows}
    selected = list(probe.get("selected_ingredients_in_queries", []))
    missing = sorted(set(queries.get("selected_ingredient_ids", [])) - set(selected))

    classified_terms_by_question: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    compliance_by_rule: dict[int, dict[str, Any]] = {}
    included_terms: dict[str, set[str]] = {}
    for question in probe.get("questions", []):
        qid = question["question_id"]
        classifications = question.get("term_classification", [])
        included_terms[qid] = {
            str(item.get("term", ""))
            for item in classifications
            if item.get("included_in_query") is True
        }
        classified_terms_by_question.append(
            {
                "question_id": qid,
                "title_ko": question.get("title_ko"),
                "block_structure": question.get("block_structure"),
                "term_counts": question.get("term_counts", {}),
                "terms": classifications,
            }
        )
        v4 = int(question.get("v4_hit_count", 0))
        v5 = int(question.get("hit_count", 0))
        changes.append(
            {
                "question_id": qid,
                "v4_hit_count": v4,
                "v5_hit_count": v5,
                "absolute_change": v5 - v4,
                "fold_change": (v5 / v4) if v4 else None,
                "display": f"{qid}: {v4} → {v5}",
            }
        )
        for check in question.get("protocol_section_3_self_check", []):
            number = int(check["rule"])
            aggregate = compliance_by_rule.setdefault(
                number,
                {
                    "rule": number,
                    "requirement_ko": check.get("requirement_ko"),
                    "question_results": [],
                },
            )
            aggregate["question_results"].append(
                {"question_id": qid, "status": check.get("status"), "evidence": check.get("evidence")}
            )

    compliance = []
    for number in range(1, 11):
        item = compliance_by_rule.get(
            number,
            {"rule": number, "requirement_ko": None, "question_results": []},
        )
        results = item["question_results"]
        item["status"] = (
            "pass"
            if len(results) == len(QUESTION_ORDER)
            and all(result.get("status") == "pass" for result in results)
            else "violation"
        )
        compliance.append(item)

    ingredient_records: list[dict[str, Any]] = []
    for ingredient_id in queries.get("selected_ingredient_ids", []):
        mapping = mapping_by_id.get(ingredient_id)
        if not mapping:
            ingredient_records.append(
                {"ingredient_id": ingredient_id, "actually_in_query": False, "mapping_missing": True}
            )
            continue
        qid = mapping.get("question_id")
        evidence = list(mapping.get("query_evidence", []))
        matched = [term for term in evidence if term in included_terms.get(str(qid), set())]
        ingredient_records.append(
            {
                **mapping,
                "matched_query_evidence": matched,
                "unmatched_query_evidence": [term for term in evidence if term not in matched],
                "actually_in_query": ingredient_id in selected and bool(matched),
            }
        )
    actual = [row["ingredient_id"] for row in ingredient_records if row.get("actually_in_query")]
    missing_actual = sorted(set(queries.get("selected_ingredient_ids", [])) - set(actual))
    ingredient_coverage = {
        "selected_scope_count": len(queries.get("selected_ingredient_ids", [])),
        "actual_search_ingredient_count": len(actual),
        "actual_search_ingredient_ids": actual,
        "missing_ingredient_ids": missing_actual,
        "records": ingredient_records,
        "selection_reconciliation": mappings.get("selection_reconciliation"),
    }

    question_details = []
    for question in probe.get("questions", []):
        qid = question["question_id"]
        definition = query_by_id.get(qid, {})
        question_details.append(
            {
                "question_id": qid,
                "title_ko": question.get("title_ko"),
                "ingredient_ids": question.get("ingredient_ids", []),
                "rule_types": question.get("rule_types", []),
                "date_range": definition.get("date_range"),
                "block_structure": question.get("block_structure"),
                "blocks": definition.get("blocks"),
                "query": question.get("query"),
                "query_sha256": question.get("query_sha256"),
                "hit_count": question.get("hit_count"),
                "v4_hit_count": question.get("v4_hit_count"),
                "change_from_v4": question.get("change_from_v4"),
                "term_counts": question.get("term_counts"),
                "term_classification": question.get("term_classification"),
                "esearch": question.get("esearch"),
                "protocol_section_3_self_check": question.get("protocol_section_3_self_check"),
                "all_rules_pass": question.get("all_rules_pass"),
            }
        )

    violations: list[str] = []
    if missing or missing_actual:
        violations.append(f"selected ingredients missing from queries: {sorted(set(missing + missing_actual))}")
    failed_rules = [item["rule"] for item in compliance if item["status"] != "pass"]
    if failed_rules:
        violations.append(f"protocol section 3 checks failed: {failed_rules}")
    phase = {
        "status": (
            "complete"
            if probe.get("status") == "complete"
            and len(question_details) == len(QUESTION_ORDER)
            and not violations
            else "incomplete_or_noncompliant"
        ),
        "method": probe.get("method"),
        "database": probe.get("database"),
        "started_at_utc": probe.get("started_at_utc"),
        "completed_at_utc": probe.get("completed_at_utc"),
        "efetch_calls": probe.get("totals", {}).get("efetch_calls"),
        "totals": probe.get("totals"),
        "query_definitions": queries,
        "questions": question_details,
        "v4_to_v5_hit_count_change": changes,
        "term_classification_tables": classified_terms_by_question,
        "protocol_section_3_compliance": compliance,
        "ingredient_coverage": ingredient_coverage,
        "v4_to_v5_causal_record_ko": probe.get("v4_to_v5_causal_record_ko"),
    }
    return phase, changes, ingredient_coverage, violations


def parse_checksum_manifest(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.*?)\s*$", line)
        if not match:
            raise ValueError(f"{repo_relative(path)}:{line_number}: invalid SHA-256 manifest row")
        rows.append({"declared_sha256": match.group(1).lower(), "relative_path": match.group(2)})
    return rows


def raw_retrieval_audit(corpus: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    audits: list[dict[str, Any]] = []
    problems: list[str] = []
    for question in corpus.get("questions", []):
        qid = str(question.get("question_id"))
        run_path = ROOT / str(question.get("run_path", ""))
        checksum_path = run_path / "checksum.sha256"
        metadata_path = run_path / "response_metadata.json"
        item: dict[str, Any] = {
            "question_id": qid,
            "run_id": question.get("run_id"),
            "run_path": repo_relative(run_path),
            "checksum_manifest": file_record(checksum_path),
            "response_metadata": file_record(metadata_path),
            "raw_xml_files": [],
        }
        if not checksum_path.is_file():
            item.update({"status": "failed", "problem": "checksum.sha256 missing"})
            problems.append(f"{qid}: checksum.sha256 missing")
            audits.append(item)
            continue
        entries = parse_checksum_manifest(checksum_path)
        listed_paths: set[str] = set()
        mismatches: list[dict[str, Any]] = []
        total_bytes = 0
        for entry in entries:
            relative = entry["relative_path"].replace("\\", "/")
            listed_paths.add(relative)
            raw_path = run_path / Path(relative)
            actual = sha256_file(raw_path) if raw_path.is_file() else None
            size = raw_path.stat().st_size if raw_path.is_file() else None
            total_bytes += size or 0
            record = {
                "path": relative,
                "declared_sha256": entry["declared_sha256"],
                "actual_sha256": actual,
                "bytes": size,
                "matches": actual == entry["declared_sha256"],
            }
            item["raw_xml_files"].append(record)
            if not record["matches"]:
                mismatches.append(record)
        actual_xml = {
            path.relative_to(run_path).as_posix()
            for path in run_path.rglob("*.xml")
            if path.is_file()
        }
        unlisted = sorted(actual_xml - listed_paths)
        non_xml_listings = sorted(listed_paths - actual_xml)
        expected_count = int(question.get("raw_xml_file_count", -1))
        ok = not mismatches and not unlisted and not non_xml_listings and len(actual_xml) == expected_count
        item.update(
            {
                "status": "pass" if ok else "failed",
                "listed_entry_count": len(entries),
                "actual_xml_file_count": len(actual_xml),
                "manifest_expected_xml_file_count": expected_count,
                "raw_xml_total_bytes": total_bytes,
                "mismatches": mismatches,
                "unlisted_xml_files": unlisted,
                "listed_paths_not_xml_files": non_xml_listings,
            }
        )
        if not ok:
            problems.append(f"{qid}: raw XML/checksum reconciliation failed")
        audits.append(item)
    return audits, problems


def evidence_map_audit(corpus: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    result = file_record(EVIDENCE_MAP)
    manifest = corpus.get("evidence_map", {})
    result["manifest"] = manifest
    if not EVIDENCE_MAP.is_file():
        result["status"] = "failed"
        return result, ["evidence_map.csv missing"]
    fields, rows = read_csv(EVIDENCE_MAP)
    result.update(
        {
            "actual_rows": len(rows),
            "actual_columns": fields,
            "sha256_matches_manifest": result["sha256"] == manifest.get("sha256"),
            "row_count_matches_manifest": len(rows) == manifest.get("rows"),
        }
    )
    input_values = [row.get("input_sha256", "") for row in rows]
    valid_input_hashes = [
        value for value in input_values if re.fullmatch(r"[0-9a-f]{64}", value or "")
    ]
    result["row_input_sha256_semantics"] = "SHA-256 of each canonical bibliographic record payload"
    result["row_input_sha256_nonempty_count"] = sum(bool(value) for value in input_values)
    result["row_input_sha256_valid_count"] = len(valid_input_hashes)
    result["row_input_sha256_unique_count"] = len(set(valid_input_hashes))
    result["every_row_has_valid_input_sha256"] = len(valid_input_hashes) == len(rows)
    result["status"] = (
        "pass"
        if result["sha256_matches_manifest"]
        and result["row_count_matches_manifest"]
        and result["every_row_has_valid_input_sha256"]
        else "failed"
    )
    if result["status"] != "pass":
        problems.append("evidence_map.csv hash, row count, or row input hash does not match its manifest")
    return result, problems


def build_phase_b(corpus: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    raw, raw_problems = raw_retrieval_audit(corpus)
    evidence, evidence_problems = evidence_map_audit(corpus)
    problems = raw_problems + evidence_problems
    question_complete = (
        len(corpus.get("questions", [])) == len(QUESTION_ORDER)
        and all(question.get("status") == "complete" for question in corpus.get("questions", []))
    )
    status = "complete" if corpus.get("status") == "complete" and question_complete and not problems else "incomplete_or_invalid"
    return {
        "status": status,
        "corpus_manifest": corpus,
        "raw_xml_and_checksum_integrity": raw,
        "evidence_map_integrity": evidence,
    }, problems


def screening_source_rows(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    decision_path = SCREENING_DECISIONS
    if manifest and manifest.get("decisions_csv_path"):
        decision_path = ROOT / str(manifest["decisions_csv_path"])
    if decision_path.is_file():
        _, rows = read_csv(decision_path)
        return [dict(row) for row in rows]
    if SCREENING_CHECKPOINTS.is_file():
        return read_jsonl(SCREENING_CHECKPOINTS)
    return []


def sequential_gate_audit(
    batch_events: list[dict[str, Any]], expected: dict[str, int],
) -> dict[str, Any]:
    committed = [event for event in batch_events if event.get("event") == "committed"]
    counts: Counter[str] = Counter()
    violations: list[dict[str, Any]] = []
    for event_number, event in enumerate(committed, start=1):
        qid = str(event.get("question_id", ""))
        if qid not in QUESTION_ORDER:
            violations.append({"event_number": event_number, "reason": "unknown_question_id", "event": qid})
            continue
        index = QUESTION_ORDER.index(qid)
        incomplete = [
            previous
            for previous in QUESTION_ORDER[:index]
            if counts[previous] < expected.get(previous, 0)
        ]
        if incomplete:
            violations.append(
                {
                    "event_number": event_number,
                    "batch_id": event.get("batch_id"),
                    "question_id": qid,
                    "incomplete_predecessors": incomplete,
                }
            )
        counts[qid] += int(event.get("appended_rows", event.get("new_rows", 0)) or 0)
    return {
        "status": "pass" if not violations else "failed",
        "rule": "A later question may start only after all earlier questions reach 100% coverage.",
        "committed_rows_seen_by_question": dict(counts),
        "violations": violations,
    }


def compact_batch_records(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "event",
        "batch_id",
        "question_id",
        "assigned_agent",
        "execution_mode",
        "started_at_utc",
        "completed_at_utc",
        "requested_rows",
        "new_rows",
        "appended_rows",
        "first_record_id",
        "last_record_id",
        "input_sha256",
        "output_sha256",
        "corpus_sha256",
        "prompt_sha256",
        "ruleset_sha256",
        "model_provenance_sha256",
        "input_truncated_rows",
    )
    return [{key: event.get(key) for key in fields if key in event} for event in events]


def build_phase_c(
    corpus: dict[str, Any], manifest: dict[str, Any] | None,
    progress: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str], list[Path]]:
    paths: list[Path] = [SCREENING_MANIFEST, SCREENING_PROGRESS, SCREENING_BATCHES, SCREENING_DECISIONS,
                        SCREENING_CHECKPOINTS, PROMPT_LOCK, FROZEN_PROMPT]
    expected = {key: int(value) for key, value in corpus.get("per_question_membership_rows", {}).items()}
    decisions = screening_source_rows(manifest)
    unique_pairs: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_pairs: list[list[str]] = []
    for row in decisions:
        key = (str(row.get("record_id", "")), str(row.get("question_id", "")))
        if key in unique_pairs:
            duplicate_pairs.append([*key])
        else:
            unique_pairs[key] = row

    per_question: list[dict[str, Any]] = []
    for qid in QUESTION_ORDER:
        rows = [row for (record_id, question_id), row in unique_pairs.items() if record_id and question_id == qid]
        reason_counter: Counter[str] = Counter()
        for row in rows:
            reason_counter.update(parse_reason_codes(row.get("reason_codes")))
        total = expected.get(qid, 0)
        screened = len(rows)
        per_question.append(
            {
                "question_id": qid,
                "total_memberships": total,
                "screened_memberships": screened,
                "remaining_memberships": max(total - screened, 0),
                "coverage": screened / total if total else 1.0,
                "complete": screened == total,
                "label_distribution": count_distribution(rows, "decision"),
                "confidence_distribution": count_distribution(rows, "confidence"),
                "evidence_basis_distribution": count_distribution(rows, "evidence_basis"),
                "reason_code_distribution": dict(sorted(reason_counter.items())),
            }
        )

    batch_events = read_jsonl(SCREENING_BATCHES)
    committed = [event for event in batch_events if event.get("event") == "committed"]
    batch_by_question: list[dict[str, Any]] = []
    for qid in QUESTION_ORDER:
        rows = [event for event in committed if event.get("question_id") == qid]
        batch_by_question.append(
            {
                "question_id": qid,
                "committed_batch_count": len(rows),
                "committed_row_count": sum(int(row.get("appended_rows", 0) or 0) for row in rows),
                "assigned_agents": sorted({str(row.get("assigned_agent")) for row in rows if row.get("assigned_agent")}),
                "first_started_at_utc": min((str(row.get("started_at_utc")) for row in rows if row.get("started_at_utc")), default=None),
                "last_completed_at_utc": max((str(row.get("completed_at_utc")) for row in rows if row.get("completed_at_utc")), default=None),
            }
        )
    gate = sequential_gate_audit(batch_events, expected)

    prompt_lock = load_json(PROMPT_LOCK) if PROMPT_LOCK.is_file() else None
    prompt_sha = sha256_file(FROZEN_PROMPT) if FROZEN_PROMPT.is_file() else None
    manifest_prompt_sha = manifest.get("prompt_sha256") if manifest else None
    prompt_integrity = {
        "prompt_lock": file_record(PROMPT_LOCK),
        "frozen_prompt": file_record(FROZEN_PROMPT),
        "locked_prompt_sha256": prompt_lock.get("prompt_sha256") if prompt_lock else None,
        "actual_frozen_prompt_sha256": prompt_sha,
        "manifest_prompt_sha256": manifest_prompt_sha,
    }
    hashes = [value for value in (prompt_integrity["locked_prompt_sha256"], prompt_sha, manifest_prompt_sha) if value]
    prompt_integrity["status"] = "pass" if len(hashes) >= 2 and len(set(hashes)) == 1 else "failed_or_unavailable"

    total = sum(item["total_memberships"] for item in per_question)
    screened = sum(item["screened_memberships"] for item in per_question)
    all_complete = bool(per_question) and all(item["complete"] for item in per_question)
    problems: list[str] = []
    if not manifest:
        problems.append("Phase C screening_manifest.json is absent")
    if not all_complete:
        pending = [f"{item['question_id']}={item['coverage']:.6f}" for item in per_question if not item["complete"]]
        problems.append("Phase C screening is incomplete: " + ", ".join(pending))
    if duplicate_pairs:
        problems.append(f"Phase C has {len(duplicate_pairs)} duplicate record/question decisions")
    if gate["status"] != "pass":
        problems.append("Phase C question-order gate was violated")
    if prompt_integrity["status"] != "pass":
        problems.append("Phase C frozen-prompt hashes are unavailable or inconsistent")

    status = (
        "complete"
        if manifest and all_complete and not problems
        else ("not_started" if not decisions and not manifest else "partial_or_invalid")
    )
    return {
        "status": status,
        "screening_manifest": manifest,
        "progress": progress,
        "prompt_freeze_integrity": prompt_integrity,
        "total_memberships": total,
        "screened_memberships": screened,
        "remaining_memberships": max(total - screened, 0),
        "coverage": screened / total if total else 1.0,
        "questions": per_question,
        "duplicate_decision_pairs": duplicate_pairs,
        "question_order_audit": gate,
        "batch_summary_by_question": batch_by_question,
        "batch_records": compact_batch_records(batch_events),
        "batch_log": file_record(SCREENING_BATCHES),
        "checkpoint_log": file_record(SCREENING_CHECKPOINTS),
        "decisions": file_record(SCREENING_DECISIONS),
        "independent_blinding": False,
        "human_decisions": 0,
        "release_ready": False,
    }, problems, paths


def build_phase_d(manifest: dict[str, Any] | None) -> tuple[dict[str, Any], list[str], list[Path]]:
    paths = [DOWNSTREAM_MANIFEST, SUPPORTING_LITERATURE, V5 / "build_downstream_v50.py"]
    if not manifest:
        return {
            "status": "not_started",
            "literature_link_manifest": None,
            "supporting_literature": file_record(SUPPORTING_LITERATURE),
            "independent_blinding": False,
            "release_ready": False,
        }, ["Phase D literature_link_manifest.json is absent"], paths

    problems: list[str] = []
    results = manifest.get("results", {})
    output_spec = manifest.get("outputs", {}).get("supporting_literature", {})
    actual_output = file_record(SUPPORTING_LITERATURE)
    output_rows = None
    if SUPPORTING_LITERATURE.is_file():
        _, rows = read_csv(SUPPORTING_LITERATURE)
        output_rows = len(rows)
    actual_output.update(
        {
            "actual_rows": output_rows,
            "sha256_matches_manifest": actual_output.get("sha256") == output_spec.get("sha256"),
            "row_count_matches_manifest": output_rows == output_spec.get("row_count"),
            "manifest": output_spec,
        }
    )
    links = results.get("links", [])
    locator_audit = {
        "required_format": "abstract:sentence:N",
        "reported_link_count": len(links),
        "format_valid_count": sum(bool(re.fullmatch(r"abstract:sentence:[1-9][0-9]*", str(link.get("locator", "")))) for link in links),
        "exact_quote_match_count": sum(link.get("quote_exact_match") is True for link in links),
    }
    locator_audit["status"] = (
        "pass"
        if locator_audit["format_valid_count"] == len(links)
        and locator_audit["exact_quote_match_count"] == len(links)
        else "failed"
    )
    unresolved_rule_ids = list(results.get("unresolved_rule_ids", []))
    if unresolved_rule_ids:
        problems.append(f"Phase D unresolved rule IDs: {unresolved_rule_ids}")
    if actual_output["sha256_matches_manifest"] is not True or actual_output["row_count_matches_manifest"] is not True:
        problems.append("Phase D supporting_literature.csv does not match its manifest")
    if locator_audit["status"] != "pass":
        problems.append("Phase D locator/quote validation is incomplete or failed")
    status = "complete" if not problems else "complete_with_unresolved_or_invalid"
    return {
        "status": status,
        "literature_link_manifest": manifest,
        "supporting_literature": actual_output,
        "locator_and_quote_validation": locator_audit,
        "resolved_rule_count": results.get("resolved_rule_count"),
        "unresolved_rule_count": results.get("unresolved_rule_count"),
        "unresolved_rule_ids": unresolved_rule_ids,
        "independent_blinding": False,
        "release_ready": False,
    }, problems, paths


def discover_one(patterns: Iterable[str], excluded: set[Path] | None = None) -> Path | None:
    excluded_resolved = {path.resolve() for path in (excluded or set())}
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in LOGS.glob(pattern) if path.is_file())
    candidates = [path for path in candidates if path.resolve() not in excluded_resolved]
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name), default=None)


def protected_comparison(baseline: dict[str, Any] | None, final: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline or not final:
        return {"status": "unavailable", "paths": []}
    baseline_paths = {item.get("path"): item for item in baseline.get("protected_paths", [])}
    final_paths = {item.get("path"): item for item in final.get("protected_paths", [])}
    rows = []
    for path in sorted(set(baseline_paths) | set(final_paths)):
        before = baseline_paths.get(path)
        after = final_paths.get(path)
        unchanged = bool(before and after) and all(
            before.get(key) == after.get(key)
            for key in ("tracked_files", "bytes", "aggregate_sha256")
        )
        rows.append({"path": path, "baseline": before, "final": after, "unchanged": unchanged})
    combined_before = baseline.get("combined_protected")
    combined_after = final.get("combined_protected")
    combined_unchanged = bool(combined_before and combined_after) and all(
        combined_before.get(key) == combined_after.get(key)
        for key in ("tracked_files", "bytes", "aggregate_sha256")
    )
    return {
        "status": "pass" if rows and all(row["unchanged"] for row in rows) and combined_unchanged else "failed",
        "paths": rows,
        "combined_baseline": combined_before,
        "combined_final": combined_after,
        "combined_unchanged": combined_unchanged,
    }


def read_snapshot(path: Path | None) -> Any:
    if path is None:
        return None
    if path.suffix.lower() == ".json":
        return load_json(path)
    return {"text": path.read_text(encoding="utf-8-sig")}


def amendment_record() -> dict[str, Any]:
    result = file_record(AMENDMENTS)
    matches: list[dict[str, str]] = []
    if AMENDMENTS.is_file():
        _, rows = read_csv(AMENDMENTS)
        matches = [row for row in rows if row.get("amendment_id") == "AM-OTC-002"]
    result.update({"amendment_id": "AM-OTC-002", "matching_rows": matches, "present_once": len(matches) == 1})
    return result


def contains_bare_sensitivity_key(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() == "sensitivity":
                found.append(child_path)
            found.extend(contains_bare_sensitivity_key(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(contains_bare_sensitivity_key(child, f"{path}[{index}]"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--require-complete", action="store_true",
        help="Refuse the atomic write when any Phase A-D or final-integrity item is unresolved.",
    )
    args = parser.parse_args()
    if args.output.resolve() != OUTPUT.resolve():
        raise SystemExit(f"output must be {OUTPUT}")

    required = (PROBE, QUERY_DEFINITIONS, INGREDIENT_MAPPINGS, CORPUS_MANIFEST, EVIDENCE_MAP)
    missing_required = [repo_relative(path) for path in required if not path.is_file()]
    if missing_required:
        raise SystemExit(f"required Phase A/B inputs are missing: {missing_required}")

    probe = load_json(PROBE)
    queries = load_json(QUERY_DEFINITIONS)
    mappings = load_json(INGREDIENT_MAPPINGS)
    corpus = load_json(CORPUS_MANIFEST)
    screening_manifest = load_json(SCREENING_MANIFEST) if SCREENING_MANIFEST.is_file() else None
    progress = load_json(SCREENING_PROGRESS) if SCREENING_PROGRESS.is_file() else None
    downstream_manifest = load_json(DOWNSTREAM_MANIFEST) if DOWNSTREAM_MANIFEST.is_file() else None

    phase_a, changes, ingredient_coverage, a_problems = build_phase_a(probe, queries, mappings)
    phase_b, b_problems = build_phase_b(corpus)
    phase_c, c_problems, c_paths = build_phase_c(corpus, screening_manifest, progress)
    phase_d, d_problems, d_paths = build_phase_d(downstream_manifest)

    final_audit_path = discover_one(
        ("v50*protected*final*.json", "v50*final*protected*.json", "v50_protected_audit.json"),
        excluded={BASELINE_AUDIT},
    )
    git_snapshot_path = discover_one(("v50*git*status*.json", "v50*git*status*.txt", "v50*git*status*.md"))
    baseline = load_json(BASELINE_AUDIT) if BASELINE_AUDIT.is_file() else None
    final_audit = load_json(final_audit_path) if final_audit_path else None
    protected = protected_comparison(baseline, final_audit)
    amendment = amendment_record()
    phase_e_problems: list[str] = []
    if not amendment["present_once"]:
        phase_e_problems.append("AM-OTC-002 is absent or duplicated in amendments.csv")
    if protected["status"] != "pass":
        phase_e_problems.append("final protected-path audit is absent or does not match the baseline")
    if git_snapshot_path is None:
        phase_e_problems.append("final git status snapshot is absent")

    phase_e = {
        "status": "complete" if not phase_e_problems else "incomplete_or_invalid",
        "amendment": amendment,
        "decisions_log": {
            **file_record(DECISIONS_LOG),
            "content": DECISIONS_LOG.read_text(encoding="utf-8-sig") if DECISIONS_LOG.is_file() else None,
        },
        "protected_baseline": {"file": file_record(BASELINE_AUDIT), "content": baseline},
        "protected_final_audit": {
            "file": file_record(final_audit_path) if final_audit_path else None,
            "content": final_audit,
        },
        "protected_path_comparison": protected,
        "git_status_snapshot": {
            "file": file_record(git_snapshot_path) if git_snapshot_path else None,
            "content": read_snapshot(git_snapshot_path),
        },
    }

    unresolved = [
        *({"phase": "A", "issue": value} for value in a_problems),
        *({"phase": "B", "issue": value} for value in b_problems),
        *({"phase": "C", "issue": value} for value in c_problems),
        *({"phase": "D", "issue": value} for value in d_problems),
        *({"phase": "E", "issue": value} for value in phase_e_problems),
    ]

    all_source_paths = [
        PROTOCOL,
        PROBE,
        QUERY_DEFINITIONS,
        INGREDIENT_MAPPINGS,
        CORPUS_MANIFEST,
        EVIDENCE_MAP,
        BASELINE_AUDIT,
        AMENDMENTS,
        DECISIONS_LOG,
        Path(__file__),
        *c_paths,
        *d_paths,
    ]
    if final_audit_path:
        all_source_paths.append(final_audit_path)
    if git_snapshot_path:
        all_source_paths.append(git_snapshot_path)

    report: dict[str, Any] = {
        "schema_version": "5.0.0",
        "report_type": "v5.0_mecir_literature_search_single_reconstruction_ledger",
        "generated_at_utc": utc_now(),
        "language": "ko",
        "authority": {
            "protocol": file_record(PROTOCOL),
            "protocol_version": "v5.0-mecir-search",
            "conflict_rule": "protocol-v5.0-mecir-search.md prevails over conflicting instructions",
        },
        "reconstruction_sources": source_registry(all_source_paths),
        "phases": {"A": phase_a, "B": phase_b, "C": phase_c, "D": phase_d, "E": phase_e},
        "v4_to_v5_hit_count_change": changes,
        "ingredient_coverage": ingredient_coverage,
        "protocol_section_3_compliance": phase_a["protocol_section_3_compliance"],
        "state_flags": {
            "independent_blinding": False,
            "release_ready": False,
            "human_reference_label_used": False,
            "human_screening_outputs_used": False,
        },
        "publication_and_repository_actions": {
            "site_deployment": "not_run",
            "vercel_deployment": "not_run",
            "git_push": "not_run",
        },
        "excluded_analyses": {
            "meta_analysis": "not_run",
            "pooled_effect_size": "not_run",
            "risk_of_bias": "not_run",
            "GRADE": "not_run",
            "clinical_recommendations": "not_created",
        },
        "unresolved": unresolved,
        "overall_status": "complete" if not unresolved else "incomplete",
    }

    bare_keys = contains_bare_sensitivity_key(report)
    if bare_keys:
        raise RuntimeError(
            "bare AI-reference metric key is forbidden; use sensitivity_vs_ai_reference: "
            + ", ".join(bare_keys)
        )
    if args.require_complete and unresolved:
        raise SystemExit(
            "report not written because --require-complete found unresolved items: "
            + "; ".join(f"{item['phase']}: {item['issue']}" for item in unresolved)
        )

    atomic_write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": repo_relative(args.output),
                "sha256": sha256_file(args.output),
                "overall_status": report["overall_status"],
                "unresolved_count": len(unresolved),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
