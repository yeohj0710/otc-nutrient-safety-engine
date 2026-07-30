"""Write a compact, evidence-backed v5.0 progress snapshot."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adjudication_pipeline_v50 import (
    PipelineError,
    validate_selection_provenance_correction,
)


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREENING = V5 / "screening"
PROGRESS = ROOT / "research_v3" / "logs" / "v50_progress.json"
SELECTION = SCREENING / "adjudication_selection.json"
VALIDATION = SCREENING / "classifier_validation.json"
CROSS_LAYER_VALIDATION = SCREENING / "classifier_validation_cross_layer.json"
CLASSIFIER = SCREENING / "classifier_decisions.csv"
CLASSIFIER_CHECKPOINTS = SCREENING / "checkpoints.jsonl"
CLASSIFIER_BATCH_ROOT = SCREENING / "batches"
CLASSIFIER_OUTPUT_ROOT = SCREENING / "agent_outputs"
CLASSIFIER_VALIDATOR = V5 / "classifier_validation_v50.py"
FROZEN_LIGHT_SCREENING_PROMPT = V5 / "prompts" / "frozen_light_screening_prompt.md"
V4_SCREENING_MANIFEST = (
    ROOT / "research_v3" / "otc" / "literature" / "screening" / "screening_manifest.json"
)
V4_EVIDENCE_MAP = ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"
V4_CHECKPOINTS = (
    ROOT / "research_v3" / "otc" / "literature" / "screening" / "checkpoints.jsonl"
)
FINAL_DECISIONS = SCREENING / "decisions.csv"
ADJUDICATION_MANIFEST = SCREENING / "adjudication_manifest.json"
OUTPUT_ROOT = SCREENING / "agent_outputs" / "adjudication"
BATCH_ROOT = SCREENING / "batches" / "adjudication"
CHECK_ROOT = SCREENING / "adjudication_validation"
SEMANTIC_ADJUDICATIONS = SCREENING / "semantic_adjudications.json"
PROMPT = V5 / "prompts" / "frozen_semantic_adjudication_prompt.md"
EVIDENCE_MAP = V5 / "evidence_map.csv"
QUERY_DEFINITIONS = V5 / "query_definitions.json"
PROBE_REPORT = V5 / "probe_report.json"
CORPUS_MANIFEST = V5 / "corpus_manifest.json"
SEARCH_ROOT = V5 / "searches"
LIGHT_SCREENING_PIPELINE = V5 / "light_screening_pipeline.py"
DOWNSTREAM_MANIFEST = V5 / "downstream" / "literature_link_manifest.json"
DOWNSTREAM_CSV = V5 / "downstream" / "supporting_literature.csv"
LOCATOR_VERIFICATION = V5 / "downstream" / "locator_verification.json"
PROTECTED_AUDIT = ROOT / "research_v3" / "logs" / "v50_protected_final_audit.json"
RUN_REPORT = ROOT / "research_v3" / "logs" / "v50_run_report.json"
QUESTION_ORDER = [
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
]
PROTECTED_PATHS = {
    "research_v3/otc/normalized": "research_v3/otc/normalized",
    "research_v3/otc/rules": "research_v3/otc/rules",
    "research_v3/otc/literature (excluding v5)": "research_v3/otc/literature",
    "research_v3/search/provisional_pubmed_20260710": (
        "research_v3/search/provisional_pubmed_20260710"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_if_file(path: Path) -> str | None:
    try:
        return sha256(path) if path.is_file() else None
    except OSError:
        return None


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def lines(value: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in value.splitlines() if line.strip()]


def excluded(path: str, label: str) -> bool:
    return label == "research_v3/otc/literature (excluding v5)" and path.startswith(
        "research_v3/otc/literature/v5/"
    )


def canonical_manifest_sha256(records: list[dict[str, object]]) -> str:
    canonical = [
        {
            "path": str(record["path"]),
            "bytes": int(record["bytes"]),
            "sha256": str(record["sha256"]),
        }
        for record in sorted(records, key=lambda item: str(item["path"]))
    ]
    rendered = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def current_file_records(paths: list[str]) -> tuple[list[dict[str, object]], list[str]]:
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for relative in sorted(paths):
        path = ROOT / relative
        try:
            stat = path.stat()
            if not path.is_file():
                raise OSError("not a regular file")
            records.append(
                {"path": relative, "bytes": stat.st_size, "sha256": sha256(path)}
            )
        except OSError as exc:
            errors.append(f"{relative}: {exc}")
    return records, errors


def recorded_canonical_records(
    records: list[object], prefix: str
) -> tuple[list[dict[str, object]], list[str]]:
    canonical: list[dict[str, object]] = []
    errors: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record {index} is not an object")
            continue
        try:
            path = str(record["path"])
            byte_count = int(record[f"{prefix}_canonical_bytes"])
            digest = str(record[f"{prefix}_canonical_sha256"])
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("canonical SHA-256 is not lowercase hexadecimal")
            canonical.append({"path": path, "bytes": byte_count, "sha256": digest})
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"record {index}: {exc}")
    return canonical, errors


def protected_audit_recheck(protected: dict) -> tuple[bool, dict[str, object]]:
    audit_paths = protected.get("protected_paths", [])
    if not isinstance(audit_paths, list):
        return False, {"status": "fail", "errors": ["protected_paths is not a list"]}
    audit_by_label = {
        str(item.get("path")): item for item in audit_paths if isinstance(item, dict)
    }
    path_results: list[dict[str, object]] = []
    combined_current_files: list[dict[str, object]] = []
    combined_recorded_baseline_canonical: list[dict[str, object]] = []
    combined_recorded_current_canonical: list[dict[str, object]] = []
    combined_current_untracked: list[dict[str, object]] = []
    combined_current_ignored: list[dict[str, object]] = []
    all_current_untracked: list[str] = []
    all_current_ignored: list[str] = []
    all_new_tracked: list[str] = []
    all_missing_tracked: list[str] = []
    all_new_untracked: list[str] = []
    all_missing_untracked: list[str] = []
    all_new_ignored: list[str] = []
    all_missing_ignored: list[str] = []
    errors: list[str] = []

    for label, actual_path in PROTECTED_PATHS.items():
        item = audit_by_label.get(label)
        if not isinstance(item, dict):
            errors.append(f"missing protected audit path: {label}")
            continue
        audit_files = item.get("files", [])
        audit_untracked_files = item.get("untracked_files", [])
        audit_ignored_files = item.get("ignored_files", [])
        if not all(
            isinstance(records, list)
            for records in (audit_files, audit_untracked_files, audit_ignored_files)
        ):
            errors.append(f"invalid file manifest type: {label}")
            continue

        current_tracked_paths = [
            path
            for path in lines(git("ls-files", "--", actual_path))
            if not excluded(path, label)
        ]
        current_untracked_paths = [
            path
            for path in lines(
                git("ls-files", "--others", "--exclude-standard", "--", actual_path)
            )
            if not excluded(path, label)
        ]
        current_ignored_paths = [
            path
            for path in lines(
                git(
                    "ls-files",
                    "--others",
                    "--ignored",
                    "--exclude-standard",
                    "--",
                    actual_path,
                )
            )
            if not excluded(path, label)
        ]
        current_files, current_file_errors = current_file_records(current_tracked_paths)
        current_untracked, current_untracked_errors = current_file_records(
            current_untracked_paths
        )
        current_ignored, current_ignored_errors = current_file_records(
            current_ignored_paths
        )
        second_tracked_paths = [
            path
            for path in lines(git("ls-files", "--", actual_path))
            if not excluded(path, label)
        ]
        second_untracked_paths = [
            path
            for path in lines(
                git("ls-files", "--others", "--exclude-standard", "--", actual_path)
            )
            if not excluded(path, label)
        ]
        second_ignored_paths = [
            path
            for path in lines(
                git(
                    "ls-files",
                    "--others",
                    "--ignored",
                    "--exclude-standard",
                    "--",
                    actual_path,
                )
            )
            if not excluded(path, label)
        ]
        second_files, second_file_errors = current_file_records(second_tracked_paths)
        second_untracked, second_untracked_errors = current_file_records(
            second_untracked_paths
        )
        second_ignored, second_ignored_errors = current_file_records(
            second_ignored_paths
        )

        audit_file_by_path = {
            str(record.get("path")): record
            for record in audit_files
            if isinstance(record, dict)
        }
        audit_untracked_by_path = {
            str(record.get("path")): record
            for record in audit_untracked_files
            if isinstance(record, dict)
        }
        audit_ignored_by_path = {
            str(record.get("path")): record
            for record in audit_ignored_files
            if isinstance(record, dict)
        }
        audit_tracked_paths = set(audit_file_by_path)
        audit_untracked_paths = set(audit_untracked_by_path)
        audit_ignored_paths = set(audit_ignored_by_path)
        current_tracked_set = set(current_tracked_paths)
        current_untracked_set = set(current_untracked_paths)
        current_ignored_set = set(current_ignored_paths)

        new_tracked = sorted(current_tracked_set - audit_tracked_paths)
        missing_tracked = sorted(audit_tracked_paths - current_tracked_set)
        new_untracked = sorted(current_untracked_set - audit_untracked_paths)
        missing_untracked = sorted(audit_untracked_paths - current_untracked_set)
        new_ignored = sorted(current_ignored_set - audit_ignored_paths)
        missing_ignored = sorted(audit_ignored_paths - current_ignored_set)
        all_new_tracked.extend(new_tracked)
        all_missing_tracked.extend(missing_tracked)
        all_new_untracked.extend(new_untracked)
        all_missing_untracked.extend(missing_untracked)
        all_new_ignored.extend(new_ignored)
        all_missing_ignored.extend(missing_ignored)
        all_current_untracked.extend(current_untracked_paths)
        all_current_ignored.extend(current_ignored_paths)

        current_by_path = {str(record["path"]): record for record in current_files}
        current_untracked_by_path = {
            str(record["path"]): record for record in current_untracked
        }
        current_ignored_by_path = {
            str(record["path"]): record for record in current_ignored
        }
        tracked_content_mismatches = sorted(
            path
            for path in current_tracked_set & audit_tracked_paths
            if current_by_path.get(path, {}).get("bytes")
            != audit_file_by_path[path].get("bytes")
            or current_by_path.get(path, {}).get("sha256")
            != audit_file_by_path[path].get("sha256")
        )
        untracked_content_mismatches = sorted(
            path
            for path in current_untracked_set & audit_untracked_paths
            if current_untracked_by_path.get(path, {}).get("bytes")
            != audit_untracked_by_path[path].get("bytes")
            or current_untracked_by_path.get(path, {}).get("sha256")
            != audit_untracked_by_path[path].get("sha256")
        )
        ignored_content_mismatches = sorted(
            path
            for path in current_ignored_set & audit_ignored_paths
            if current_ignored_by_path.get(path, {}).get("bytes")
            != audit_ignored_by_path[path].get("bytes")
            or current_ignored_by_path.get(path, {}).get("sha256")
            != audit_ignored_by_path[path].get("sha256")
        )

        current_manifest_sha = canonical_manifest_sha256(current_files)
        current_untracked_sha = canonical_manifest_sha256(current_untracked)
        current_ignored_sha = canonical_manifest_sha256(current_ignored)
        consecutive_snapshot_matches = all(
            (
                sorted(second_tracked_paths) == sorted(current_tracked_paths),
                sorted(second_untracked_paths) == sorted(current_untracked_paths),
                sorted(second_ignored_paths) == sorted(current_ignored_paths),
                canonical_manifest_sha256(second_files) == current_manifest_sha,
                canonical_manifest_sha256(second_untracked) == current_untracked_sha,
                canonical_manifest_sha256(second_ignored) == current_ignored_sha,
                not second_file_errors,
                not second_untracked_errors,
                not second_ignored_errors,
            )
        )
        verification = item.get("verification", {})
        recorded_baseline_canonical, baseline_canonical_errors = (
            recorded_canonical_records(audit_files, "baseline")
        )
        recorded_current_canonical, current_canonical_errors = (
            recorded_canonical_records(audit_files, "current")
        )
        baseline_canonical_sha = canonical_manifest_sha256(
            recorded_baseline_canonical
        )
        current_canonical_sha = canonical_manifest_sha256(recorded_current_canonical)
        per_file_baseline_checks_valid = (
            len(audit_file_by_path) == len(audit_files)
            and not baseline_canonical_errors
            and not current_canonical_errors
            and recorded_baseline_canonical == recorded_current_canonical
            and all(
                record.get("canonical_sha256_matches_baseline") is True
                and record.get("baseline_canonical_bytes")
                == record.get("current_canonical_bytes")
                and record.get("baseline_canonical_sha256")
                == record.get("current_canonical_sha256")
                and record.get("baseline_git_blob_oid")
                == record.get("current_git_blob_oid")
                for record in audit_files
                if isinstance(record, dict)
            )
            and isinstance(verification, dict)
            and verification.get("canonical_per_file_sha256_matches_baseline") is True
            and verification.get("canonical_manifest_sha256_matches_baseline") is True
            and baseline_canonical_sha
            == item.get("baseline_canonical_file_manifest_sha256")
            and current_canonical_sha
            == item.get("current_canonical_file_manifest_sha256")
            and baseline_canonical_sha == current_canonical_sha
        )
        path_ok = all(
            (
                item.get("status") == "pass",
                not new_tracked,
                not missing_tracked,
                not new_untracked,
                not missing_untracked,
                not new_ignored,
                not missing_ignored,
                not tracked_content_mismatches,
                not untracked_content_mismatches,
                not ignored_content_mismatches,
                not current_file_errors,
                not current_untracked_errors,
                not current_ignored_errors,
                consecutive_snapshot_matches,
                not current_untracked_paths,
                current_manifest_sha == item.get("current_file_manifest_sha256"),
                current_untracked_sha == item.get("untracked_file_manifest_sha256"),
                current_ignored_sha == item.get("ignored_file_manifest_sha256"),
                len(current_files) == item.get("tracked_files"),
                sum(int(record["bytes"]) for record in current_files)
                == item.get("bytes"),
                len(current_untracked) == item.get("untracked_file_count"),
                len(current_ignored) == item.get("ignored_file_count"),
                per_file_baseline_checks_valid,
                verification.get("ignored_files_with_mtime_after_baseline_capture")
                == [],
            )
        )
        path_results.append(
            {
                "path": label,
                "status": "pass" if path_ok else "fail",
                "tracked_file_count": len(current_files),
                "current_file_manifest_sha256": current_manifest_sha,
                "current_untracked_files": current_untracked_paths,
                "current_ignored_files": current_ignored_paths,
                "new_tracked_since_audit": new_tracked,
                "missing_tracked_since_audit": missing_tracked,
                "new_untracked_since_audit": new_untracked,
                "missing_untracked_since_audit": missing_untracked,
                "new_ignored_since_audit": new_ignored,
                "missing_ignored_since_audit": missing_ignored,
                "tracked_content_mismatches": tracked_content_mismatches,
                "untracked_content_mismatches": untracked_content_mismatches,
                "ignored_content_mismatches": ignored_content_mismatches,
                "consecutive_raw_snapshot_matches": consecutive_snapshot_matches,
                "recorded_canonical_manifest_sha256": {
                    "baseline": baseline_canonical_sha,
                    "current": current_canonical_sha,
                },
                "file_read_errors": (
                    current_file_errors
                    + current_untracked_errors
                    + current_ignored_errors
                    + second_file_errors
                    + second_untracked_errors
                    + second_ignored_errors
                    + baseline_canonical_errors
                    + current_canonical_errors
                ),
            }
        )
        combined_current_files.extend(current_files)
        combined_recorded_baseline_canonical.extend(recorded_baseline_canonical)
        combined_recorded_current_canonical.extend(recorded_current_canonical)
        combined_current_untracked.extend(current_untracked)
        combined_current_ignored.extend(current_ignored)

    combined = protected.get("combined_protected", {})
    combined_files_sha = canonical_manifest_sha256(combined_current_files)
    combined_recorded_baseline_canonical_sha = canonical_manifest_sha256(
        combined_recorded_baseline_canonical
    )
    combined_recorded_current_canonical_sha = canonical_manifest_sha256(
        combined_recorded_current_canonical
    )
    combined_untracked_sha = canonical_manifest_sha256(combined_current_untracked)
    combined_ignored_sha = canonical_manifest_sha256(combined_current_ignored)
    combined_ok = all(
        (
            isinstance(combined, dict),
            combined_files_sha == combined.get("current_file_manifest_sha256"),
            combined_untracked_sha == combined.get("untracked_file_manifest_sha256"),
            combined_ignored_sha == combined.get("ignored_file_manifest_sha256"),
            combined_recorded_baseline_canonical_sha
            == combined.get("baseline_canonical_file_manifest_sha256"),
            combined_recorded_current_canonical_sha
            == combined.get("current_canonical_file_manifest_sha256"),
            combined_recorded_baseline_canonical_sha
            == combined_recorded_current_canonical_sha,
            len(combined_current_files) == combined.get("tracked_files"),
            len(combined_current_untracked) == combined.get("untracked_file_count"),
            len(combined_current_ignored) == combined.get("ignored_file_count"),
            sum(int(record["bytes"]) for record in combined_current_files)
            == combined.get("bytes"),
        )
    )
    complete = (
        not errors
        and len(path_results) == len(PROTECTED_PATHS)
        and all(result["status"] == "pass" for result in path_results)
        and combined_ok
    )
    ignored_limitation_present = bool(all_current_ignored)
    recheck_status = (
        "pass_for_434_baseline_tracked_files_with_ignored_baseline_limitation"
        if complete and ignored_limitation_present
        else "pass" if complete else "fail"
    )
    return complete, {
        "status": recheck_status,
        "completion_scope": (
            "434_baseline_tracked_files_with_ignored_baseline_limitation"
            if ignored_limitation_present
            else "all_baseline_tracked_files"
        ),
        "checked_at_utc": iso(datetime.now(timezone.utc)),
        "tracked_file_count": len(combined_current_files),
        "current_file_manifest_sha256": combined_files_sha,
        "current_untracked_files": sorted(all_current_untracked),
        "current_ignored_files": sorted(all_current_ignored),
        "new_tracked_since_audit": sorted(all_new_tracked),
        "missing_tracked_since_audit": sorted(all_missing_tracked),
        "new_untracked_since_audit": sorted(all_new_untracked),
        "missing_untracked_since_audit": sorted(all_missing_untracked),
        "new_ignored_since_audit": sorted(all_new_ignored),
        "missing_ignored_since_audit": sorted(all_missing_ignored),
        "ignored_file_baseline_limitation_present": ignored_limitation_present,
        "errors": errors,
        "paths": path_results,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def current_file_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    if not path.is_file():
        raise OSError(f"not a regular file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "bytes": stat.st_size,
    }


def verify_phase_a_current(
    queries: dict, probe: dict
) -> dict[str, object]:
    query_rows = queries.get("questions")
    probe_rows = probe.get("questions")
    if not (
        isinstance(query_rows, list)
        and isinstance(probe_rows, list)
        and all(isinstance(row, dict) for row in query_rows)
        and all(isinstance(row, dict) for row in probe_rows)
    ):
        raise ValueError("Phase A question records are missing")
    if [row.get("question_id") for row in query_rows] != QUESTION_ORDER:
        raise ValueError("query definition question order changed")
    if [row.get("question_id") for row in probe_rows] != QUESTION_ORDER:
        raise ValueError("probe question order changed")

    checks: list[dict[str, object]] = []
    for query_row, probe_row in zip(query_rows, probe_rows, strict=True):
        query_hash = hashlib.sha256(
            str(query_row.get("query", "")).encode("utf-8")
        ).hexdigest()
        rules = probe_row.get("protocol_section_3_self_check")
        esearch = probe_row.get("esearch")
        valid = all(
            (
                query_hash == query_row.get("query_sha256"),
                probe_row.get("query") == query_row.get("query"),
                probe_row.get("query_sha256") == query_hash,
                isinstance(rules, list),
                len(rules) == 10 if isinstance(rules, list) else False,
                [rule.get("rule") for rule in rules]
                == list(range(1, 11))
                if isinstance(rules, list)
                and all(isinstance(rule, dict) for rule in rules)
                else False,
                all(rule.get("status") == "pass" for rule in rules)
                if isinstance(rules, list)
                and all(isinstance(rule, dict) for rule in rules)
                else False,
                probe_row.get("all_rules_pass") is True,
                esearch.get("count") == probe_row.get("hit_count")
                if isinstance(esearch, dict)
                else False,
                esearch.get("http_status") == 200
                if isinstance(esearch, dict)
                else False,
            )
        )
        if not valid:
            raise ValueError(
                f"Phase A query/probe contract failed: {query_row.get('question_id')}"
            )
        checks.append(
            {
                "question_id": query_row["question_id"],
                "query_sha256": query_hash,
                "hit_count": probe_row["hit_count"],
                "protocol_rules_checked": 10,
                "passed": True,
            }
        )

    totals = probe.get("totals")
    if not isinstance(totals, dict) or not all(
        (
            probe.get("status") == "complete",
            probe.get("query_definitions_path")
            == QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
            probe.get("query_definitions_sha256") == sha256(QUERY_DEFINITIONS),
            sum(int(row["hit_count"]) for row in probe_rows) == 43_249,
            totals.get("hit_count_before_cross_question_deduplication") == 43_249,
            totals.get("efetch_calls") == 0,
            probe.get("selected_ingredient_count") == 28,
            len(probe.get("selected_ingredients_in_queries", [])) == 28,
            probe.get("missing_selected_ingredients") == [],
        )
    ):
        raise ValueError("Phase A aggregate contract failed")
    return {
        "current_artifact_integrity_verified": True,
        "question_checks": checks,
        "total_hit_count": 43_249,
        "retrieval_rerun": False,
        "defense_start_hash_baseline_available": False,
        "unchanged_since_defense_start_cryptographically_proven": False,
    }


def verify_checksum_manifest_current(
    run_path: Path, expected_sha256: str, expected_files: int
) -> tuple[dict[str, object], set[str]]:
    checksum_path = run_path / "checksum.sha256"
    if sha256(checksum_path) != expected_sha256:
        raise ValueError(f"checksum manifest hash mismatch: {checksum_path}")

    entries: list[dict[str, object]] = []
    entry_paths: set[str] = set()
    for line_number, line in enumerate(
        checksum_path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        parts = line.split(None, 1)
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(character not in "0123456789abcdef" for character in parts[0])
        ):
            raise ValueError(f"invalid checksum line: {checksum_path}:{line_number}")
        relative = parts[1].strip().replace("\\", "/")
        if not relative.endswith(".xml"):
            raise ValueError(
                f"checksum entry does not have the .xml extension: "
                f"{checksum_path}:{line_number}"
            )
        candidate = (run_path / relative).resolve()
        try:
            candidate.relative_to(run_path.resolve())
        except ValueError as exc:
            raise ValueError(f"checksum path escapes run directory: {relative}") from exc
        if (
            not candidate.is_file()
            or candidate.suffix.lower() != ".xml"
            or sha256(candidate) != parts[0]
        ):
            raise ValueError(f"raw retrieval checksum mismatch: {relative}")
        relative_to_root = candidate.relative_to(ROOT).as_posix()
        if relative_to_root in entry_paths:
            raise ValueError(f"duplicate raw retrieval checksum path: {relative}")
        entry_paths.add(relative_to_root)
        entries.append(current_file_record(candidate))

    rglob_paths = {
        path.resolve().relative_to(ROOT).as_posix()
        for path in run_path.rglob("*.xml")
        if path.is_file()
    }
    if len(entries) != expected_files or entry_paths != rglob_paths:
        raise ValueError(
            f"raw retrieval XML set mismatch for {run_path}: "
            f"manifest={len(entries)}, rglob={len(rglob_paths)}, expected={expected_files}"
        )
    return (
        {
            "checksum_manifest": current_file_record(checksum_path),
            "verified_file_count": len(entries),
            "duplicate_paths_rejected": True,
            "xml_extension_required": True,
            "manifest_matches_recursive_xml_set": True,
            "files": entries,
        },
        entry_paths,
    )


def verify_phase_b_current(
    corpus: dict,
    queries: dict,
    probe: dict,
    evidence_fields: list[str],
    evidence_rows: list[dict[str, str]],
) -> dict[str, object]:
    questions = corpus.get("questions")
    if not (
        isinstance(questions, list)
        and all(isinstance(row, dict) for row in questions)
        and [row.get("question_id") for row in questions] == QUESTION_ORDER
    ):
        raise ValueError("Phase B question records are missing or reordered")

    query_rows = queries.get("questions")
    probe_rows = probe.get("questions")
    if not (
        isinstance(query_rows, list)
        and isinstance(probe_rows, list)
        and all(isinstance(row, dict) for row in query_rows)
        and all(isinstance(row, dict) for row in probe_rows)
    ):
        raise ValueError("Phase A records required by Phase B are missing")
    query_by_id = {row["question_id"]: row for row in query_rows}
    probe_by_id = {row["question_id"]: row for row in probe_rows}

    raw_checks: list[dict[str, object]] = []
    verified_xml_paths: set[str] = set()
    search_root = SEARCH_ROOT.resolve()
    for row in questions:
        run_relative = row.get("run_path")
        if not isinstance(run_relative, str):
            raise ValueError("Phase B run path is missing")
        run_path = (ROOT / run_relative).resolve()
        try:
            run_path.relative_to(search_root)
        except ValueError as exc:
            raise ValueError(f"Phase B run path escapes search root: {run_relative}") from exc
        response_path = run_path / "response_metadata.json"
        question_id = row.get("question_id")
        if not all(
            (
                row.get("status") == "complete",
                row.get("phase_a_probe_count") == row.get("phase_b_base_count"),
                row.get("phase_b_base_count") == row.get("segment_count_sum"),
                row.get("query_sha256")
                == query_by_id.get(question_id, {}).get("query_sha256"),
                row.get("phase_a_probe_count")
                == probe_by_id.get(question_id, {}).get("hit_count"),
                sha256(response_path) == row.get("response_metadata_sha256"),
            )
        ):
            raise ValueError(f"Phase B question contract failed: {question_id}")
        manifest_check, xml_paths = verify_checksum_manifest_current(
            run_path,
            str(row.get("checksum_manifest_sha256")),
            int(row.get("raw_xml_file_count", -1)),
        )
        if verified_xml_paths & xml_paths:
            raise ValueError("Phase B XML paths are not unique across retrieval runs")
        verified_xml_paths.update(xml_paths)
        raw_checks.append(
            {
                "question_id": question_id,
                "run_path": run_relative,
                **manifest_check,
            }
        )

    all_search_xml_paths = {
        path.resolve().relative_to(ROOT).as_posix()
        for path in SEARCH_ROOT.rglob("*.xml")
        if path.is_file()
    }
    if len(verified_xml_paths) != 105 or verified_xml_paths != all_search_xml_paths:
        raise ValueError("Phase B does not contain the exact recorded set of 105 XML files")

    evidence = corpus.get("evidence_map")
    totals = corpus.get("totals")
    if not isinstance(evidence, dict) or not isinstance(totals, dict):
        raise ValueError("Phase B aggregate records are missing")
    membership_rows = sum(
        len([value for value in row.get("question_ids", "").split(";") if value])
        for row in evidence_rows
    )
    if not all(
        (
            corpus.get("status") == "complete",
            corpus.get("query_definitions_path")
            == QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
            corpus.get("probe_report_path") == PROBE_REPORT.relative_to(ROOT).as_posix(),
            corpus.get("query_definitions_sha256") == sha256(QUERY_DEFINITIONS),
            corpus.get("probe_report_sha256") == sha256(PROBE_REPORT),
            evidence.get("path") == EVIDENCE_MAP.relative_to(ROOT).as_posix(),
            evidence.get("sha256") == sha256(EVIDENCE_MAP),
            evidence.get("rows") == len(evidence_rows) == 42_822,
            evidence.get("columns") == evidence_fields,
            membership_rows == 43_207,
            totals.get("phase_a_probe_hits_before_cross_question_deduplication")
            == 43_249,
            totals.get("phase_b_hits_before_cross_question_deduplication") == 43_249,
            totals.get("question_membership_units_after_bibliographic_deduplication")
            == 43_207,
            totals.get("evidence_map_rows_unique_papers") == 42_822,
            totals.get("raw_xml_files") == 105,
            sum(int(row["raw_xml_file_count"]) for row in questions) == 105,
        )
    ):
        raise ValueError("Phase B aggregate contract failed")
    return {
        "current_artifact_integrity_verified": True,
        "raw_retrieval_checks": raw_checks,
        "raw_xml_files_verified": 105,
        "evidence_map_rows": 42_822,
        "question_memberships": 43_207,
        "retrieval_rerun": False,
        "defense_start_hash_baseline_available": False,
        "unchanged_since_defense_start_cryptographically_proven": False,
    }


def report_phase_a_b_current(run_report: dict) -> bool:
    try:
        queries = load_json(QUERY_DEFINITIONS)
        probe = load_json(PROBE_REPORT)
        corpus = load_json(CORPUS_MANIFEST)
        evidence_fields, evidence_rows = read_csv(EVIDENCE_MAP)
        if not all(isinstance(value, dict) for value in (queries, probe, corpus)):
            return False

        query_report = run_report.get("query_definitions")
        phases = run_report.get("phases")
        if not isinstance(query_report, dict) or not isinstance(phases, dict):
            return False
        phase_a_report = phases.get("A")
        phase_b_report = phases.get("B")
        if not isinstance(phase_a_report, dict) or not isinstance(phase_b_report, dict):
            return False

        phase_a_integrity = verify_phase_a_current(queries, probe)
        phase_b_integrity = verify_phase_b_current(
            corpus, queries, probe, evidence_fields, evidence_rows
        )
        return all(
            (
                query_report.get("full_record") == queries,
                query_report.get("source") == current_file_record(QUERY_DEFINITIONS),
                phase_a_report.get("status") == "complete",
                phase_a_report.get("full_record") == probe,
                phase_a_report.get("source") == current_file_record(PROBE_REPORT),
                phase_a_report.get("integrity_checks") == phase_a_integrity,
                phase_b_report.get("status") == "complete",
                phase_b_report.get("full_record") == corpus,
                phase_b_report.get("source") == current_file_record(CORPUS_MANIFEST),
                phase_b_report.get("integrity_checks") == phase_b_integrity,
            )
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


def jsonl_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def main() -> int:
    now = datetime.now(timezone.utc)
    selection = load_json(SELECTION)
    try:
        selection_provenance_correction = validate_selection_provenance_correction(selection)
    except (PipelineError, OSError, KeyError, TypeError, ValueError) as exc:
        selection_provenance_correction = {
            "valid": False,
            "correction_id": None,
            "error": str(exc),
        }
    selection_provenance_correction_complete = all(
        (
            selection_provenance_correction.get("valid") is True,
            selection_provenance_correction.get("correction_id") == "V50-PC-001",
            selection_provenance_correction.get("allowed_selection_changes")
            == ["independent_blinding_ai", "provenance_correction"],
            selection_provenance_correction.get("selected_records_changed") is False,
            selection_provenance_correction.get("execution_contract_changed") is False,
            selection_provenance_correction.get("batch_inputs_changed") is False,
            selection_provenance_correction.get("batch_outputs_changed") is False,
        )
    )
    classifier_validation: dict = {}
    classifier_validation_load_error: str | None = None
    try:
        loaded_validation = load_json(VALIDATION)
        if not isinstance(loaded_validation, dict):
            raise ValueError("classifier validation root is not an object")
        classifier_validation = loaded_validation
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        classifier_validation_load_error = f"{type(exc).__name__}: {exc}"
    classifier_cross_layer: dict = {}
    classifier_cross_layer_load_error: str | None = None
    try:
        loaded_cross_layer = load_json(CROSS_LAYER_VALIDATION)
        if not isinstance(loaded_cross_layer, dict):
            raise ValueError("cross-layer validation root is not an object")
        classifier_cross_layer = loaded_cross_layer
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        classifier_cross_layer_load_error = f"{type(exc).__name__}: {exc}"
    with CLASSIFIER.open("r", encoding="utf-8-sig", newline="") as handle:
        classifier_rows = list(csv.DictReader(handle))
    classifier_output_paths = sorted(
        path
        for question in QUESTION_ORDER
        for path in (CLASSIFIER_OUTPUT_ROOT / question).glob("*.jsonl")
        if path.is_file()
    )
    current_classifier_output_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in classifier_output_paths
    }
    classifier_input_paths = sorted(
        path
        for question in QUESTION_ORDER
        for path in (CLASSIFIER_BATCH_ROOT / question).glob("*.jsonl")
        if path.is_file()
    )
    current_classifier_input_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in classifier_input_paths
    }
    classifier_manifest_paths = [
        CLASSIFIER_BATCH_ROOT / question / "manifest.json"
        for question in QUESTION_ORDER
    ]
    current_classifier_manifest_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in classifier_manifest_paths
        if path.is_file()
    }
    current_classifier_sha = sha256_if_file(CLASSIFIER)
    current_evidence_map_sha = sha256_if_file(EVIDENCE_MAP)
    current_classifier_checkpoints_sha = sha256_if_file(CLASSIFIER_CHECKPOINTS)
    current_classifier_validator_sha = sha256_if_file(CLASSIFIER_VALIDATOR)
    current_light_screening_pipeline_sha = sha256_if_file(LIGHT_SCREENING_PIPELINE)
    current_frozen_light_prompt_sha = sha256_if_file(FROZEN_LIGHT_SCREENING_PROMPT)
    current_cross_layer_validation_sha = sha256_if_file(CROSS_LAYER_VALIDATION)
    current_original_validation_sha = sha256_if_file(VALIDATION)
    current_v4_screening_manifest_sha = sha256_if_file(V4_SCREENING_MANIFEST)
    current_v4_evidence_map_sha = sha256_if_file(V4_EVIDENCE_MAP)
    current_v4_checkpoints_sha = sha256_if_file(V4_CHECKPOINTS)
    validation_cases_value = classifier_validation.get("cases", [])
    validation_cases_are_list = isinstance(validation_cases_value, list)
    validation_cases = validation_cases_value if validation_cases_are_list else []
    validation_case_keys = [
        (str(case.get("record_id", "")), str(case.get("question_id", "")))
        for case in validation_cases
        if isinstance(case, dict)
    ]
    validation_pass_count = sum(
        isinstance(case, dict) and case.get("passed") is True for case in validation_cases
    )
    validation_fail_count = sum(
        isinstance(case, dict) and case.get("passed") is False for case in validation_cases
    )
    selected_keys = {
        (str(row.get("record_id", "")), str(row.get("question_id", "")))
        for row in selection.get("selected_records", [])
        if isinstance(row, dict)
    }
    failed_validation_keys = {
        (str(case.get("record_id", "")), str(case.get("question_id", "")))
        for case in validation_cases
        if isinstance(case, dict) and case.get("passed") is False
    }
    validation_sources_value = classifier_validation.get("source_hashes", {})
    validation_format_value = classifier_validation.get("format_contract", {})
    validation_layer_value = classifier_validation.get("classifier_layer", {})
    validation_sources = (
        validation_sources_value if isinstance(validation_sources_value, dict) else {}
    )
    validation_format = (
        validation_format_value if isinstance(validation_format_value, dict) else {}
    )
    validation_layer = (
        validation_layer_value if isinstance(validation_layer_value, dict) else {}
    )
    selection_sources = selection.get("source_files", {})
    if not isinstance(selection_sources, dict):
        selection_sources = {}
    frozen_validation_value = selection_sources.get("classifier_validation", {})
    frozen_validation = (
        frozen_validation_value if isinstance(frozen_validation_value, dict) else {}
    )
    original_classifier_validation_complete = all(
        (
            classifier_validation_load_error is None,
            validation_cases_are_list,
            len(validation_cases) >= 20,
            classifier_validation.get("case_count") == len(validation_cases),
            len(validation_case_keys) == len(validation_cases),
            len(validation_case_keys) == len(set(validation_case_keys)),
            all(all(key) and key[1] in QUESTION_ORDER for key in validation_case_keys),
            all(
                isinstance(case, dict) and isinstance(case.get("passed"), bool)
                for case in validation_cases
            ),
            classifier_validation.get("pass_count") == validation_pass_count,
            classifier_validation.get("fail_count") == validation_fail_count,
            validation_pass_count + validation_fail_count == len(validation_cases),
            validation_format.get("passed") is True,
            validation_format.get("batch_count") == 182,
            validation_format.get("row_count") == 43_207,
            validation_layer.get("rows") == len(classifier_rows) == 43_207,
            validation_layer.get("sha256") == current_classifier_sha,
            validation_sources.get("classifier_decisions.csv")
            == current_classifier_sha,
            validation_sources.get("evidence_map.csv") == current_evidence_map_sha,
            validation_sources.get("light_screening_pipeline.py")
            == current_light_screening_pipeline_sha,
            frozen_validation.get("path") == VALIDATION.relative_to(ROOT).as_posix(),
            current_original_validation_sha is not None,
            frozen_validation.get("sha256") == current_original_validation_sha,
            frozen_validation.get("failed_case_count") == validation_fail_count,
            failed_validation_keys <= selected_keys,
            classifier_validation.get("human_reference_rows") == 0,
            classifier_validation.get("independent_blinding") is False,
            classifier_validation.get("release_ready") is False,
        )
    )
    cross_layer_integrity_value = classifier_cross_layer.get(
        "cross_layer_integrity", {}
    )
    cross_layer_sources_value = classifier_cross_layer.get("source_hashes", {})
    cross_layer_classifier_value = classifier_cross_layer.get("classifier_layer", {})
    cross_layer_frozen_validation_value = classifier_cross_layer.get(
        "frozen_classifier_validation", {}
    )
    cross_layer_integrity = (
        cross_layer_integrity_value
        if isinstance(cross_layer_integrity_value, dict)
        else {}
    )
    cross_layer_sources = (
        cross_layer_sources_value if isinstance(cross_layer_sources_value, dict) else {}
    )
    cross_layer_classifier = (
        cross_layer_classifier_value
        if isinstance(cross_layer_classifier_value, dict)
        else {}
    )
    cross_layer_frozen_validation = (
        cross_layer_frozen_validation_value
        if isinstance(cross_layer_frozen_validation_value, dict)
        else {}
    )
    recorded_classifier_output_hashes = cross_layer_integrity.get(
        "batch_output_files_sha256", {}
    )
    recorded_classifier_input_hashes = cross_layer_integrity.get(
        "batch_input_files_sha256", {}
    )
    recorded_classifier_manifest_hashes = cross_layer_sources.get(
        "classifier_batch_manifests", {}
    )
    normalized_decision_fields = [
        "record_id",
        "question_id",
        "decision",
        "reason_codes",
        "confidence",
        "evidence_basis",
    ]
    classifier_cross_layer_checks = {
        "artifact_loaded": classifier_cross_layer_load_error is None,
        "artifact_sha256_computed": current_cross_layer_validation_sha is not None,
        "schema_1_1_0": classifier_cross_layer.get("schema_version") == "1.1.0",
        "case_pass_fail_match_original_validation": all(
            (
                classifier_cross_layer.get("case_count")
                == classifier_validation.get("case_count")
                == len(validation_cases),
                classifier_cross_layer.get("pass_count")
                == classifier_validation.get("pass_count")
                == validation_pass_count,
                classifier_cross_layer.get("fail_count")
                == classifier_validation.get("fail_count")
                == validation_fail_count,
            )
        ),
        "frozen_original_validation_current": all(
            (
                cross_layer_frozen_validation.get("path")
                == VALIDATION.relative_to(ROOT).as_posix(),
                cross_layer_frozen_validation.get("exists") is True,
                current_original_validation_sha is not None,
                cross_layer_frozen_validation.get("sha256")
                == current_original_validation_sha,
                cross_layer_frozen_validation.get("primary_contract_validated")
                is True,
                cross_layer_frozen_validation.get("modified_by_this_validator")
                is False,
            )
        ),
        "cross_layer_counts_exact": all(
            (
                cross_layer_integrity.get("expected_screening_units") == 43_207,
                cross_layer_integrity.get("evidence_map_membership_key_count")
                == 43_207,
                cross_layer_integrity.get("classifier_checkpoint_row_count") == 43_207,
                cross_layer_integrity.get("classifier_batch_count") == 182,
                cross_layer_integrity.get("classifier_batch_output_row_count")
                == 43_207,
                cross_layer_integrity.get("classifier_decisions_csv_row_count")
                == 43_207,
            )
        ),
        "six_normalized_decision_fields_exact": all(
            (
                cross_layer_integrity.get("normalized_decision_fields")
                == normalized_decision_fields,
                cross_layer_integrity.get("key_universe_exact_match") is True,
                cross_layer_integrity.get("six_normalized_decision_fields_exact_match")
                is True,
            )
        ),
        "classifier_output_hash_map_exact": all(
            (
                isinstance(recorded_classifier_output_hashes, dict),
                len(recorded_classifier_output_hashes) == 182,
                recorded_classifier_output_hashes == current_classifier_output_hashes,
                len(classifier_output_paths) == 182,
            )
        ),
        "classifier_input_hash_map_exact": all(
            (
                cross_layer_integrity.get(
                    "batch_input_evidence_fields_and_order_exact_match"
                )
                is True,
                isinstance(recorded_classifier_input_hashes, dict),
                len(recorded_classifier_input_hashes) == 182,
                recorded_classifier_input_hashes == current_classifier_input_hashes,
                len(classifier_input_paths) == 182,
            )
        ),
        "classifier_batch_manifest_hash_map_exact": all(
            (
                isinstance(recorded_classifier_manifest_hashes, dict),
                len(recorded_classifier_manifest_hashes) == len(QUESTION_ORDER) == 5,
                recorded_classifier_manifest_hashes
                == current_classifier_manifest_hashes,
                len(current_classifier_manifest_hashes) == 5,
            )
        ),
        "classifier_layer_current": all(
            (
                cross_layer_classifier.get("path")
                == CLASSIFIER.relative_to(ROOT).as_posix(),
                cross_layer_classifier.get("rows")
                == len(classifier_rows)
                == 43_207,
                cross_layer_classifier.get("sha256") == current_classifier_sha,
            )
        ),
        "current_source_hashes_match": all(
            (
                cross_layer_sources.get("evidence_map.csv")
                == current_evidence_map_sha,
                cross_layer_sources.get("classifier_decisions.csv")
                == current_classifier_sha,
                cross_layer_sources.get("classifier_checkpoints.jsonl")
                == current_classifier_checkpoints_sha,
                cross_layer_sources.get("classifier_validation_v50.py")
                == current_classifier_validator_sha,
                cross_layer_sources.get("light_screening_pipeline.py")
                == current_light_screening_pipeline_sha,
                cross_layer_sources.get("frozen_light_screening_prompt.md")
                == current_frozen_light_prompt_sha,
                cross_layer_sources.get("v4_screening_manifest.json")
                == current_v4_screening_manifest_sha,
                cross_layer_sources.get("v4_evidence_map.csv")
                == current_v4_evidence_map_sha,
                cross_layer_sources.get("v4_checkpoints.jsonl")
                == current_v4_checkpoints_sha,
            )
        ),
        "release_limitations_preserved": all(
            (
                classifier_cross_layer.get("human_reference_rows") == 0,
                classifier_cross_layer.get("independent_blinding") is False,
                classifier_cross_layer.get("release_ready") is False,
            )
        ),
    }
    classifier_cross_layer_complete = all(classifier_cross_layer_checks.values())
    classifier_validation_complete = (
        original_classifier_validation_complete and classifier_cross_layer_complete
    )

    previous: dict = {}
    if PROGRESS.exists():
        try:
            previous = load_json(PROGRESS)
        except (json.JSONDecodeError, OSError):
            previous = {}
    started_text = previous.get("tracking_started_at_utc")
    if isinstance(started_text, str):
        try:
            started = datetime.fromisoformat(started_text)
        except ValueError:
            started = now
    else:
        started = now

    quotas = selection["question_quotas"]
    recent_cutoff = now - timedelta(minutes=30)
    recent_rows = 0
    questions: dict[str, dict] = {}
    completed_total = 0
    for question in QUESTION_ORDER:
        output_paths = sorted((OUTPUT_ROOT / question).glob("*.jsonl"))
        present_rows = sum(jsonl_rows(path) for path in output_paths)
        for path in output_paths:
            changed = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if changed >= recent_cutoff:
                recent_rows += jsonl_rows(path)
        check_path = CHECK_ROOT / f"{question}.json"
        checked_rows = 0
        state = "pending"
        expected_rows = int(quotas[question]["selected_rows"])
        expected_batches = int(quotas[question]["batch_count"])
        if check_path.exists():
            check = load_json(check_path)
            batch_records = check.get("batches", [])
            batch_proofs: list[bool] = []
            for batch in batch_records if isinstance(batch_records, list) else []:
                input_path = ROOT / str(batch.get("input_path", ""))
                output_path = ROOT / str(batch.get("output_path", ""))
                expected_batch_rows = int(batch.get("row_count", -1))
                batch_proofs.append(
                    all(
                        (
                            input_path.is_file(),
                            output_path.is_file(),
                            input_path.parent == BATCH_ROOT / question,
                            output_path.parent == OUTPUT_ROOT / question,
                            expected_batch_rows == 200,
                            jsonl_rows(input_path) == expected_batch_rows
                            if input_path.is_file()
                            else False,
                            jsonl_rows(output_path) == expected_batch_rows
                            if output_path.is_file()
                            else False,
                            sha256(input_path) == batch.get("input_sha256")
                            if input_path.is_file()
                            else False,
                            sha256(output_path) == batch.get("output_sha256")
                            if output_path.is_file()
                            else False,
                        )
                    )
                )
            contract_complete = all(
                (
                    check.get("complete") is True,
                    check.get("question_id") == question,
                    check.get("expected_rows") == expected_rows,
                    check.get("contract_checked_rows") == expected_rows,
                    check.get("batch_count") == expected_batches,
                    isinstance(batch_records, list),
                    len(batch_records) == expected_batches,
                    len(output_paths) == expected_batches,
                    present_rows == expected_rows,
                    sum(int(batch.get("row_count", 0)) for batch in batch_records)
                    == expected_rows,
                    all(batch_proofs),
                    check.get("selection_sha256") == sha256(SELECTION),
                    check.get("prompt_sha256") == sha256(PROMPT),
                    check.get("classifier_decisions_sha256") == sha256(CLASSIFIER),
                    check.get("evidence_map_sha256") == sha256(EVIDENCE_MAP),
                )
            )
            if contract_complete:
                checked_rows = expected_rows
                state = "complete"
            else:
                state = "check_failed"
        elif present_rows:
            state = "outputs_in_progress"
        completed_total += checked_rows
        questions[question] = {
            "selected_rows": expected_rows,
            "batch_count": expected_batches,
            "output_files_present": len(output_paths),
            "output_rows_present": present_rows,
            "contract_checked_rows": checked_rows,
            "state": state,
        }

    elapsed = max(0.0, (now - started).total_seconds())
    rate = completed_total / elapsed if elapsed > 0 and completed_total else 0.0
    remaining = selection["selected_rows"] - completed_total
    estimate = round(remaining / rate, 1) if rate else None
    question_contracts_complete = (
        selection.get("selected_rows") == 5_000
        and selection.get("batch_count") == 25
        and selection.get("batch_size") == 200
        and completed_total == int(selection["selected_rows"])
        and all(questions[question]["state"] == "complete" for question in QUESTION_ORDER)
    )
    all_question_contracts_complete = (
        classifier_validation_complete
        and selection_provenance_correction_complete
        and question_contracts_complete
    )
    current_question = (
        None
        if question_contracts_complete
        else next(
            (
                question
                for question in QUESTION_ORDER
                if questions[question]["state"] != "complete"
            ),
            QUESTION_ORDER[0],
        )
    )
    compiled_complete = False
    if (
        all_question_contracts_complete
        and ADJUDICATION_MANIFEST.exists()
        and FINAL_DECISIONS.exists()
        and SEMANTIC_ADJUDICATIONS.exists()
    ):
        manifest = load_json(ADJUDICATION_MANIFEST)
        compiled = manifest.get("layers", {}).get("compiled_decisions", {})
        semantic_layer = manifest.get("layers", {}).get("semantic_adjudication", {})
        classifier_layer = manifest.get("layers", {}).get("classifier", {})
        final_fields, final_rows = read_csv(FINAL_DECISIONS)
        final_keys = [(row.get("record_id", ""), row.get("question_id", "")) for row in final_rows]
        semantic = load_json(SEMANTIC_ADJUDICATIONS)
        semantic_records = semantic.get("records", [])
        compiled_complete = all(
            (
                manifest.get("run_complete") is True,
                manifest.get("counts", {}).get("adjudicated_rows") == selection["selected_rows"],
                manifest.get("counts", {}).get("selected_rows") == selection["selected_rows"],
                manifest.get("counts", {}).get("classifier_rows") == 43_207,
                manifest.get("counts", {}).get("compiled_decision_rows") == 43_207,
                final_fields
                == [
                    "record_id",
                    "question_id",
                    "decision",
                    "reason_codes",
                    "confidence",
                    "evidence_basis",
                ],
                len(final_rows) == 43_207,
                len(set(final_keys)) == 43_207,
                all(all(key) for key in final_keys),
                all(
                    row.get("decision") in {"retain", "deprioritize", "uncertain"}
                    for row in final_rows
                ),
                compiled.get("row_count") == 43_207,
                compiled.get("sha256") == sha256(FINAL_DECISIONS),
                compiled.get("adjudication_labels_applied") is True,
                semantic_layer.get("row_count") == selection["selected_rows"],
                semantic_layer.get("sha256") == sha256(SEMANTIC_ADJUDICATIONS),
                semantic.get("row_count") == selection["selected_rows"],
                isinstance(semantic_records, list),
                len(semantic_records) == selection["selected_rows"],
                semantic.get("selection_sha256") == sha256(SELECTION),
                semantic.get("prompt_sha256") == sha256(PROMPT),
                classifier_layer.get("row_count") == 43_207,
                classifier_layer.get("sha256") == sha256(CLASSIFIER),
                manifest.get("hashes", {}).get("evidence_map_sha256")
                == sha256(EVIDENCE_MAP),
                manifest.get("classifier_decisions_unchanged") is True,
                manifest.get("adjudication_input_blinded_to_classifier_labels") is True,
                manifest.get("agent_identity_recorded") is False,
                manifest.get("specific_agent_attribution_supported") is False,
                manifest.get("execution_receipts_recorded") is False,
                manifest.get("question_sequence_receipt_recorded") is False,
                manifest.get("independent_blinding_ai") is False,
                manifest.get("independent_blinding") is False,
                manifest.get("release_ready") is False,
            )
        )
    downstream_complete = False
    if (
        compiled_complete
        and DOWNSTREAM_MANIFEST.exists()
        and DOWNSTREAM_CSV.exists()
        and LOCATOR_VERIFICATION.exists()
    ):
        downstream = load_json(DOWNSTREAM_MANIFEST)
        locator = load_json(LOCATOR_VERIFICATION)
        downstream_fields, downstream_rows = read_csv(DOWNSTREAM_CSV)
        downstream_output = downstream.get("outputs", {}).get("supporting_literature", {})
        downstream_results = downstream.get("results", {})
        locator_inputs = locator.get("inputs", {})
        downstream_complete = all(
            (
                downstream.get("inputs", {}).get("screening_decisions", {}).get("sha256")
                == sha256(FINAL_DECISIONS),
                downstream.get("inputs", {}).get("adjudication_manifest", {}).get("sha256")
                == sha256(ADJUDICATION_MANIFEST),
                downstream_output.get("path") == DOWNSTREAM_CSV.relative_to(ROOT).as_posix(),
                downstream_output.get("sha256") == sha256(DOWNSTREAM_CSV),
                downstream_output.get("row_count") == len(downstream_rows),
                downstream_results.get("emitted_link_count") == len(downstream_rows),
                downstream_results.get("emitted_link_count", 0) > 0,
                downstream_results.get("emitted_link_count", 0)
                + downstream_results.get("rejected_candidate_count", 0)
                == 20,
                downstream.get("inputs", {}).get("query_definitions", {}).get("sha256")
                == sha256(V5 / "query_definitions.json"),
                bool(downstream_fields),
                locator.get("status") == "pass",
                locator_inputs.get("supporting_literature", {}).get("sha256")
                == sha256(DOWNSTREAM_CSV),
                locator_inputs.get("downstream_manifest", {}).get("sha256")
                == sha256(DOWNSTREAM_MANIFEST),
                locator_inputs.get("final_decisions", {}).get("sha256")
                == sha256(FINAL_DECISIONS),
                locator_inputs.get("adjudication_manifest", {}).get("sha256")
                == sha256(ADJUDICATION_MANIFEST),
                locator.get("checks", {}).get("locator_quote_exact_match_for_every_link")
                is True,
                locator.get("checks", {}).get("site_output_unchanged") is True,
                locator.get("checks", {}).get(
                    "site_output_hash_captured_before_original_builder_import"
                )
                is True,
                locator.get("checks", {}).get("nonzero_link_set") is True,
            )
        )
    protected_complete = False
    protected: dict = {}
    protected_recheck: dict[str, object] = {
        "status": "not_run",
        "errors": ["protected audit artifact is missing"],
    }
    if PROTECTED_AUDIT.exists():
        protected = load_json(PROTECTED_AUDIT)
        protected_recheck_ok, protected_recheck = protected_audit_recheck(protected)
        protected_paths = protected.get("protected_paths", [])
        combined_protected = protected.get("combined_protected", {})
        limitations = protected.get("limitations", [])
        ignored_limitations = [
            item
            for item in limitations
            if isinstance(item, dict)
            and item.get("code") == "IGNORED_FILES_NOT_CAPTURED_IN_FROZEN_BASELINE"
        ] if isinstance(limitations, list) else []
        ignored_limitation_valid = (
            len(ignored_limitations) == 1
            and ignored_limitations[0].get("file_count")
            == combined_protected.get("ignored_file_count")
            == len(protected_recheck.get("current_ignored_files", []))
            and int(ignored_limitations[0].get("file_count", 0)) > 0
            and bool(ignored_limitations[0].get("effect"))
        )
        snapshot = protected.get("final_artifact_snapshot", {})
        snapshot_records = snapshot.get("artifacts", [])
        snapshot_hashes_current = isinstance(snapshot_records, list) and all(
            (ROOT / str(record.get("path", ""))).is_file()
            and sha256(ROOT / str(record.get("path", ""))) == record.get("sha256")
            for record in snapshot_records
        )
        protected_complete = all(
            (
                protected.get("schema_version") == "1.1.0",
                protected.get("status") == "pass_with_unverified_ignored_files",
                protected.get("status_scope") == "434_baseline_tracked_files",
                protected.get("ignored_file_baseline_limitation_present") is True,
                ignored_limitation_valid,
                protected.get("problems") == [],
                combined_protected.get("status") == "pass",
                combined_protected.get("tracked_files") == 434,
                combined_protected.get("bytes") == 404_869_977,
                combined_protected.get("ignored_baseline_comparison_supported") is False,
                isinstance(protected_paths, list),
                len(protected_paths) == 4,
                all(item.get("status") == "pass" for item in protected_paths),
                all(
                    item.get("verification", {}).get(
                        "consecutive_raw_snapshot_matches"
                    )
                    is True
                    for item in protected_paths
                ),
                protected_recheck_ok,
                snapshot.get("required_count") == snapshot.get("captured_count"),
                snapshot.get("missing") == [],
                snapshot.get("audit_after_required_artifacts") is True,
                snapshot_hashes_current,
            )
        )
    report_complete = False
    phase_a_b_report_current = False
    if RUN_REPORT.exists() and downstream_complete and protected_complete:
        run_report = load_json(RUN_REPORT)
        report_phase_c = run_report.get("phases", {}).get("C", {})
        report_phase_d = run_report.get("phases", {}).get("D", {})
        phase_a_b_report_current = report_phase_a_b_current(run_report)
        report_complete = all(
            (
                run_report.get("schema_version") == "5.0.1",
                run_report.get("overall_execution_status")
                == "complete_with_recorded_evidence_limitations_and_unresolved_items",
                phase_a_b_report_current,
                report_phase_c.get("semantic_adjudication_layer", {})
                .get("selection_provenance_correction", {})
                .get("validated")
                is True,
                report_phase_c.get("semantic_adjudication_layer", {})
                .get("selection_provenance_correction", {})
                .get("correction_id")
                == "V50-PC-001",
                report_phase_c.get("semantic_adjudication_layer", {}).get("reviewed_rows")
                == selection["selected_rows"],
                report_phase_c.get("semantic_adjudication_layer", {})
                .get("manifest", {})
                .get("sha256")
                == sha256(ADJUDICATION_MANIFEST),
                report_phase_c.get("final_layer", {}).get("artifact", {}).get("sha256")
                == sha256(FINAL_DECISIONS),
                report_phase_d.get("manifest", {}).get("sha256")
                == sha256(DOWNSTREAM_MANIFEST),
                report_phase_d.get("supporting_literature", {})
                .get("artifact", {})
                .get("sha256")
                == sha256(DOWNSTREAM_CSV),
                report_phase_d.get("original_builder_read_only_check", {})
                .get("artifact", {})
                .get("sha256")
                == sha256(LOCATOR_VERIFICATION),
                run_report.get("protected_path_verification") == protected,
                RUN_REPORT.stat().st_mtime
                >= max(
                    path.stat().st_mtime
                    for path in (
                        FINAL_DECISIONS,
                        ADJUDICATION_MANIFEST,
                        DOWNSTREAM_CSV,
                        DOWNSTREAM_MANIFEST,
                        LOCATOR_VERIFICATION,
                        PROTECTED_AUDIT,
                    )
                ),
            )
        )
    if not classifier_validation_complete:
        current_stage = "classifier_validation_pending"
    elif not selection_provenance_correction_complete:
        current_stage = "selection_provenance_correction_pending"
    elif current_question:
        current_stage = "semantic_adjudication"
    elif not compiled_complete:
        current_stage = "compile_pending"
    elif not downstream_complete:
        current_stage = "downstream_pending"
    elif not protected_complete:
        current_stage = "protected_audit_pending"
    elif not report_complete:
        current_stage = "run_report_pending"
    else:
        current_stage = "complete"
    if current_stage in {
        "classifier_validation_pending",
        "selection_provenance_correction_pending",
        "semantic_adjudication",
        "compile_pending",
    }:
        phase = "C"
    elif current_stage == "downstream_pending":
        phase = "D"
    elif current_stage == "complete":
        phase = "complete"
    else:
        phase = "finalization"
    classifier_distribution = Counter(row["decision"] for row in classifier_rows)
    document = {
        "schema_version": "5.0.1",
        "phase": phase,
        "current_stage": current_stage,
        "tracking_started_at_utc": iso(started),
        "updated_at_utc": iso(now),
        "elapsed_time_seconds": round(elapsed, 1),
        "classifier_layer": {
            "status": "complete_preserved_immutable",
            "rows": len(classifier_rows),
            "sha256": sha256(CLASSIFIER),
            "decision_distribution": dict(classifier_distribution),
            "execution_layer": "deterministic_text_classifier",
            "attribution_unsupported": True,
        },
        "classifier_validation": {
            "status": (
                "complete_with_recorded_failures"
                if classifier_validation_complete
                else "pending_original_validation_contract"
                if not original_classifier_validation_complete
                else "pending_cross_layer_integrity_validation"
            ),
            **(
                {"sha256": current_original_validation_sha}
                if current_original_validation_sha is not None
                else {}
            ),
            "case_count": classifier_validation.get("case_count"),
            "pass_count": classifier_validation.get("pass_count"),
            "fail_count": classifier_validation.get("fail_count"),
            "agreement_vs_ai_reference": classifier_validation.get(
                "agreement_vs_ai_reference"
            ),
            "human_reference_rows": classifier_validation.get("human_reference_rows"),
            "independent_blinding": classifier_validation.get("independent_blinding"),
            "release_ready": classifier_validation.get("release_ready"),
            "original_validation_complete": original_classifier_validation_complete,
            "original_validation_load_error": classifier_validation_load_error,
            "cross_layer_validation": {
                "status": "complete" if classifier_cross_layer_complete else "pending",
                "path": CROSS_LAYER_VALIDATION.relative_to(ROOT).as_posix(),
                **(
                    {"sha256": current_cross_layer_validation_sha}
                    if current_cross_layer_validation_sha is not None
                    else {}
                ),
                "schema_version": classifier_cross_layer.get("schema_version"),
                "classifier_batch_input_file_count": len(classifier_input_paths),
                "classifier_batch_output_file_count": len(classifier_output_paths),
                "classifier_batch_manifest_file_count": len(
                    current_classifier_manifest_hashes
                ),
                "current_input_hash_map_exact_match": (
                    recorded_classifier_input_hashes
                    == current_classifier_input_hashes
                    and len(current_classifier_input_hashes) == 182
                ),
                "current_output_hash_map_exact_match": (
                    recorded_classifier_output_hashes
                    == current_classifier_output_hashes
                    and len(current_classifier_output_hashes) == 182
                ),
                "current_manifest_hash_map_exact_match": (
                    recorded_classifier_manifest_hashes
                    == current_classifier_manifest_hashes
                    and len(current_classifier_manifest_hashes) == 5
                ),
                "checks": classifier_cross_layer_checks,
                "load_error": classifier_cross_layer_load_error,
            },
        },
        "semantic_adjudication": {
            "status": (
                "pending_selection_provenance_correction"
                if not selection_provenance_correction_complete
                else "in_progress"
                if current_question
                else "complete"
            ),
            "selected_rows": selection["selected_rows"],
            "completed_rows": completed_total,
            "remaining_rows": remaining,
            "recent_30min_output_rows": recent_rows,
            "estimated_remaining_time_seconds": estimate,
            "batch_size": selection["batch_size"],
            "batch_count": selection["batch_count"],
            "selection_sha256": sha256(SELECTION),
            "selection_provenance_correction": selection_provenance_correction,
            "processing_order": QUESTION_ORDER,
            "current_question": current_question,
            "questions": questions,
        },
        "final_decisions": {
            "status": (
                "complete"
                if compiled_complete
                else "pending_classifier_validation"
                if not classifier_validation_complete
                else "pending_selection_provenance_correction"
                if not selection_provenance_correction_complete
                else "pending_semantic_adjudication"
                if current_question
                else "ready_to_compile"
            ),
            **(
                {
                    "path": FINAL_DECISIONS.relative_to(ROOT).as_posix(),
                    "rows": 43_207,
                    "sha256": sha256(FINAL_DECISIONS),
                }
                if compiled_complete
                else {}
            ),
        },
        "downstream": {
            "status": "complete" if downstream_complete else "pending",
            **(
                {"manifest_sha256": sha256(DOWNSTREAM_MANIFEST)}
                if downstream_complete
                else {}
            ),
        },
        "protected_path_audit": {
            "status": (
                "complete_for_434_baseline_tracked_files_with_ignored_baseline_limitation"
                if protected_complete
                else "pending"
            ),
            "recheck": protected_recheck,
            **({"sha256": sha256(PROTECTED_AUDIT)} if protected_complete else {}),
        },
        "run_report": {
            "status": "complete" if report_complete else "pending",
            "phase_a_b_current_integrity_verified": phase_a_b_report_current,
            **({"sha256": sha256(RUN_REPORT)} if report_complete else {}),
        },
        "independent_blinding": False,
        "release_ready": False,
    }
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = PROGRESS.with_name(f".{PROGRESS.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, PROGRESS)
    print(json.dumps({"path": str(PROGRESS.relative_to(ROOT)), "completed_rows": completed_total, "total_rows": selection["selected_rows"], "current_question": current_question}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
