"""Build the corrected single-ledger v5.0 report.

Phase C is deliberately split into an immutable deterministic classifier layer
and a blinded semantic-adjudication layer.  The report is derived from persisted
artifacts; it never infers completion from the legacy progress file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from adjudication_pipeline_v50 import validate_selection_provenance_correction


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREEN = V5 / "screening"
LOGS = ROOT / "research_v3" / "logs"
OUT = LOGS / "v50_run_report.json"
QUESTION_ORDER = [
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
]
LABELS = ("deprioritize", "retain", "uncertain")
PROTECTED_PATHS = {
    "research_v3/otc/normalized": "research_v3/otc/normalized",
    "research_v3/otc/rules": "research_v3/otc/rules",
    "research_v3/otc/literature (excluding v5)": "research_v3/otc/literature",
    "research_v3/search/provisional_pubmed_20260710": (
        "research_v3/search/provisional_pubmed_20260710"
    ),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def git_paths(value: str) -> list[str]:
    return [
        line.strip().replace("\\", "/")
        for line in value.splitlines()
        if line.strip()
    ]


def excluded_protected_path(path: str, label: str) -> bool:
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
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("canonical SHA-256 is not lowercase hexadecimal")
            canonical.append({"path": path, "bytes": byte_count, "sha256": digest})
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"record {index}: {exc}")
    return canonical, errors


def protected_audit_recheck(protected: dict[str, Any]) -> tuple[bool, dict[str, object]]:
    """Re-enumerate and rehash every file claimed by the protected-path audit."""

    audit_paths = protected.get("protected_paths", [])
    if not isinstance(audit_paths, list):
        return False, {"status": "fail", "problems": ["protected_paths is not a list"]}
    audit_by_label = {
        str(item.get("path")): item for item in audit_paths if isinstance(item, dict)
    }
    problems: list[str] = []
    if len(audit_by_label) != len(audit_paths):
        problems.append("protected_paths contains a duplicate or invalid path record")
    if set(audit_by_label) != set(PROTECTED_PATHS):
        problems.append("protected_paths does not match the required path set")

    path_results: list[dict[str, object]] = []
    combined_current_tracked: list[dict[str, object]] = []
    combined_current_untracked: list[dict[str, object]] = []
    combined_current_ignored: list[dict[str, object]] = []
    combined_baseline_canonical: list[dict[str, object]] = []
    combined_current_canonical: list[dict[str, object]] = []

    for label, actual_path in PROTECTED_PATHS.items():
        item = audit_by_label.get(label)
        if not isinstance(item, dict):
            problems.append(f"missing protected audit path: {label}")
            continue
        audit_tracked = item.get("files", [])
        audit_untracked = item.get("untracked_files", [])
        audit_ignored = item.get("ignored_files", [])
        if not all(
            isinstance(records, list)
            for records in (audit_tracked, audit_untracked, audit_ignored)
        ):
            problems.append(f"invalid protected manifest type: {label}")
            continue

        def enumerate_paths(*git_args: str) -> list[str]:
            return [
                path
                for path in git_paths(git(*git_args, "--", actual_path))
                if not excluded_protected_path(path, label)
            ]

        current_paths = {
            "tracked": enumerate_paths("ls-files"),
            "untracked": enumerate_paths("ls-files", "--others", "--exclude-standard"),
            "ignored": enumerate_paths(
                "ls-files", "--others", "--ignored", "--exclude-standard"
            ),
        }
        current_records: dict[str, list[dict[str, object]]] = {}
        read_errors: list[str] = []
        for kind, paths in current_paths.items():
            current_records[kind], errors = current_file_records(paths)
            read_errors.extend(errors)

        second_paths = {
            "tracked": enumerate_paths("ls-files"),
            "untracked": enumerate_paths("ls-files", "--others", "--exclude-standard"),
            "ignored": enumerate_paths(
                "ls-files", "--others", "--ignored", "--exclude-standard"
            ),
        }
        second_records: dict[str, list[dict[str, object]]] = {}
        second_errors: list[str] = []
        for kind, paths in second_paths.items():
            second_records[kind], errors = current_file_records(paths)
            second_errors.extend(errors)

        audit_manifests = {
            "tracked": audit_tracked,
            "untracked": audit_untracked,
            "ignored": audit_ignored,
        }
        audit_indexes: dict[str, dict[str, dict[str, object]]] = {}
        duplicate_manifest_paths: list[str] = []
        for kind, records in audit_manifests.items():
            index = {
                str(record.get("path")): record
                for record in records
                if isinstance(record, dict)
            }
            audit_indexes[kind] = index
            if len(index) != len(records):
                duplicate_manifest_paths.append(kind)

        new_paths: dict[str, list[str]] = {}
        missing_paths: dict[str, list[str]] = {}
        content_mismatches: dict[str, list[str]] = {}
        for kind in ("tracked", "untracked", "ignored"):
            current_set = set(current_paths[kind])
            audit_set = set(audit_indexes[kind])
            current_by_path = {
                str(record["path"]): record for record in current_records[kind]
            }
            new_paths[kind] = sorted(current_set - audit_set)
            missing_paths[kind] = sorted(audit_set - current_set)
            content_mismatches[kind] = sorted(
                path
                for path in current_set & audit_set
                if current_by_path.get(path, {}).get("bytes")
                != audit_indexes[kind][path].get("bytes")
                or current_by_path.get(path, {}).get("sha256")
                != audit_indexes[kind][path].get("sha256")
            )

        raw_manifest_hashes = {
            kind: canonical_manifest_sha256(current_records[kind])
            for kind in ("tracked", "untracked", "ignored")
        }
        consecutive_snapshot_matches = all(
            current_paths[kind] == second_paths[kind]
            and canonical_manifest_sha256(second_records[kind])
            == raw_manifest_hashes[kind]
            for kind in ("tracked", "untracked", "ignored")
        ) and not second_errors

        baseline_canonical, baseline_errors = recorded_canonical_records(
            audit_tracked, "baseline"
        )
        recorded_current_canonical, current_canonical_errors = (
            recorded_canonical_records(audit_tracked, "current")
        )
        baseline_canonical_hash = canonical_manifest_sha256(baseline_canonical)
        recorded_current_canonical_hash = canonical_manifest_sha256(
            recorded_current_canonical
        )
        verification_value = item.get("verification", {})
        verification_is_object = isinstance(verification_value, dict)
        verification = verification_value if verification_is_object else {}
        canonical_baseline_match = all(
            (
                not baseline_errors,
                not current_canonical_errors,
                baseline_canonical == recorded_current_canonical,
                baseline_canonical_hash
                == item.get("baseline_canonical_file_manifest_sha256"),
                recorded_current_canonical_hash
                == item.get("current_canonical_file_manifest_sha256"),
                baseline_canonical_hash == recorded_current_canonical_hash,
                verification_is_object,
                verification.get("canonical_per_file_sha256_matches_baseline") is True,
                verification.get("canonical_manifest_sha256_matches_baseline") is True,
                all(
                    isinstance(record, dict)
                    and record.get("canonical_sha256_matches_baseline") is True
                    and record.get("baseline_canonical_bytes")
                    == record.get("current_canonical_bytes")
                    and record.get("baseline_canonical_sha256")
                    == record.get("current_canonical_sha256")
                    and record.get("baseline_git_blob_oid")
                    == record.get("current_git_blob_oid")
                    for record in audit_tracked
                ),
            )
        )
        path_problems = [
            *read_errors,
            *second_errors,
            *baseline_errors,
            *current_canonical_errors,
        ]
        if duplicate_manifest_paths:
            path_problems.append(
                "duplicate audit manifest paths: " + ", ".join(duplicate_manifest_paths)
            )
        if any(new_paths.values()):
            path_problems.append("current path set contains files absent from the audit")
        if any(missing_paths.values()):
            path_problems.append("audit path set contains files absent from the current tree")
        if any(content_mismatches.values()):
            path_problems.append("current file bytes or hashes differ from the audit")
        if not consecutive_snapshot_matches:
            path_problems.append("consecutive protected-path snapshots differ")
        if current_paths["untracked"]:
            path_problems.append("protected path contains untracked files")
        if not canonical_baseline_match:
            path_problems.append("recorded baseline/current canonical manifests differ")
        if raw_manifest_hashes["tracked"] != item.get("current_file_manifest_sha256"):
            path_problems.append("tracked manifest SHA-256 differs from the audit")
        if raw_manifest_hashes["untracked"] != item.get("untracked_file_manifest_sha256"):
            path_problems.append("untracked manifest SHA-256 differs from the audit")
        if raw_manifest_hashes["ignored"] != item.get("ignored_file_manifest_sha256"):
            path_problems.append("ignored manifest SHA-256 differs from the audit")
        if len(current_records["tracked"]) != item.get("tracked_files"):
            path_problems.append("tracked file count differs from the audit")
        if sum(int(record["bytes"]) for record in current_records["tracked"]) != item.get(
            "bytes"
        ):
            path_problems.append("tracked byte count differs from the audit")
        if len(current_records["untracked"]) != item.get("untracked_file_count"):
            path_problems.append("untracked file count differs from the audit")
        if len(current_records["ignored"]) != item.get("ignored_file_count"):
            path_problems.append("ignored file count differs from the audit")
        if item.get("status") != "pass":
            path_problems.append("audit path status is not pass")
        if not verification_is_object or verification.get(
            "ignored_files_with_mtime_after_baseline_capture"
        ) != []:
            path_problems.append("ignored-file mtime check is not clean")

        path_results.append(
            {
                "path": label,
                "status": "pass" if not path_problems else "fail",
                "tracked_file_count": len(current_records["tracked"]),
                "untracked_file_count": len(current_records["untracked"]),
                "ignored_file_count": len(current_records["ignored"]),
                "current_manifest_sha256": raw_manifest_hashes,
                "recorded_canonical_manifest_sha256": {
                    "baseline": baseline_canonical_hash,
                    "current": recorded_current_canonical_hash,
                },
                "new_paths": new_paths,
                "missing_paths": missing_paths,
                "content_mismatches": content_mismatches,
                "consecutive_snapshot_matches": consecutive_snapshot_matches,
                "problems": path_problems,
            }
        )
        problems.extend(f"{label}: {problem}" for problem in path_problems)
        combined_current_tracked.extend(current_records["tracked"])
        combined_current_untracked.extend(current_records["untracked"])
        combined_current_ignored.extend(current_records["ignored"])
        combined_baseline_canonical.extend(baseline_canonical)
        combined_current_canonical.extend(recorded_current_canonical)

    combined = protected.get("combined_protected", {})
    combined_hashes = {
        "tracked": canonical_manifest_sha256(combined_current_tracked),
        "untracked": canonical_manifest_sha256(combined_current_untracked),
        "ignored": canonical_manifest_sha256(combined_current_ignored),
        "baseline_canonical": canonical_manifest_sha256(combined_baseline_canonical),
        "current_canonical": canonical_manifest_sha256(combined_current_canonical),
    }
    combined_problems: list[str] = []
    if not isinstance(combined, dict):
        combined_problems.append("combined_protected is not an object")
    else:
        combined_contract = {
            "tracked": "current_file_manifest_sha256",
            "untracked": "untracked_file_manifest_sha256",
            "ignored": "ignored_file_manifest_sha256",
            "baseline_canonical": "baseline_canonical_file_manifest_sha256",
            "current_canonical": "current_canonical_file_manifest_sha256",
        }
        for kind, field in combined_contract.items():
            if combined_hashes[kind] != combined.get(field):
                combined_problems.append(f"combined {field} differs from current recheck")
        if combined_hashes["baseline_canonical"] != combined_hashes["current_canonical"]:
            combined_problems.append("combined baseline/current canonical manifests differ")
        if len(combined_current_tracked) != combined.get("tracked_files"):
            combined_problems.append("combined tracked file count differs from current recheck")
        if len(combined_current_untracked) != combined.get("untracked_file_count"):
            combined_problems.append("combined untracked file count differs from current recheck")
        if len(combined_current_ignored) != combined.get("ignored_file_count"):
            combined_problems.append("combined ignored file count differs from current recheck")
        if sum(int(record["bytes"]) for record in combined_current_tracked) != combined.get(
            "bytes"
        ):
            combined_problems.append("combined tracked byte count differs from current recheck")
        if combined.get("status") != "pass":
            combined_problems.append("combined protected status is not pass")
    if len(combined_current_tracked) != 434:
        combined_problems.append("current protected tracked file count is not 434")
    if protected.get("problems") != []:
        combined_problems.append("protected audit records non-empty problems")
    problems.extend(combined_problems)

    complete = (
        not problems
        and len(path_results) == len(PROTECTED_PATHS)
        and all(result["status"] == "pass" for result in path_results)
    )
    return complete, {
        "status": (
            "pass_for_434_baseline_tracked_files_with_ignored_baseline_limitation"
            if complete and combined_current_ignored
            else "pass" if complete else "fail"
        ),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "tracked_file_count": len(combined_current_tracked),
        "untracked_file_count": len(combined_current_untracked),
        "ignored_file_count": len(combined_current_ignored),
        "current_manifest_sha256": combined_hashes,
        "ignored_file_baseline_limitation_present": bool(combined_current_ignored),
        "paths": path_results,
        "problems": problems,
    }


def file_record(path: Path, **extra: object) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        **extra,
    }


def atomic_json(path: Path, value: object) -> None:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def label_distribution(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["decision"]) for row in rows)
    return {label: counts[label] for label in LABELS}


def per_question(rows: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for question_id in QUESTION_ORDER:
        subset = [row for row in rows if row["question_id"] == question_id]
        result[question_id] = {
            "rows": len(subset),
            "decision_distribution": label_distribution(subset),
            "confidence_distribution": dict(
                sorted(Counter(str(row["confidence"]) for row in subset).items())
            ),
            "evidence_basis_distribution": dict(
                sorted(Counter(str(row["evidence_basis"]) for row in subset).items())
            ),
        }
    return result


def decision_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["record_id"]), str(row["question_id"])


def decision_payload(row: dict[str, Any]) -> tuple[str, tuple[str, ...], str, str]:
    reasons = row["reason_codes"]
    if isinstance(reasons, str):
        reason_tuple = tuple(value for value in reasons.split(";") if value)
    elif isinstance(reasons, list):
        reason_tuple = tuple(str(value) for value in reasons)
    else:
        raise ValueError(f"invalid reason_codes type for {decision_key(row)}")
    return (
        str(row["decision"]),
        reason_tuple,
        str(row["confidence"]),
        str(row["evidence_basis"]),
    )


def semantic_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return payload["records"]
    raise ValueError("semantic_adjudications.json must be a list or contain records[]")


def movement_matrix(
    classifier: dict[tuple[str, str], dict[str, Any]],
    reviewed: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, int]], int]:
    matrix = {before: {after: 0 for after in LABELS} for before in LABELS}
    disagreement = 0
    for row in reviewed:
        key = decision_key(row)
        before = str(classifier[key]["decision"])
        after = str(row["decision"])
        matrix[before][after] += 1
        disagreement += before != after
    return matrix, disagreement


def batch_inventory(root: Path) -> list[dict[str, object]]:
    return [
        file_record(path, rows=sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line))
        for path in sorted(root.glob("*/*.jsonl"))
    ]


def verify_checksum_manifest(run_path: Path, expected_sha256: str, expected_files: int) -> dict[str, object]:
    checksum_path = run_path / "checksum.sha256"
    if sha256(checksum_path) != expected_sha256:
        raise ValueError(f"checksum manifest hash mismatch: {checksum_path}")
    entries: list[dict[str, object]] = []
    manifest_paths: set[str] = set()
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
                f"checksum entry does not have the .xml extension: {checksum_path}:{line_number}"
            )
        if relative in manifest_paths:
            raise ValueError(f"duplicate checksum path: {checksum_path}:{relative}")
        manifest_paths.add(relative)
        candidate = (run_path / relative).resolve()
        try:
            candidate.relative_to(run_path.resolve())
        except ValueError as exc:
            raise ValueError(f"checksum path escapes run directory: {relative}") from exc
        if not candidate.is_file() or sha256(candidate) != parts[0]:
            raise ValueError(f"raw retrieval checksum mismatch: {relative}")
        entries.append(file_record(candidate))
    if len(entries) != expected_files:
        raise ValueError(
            f"raw retrieval file count mismatch for {run_path}: {len(entries)} != {expected_files}"
        )
    actual_xml_paths = {
        path.relative_to(run_path).as_posix()
        for path in run_path.rglob("*.xml")
        if path.is_file()
    }
    if manifest_paths != actual_xml_paths:
        missing_from_manifest = sorted(actual_xml_paths - manifest_paths)
        missing_from_run = sorted(manifest_paths - actual_xml_paths)
        raise ValueError(
            "checksum/XML path set mismatch for "
            f"{run_path}: missing_from_manifest={missing_from_manifest}, "
            f"missing_from_run={missing_from_run}"
        )
    return {
        "checksum_manifest": file_record(checksum_path),
        "verified_file_count": len(entries),
        "duplicate_paths_rejected": True,
        "xml_extension_required": True,
        "manifest_matches_recursive_xml_set": True,
        "files": entries,
    }


def verify_phase_a(
    queries: dict[str, Any], probe: dict[str, Any], queries_path: Path
) -> dict[str, object]:
    query_rows = queries.get("questions")
    probe_rows = probe.get("questions")
    if not isinstance(query_rows, list) or not isinstance(probe_rows, list):
        raise ValueError("Phase A question records are missing")
    if [row.get("question_id") for row in query_rows] != QUESTION_ORDER:
        raise ValueError("query definition question order changed")
    if [row.get("question_id") for row in probe_rows] != QUESTION_ORDER:
        raise ValueError("probe question order changed")
    checks: list[dict[str, object]] = []
    for query_row, probe_row in zip(query_rows, probe_rows, strict=True):
        query_hash = hashlib.sha256(str(query_row.get("query", "")).encode("utf-8")).hexdigest()
        rules = probe_row.get("protocol_section_3_self_check")
        valid = all(
            (
                query_hash == query_row.get("query_sha256"),
                probe_row.get("query") == query_row.get("query"),
                probe_row.get("query_sha256") == query_hash,
                isinstance(rules, list),
                len(rules) == 10,
                [rule.get("rule") for rule in rules] == list(range(1, 11)),
                all(rule.get("status") == "pass" for rule in rules),
                probe_row.get("all_rules_pass") is True,
                probe_row.get("esearch", {}).get("count") == probe_row.get("hit_count"),
                probe_row.get("esearch", {}).get("http_status") == 200,
            )
        )
        if not valid:
            raise ValueError(f"Phase A query/probe contract failed: {query_row.get('question_id')}")
        checks.append(
            {
                "question_id": query_row["question_id"],
                "query_sha256": query_hash,
                "hit_count": probe_row["hit_count"],
                "protocol_rules_checked": 10,
                "passed": True,
            }
        )
    totals = probe.get("totals", {})
    if not all(
        (
            probe.get("status") == "complete",
            probe.get("query_definitions_path") == queries_path.relative_to(ROOT).as_posix(),
            probe.get("query_definitions_sha256") == sha256(queries_path),
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


def verify_phase_b(
    corpus: dict[str, Any],
    queries: dict[str, Any],
    probe: dict[str, Any],
    queries_path: Path,
    probe_path: Path,
    evidence_path: Path,
    evidence_rows: list[dict[str, str]],
) -> dict[str, object]:
    questions = corpus.get("questions")
    if not isinstance(questions, list) or [row.get("question_id") for row in questions] != QUESTION_ORDER:
        raise ValueError("Phase B question records are missing or reordered")
    raw_checks: list[dict[str, object]] = []
    query_by_id = {row["question_id"]: row for row in queries.get("questions", [])}
    probe_by_id = {row["question_id"]: row for row in probe.get("questions", [])}
    for row in questions:
        run_path = ROOT / str(row.get("run_path", ""))
        response_path = run_path / "response_metadata.json"
        if not all(
            (
                row.get("status") == "complete",
                row.get("phase_a_probe_count") == row.get("phase_b_base_count"),
                row.get("phase_b_base_count") == row.get("segment_count_sum"),
                row.get("query_sha256")
                == query_by_id.get(row.get("question_id"), {}).get("query_sha256"),
                row.get("phase_a_probe_count")
                == probe_by_id.get(row.get("question_id"), {}).get("hit_count"),
                sha256(response_path) == row.get("response_metadata_sha256"),
            )
        ):
            raise ValueError(f"Phase B question contract failed: {row.get('question_id')}")
        raw_checks.append(
            {
                "question_id": row["question_id"],
                "run_path": row["run_path"],
                **verify_checksum_manifest(
                    run_path,
                    str(row.get("checksum_manifest_sha256")),
                    int(row.get("raw_xml_file_count", -1)),
                ),
            }
        )
    evidence = corpus.get("evidence_map", {})
    membership_rows = sum(
        len([value for value in row.get("question_ids", "").split(";") if value])
        for row in evidence_rows
    )
    totals = corpus.get("totals", {})
    if not all(
        (
            corpus.get("status") == "complete",
            corpus.get("query_definitions_sha256") == sha256(queries_path),
            corpus.get("probe_report_sha256") == sha256(probe_path),
            evidence.get("path") == evidence_path.relative_to(ROOT).as_posix(),
            evidence.get("sha256") == sha256(evidence_path),
            evidence.get("rows") == len(evidence_rows) == 42_822,
            membership_rows == 43_207,
            totals.get("phase_a_probe_hits_before_cross_question_deduplication") == 43_249,
            totals.get("phase_b_hits_before_cross_question_deduplication") == 43_249,
            totals.get("question_membership_units_after_bibliographic_deduplication") == 43_207,
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


def missing_v4_links(evidence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    evidence_pmids = {row["pmid"] for row in evidence_rows}
    source = read_csv(ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv")
    return [
        {
            "link_id": row["link_id"],
            "rule_id": row["rule_id"],
            "rule_type": row["rule_type"],
            "pmid": row["pmid"],
            "title": row["title"],
            "reason": "pmid_absent_from_v5_corpus",
        }
        for row in source
        if row["pmid"] not in evidence_pmids
    ]


def main() -> None:
    probe_path = V5 / "probe_report.json"
    corpus_path = V5 / "corpus_manifest.json"
    queries_path = V5 / "query_definitions.json"
    classifier_path = SCREEN / "classifier_decisions.csv"
    final_path = SCREEN / "decisions.csv"
    validation_path = SCREEN / "classifier_validation.json"
    cross_validation_path = SCREEN / "classifier_validation_cross_layer.json"
    selection_path = SCREEN / "adjudication_selection.json"
    semantic_path = SCREEN / "semantic_adjudications.json"
    adjudication_manifest_path = SCREEN / "adjudication_manifest.json"
    downstream_manifest_path = V5 / "downstream" / "literature_link_manifest.json"
    downstream_csv_path = V5 / "downstream" / "supporting_literature.csv"
    locator_verification_path = V5 / "downstream" / "locator_verification.json"
    protected_path = LOGS / "v50_protected_final_audit.json"
    decision_history_path = LOGS / "DECISIONS_v50.md"
    final_summary_path = LOGS / "v50_FINAL.md"
    amendments_path = ROOT / "research_v3" / "protocol" / "amendments.csv"

    required = [
        probe_path,
        corpus_path,
        queries_path,
        classifier_path,
        final_path,
        validation_path,
        cross_validation_path,
        selection_path,
        semantic_path,
        adjudication_manifest_path,
        downstream_manifest_path,
        downstream_csv_path,
        locator_verification_path,
        protected_path,
        decision_history_path,
        final_summary_path,
        amendments_path,
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required v5 artifacts are missing: {missing}")

    probe = load_json(probe_path)
    corpus = load_json(corpus_path)
    queries = load_json(queries_path)
    validation = load_json(validation_path)
    cross_validation = load_json(cross_validation_path)
    selection = load_json(selection_path)
    selection_provenance_correction = validate_selection_provenance_correction(selection)
    semantic_payload = load_json(semantic_path)
    adjudication_manifest = load_json(adjudication_manifest_path)
    downstream = load_json(downstream_manifest_path)
    locator_verification = load_json(locator_verification_path)
    protected = load_json(protected_path)
    evidence_path = V5 / "evidence_map.csv"
    evidence_rows = read_csv(evidence_path)
    phase_a_integrity = verify_phase_a(queries, probe, queries_path)
    phase_b_integrity = verify_phase_b(
        corpus, queries, probe, queries_path, probe_path, evidence_path, evidence_rows
    )

    classifier_rows: list[dict[str, Any]] = read_csv(classifier_path)
    final_rows: list[dict[str, Any]] = read_csv(final_path)
    reviewed = semantic_records(semantic_payload)
    classifier = {decision_key(row): row for row in classifier_rows}
    final = {decision_key(row): row for row in final_rows}
    if len(classifier_rows) != 43_207 or len(classifier) != 43_207:
        raise ValueError("classifier layer must contain 43,207 unique rows")
    classifier_keys = [decision_key(row) for row in classifier_rows]
    final_keys = [decision_key(row) for row in final_rows]
    if final_keys != classifier_keys or len(final) != 43_207:
        raise ValueError("final decision keys/order differ from classifier layer")
    reviewed_keys = [decision_key(row) for row in reviewed]
    if len(reviewed_keys) != len(set(reviewed_keys)):
        raise ValueError("semantic adjudications contain duplicate keys")
    selection_records = selection.get("selected_records")
    if not isinstance(selection_records, list):
        raise ValueError("adjudication selection lacks selected_records")
    selection_keys = [decision_key(row) for row in selection_records]
    if reviewed_keys != selection_keys:
        raise ValueError("semantic adjudication keys/order differ from frozen selection")
    question_index = {question: index for index, question in enumerate(QUESTION_ORDER)}
    if not set(selection_keys) <= set(classifier):
        raise ValueError("frozen selection contains a key outside the classifier layer")
    if selection.get("processing_order") != QUESTION_ORDER:
        raise ValueError("frozen selection question order changed")
    if selection_keys != sorted(selection_keys, key=lambda key: (question_index[key[1]], key[0])):
        raise ValueError("frozen selection is not in stable question/key order")
    reviewed_by_key = {decision_key(row): row for row in reviewed}
    for classifier_row, final_row in zip(classifier_rows, final_rows, strict=True):
        key = decision_key(classifier_row)
        expected = reviewed_by_key.get(key, classifier_row)
        if decision_payload(final_row) != decision_payload(expected):
            raise ValueError(f"compiled final payload mismatch: {key}")

    expected_selection_rows = int(selection.get("selected_count", selection.get("selected_rows", -1)))
    layers = adjudication_manifest.get("layers", {})
    counts = adjudication_manifest.get("counts", {})
    manifest_hashes = adjudication_manifest.get("hashes", {})
    expected_contract_status_hashes = {
        question: sha256(SCREEN / "adjudication_validation" / f"{question}.json")
        for question in QUESTION_ORDER
    }
    manifest_batch_hashes = adjudication_manifest.get("batch_hashes", [])
    adjudication_batch_inputs = batch_inventory(SCREEN / "batches" / "adjudication")
    adjudication_agent_outputs = batch_inventory(SCREEN / "agent_outputs" / "adjudication")
    question_mtime_ranges: list[dict[str, object]] = []
    for question in QUESTION_ORDER:
        output_paths = sorted((SCREEN / "agent_outputs" / "adjudication" / question).glob("*.jsonl"))
        if not output_paths:
            raise ValueError(f"no adjudication outputs for {question}")
        mtimes = [path.stat().st_mtime_ns for path in output_paths]
        question_mtime_ranges.append(
            {
                "question_id": question,
                "first_output_mtime_utc": datetime.fromtimestamp(
                    min(mtimes) / 1_000_000_000, timezone.utc
                ).isoformat(),
                "last_output_mtime_utc": datetime.fromtimestamp(
                    max(mtimes) / 1_000_000_000, timezone.utc
                ).isoformat(),
                "batch_count": len(output_paths),
            }
        )
    mtime_order_supports_question_sequence = all(
        datetime.fromisoformat(str(previous["last_output_mtime_utc"]))
        <= datetime.fromisoformat(str(current["first_output_mtime_utc"]))
        for previous, current in zip(question_mtime_ranges, question_mtime_ranges[1:])
    )
    input_inventory = {row["path"]: row for row in adjudication_batch_inputs}
    output_inventory = {row["path"]: row for row in adjudication_agent_outputs}
    batch_artifacts_match = (
        isinstance(manifest_batch_hashes, list)
        and len(manifest_batch_hashes) == 25
        and len(adjudication_batch_inputs) == 25
        and len(adjudication_agent_outputs) == 25
        and sum(int(row["rows"]) for row in adjudication_batch_inputs) == 5_000
        and sum(int(row["rows"]) for row in adjudication_agent_outputs) == 5_000
    )
    raw_output_records: list[dict[str, Any]] = []
    if batch_artifacts_match:
        for batch in manifest_batch_hashes:
            input_row = input_inventory.get(batch.get("input_path"))
            output_row = output_inventory.get(batch.get("output_path"))
            if not (
                input_row
                and output_row
                and input_row["sha256"] == batch.get("input_sha256")
                and output_row["sha256"] == batch.get("output_sha256")
                and input_row["rows"] == batch.get("row_count")
                and output_row["rows"] == batch.get("row_count")
            ):
                batch_artifacts_match = False
                break
            output_path = ROOT / str(batch["output_path"])
            try:
                raw_output_records.extend(
                    json.loads(line)
                    for line in output_path.read_text(encoding="utf-8-sig").splitlines()
                    if line
                )
            except (json.JSONDecodeError, OSError, TypeError):
                batch_artifacts_match = False
                break
    batch_artifacts_match = batch_artifacts_match and raw_output_records == reviewed
    prompt_path = V5 / "prompts" / "frozen_semantic_adjudication_prompt.md"
    evidence_path = V5 / "evidence_map.csv"
    adjudication_contract_ok = all(
        (
            adjudication_manifest.get("run_complete") is True,
            expected_selection_rows == 5_000,
            len(reviewed) == expected_selection_rows,
            counts.get("classifier_rows") == len(classifier_rows),
            counts.get("selected_rows") == len(reviewed),
            counts.get("adjudicated_rows") == len(reviewed),
            counts.get("compiled_decision_rows") == len(final_rows),
            layers.get("classifier", {}).get("sha256") == sha256(classifier_path),
            layers.get("classifier", {}).get("row_count") == len(classifier_rows),
            layers.get("semantic_adjudication", {}).get("sha256") == sha256(semantic_path),
            layers.get("semantic_adjudication", {}).get("row_count") == len(reviewed),
            layers.get("compiled_decisions", {}).get("sha256") == sha256(final_path),
            layers.get("compiled_decisions", {}).get("row_count") == len(final_rows),
            manifest_hashes.get("prompt_sha256") == sha256(prompt_path),
            manifest_hashes.get("evidence_map_sha256") == sha256(evidence_path),
            manifest_hashes.get("classifier_decisions_sha256") == sha256(classifier_path),
            manifest_hashes.get("classifier_validation_sha256") == sha256(validation_path),
            manifest_hashes.get("adjudication_selection_sha256") == sha256(selection_path),
            manifest_hashes.get("semantic_adjudications_sha256") == sha256(semantic_path),
            manifest_hashes.get("decisions_csv_sha256") == sha256(final_path),
            manifest_hashes.get("contract_check_status_sha256")
            == expected_contract_status_hashes,
            batch_artifacts_match,
            selection_provenance_correction.get("valid") is True,
            selection_provenance_correction.get("correction_id") == "V50-PC-001",
            selection_provenance_correction.get("allowed_selection_changes")
            == ["independent_blinding_ai", "provenance_correction"],
            selection.get("classifier_fields_excluded_from_batch_inputs") is True,
            selection.get("selection_triggers_excluded_from_batch_inputs") is True,
            selection.get("independent_blinding_ai") is False,
            selection.get("independent_blinding") is False,
            selection.get("release_ready") is False,
            adjudication_manifest.get("adjudication_input_blinded_to_classifier_labels") is True,
            adjudication_manifest.get("agent_identity_recorded") is False,
            adjudication_manifest.get("specific_agent_attribution_supported") is False,
            adjudication_manifest.get("execution_receipts_recorded") is False,
            adjudication_manifest.get("question_sequence_receipt_recorded") is False,
            adjudication_manifest.get("independent_blinding_ai") is False,
            adjudication_manifest.get("independent_blinding") is False,
            adjudication_manifest.get("release_ready") is False,
        )
    )
    if not adjudication_contract_ok:
        raise ValueError("adjudication manifest, source hashes, or compiled layers are inconsistent")

    matrix, disagreement = movement_matrix(classifier, reviewed)
    classifier_distribution = label_distribution(classifier_rows)
    adjudication_distribution = label_distribution(reviewed)
    final_distribution = label_distribution(final_rows)
    classifier_batches: list[dict[str, object]] = []
    classifier_question_manifests: dict[str, object] = {}
    for question_id in QUESTION_ORDER:
        manifest_path = SCREEN / "batches" / question_id / "manifest.json"
        manifest = load_json(manifest_path)
        classifier_question_manifests[question_id] = {
            "artifact": file_record(manifest_path),
            "classifier_rule_specification_path": manifest["prompt_path"],
            "classifier_rule_specification_sha256": manifest["prompt_sha256"],
            "row_count": manifest["row_count"],
            "batch_count": len(manifest["batches"]),
        }
        for batch in manifest["batches"]:
            input_path = ROOT / batch["input_path"]
            output_path = ROOT / batch["output_path"]
            classifier_batches.append(
                {
                    "question_id": question_id,
                    "batch_id": batch["batch_id"],
                    "row_count": batch["row_count"],
                    "input_path": batch["input_path"],
                    "input_sha256": sha256(input_path),
                    "output_path": batch["output_path"],
                    "output_sha256": sha256(output_path),
                    "output_file_mtime_utc": datetime.fromtimestamp(
                        output_path.stat().st_mtime, timezone.utc
                    ).isoformat(),
                    "semantic_review_completed_at_utc": None,
                    "completion_time_unsupported": True,
                    "execution_layer": "deterministic_text_classifier",
                    "output_role": "classifier_output",
                    "attribution_unsupported": True,
                    "attribution_note": (
                        "6개 필드 출력과 배치 매니페스트에는 실행 주체를 확인할 수 있는 식별자가 없다."
                    ),
                }
            )
    if len(classifier_batches) != 182:
        raise ValueError(f"expected 182 classifier batches, found {len(classifier_batches)}")

    question_term_classification: dict[str, object] = {}
    hit_changes: list[dict[str, object]] = []
    for question in probe["questions"]:
        question_id = question["question_id"]
        question_term_classification[question_id] = question["term_classification"]
        hit_changes.append(
            {
                "question_id": question_id,
                "v4_hit_count": question["v4_hit_count"],
                "v5_hit_count": question["hit_count"],
                "absolute_change": question["hit_count"] - question["v4_hit_count"],
            }
        )

    v4_manifest_path = ROOT / "research_v3" / "otc" / "literature" / "screening" / "screening_manifest.json"
    v4_evidence_path = ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"
    v4_checkpoints_path = ROOT / "research_v3" / "otc" / "literature" / "screening" / "checkpoints.jsonl"
    v4_manifest = load_json(v4_manifest_path)
    v5_abstract_rows = sum(row["evidence_basis"] == "abstract" for row in classifier_rows)
    v5_title_only_rows = len(classifier_rows) - v5_abstract_rows
    v5_uncertain_abstract = sum(
        row["decision"] == "uncertain" and row["evidence_basis"] == "abstract"
        for row in classifier_rows
    )
    v5_uncertain_title_only = classifier_distribution["uncertain"] - v5_uncertain_abstract
    selected = probe["selected_ingredients_in_queries"]
    missing_ingredients = probe["missing_selected_ingredients"]
    absent_links = missing_v4_links(evidence_rows)
    absent_rule_ids = sorted({row["rule_id"] for row in absent_links})
    if len(absent_links) != 6:
        raise ValueError(f"expected six v4 links absent from v5, found {len(absent_links)}")

    validation_cases = validation.get("cases", [])
    validation_case_count = int(validation.get("case_count", len(validation_cases)))
    validation_pass_count = sum(case.get("passed") is True for case in validation_cases)
    validation_fail_count = sum(case.get("passed") is False for case in validation_cases)
    required_categories = set(validation.get("required_categories", []))
    covered_from_cases = {
        category for case in validation_cases for category in case.get("categories", [])
    }
    validation_keys = [decision_key(case) for case in validation_cases]
    validation_cases_current = True
    for case in validation_cases:
        source = classifier.get(decision_key(case))
        if source is None:
            validation_cases_current = False
            break
        observed_reasons = case.get("observed_reason_codes")
        source_reasons = [value for value in source["reason_codes"].split(";") if value]
        recomputed_passed = case.get("expected") == source["decision"]
        if not all(
            (
                isinstance(case.get("passed"), bool),
                case.get("passed") is recomputed_passed,
                case.get("observed_decision") == source["decision"],
                observed_reasons == source_reasons,
                case.get("observed_confidence") == source["confidence"],
                case.get("observed_evidence_basis") == source["evidence_basis"],
            )
        ):
            validation_cases_current = False
            break
    validation_sources = validation.get("source_hashes", {})
    validation_classifier_layer = validation.get("classifier_layer", {})
    validation_format = validation.get("format_contract", {})
    failed_validation_keys = {
        decision_key(case) for case in validation_cases if case.get("passed") is False
    }
    cross_integrity = cross_validation.get("cross_layer_integrity", {})
    cross_sources = cross_validation.get("source_hashes", {})
    cross_frozen_validation = cross_validation.get("frozen_classifier_validation", {})
    current_classifier_batch_input_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for question_id in QUESTION_ORDER
        for path in sorted((SCREEN / "batches" / question_id).glob("*.jsonl"))
    }
    current_classifier_batch_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in sorted((SCREEN / "agent_outputs").glob("*/*.jsonl"))
    }
    current_classifier_manifest_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for question_id in QUESTION_ORDER
        for path in [(SCREEN / "batches" / question_id / "manifest.json")]
    }
    validation_case_projection = [
        (
            decision_key(case),
            case.get("expected"),
            case.get("observed_decision"),
            case.get("passed"),
            case.get("categories"),
        )
        for case in validation_cases
    ]
    cross_case_projection = [
        (
            decision_key(case),
            case.get("expected"),
            case.get("observed_decision"),
            case.get("passed"),
            case.get("categories"),
        )
        for case in cross_validation.get("cases", [])
    ]
    cross_layer_validation_complete = all(
        (
            cross_validation.get("schema_version") == "1.1.0",
            cross_validation.get("case_count") == validation_case_count,
            cross_validation.get("pass_count") == validation_pass_count,
            cross_validation.get("fail_count") == validation_fail_count,
            cross_case_projection == validation_case_projection,
            cross_frozen_validation.get("path") == validation_path.relative_to(ROOT).as_posix(),
            cross_frozen_validation.get("exists") is True,
            cross_frozen_validation.get("sha256") == sha256(validation_path),
            cross_frozen_validation.get("modified_by_this_validator") is False,
            cross_frozen_validation.get("primary_contract_validated") is True,
            cross_integrity.get("expected_screening_units") == 43_207,
            cross_integrity.get("evidence_map_record_count") == len(evidence_rows) == 42_822,
            cross_integrity.get("evidence_map_membership_key_count") == 43_207,
            cross_integrity.get("classifier_checkpoint_row_count") == 43_207,
            cross_integrity.get("classifier_batch_count") == 182,
            cross_integrity.get("classifier_batch_output_row_count") == 43_207,
            cross_integrity.get("classifier_decisions_csv_row_count") == 43_207,
            cross_integrity.get("key_universe_exact_match") is True,
            cross_integrity.get("batch_input_evidence_fields_and_order_exact_match") is True,
            cross_integrity.get("six_normalized_decision_fields_exact_match") is True,
            cross_integrity.get("batch_input_files_sha256")
            == current_classifier_batch_input_hashes,
            cross_integrity.get("batch_output_files_sha256")
            == current_classifier_batch_hashes,
            cross_sources.get("evidence_map.csv") == sha256(evidence_path),
            cross_sources.get("classifier_decisions.csv") == sha256(classifier_path),
            cross_sources.get("classifier_checkpoints.jsonl")
            == sha256(SCREEN / "checkpoints.jsonl"),
            cross_sources.get("classifier_validation_v50.py")
            == sha256(V5 / "classifier_validation_v50.py"),
            cross_sources.get("light_screening_pipeline.py")
            == sha256(V5 / "light_screening_pipeline.py"),
            cross_sources.get("frozen_light_screening_prompt.md")
            == sha256(V5 / "prompts" / "frozen_light_screening_prompt.md"),
            cross_sources.get("classifier_batch_manifests")
            == current_classifier_manifest_hashes,
            cross_sources.get("v4_screening_manifest.json") == sha256(v4_manifest_path),
            cross_sources.get("v4_evidence_map.csv") == sha256(v4_evidence_path),
            cross_sources.get("v4_checkpoints.jsonl") == sha256(v4_checkpoints_path),
        )
    )
    validation_complete = all(
        (
            validation_case_count >= 20,
            len(validation_cases) == validation_case_count,
            len(validation_keys) == len(set(validation_keys)),
            validation_pass_count + validation_fail_count == validation_case_count,
            validation.get("pass_count") == validation_pass_count,
            validation.get("fail_count") == validation_fail_count,
            validation_cases_current,
            validation_format.get("passed") is True,
            validation_format.get("batch_count") == 182,
            validation_format.get("row_count") == 43_207,
            bool(required_categories),
            required_categories <= covered_from_cases,
            set(validation.get("covered_categories", [])) == covered_from_cases,
            validation_classifier_layer.get("path") == classifier_path.relative_to(ROOT).as_posix(),
            validation_classifier_layer.get("sha256") == sha256(classifier_path),
            validation_classifier_layer.get("rows") == 43_207,
            validation_sources.get("classifier_decisions.csv") == sha256(classifier_path),
            validation_sources.get("evidence_map.csv") == sha256(evidence_path),
            validation_sources.get("light_screening_pipeline.py")
            == sha256(V5 / "light_screening_pipeline.py"),
            failed_validation_keys <= set(selection_keys),
            validation.get("human_reference_rows") == 0,
            validation.get("independent_blinding") is False,
            validation.get("release_ready") is False,
            cross_layer_validation_complete,
        )
    )
    adjudication_complete = adjudication_contract_ok
    phase_c_complete = validation_complete and adjudication_complete

    downstream_csv_rows = read_csv(downstream_csv_path)
    rules_path = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
    rule_rows = read_csv(rules_path)
    all_rule_ids = {row["rule_id"] for row in rule_rows}
    linked_rule_ids = {row["rule_id"] for row in downstream_csv_rows}
    unresolved_rule_ids = sorted(all_rule_ids - linked_rule_ids)
    downstream_inputs = downstream.get("inputs", {})
    downstream_outputs = downstream.get("outputs", {})
    downstream_results = downstream.get("results", {})
    locator_inputs = locator_verification.get("inputs", {})
    locator_checks = locator_verification.get("checks", {})
    phase_d_complete = all(
        (
            downstream_inputs.get("screening_decisions", {}).get("path")
            == final_path.relative_to(ROOT).as_posix(),
            downstream_inputs.get("screening_decisions", {}).get("sha256") == sha256(final_path),
            downstream_inputs.get("adjudication_manifest", {}).get("sha256")
            == sha256(adjudication_manifest_path),
            downstream_inputs.get("adjudication_manifest", {}).get("run_complete") is True,
            downstream_inputs.get("evidence_map", {}).get("sha256")
            == sha256(V5 / "evidence_map.csv"),
            downstream_inputs.get("v4_candidate_links", {}).get("candidate_count") == 20,
            downstream_inputs.get("v4_candidate_links", {}).get("sha256")
            == sha256(ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"),
            downstream_inputs.get("rules", {}).get("path")
            == rules_path.relative_to(ROOT).as_posix(),
            downstream_inputs.get("rules", {}).get("sha256") == sha256(rules_path),
            downstream_inputs.get("rules", {}).get("rule_count") == len(all_rule_ids) == 16,
            downstream_inputs.get("query_definitions", {}).get("path")
            == queries_path.relative_to(ROOT).as_posix(),
            downstream_inputs.get("query_definitions", {}).get("sha256")
            == sha256(queries_path),
            downstream_inputs.get("query_definitions", {}).get("mapping_field")
            == "questions[].rule_types",
            downstream_inputs.get("query_definitions", {}).get("question_count") == 5,
            downstream_outputs.get("supporting_literature", {}).get("sha256")
            == sha256(downstream_csv_path),
            downstream_outputs.get("supporting_literature", {}).get("row_count")
            == len(downstream_csv_rows),
            downstream_results.get("emitted_link_count") == len(downstream_csv_rows),
            downstream_results.get("emitted_link_count", 0) > 0,
            downstream_results.get("emitted_link_count", 0)
            + downstream_results.get("rejected_candidate_count", 0)
            == 20,
            downstream_results.get("rule_count") == len(all_rule_ids),
            downstream_results.get("resolved_rule_count") == len(linked_rule_ids),
            downstream_results.get("unresolved_rule_count") == len(unresolved_rule_ids),
            downstream_results.get("unresolved_rule_ids") == unresolved_rule_ids,
            locator_verification.get("status") == "pass",
            locator_inputs.get("supporting_literature", {}).get("sha256")
            == sha256(downstream_csv_path),
            locator_inputs.get("downstream_manifest", {}).get("sha256")
            == sha256(downstream_manifest_path),
            locator_inputs.get("final_decisions", {}).get("sha256")
            == sha256(final_path),
            locator_inputs.get("adjudication_manifest", {}).get("sha256")
            == sha256(adjudication_manifest_path),
            locator_inputs.get("query_definitions", {}).get("sha256")
            == sha256(queries_path),
            locator_checks.get("locator_quote_exact_match_for_every_link") is True,
            locator_checks.get("site_output_unchanged") is True,
            locator_checks.get("site_output_hash_captured_before_original_builder_import")
            is True,
            locator_checks.get("nonzero_link_set") is True,
            locator_checks.get("rules_and_query_source_hashes_match_downstream_manifest")
            is True,
        )
    )
    if not phase_d_complete:
        raise ValueError("downstream artifacts do not prove final-label and locator dependencies")

    phase_a_complete = phase_a_integrity.get("current_artifact_integrity_verified") is True
    phase_b_complete = phase_b_integrity.get("current_artifact_integrity_verified") is True
    amendment_rows = read_csv(amendments_path)
    amendment_matches = [row for row in amendment_rows if row.get("amendment_id") == "AM-OTC-002"]
    protocol_path = ROOT / "research_v3" / "protocol" / "protocol-v5.0-mecir-search.md"
    protocol_text = protocol_path.read_text(encoding="utf-8-sig")
    amendment_complete = (
        len(amendment_matches) == 1
        and amendment_matches[0].get("protocol_version_before") == "v4.0-full-ai"
        and amendment_matches[0].get("protocol_version_after") == "v5.0-mecir-search"
        and amendment_matches[0].get("section") == "literature_search"
        and amendment_matches[0].get("status") == "adopted"
        and bool(amendment_matches[0].get("approved_by"))
        and bool(amendment_matches[0].get("date"))
        and "상태: 채택" in protocol_text
    )
    protected_items = protected.get("protected_paths", [])
    protected_combined = protected.get("combined_protected", {})
    protected_limitations = protected.get("limitations", [])
    ignored_limitations = [
        item
        for item in protected_limitations
        if isinstance(item, dict)
        and item.get("code") == "IGNORED_FILES_NOT_CAPTURED_IN_FROZEN_BASELINE"
    ] if isinstance(protected_limitations, list) else []
    protected_snapshot = protected.get("final_artifact_snapshot", {})
    protected_snapshot_records = protected_snapshot.get("artifacts", [])
    protected_recheck_ok, protected_recheck = protected_audit_recheck(protected)
    protected_snapshot_hashes_current = all(
        (
            isinstance(protected_snapshot_records, list),
            all(isinstance(record, dict) for record in protected_snapshot_records),
            all(
                (ROOT / str(record.get("path", ""))).is_file()
                and sha256(ROOT / str(record.get("path", ""))) == record.get("sha256")
                for record in protected_snapshot_records
                if isinstance(record, dict)
            ),
        )
    )
    ignored_limitation_valid = all(
        (
            len(ignored_limitations) == 1,
            ignored_limitations[0].get("file_count")
            == protected_combined.get("ignored_file_count")
            if ignored_limitations
            else False,
            int(ignored_limitations[0].get("file_count", 0)) > 0
            if ignored_limitations
            else False,
            bool(ignored_limitations[0].get("effect"))
            if ignored_limitations
            else False,
        )
    )
    protected_captured = datetime.fromisoformat(str(protected.get("captured_at_utc")))
    protected_audit_is_current = protected_captured.timestamp() >= max(
        path.stat().st_mtime
        for path in (
            final_path,
            semantic_path,
            adjudication_manifest_path,
            downstream_manifest_path,
            downstream_csv_path,
            locator_verification_path,
            decision_history_path,
            final_summary_path,
            amendments_path,
        )
    )
    protected_complete = all(
        (
            protected.get("status") == "pass_with_unverified_ignored_files",
            protected.get("status_scope") == "434_baseline_tracked_files",
            protected.get("ignored_file_baseline_limitation_present") is True,
            ignored_limitation_valid,
            protected.get("problems") == [],
            protected_combined.get("status") == "pass",
            protected_combined.get("tracked_files") == 434,
            protected_combined.get("bytes") == 404_869_977,
            protected_combined.get("ignored_baseline_comparison_supported") is False,
            isinstance(protected_items, list) and len(protected_items) == 4,
            all(item.get("status") == "pass" for item in protected_items),
            protected_snapshot.get("audit_after_required_artifacts") is True,
            protected_snapshot.get("missing") == [],
            protected_snapshot.get("required_count")
            == protected_snapshot.get("captured_count"),
            protected_snapshot_hashes_current,
            protected_audit_is_current,
            protected_recheck_ok,
        )
    )
    overall_complete = all(
        (
            phase_a_complete,
            phase_b_complete,
            phase_c_complete,
            phase_d_complete,
            protected_complete,
            amendment_complete,
        )
    )

    report = {
        "schema_version": "5.0.1",
        "report_type": "v5.0_mecir_search_single_reconstruction_ledger",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": file_record(protocol_path),
        "query_definitions": {
            "full_record": queries,
            "source": file_record(queries_path),
        },
        "phases": {
            "A": {
                "status": probe["status"],
                "method": "current_artifact_integrity_check_without_search_rerun",
                "integrity_checks": phase_a_integrity,
                "immutability_scope_note": (
                    "방어 작업 시작 시점의 Phase A 해시 기준선은 보존되지 않았다. 현재 질의·probe의 "
                    "해시와 내부 계약은 확인했지만 시작 시점 이후 불변성을 암호학적으로 증명하지는 못한다."
                ),
                "full_record": probe,
                "source": file_record(probe_path),
            },
            "B": {
                "status": corpus["status"],
                "method": "current_artifact_integrity_check_without_retrieval_rerun",
                "integrity_checks": phase_b_integrity,
                "immutability_scope_note": (
                    "방어 작업 시작 시점의 Phase B 해시 기준선은 보존되지 않았다. 현재 XML 105개, "
                    "체크섬, evidence map과 corpus 계약은 확인했지만 시작 시점 이후 불변성을 "
                    "암호학적으로 증명하지는 못한다."
                ),
                "full_record": corpus,
                "source": file_record(corpus_path),
            },
            "C": {
                "status": "complete" if phase_c_complete else "partial",
                "method": "deterministic_classifier_layer_plus_contract_checked_semantic_adjudication_layer",
                "question_order": QUESTION_ORDER,
                "classifier_layer": {
                    "method": "deterministic_text_classifier_full_corpus_projection",
                    "rows": len(classifier_rows),
                    "coverage": len(classifier_rows) / 43_207,
                    "decision_distribution": classifier_distribution,
                    "questions": per_question(classifier_rows),
                    "artifact": file_record(classifier_path, immutable=True),
                    "records": classifier_rows,
                    "pipeline": file_record(V5 / "light_screening_pipeline.py"),
                    "legacy_batch_count": len(classifier_batches),
                    "question_manifests": classifier_question_manifests,
                    "batch_records": classifier_batches,
                    "legacy_output_schema_has_agent_identity": False,
                    "attribution_unsupported": True,
                    "unsupported_legacy_attribution_entries": len(classifier_batches),
                    "attribution_note": (
                        "기존 6개 필드 출력과 배치 매니페스트에는 실행 주체 식별자가 없다. "
                        "따라서 기존 담당자 귀속 값은 실행 증거로 유지하지 않는다."
                    ),
                },
                "classifier_validation": {
                    "status": "complete_with_recorded_failures" if validation_complete else "partial",
                    "case_count": validation_case_count,
                    "pass_count": validation_pass_count,
                    "fail_count": validation_fail_count,
                    "full_record": validation,
                    "artifact": file_record(validation_path),
                    "supplemental_cross_layer_verification": {
                        "status": "complete" if cross_layer_validation_complete else "partial",
                        "full_record": cross_validation,
                        "artifact": file_record(cross_validation_path),
                        "frozen_selection_validation_unchanged": True,
                        "purpose": (
                            "동결된 사례 검증 파일을 다시 쓰지 않고 현재 evidence map, 182개 분류기 "
                            "출력, 체크포인트와 43,207행 CSV의 키·6개 판정 필드 일치를 재검증한다."
                        ),
                    },
                },
                "semantic_adjudication_layer": {
                    "status": "complete" if adjudication_complete else "partial",
                    "selected_rows": int(selection.get("selected_count", len(reviewed))),
                    "reviewed_rows": len(reviewed),
                    "selection_provenance_correction": {
                        "validated": selection_provenance_correction["valid"],
                        "correction_id": selection_provenance_correction["correction_id"],
                        "field": "independent_blinding_ai",
                        "old_value": True,
                        "new_value": False,
                        "old_selection_sha256": selection_provenance_correction[
                            "old_selection_sha256"
                        ],
                        "selected_records_sha256": selection_provenance_correction[
                            "selected_records_sha256"
                        ],
                        "execution_contract_sha256": selection_provenance_correction[
                            "execution_contract_sha256"
                        ],
                        "selected_records_changed": selection_provenance_correction[
                            "selected_records_changed"
                        ],
                        "execution_contract_changed": selection_provenance_correction[
                            "execution_contract_changed"
                        ],
                        "batch_inputs_changed": selection_provenance_correction[
                            "batch_inputs_changed"
                        ],
                        "batch_outputs_changed": selection_provenance_correction[
                            "batch_outputs_changed"
                        ],
                        "input_file_count": selection_provenance_correction[
                            "input_file_count"
                        ],
                        "output_file_count": selection_provenance_correction[
                            "output_file_count"
                        ],
                        "input_inventory_sha256": selection_provenance_correction[
                            "input_inventory_sha256"
                        ],
                        "output_inventory_sha256": selection_provenance_correction[
                            "output_inventory_sha256"
                        ],
                        "allowed_selection_changes": selection_provenance_correction[
                            "allowed_selection_changes"
                        ],
                        "execution_receipts_created_by_correction": False,
                    },
                    "selection": {"full_record": selection, "artifact": file_record(selection_path)},
                    "prompt": file_record(V5 / "prompts" / "frozen_semantic_adjudication_prompt.md"),
                    "batch_inputs": adjudication_batch_inputs,
                    "agent_outputs": adjudication_agent_outputs,
                    "full_record": adjudication_manifest,
                    "manifest": file_record(adjudication_manifest_path),
                    "decisions": file_record(semantic_path, rows=len(reviewed)),
                    "records": reviewed,
                    "decision_distribution": adjudication_distribution,
                    "classifier_to_adjudication_movement": matrix,
                    "disagreement_count": disagreement,
                    "disagreement_rate": disagreement / len(reviewed) if reviewed else None,
                    "adjudication_input_blinded_to_classifier_labels": True,
                    "agent_identity_recorded": False,
                    "specific_agent_attribution_supported": False,
                    "execution_receipts_recorded": False,
                    "question_sequence_receipt_recorded": False,
                    "filesystem_mtime_sequence_evidence": {
                        "question_ranges": question_mtime_ranges,
                        "mtime_order_supports_q01_to_q05": mtime_order_supports_question_sequence,
                        "cryptographically_bound_to_execution": False,
                        "interpretation": (
                            "현재 출력 파일 수정 시각은 Q01→Q05 순서와 일치한다. 그러나 실행자, 모델, "
                            "시작·종료 시각, 질문 내 병렬 처리를 묶은 해시 영수증이 없어 실제 실행 귀속과 "
                            "병렬 처리 방식은 산출물만으로 독립 증명할 수 없다."
                        ),
                    },
                    "independent_blinding_ai": False,
                    "independent_blinding": False,
                },
                "final_layer": {
                    "rows": len(final_rows),
                    "decision_distribution": final_distribution,
                    "questions": per_question(final_rows),
                    "artifact": file_record(final_path),
                    "records": final_rows,
                    "override_rule": "semantic_adjudication_overrides_classifier_for_reviewed_keys",
                },
                "layered_label_distribution": {
                    "overall_final_43207": final_distribution,
                    "classifier_layer_43207": classifier_distribution,
                    "adjudication_layer_reviewed_subset": adjudication_distribution,
                },
            },
            "D": {
                "status": "complete" if phase_d_complete else "partial",
                "method": "v4_candidates_rebuilt_from_final_v5_retain_labels_with_exact_sentence_validation",
                "dependency_checks": {
                    "final_decisions_sha256_matches": True,
                    "supporting_literature_sha256_matches": True,
                    "emitted_link_count_matches": True,
                    "original_builder_read_only_check_passed": True,
                },
                "full_record": downstream,
                "manifest": file_record(downstream_manifest_path),
                "supporting_literature": {
                    "artifact": file_record(downstream_csv_path),
                    "records": downstream_csv_rows,
                },
                "original_builder_read_only_check": {
                    "full_record": locator_verification,
                    "artifact": file_record(locator_verification_path),
                },
            },
        },
        "v4_to_v5_hit_count_change": hit_changes,
        "reconstruction_rule": (
            "phases.C.classifier_layer.records에서 시작해 record_id와 question_id가 같은 행을 "
            "phases.C.semantic_adjudication_layer.records로 교체한다. 교체할 때 재판정 행의 "
            "reason_codes 배열은 원래 순서를 유지해 세미콜론(;)으로 연결한 문자열로 바꾼다. "
            "그 결과는 분류기 순서를 유지한 phases.C.final_layer.records와 같아야 한다."
        ),
        "reconstruction_normalization": {
            "semantic_reason_codes": "join_array_with_semicolon_preserving_order",
            "classifier_reason_codes_type": "semicolon_delimited_string",
            "final_reason_codes_type": "semicolon_delimited_string",
        },
        "question_term_classification": question_term_classification,
        "ingredient_coverage": {
            "frozen_scope_count": 28,
            "included_count": len(selected),
            "included_ingredient_ids": selected,
            "missing_count": len(missing_ingredients),
            "missing_ingredient_ids": missing_ingredients,
            "ingredient_master_reconciliation": probe["ingredient_master_reconciliation"],
        },
        "uncertain_distribution_comparison": {
            "v4_0_otc": {
                "rows": int(v4_manifest["classified_rows"]),
                "uncertain": int(v4_manifest["decision_distribution"]["uncertain"]),
                "rate": int(v4_manifest["decision_distribution"]["uncertain"]) / int(v4_manifest["classified_rows"]),
                "source": file_record(v4_manifest_path),
            },
            "v5_0_classifier_layer": {
                "rows": len(classifier_rows),
                "uncertain": classifier_distribution["uncertain"],
                "rate": classifier_distribution["uncertain"] / len(classifier_rows),
                "abstract_rows": v5_abstract_rows,
                "abstract_uncertain": v5_uncertain_abstract,
                "title_only_rows": v5_title_only_rows,
                "title_only_uncertain": v5_uncertain_title_only,
            },
            "explanation": {
                "status": "recorded_hypotheses_not_causal_findings",
                "derived_facts": {
                    "v5_rows_minus_v4_rows": len(classifier_rows) - int(v4_manifest["classified_rows"]),
                    "v5_uncertain_minus_v4_uncertain": classifier_distribution["uncertain"]
                    - int(v4_manifest["decision_distribution"]["uncertain"]),
                    "v5_uncertain_with_abstract": v5_uncertain_abstract,
                    "v5_uncertain_title_only": v5_uncertain_title_only,
                },
                "source_record": validation.get(
                    "uncertain_comparison", validation.get("uncertain_rate_explanation")
                ),
                "interpretation_limit": (
                    "코퍼스 중첩·사람 참조표준·정밀도 측정이 없으므로 검색 확대나 분류 규칙이 "
                    "uncertain 증가를 일으켰다고 확정하지 않는다."
                ),
            },
        },
        "amendment": {
            "id": "AM-OTC-002",
            "transition": "v4.0-full-ai -> v5.0-mecir-search",
            "section": "literature_search",
            "full_record": amendment_matches[0],
            "contract_check_passed": amendment_complete,
            "source": file_record(amendments_path),
        },
        "decision_history": file_record(decision_history_path),
        "final_summary": file_record(final_summary_path),
        "protected_path_verification": protected,
        "protected_path_current_recheck": protected_recheck,
        "limitations_and_unresolved_items": [
            {
                "id": "ADJUDICATION_EXECUTION_RECEIPTS_UNAVAILABLE",
                "status": "limitation",
                "detail": (
                    "재판정 입력·출력·프롬프트·검사 해시는 보존됐다. 실행자/task ID, provider/model, "
                    "시작·종료 시각, 선행 질문 영수증은 보존되지 않아 특정 에이전트 귀속, 실제 질문 간 "
                    "순서, 질문 내 병렬 처리를 산출물만으로 독립 증명할 수 없다."
                ),
            },
            {
                "id": "PHASE_AB_DEFENSE_START_BASELINE_UNAVAILABLE",
                "status": "limitation",
                "detail": (
                    "Phase A/B는 재실행하지 않았고 현재 질의·probe·XML 105개·체크섬·evidence map의 "
                    "내부 무결성을 확인했다. 다만 방어 시작 시점 해시 기준선이 없어 그 시점 이후 "
                    "불변성을 암호학적으로 증명할 수 없다."
                ),
            },
            {
                "id": "PROTECTED_IGNORED_FILES_BASELINE_UNAVAILABLE",
                "status": "limitation",
                "detail": (
                    "보호 경로의 기준선 추적 파일 434개는 Git blob과 현재 바이트를 파일별로 대조했다. "
                    "현재 ignored 파일은 경로·크기·SHA-256을 기록했지만 동결 기준선에 ignored 파일 "
                    "목록과 해시가 없어 과거 내용 동일성은 증명하지 못한다."
                ),
            },
            {
                "id": "Q05_HIT_COUNT_DECREASE",
                "status": "unresolved_record_only",
                "detail": (
                    "Q05 검색 결과는 v4.0 713건에서 v5.0 517건으로 줄었다. P 블록이 "
                    "과도하게 좁을 수 있지만 이번 실행에서는 검색식을 바꾸지 않았다."
                ),
            },
            {
                "id": "V4_LINKS_ABSENT_FROM_V5",
                "status": "unresolved_record_only",
                "detail": (
                    "v4.0 규칙–문헌 연결 20개 중 6개가 v5 코퍼스에 없다. 프로토콜에 기록된 "
                    "설명은 v4.0 검색식의 결과 용어 의존이다. 누락 연결별 직접 인과는 이번 "
                    "실행에서 다시 검증하지 않았다."
                ),
                "affected_rule_ids": absent_rule_ids,
                "links": absent_links,
            },
            {
                "id": "NO_HUMAN_REFERENCE_STANDARD",
                "status": "unresolved_record_only",
                "human_reference_rows": 0,
                "detail": "사람 참조표준이 0건이므로 선별 성능은 측정되지 않았다.",
            },
            {
                "id": "CLASSIFIER_VALIDATION_LIMIT",
                "status": "limitation",
                "detail": (
                    "불변식 사례는 AI가 작성한 회귀 점검이며 사람 참조표준이 아니다. "
                    "실패 사례는 그대로 기록하며 분류기 원본을 다시 쓰지 않는다."
                ),
            },
        ],
        "state_flags": {
            "independent_blinding": False,
            "classifier_validation_independent_blinding_ai": False,
            "semantic_adjudication_independent_blinding_ai": False,
            "semantic_adjudication_input_blinded_to_classifier_labels": True,
            "semantic_adjudication_agent_identity_recorded": False,
            "semantic_adjudication_specific_agent_attribution_supported": False,
            "semantic_adjudication_execution_receipts_recorded": False,
            "release_ready": False,
            "human_reference_rows": 0,
            "human_reference_label_used": False,
            "human_screening_outputs_used": False,
            "official_v5_chain_local_language_model_used": False,
            "discarded_pilot_history": file_record(SCREEN / "pilot_discard_history.jsonl"),
            "deployment_run": False,
            "git_push_run": False,
        },
        "excluded_analyses": {
            "meta_analysis": False,
            "pooled_effect_size": False,
            "risk_of_bias": False,
            "GRADE": False,
            "clinical_recommendations": False,
        },
        "overall_execution_status": (
            "complete_with_recorded_evidence_limitations_and_unresolved_items"
            if overall_complete
            else "partial"
        ),
    }
    atomic_json(OUT, report)
    print(
        json.dumps(
            {
                "path": OUT.relative_to(ROOT).as_posix(),
                "sha256": sha256(OUT),
                "phase_c_status": report["phases"]["C"]["status"],
                "adjudicated_rows": len(reviewed),
                "disagreement_count": disagreement,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
