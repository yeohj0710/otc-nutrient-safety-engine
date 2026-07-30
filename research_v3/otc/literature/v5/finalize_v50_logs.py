"""Write the final Korean v5.0 decision history and one-page summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from adjudication_pipeline_v50 import (
    status as adjudication_pipeline_status,
    validate_selection_provenance_correction,
)
from build_light_run_report_v50 import (
    read_csv,
    verify_phase_a,
    verify_phase_b,
)
from update_progress_v50 import protected_audit_recheck


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREEN = V5 / "screening"
LOGS = ROOT / "research_v3" / "logs"
DECISIONS_MD = LOGS / "DECISIONS_v50.md"
FINAL_MD = LOGS / "v50_FINAL.md"
LABELS = ("retain", "deprioritize", "uncertain")
QUESTION_ORDER = [
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
]
V4_SCREENING_MANIFEST = (
    ROOT / "research_v3" / "otc" / "literature" / "screening" / "screening_manifest.json"
)
V4_EVIDENCE_MAP = ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"
V4_CHECKPOINTS = (
    ROOT / "research_v3" / "otc" / "literature" / "screening" / "checkpoints.jsonl"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_records(
    recorded: list[dict[str, object]], *, label: str
) -> list[dict[str, object]]:
    """Rehash a recorded file set and reject stale paths, sizes, or hashes."""

    current: list[dict[str, object]] = []
    root = ROOT.resolve()
    for item in recorded:
        relative = str(item.get("path", ""))
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"{label} path escapes repository: {relative}") from exc
        if not path.is_file():
            raise RuntimeError(f"{label} file is missing: {relative}")
        actual = {
            "path": relative.replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        if any(actual[field] != item.get(field) for field in actual):
            raise RuntimeError(f"{label} audit record is stale: {relative}")
        current.append(actual)
    return current


def verify_recorded_hashes_current(recorded: object, *, label: str) -> dict[str, str]:
    """Rehash every path in a recorded path-to-SHA-256 mapping."""

    if not isinstance(recorded, dict):
        raise RuntimeError(f"{label} hash mapping is missing")
    root = ROOT.resolve()
    current: dict[str, str] = {}
    for key, expected in recorded.items():
        relative = str(key).replace("\\", "/")
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"{label} path escapes repository: {relative}") from exc
        if not path.is_file():
            raise RuntimeError(f"{label} file is missing: {relative}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"{label} hash is stale: {relative}")
        current[relative] = actual
    return current


def verify_primary_classifier_validation(
    validation: dict,
    supplemental: dict,
    classifier_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
) -> bool:
    """Recompute the frozen primary validation against current source artifacts."""

    decision_fields = {
        "record_id",
        "question_id",
        "decision",
        "reason_codes",
        "confidence",
        "evidence_basis",
    }
    if len(classifier_rows) != 43_207 or any(
        set(row) != decision_fields for row in classifier_rows
    ):
        raise RuntimeError("current classifier does not contain the exact 43,207-row schema")
    classifier = {
        (row["record_id"], row["question_id"]): row for row in classifier_rows
    }
    if len(classifier) != len(classifier_rows):
        raise RuntimeError("current classifier contains duplicate screening keys")
    evidence = {row["record_id"]: row for row in evidence_rows}
    if len(evidence) != len(evidence_rows):
        raise RuntimeError("current evidence map contains duplicate record_id values")

    cases = validation.get("cases")
    if not isinstance(cases, list) or len(cases) < 20:
        raise RuntimeError("primary classifier validation must contain at least 20 cases")
    case_ids: set[str] = set()
    case_keys: set[tuple[str, str]] = set()
    covered_categories: set[str] = set()
    recomputed_pass_count = 0
    projection_fields = (
        "case_id",
        "record_id",
        "question_id",
        "expected",
        "categories",
        "observed_decision",
        "observed_reason_codes",
        "observed_confidence",
        "observed_evidence_basis",
        "passed",
    )
    primary_projection: list[tuple[object, ...]] = []
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            raise RuntimeError(f"primary validation case {index} is not an object")
        case_id = case.get("case_id")
        key = (str(case.get("record_id", "")), str(case.get("question_id", "")))
        categories = case.get("categories")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise RuntimeError(f"primary validation case {index} has a duplicate case_id")
        if not all(key) or key[1] not in QUESTION_ORDER or key in case_keys:
            raise RuntimeError(f"primary validation case {case_id} has an invalid or duplicate key")
        if (
            not isinstance(categories, list)
            or not categories
            or len(categories) != len(set(categories))
            or not all(isinstance(value, str) and value for value in categories)
        ):
            raise RuntimeError(f"primary validation case {case_id} has invalid categories")
        if type(case.get("passed")) is not bool:
            raise RuntimeError(f"primary validation case {case_id}.passed is not boolean")
        current = classifier.get(key)
        if current is None:
            raise RuntimeError(f"primary validation case is absent from classifier: {key}")
        observed_reason_codes = case.get("observed_reason_codes")
        current_reason_codes = [
            value for value in current["reason_codes"].split(";") if value
        ]
        recomputed_passed = case.get("expected") == current["decision"]
        if not all(
            (
                case.get("expected") in LABELS,
                case.get("observed_decision") == current["decision"],
                isinstance(observed_reason_codes, list),
                observed_reason_codes == current_reason_codes,
                case.get("observed_confidence") == current["confidence"],
                case.get("observed_evidence_basis") == current["evidence_basis"],
                case.get("passed") is recomputed_passed,
            )
        ):
            raise RuntimeError(
                f"primary validation case differs from current classifier: {case_id}"
            )
        evidence_row = evidence.get(key[0])
        if evidence_row is None:
            raise RuntimeError(f"primary validation evidence is missing: {case_id}")
        if not all(
            (
                case.get("title") == evidence_row.get("title"),
                case.get("has_abstract")
                is bool(str(evidence_row.get("abstract", "")).strip()),
            )
        ):
            raise RuntimeError(
                f"primary validation evidence projection is stale: {case_id}"
            )
        case_ids.add(case_id)
        case_keys.add(key)
        covered_categories.update(categories)
        recomputed_pass_count += int(recomputed_passed)
        primary_projection.append(
            tuple(
                tuple(case[field]) if field in {"categories", "observed_reason_codes"}
                else case.get(field)
                for field in projection_fields
            )
        )

    supplemental_cases = supplemental.get("cases")
    if not isinstance(supplemental_cases, list):
        raise RuntimeError("supplemental validation cases are missing")
    supplemental_projection: list[tuple[object, ...]] = []
    for case in supplemental_cases:
        if not isinstance(case, dict):
            raise RuntimeError("supplemental validation case is not an object")
        supplemental_projection.append(
            tuple(
                tuple(case[field]) if field in {"categories", "observed_reason_codes"}
                and isinstance(case.get(field), list)
                else case.get(field)
                for field in projection_fields
            )
        )
    if supplemental_projection != primary_projection:
        raise RuntimeError("supplemental case projection differs from primary validation")

    required_categories = validation.get("required_categories")
    recorded_covered_categories = validation.get("covered_categories")
    pass_count = recomputed_pass_count
    fail_count = len(cases) - pass_count
    validation_format = validation.get("format_contract", {})
    validation_layer = validation.get("classifier_layer", {})
    validation_sources = validation.get("source_hashes", {})
    classifier_distribution = dict(
        sorted(Counter(row["decision"] for row in classifier_rows).items())
    )
    primary_contract_current = all(
        (
            validation.get("schema_version") == "1.0.0",
            validation.get("case_count") == len(cases),
            validation.get("pass_count") == pass_count,
            validation.get("fail_count") == fail_count,
            validation.get("agreement_vs_ai_reference") == pass_count / len(cases),
            isinstance(required_categories, list),
            bool(required_categories),
            all(isinstance(value, str) and value for value in required_categories),
            required_categories == sorted(set(required_categories)),
            set(required_categories) <= covered_categories,
            isinstance(recorded_covered_categories, list),
            recorded_covered_categories == sorted(covered_categories),
            isinstance(validation_format, dict),
            validation_format.get("passed") is True,
            validation_format.get("batch_count") == 182,
            validation_format.get("expected_batch_count") == 182,
            validation_format.get("row_count") == 43_207,
            validation_format.get("expected_row_count") == 43_207,
            isinstance(validation_layer, dict),
            validation_layer.get("path")
            == (SCREEN / "classifier_decisions.csv").relative_to(ROOT).as_posix(),
            validation_layer.get("sha256")
            == sha256(SCREEN / "classifier_decisions.csv"),
            validation_layer.get("rows") == 43_207,
            validation_layer.get("decision_distribution") == classifier_distribution,
            isinstance(validation_sources, dict),
            validation_sources.get("evidence_map.csv")
            == sha256(V5 / "evidence_map.csv"),
            validation_sources.get("classifier_decisions.csv")
            == sha256(SCREEN / "classifier_decisions.csv"),
            validation_sources.get("light_screening_pipeline.py")
            == sha256(V5 / "light_screening_pipeline.py"),
            validation_sources.get("v4_screening_manifest.json")
            == sha256(V4_SCREENING_MANIFEST),
            validation_sources.get("v4_evidence_map.csv") == sha256(V4_EVIDENCE_MAP),
            validation_sources.get("v4_checkpoints.jsonl") == sha256(V4_CHECKPOINTS),
            validation.get("human_reference_rows") == 0,
            validation.get("independent_blinding") is False,
            validation.get("independent_blinding_ai") is False,
            validation.get("release_ready") is False,
        )
    )
    if not primary_contract_current:
        raise RuntimeError("primary classifier validation contract is stale")

    v4_manifest = load(V4_SCREENING_MANIFEST)
    v4_rows = int(v4_manifest["classified_rows"])
    v4_uncertain = int(v4_manifest["decision_distribution"]["uncertain"])
    v4_abstract_rows = int(v4_manifest["evidence_basis_distribution"]["title_abstract"])
    v4_title_only_rows = int(v4_manifest["evidence_basis_distribution"]["title_only"])
    v4_abstract_uncertain = int(
        v4_manifest["decision_by_evidence_basis"]["title_abstract|uncertain"]
    )
    v4_title_only_uncertain = int(
        v4_manifest["decision_by_evidence_basis"]["title_only|uncertain"]
    )
    rate = lambda part, whole: part / whole if whole else 0.0
    v5_rows = len(classifier_rows)
    v5_uncertain = sum(row["decision"] == "uncertain" for row in classifier_rows)
    v5_abstract_rows = sum(row["evidence_basis"] == "abstract" for row in classifier_rows)
    v5_title_only_rows = sum(
        row["evidence_basis"] == "title_only" for row in classifier_rows
    )
    if v5_abstract_rows + v5_title_only_rows != v5_rows:
        raise RuntimeError("current classifier contains an unexpected evidence_basis")
    v5_abstract_uncertain = sum(
        row["decision"] == "uncertain" and row["evidence_basis"] == "abstract"
        for row in classifier_rows
    )
    v5_title_only_uncertain = sum(
        row["decision"] == "uncertain" and row["evidence_basis"] == "title_only"
        for row in classifier_rows
    )
    uncertain_abstract_lengths = sorted(
        len(evidence[row["record_id"]]["abstract"].strip())
        for row in classifier_rows
        if row["decision"] == "uncertain" and row["evidence_basis"] == "abstract"
    )
    expected_v4 = {
        "classifier_output_rows": v4_rows,
        "uncertain": v4_uncertain,
        "uncertain_rate": rate(v4_uncertain, v4_rows),
        "abstract_rows": v4_abstract_rows,
        "abstract_uncertain": v4_abstract_uncertain,
        "abstract_uncertain_rate": rate(v4_abstract_uncertain, v4_abstract_rows),
        "title_only_rows": v4_title_only_rows,
        "title_only_uncertain": v4_title_only_uncertain,
        "title_only_uncertain_rate": rate(v4_title_only_uncertain, v4_title_only_rows),
    }
    expected_v5 = {
        "classifier_output_rows": v5_rows,
        "uncertain": v5_uncertain,
        "uncertain_rate": rate(v5_uncertain, v5_rows),
        "abstract_rows": v5_abstract_rows,
        "abstract_uncertain": v5_abstract_uncertain,
        "abstract_uncertain_rate": rate(v5_abstract_uncertain, v5_abstract_rows),
        "title_only_rows": v5_title_only_rows,
        "title_only_uncertain": v5_title_only_uncertain,
        "title_only_uncertain_rate": rate(v5_title_only_uncertain, v5_title_only_rows),
        "uncertain_with_abstract_share": rate(v5_abstract_uncertain, v5_uncertain),
        "uncertain_abstract_length_median": median(uncertain_abstract_lengths),
        "uncertain_abstract_at_least_180_chars": sum(
            length >= 180 for length in uncertain_abstract_lengths
        ),
        "uncertain_abstract_at_least_600_chars": sum(
            length >= 600 for length in uncertain_abstract_lengths
        ),
        "questions": {
            question_id: {
                "rows": len(subset := [
                    row for row in classifier_rows if row["question_id"] == question_id
                ]),
                "uncertain": (question_uncertain := sum(
                    row["decision"] == "uncertain" for row in subset
                )),
                "uncertain_rate": rate(question_uncertain, len(subset)),
            }
            for question_id in QUESTION_ORDER
        },
    }
    uncertain_comparison = validation.get("uncertain_comparison", {})
    expected_difference = {
        "uncertain_rate_percentage_point_change": 100
        * (expected_v5["uncertain_rate"] - expected_v4["uncertain_rate"]),
        "uncertain_rate_ratio": expected_v5["uncertain_rate"]
        / expected_v4["uncertain_rate"],
    }
    if not all(
        (
            isinstance(uncertain_comparison, dict),
            uncertain_comparison.get("comparison_unit") == "classifier_output_row",
            uncertain_comparison.get("v4_0") == expected_v4,
            uncertain_comparison.get("v5_0_classifier_layer") == expected_v5,
            uncertain_comparison.get("difference") == expected_difference,
        )
    ):
        raise RuntimeError("primary uncertain comparison differs from current v4/v5 data")
    return True


def verify_protected_audit_current(protected: dict) -> bool:
    """Recheck protected paths, canonical baseline equality, and audit freshness."""

    captured = datetime.fromisoformat(
        str(protected.get("captured_at_utc", "")).replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    protected_items = protected.get("protected_paths", [])
    combined = protected.get("combined_protected", {})
    limitations = protected.get("limitations", [])
    ignored_limitations = (
        [
            item
            for item in limitations
            if isinstance(item, dict)
            and item.get("code") == "IGNORED_FILES_NOT_CAPTURED_IN_FROZEN_BASELINE"
        ]
        if isinstance(limitations, list)
        else []
    )
    recheck_ok, recheck = protected_audit_recheck(protected)
    current_ignored = recheck.get("current_ignored_files", [])
    path_rechecks = recheck.get("paths", [])
    ignored_limitation = ignored_limitations[0] if len(ignored_limitations) == 1 else {}
    ignored_limitation_valid = all(
        (
            len(ignored_limitations) == 1,
            isinstance(current_ignored, list),
            ignored_limitation.get("file_count")
            == combined.get("ignored_file_count")
            == len(current_ignored),
            int(ignored_limitation.get("file_count", 0)) > 0,
            bool(ignored_limitation.get("effect")),
        )
    )
    protected_contract_current = all(
        (
            protected.get("schema_version") == "1.1.0",
            protected.get("status") == "pass_with_unverified_ignored_files",
            protected.get("status_scope") == "434_baseline_tracked_files",
            protected.get("ignored_file_baseline_limitation_present") is True,
            protected.get("problems") == [],
            isinstance(protected_items, list) and len(protected_items) == 4,
            all(item.get("status") == "pass" for item in protected_items),
            all(
                item.get("verification", {}).get("consecutive_raw_snapshot_matches")
                is True
                for item in protected_items
            ),
            combined.get("status") == "pass",
            combined.get("tracked_files") == 434,
            combined.get("bytes") == 404_869_977,
            combined.get("untracked_file_count") == 0,
            combined.get("ignored_file_count") == len(current_ignored) > 0,
            combined.get("ignored_baseline_comparison_supported") is False,
            ignored_limitation_valid,
            recheck_ok,
            recheck.get("status")
            == "pass_for_434_baseline_tracked_files_with_ignored_baseline_limitation",
            recheck.get("completion_scope")
            == "434_baseline_tracked_files_with_ignored_baseline_limitation",
            recheck.get("tracked_file_count") == 434,
            recheck.get("current_untracked_files") == [],
            recheck.get("ignored_file_baseline_limitation_present") is True,
            recheck.get("errors") == [],
            isinstance(path_rechecks, list) and len(path_rechecks) == 4,
            all(item.get("status") == "pass" for item in path_rechecks),
        )
    )
    if not protected_contract_current:
        raise RuntimeError("protected audit canonical/current recheck failed")

    snapshot = protected.get("final_artifact_snapshot", {})
    recorded_artifacts = snapshot.get("artifacts", [])
    if not isinstance(recorded_artifacts, list):
        raise RuntimeError("protected audit lacks final artifact snapshot")
    current_artifacts = current_records(recorded_artifacts, label="final artifact snapshot")
    newest_mtime = max(
        (ROOT / str(row["path"])).stat().st_mtime for row in current_artifacts
    )
    if not all(
        (
            snapshot.get("missing") == [],
            snapshot.get("captured_count") == snapshot.get("required_count"),
            snapshot.get("audit_after_required_artifacts") is True,
            captured.timestamp() >= newest_mtime,
        )
    ):
        raise RuntimeError("protected audit final artifact snapshot is stale")
    return True


def verify_adjudication_mtime_sequence(
    selection: dict, adjudication: dict
) -> list[dict[str, object]]:
    """Recompute current output mtime ranges without treating them as execution receipts."""

    if selection.get("independent_blinding_ai") is not False:
        raise RuntimeError("selection contains unsupported independent_blinding_ai provenance")
    if selection.get("processing_order") != QUESTION_ORDER:
        raise RuntimeError("selection processing order changed")
    if adjudication.get("processing_order") != QUESTION_ORDER:
        raise RuntimeError("adjudication processing order changed")
    ranges: list[dict[str, object]] = []
    for question_id in QUESTION_ORDER:
        paths = sorted(
            (SCREEN / "agent_outputs" / "adjudication" / question_id).glob("*.jsonl")
        )
        expected_batches = int(adjudication["per_question"][question_id]["batch_count"])
        if len(paths) != expected_batches or not paths:
            raise RuntimeError(f"adjudication output batch count changed: {question_id}")
        mtimes = [path.stat().st_mtime_ns for path in paths]
        ranges.append(
            {
                "question_id": question_id,
                "first_output_mtime_utc": datetime.fromtimestamp(
                    min(mtimes) / 1_000_000_000, timezone.utc
                ).isoformat(),
                "last_output_mtime_utc": datetime.fromtimestamp(
                    max(mtimes) / 1_000_000_000, timezone.utc
                ).isoformat(),
                "batch_count": len(paths),
            }
        )
    if not all(
        datetime.fromisoformat(str(previous["last_output_mtime_utc"]))
        <= datetime.fromisoformat(str(current["first_output_mtime_utc"]))
        for previous, current in zip(ranges, ranges[1:])
    ):
        raise RuntimeError("current output mtimes do not support Q01-to-Q05 ordering")
    return ranges


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def matrix_table(matrix: dict[str, dict[str, int]]) -> str:
    rows = [
        "| 분류기 → 재판정 | retain | deprioritize | uncertain | 합계 |",
        "|---|---:|---:|---:|---:|",
    ]
    for source in LABELS:
        values = [int(matrix[source][target]) for target in LABELS]
        rows.append(
            f"| {source} | {values[0]:,} | {values[1]:,} | {values[2]:,} | {sum(values):,} |"
        )
    return "\n".join(rows)


def distribution_text(distribution: dict[str, int]) -> str:
    return " / ".join(f"`{label}` {int(distribution[label]):,}" for label in LABELS)


def main(*, check_only: bool = False) -> int:
    adjudication_path = SCREEN / "adjudication_manifest.json"
    decisions_path = SCREEN / "decisions.csv"
    downstream_csv_path = V5 / "downstream" / "supporting_literature.csv"
    downstream_manifest_path = V5 / "downstream" / "literature_link_manifest.json"
    queries_path = V5 / "query_definitions.json"
    probe_path = V5 / "probe_report.json"
    evidence_path = V5 / "evidence_map.csv"
    classifier_validation = load(SCREEN / "classifier_validation.json")
    cross_validation = load(SCREEN / "classifier_validation_cross_layer.json")
    selection = load(SCREEN / "adjudication_selection.json")
    selection_provenance_correction = validate_selection_provenance_correction(selection)
    adjudication = load(adjudication_path)
    downstream = load(downstream_manifest_path)
    locator = load(V5 / "downstream" / "locator_verification.json")
    protected = load(LOGS / "v50_protected_final_audit.json")
    queries = load(queries_path)
    probe = load(probe_path)
    corpus = load(V5 / "corpus_manifest.json")
    evidence_rows = read_csv(evidence_path)
    classifier_rows = read_csv(SCREEN / "classifier_decisions.csv")
    primary_classifier_validation_current = verify_primary_classifier_validation(
        classifier_validation,
        cross_validation,
        classifier_rows,
        evidence_rows,
    )
    phase_a_integrity = verify_phase_a(queries, probe, queries_path)
    phase_b_integrity = verify_phase_b(
        corpus,
        queries,
        probe,
        queries_path,
        probe_path,
        evidence_path,
        evidence_rows,
    )
    adjudication_status = adjudication_pipeline_status()
    adjudication_mtime_ranges = verify_adjudication_mtime_sequence(
        selection, adjudication
    )
    protected_audit_current = verify_protected_audit_current(protected)

    downstream_inputs = downstream.get("inputs", {})
    downstream_outputs = downstream.get("outputs", {})
    downstream_results = downstream.get("results", {})
    locator_inputs = locator.get("inputs", {})
    locator_checks = locator.get("checks", {})
    cross_integrity = cross_validation.get("cross_layer_integrity", {})
    cross_sources = cross_validation.get("source_hashes", {})
    frozen_classifier_validation = cross_validation.get(
        "frozen_classifier_validation", {}
    )
    current_classifier_batch_inputs = verify_recorded_hashes_current(
        cross_integrity.get("batch_input_files_sha256"),
        label="classifier batch input",
    )
    current_classifier_batch_outputs = verify_recorded_hashes_current(
        cross_integrity.get("batch_output_files_sha256"),
        label="classifier batch output",
    )
    current_classifier_batch_manifests = verify_recorded_hashes_current(
        cross_sources.get("classifier_batch_manifests"),
        label="classifier batch manifest",
    )
    if not all(
        (
            adjudication.get("run_complete") is True,
            selection_provenance_correction.get("valid") is True,
            selection_provenance_correction.get("correction_id") == "V50-PC-001",
            selection_provenance_correction.get("allowed_selection_changes")
            == ["independent_blinding_ai", "provenance_correction"],
            selection_provenance_correction.get("selected_records_changed") is False,
            selection_provenance_correction.get("execution_contract_changed") is False,
            selection_provenance_correction.get("batch_inputs_changed") is False,
            selection_provenance_correction.get("batch_outputs_changed") is False,
            adjudication_status.get("ready_to_compile") is True,
            adjudication_status.get("compiled") is True,
            phase_a_integrity.get("current_artifact_integrity_verified") is True,
            phase_a_integrity.get("total_hit_count") == 43_249,
            phase_a_integrity.get("retrieval_rerun") is False,
            phase_b_integrity.get("current_artifact_integrity_verified") is True,
            phase_b_integrity.get("raw_xml_files_verified") == 105,
            phase_b_integrity.get("evidence_map_rows") == 42_822,
            phase_b_integrity.get("question_memberships") == 43_207,
            phase_b_integrity.get("retrieval_rerun") is False,
            primary_classifier_validation_current,
            cross_validation.get("schema_version") == "1.1.0",
            cross_validation.get("case_count") == classifier_validation.get("case_count"),
            cross_validation.get("pass_count") == classifier_validation.get("pass_count"),
            cross_validation.get("fail_count") == classifier_validation.get("fail_count"),
            frozen_classifier_validation.get("path")
            == (SCREEN / "classifier_validation.json").relative_to(ROOT).as_posix(),
            frozen_classifier_validation.get("exists") is True,
            frozen_classifier_validation.get("sha256")
            == sha256(SCREEN / "classifier_validation.json"),
            frozen_classifier_validation.get("modified_by_this_validator") is False,
            frozen_classifier_validation.get("primary_contract_validated") is True,
            cross_integrity.get("evidence_map_membership_key_count") == 43_207,
            cross_integrity.get("classifier_checkpoint_row_count") == 43_207,
            cross_integrity.get("classifier_batch_count") == 182,
            cross_integrity.get("classifier_batch_output_row_count") == 43_207,
            cross_integrity.get("classifier_decisions_csv_row_count") == 43_207,
            cross_integrity.get("key_universe_exact_match") is True,
            cross_integrity.get("batch_input_evidence_fields_and_order_exact_match")
            is True,
            cross_integrity.get("six_normalized_decision_fields_exact_match") is True,
            cross_integrity.get("batch_input_files_sha256")
            == current_classifier_batch_inputs,
            cross_integrity.get("batch_output_files_sha256")
            == current_classifier_batch_outputs,
            len(current_classifier_batch_inputs) == 182,
            len(current_classifier_batch_outputs) == 182,
            cross_sources.get("classifier_batch_manifests")
            == current_classifier_batch_manifests,
            len(current_classifier_batch_manifests) == 5,
            cross_sources.get("evidence_map.csv") == sha256(evidence_path),
            cross_sources.get("frozen_light_screening_prompt.md")
            == sha256(V5 / "prompts" / "frozen_light_screening_prompt.md"),
            cross_sources.get("classifier_decisions.csv")
            == sha256(SCREEN / "classifier_decisions.csv"),
            cross_sources.get("classifier_checkpoints.jsonl")
            == sha256(SCREEN / "checkpoints.jsonl"),
            cross_sources.get("classifier_validation_v50.py")
            == sha256(V5 / "classifier_validation_v50.py"),
            cross_sources.get("light_screening_pipeline.py")
            == sha256(V5 / "light_screening_pipeline.py"),
            cross_sources.get("v4_screening_manifest.json")
            == sha256(
                ROOT
                / "research_v3"
                / "otc"
                / "literature"
                / "screening"
                / "screening_manifest.json"
            ),
            cross_sources.get("v4_evidence_map.csv")
            == sha256(ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"),
            cross_sources.get("v4_checkpoints.jsonl")
            == sha256(
                ROOT
                / "research_v3"
                / "otc"
                / "literature"
                / "screening"
                / "checkpoints.jsonl"
            ),
            adjudication.get("counts", {}).get("adjudicated_rows") == 5_000,
            adjudication.get("counts", {}).get("compiled_decision_rows") == 43_207,
            adjudication.get("agent_identity_recorded") is False,
            adjudication.get("specific_agent_attribution_supported") is False,
            adjudication.get("execution_receipts_recorded") is False,
            adjudication.get("question_sequence_receipt_recorded") is False,
            adjudication.get("independent_blinding_ai") is False,
            adjudication.get("layers", {}).get("compiled_decisions", {}).get("sha256")
            == sha256(decisions_path),
            downstream_inputs.get("screening_decisions", {}).get("sha256")
            == sha256(decisions_path),
            downstream_inputs.get("adjudication_manifest", {}).get("sha256")
            == sha256(adjudication_path),
            downstream_outputs.get("supporting_literature", {}).get("sha256")
            == sha256(downstream_csv_path),
            downstream_outputs.get("supporting_literature", {}).get("row_count")
            == downstream_results.get("emitted_link_count"),
            downstream_results.get("emitted_link_count", 0)
            + downstream_results.get("rejected_candidate_count", 0)
            == 20,
            downstream_results.get("emitted_link_count", 0) > 0,
            downstream_inputs.get("query_definitions", {}).get("sha256")
            == sha256(V5 / "query_definitions.json"),
            locator.get("status") == "pass",
            locator_inputs.get("supporting_literature", {}).get("sha256")
            == sha256(downstream_csv_path),
            locator_inputs.get("downstream_manifest", {}).get("sha256")
            == sha256(downstream_manifest_path),
            locator_inputs.get("final_decisions", {}).get("sha256")
            == sha256(decisions_path),
            locator_inputs.get("adjudication_manifest", {}).get("sha256")
            == sha256(adjudication_path),
            locator_checks.get("locator_quote_exact_match_for_every_link") is True,
            locator_checks.get("site_output_unchanged") is True,
            locator_checks.get("site_output_hash_captured_before_original_builder_import") is True,
            locator_checks.get("nonzero_link_set") is True,
            protected.get("status") == "pass_with_unverified_ignored_files",
            protected.get("status_scope") == "434_baseline_tracked_files",
            protected.get("ignored_file_baseline_limitation_present") is True,
            protected_audit_current,
            len(adjudication_mtime_ranges) == len(QUESTION_ORDER),
        )
    ):
        raise RuntimeError("final artifacts are not ready for log generation")

    classifier_dist = adjudication["layer_distributions"]["classifier_all"]
    selected_dist = adjudication["layer_distributions"]["classifier_selected"]
    adjudication_dist = adjudication["layer_distributions"]["semantic_adjudication"]
    final_dist = adjudication["layer_distributions"]["compiled_decisions"]
    disagreement = adjudication["disagreement"]
    matrix = adjudication["movement_matrix"]

    # 최종 retain 이 어느 층에서 왔는지. 재판정을 받지 않은 분류기 행이 최종 retain 의
    # 대부분을 차지한다는 사실은 표에서 읽히지 않으므로 따로 계산해 본문에 적는다.
    retain_final = final_dist["retain"]
    retain_adjudicated = adjudication_dist["retain"]
    retain_classifier_only = classifier_dist["retain"] - selected_dist["retain"]
    if retain_classifier_only + retain_adjudicated != retain_final:
        raise RuntimeError(
            "retain 구성 검산 실패: "
            f"{retain_classifier_only} + {retain_adjudicated} != {retain_final}"
        )
    retain_classifier_only_rate = retain_classifier_only / retain_final
    retain_adjudicated_rate = retain_adjudicated / retain_final
    # 재판정된 분류기 retain 행 중 retain 을 유지한 비율
    selected_retain = selected_dist["retain"]
    selected_retain_kept = matrix["retain"]["retain"]
    selected_retain_moved = selected_retain - selected_retain_kept
    selected_retain_moved_rate = selected_retain_moved / selected_retain
    validation_case_count = len(classifier_validation["cases"])
    validation_pass_count = sum(
        case.get("passed") is True for case in classifier_validation["cases"]
    )
    validation_fail_count = validation_case_count - validation_pass_count
    uncertain_comparison = classifier_validation["uncertain_comparison"]
    v4_uncertain = uncertain_comparison["v4_0"]
    v5_uncertain = uncertain_comparison["v5_0_classifier_layer"]
    adjudication_batch_count = int(selection["batch_count"])
    raw_xml_count = int(corpus["totals"]["raw_xml_files"])
    missing_links = [
        row
        for row in downstream["results"]["rejected_candidates"]
        if row["reason"] == "not_in_v5_corpus"
    ]
    missing_rule_ids = sorted({row["rule_id"] for row in missing_links})
    unresolved_rule_ids = downstream["results"]["unresolved_rule_ids"]
    question_rows = []
    for question_id in adjudication["processing_order"]:
        row = adjudication["per_question"][question_id]
        question_rows.append(
            "| "
            + " | ".join(
                (
                    question_id.split("-")[2],
                    f"{row['classifier_rows']:,}",
                    f"{row['selected_rows']:,}",
                    f"{row['disagreement_count']:,}",
                    percent(row["disagreement_rate"]),
                    f"{row['compiled_decisions_distribution']['retain']:,}",
                    f"{row['compiled_decisions_distribution']['deprioritize']:,}",
                    f"{row['compiled_decisions_distribution']['uncertain']:,}",
                )
            )
            + " |"
        )

    decisions_text = f"""# v5.0 문헌 선별 결정 기록

## 먼저 바로잡은 기록

기존 43,207개 `(논문, 질문)` 라벨은 결정적 텍스트 분류기가 만들었다. 기존 출력과 배치 매니페스트에는 실행 주체 식별자가 없으므로 과거 담당자 귀속 182개는 증거로 인정하지 않는다. 실행 방식과 귀속 한계는 보고서의 `phases.C.classifier_layer`에 선언했다. `execution_layer: deterministic_text_classifier`와 `attribution_unsupported: true`는 43,207개 판정 행이 아니라 그 아래 182개 `batch_records`에 기록했다.

과거 `completed_at_utc`도 실제 완료 시각이 아니었다. 출력 파일의 수정 시각을 완료 시각처럼 기록한 값이므로 `output_file_mtime_utc`로 바로잡고, 의미 검토 완료 시각은 지원되지 않는다고 표시한다.

분류기 원본은 `research_v3/otc/literature/v5/screening/classifier_decisions.csv`에 그대로 보존했다.

선정 파일의 `independent_blinding_ai`(독립 AI 재판정 증명 상태)는 실행 영수증이 없는데도 `true`로 기록돼 있었다. `V50-PC-001`에서 값을 `false`로 수정하고 `provenance_correction` 기록을 추가했다. 그 밖의 선정 계약, 5,000개 선정 행, 입력 25개와 출력 25개는 바뀌지 않았다. 이 정정은 누락된 실행자·순서 영수증을 새로 만들지 않는다.

- 행수: 43,207
- 분포: {distribution_text(classifier_dist)}
- SHA-256: `{sha256(SCREEN / 'classifier_decisions.csv')}`

## 분류기는 AI 참조 기준과 어디서 달랐는가

실제 문헌 사례 {validation_case_count}건을 AI 참조 기준과 비교했다. {validation_pass_count}건은 일치했고 {validation_fail_count}건은 불일치했다. 이 사례는 오분류 후보와 경계 사례를 의도적으로 모은 비확률 표본이다. 따라서 `agreement_vs_ai_reference` {percent(classifier_validation['agreement_vs_ai_reference'])}를 전체 코퍼스 성능으로 해석할 수 없다. 별도 교차층 검증은 evidence map의 43,207개 멤버십, 182개 분류기 출력, 체크포인트와 분류기 CSV의 키·6개 판정 필드가 정확히 같음을 확인했다. 사람 참조표준은 0건이고 `independent_blinding=false`, `release_ready=false`다.

v5.0 분류기 층의 `uncertain`은 {v5_uncertain['uncertain']:,}/{v5_uncertain['classifier_output_rows']:,}건({percent(v5_uncertain['uncertain_rate'])})이고, v4.0은 {v4_uncertain['uncertain']:,}/{v4_uncertain['classifier_output_rows']:,}건({percent(v4_uncertain['uncertain_rate'])})이다. v5.0 `uncertain` 가운데 {v5_uncertain['abstract_uncertain']:,}건은 초록이 있고 {v5_uncertain['title_only_uncertain']:,}건은 제목만 있다. 검색 확대와 분류 규칙 차이는 원인 가설일 뿐이다. 코퍼스 중첩과 사람 참조표준이 없어 원인을 확정하지 않는다.

## 5,000건은 어떻게 다시 판정했는가

재판정 표본은 분류기 `uncertain` 2,246건 전수와 `retain`·`deprioritize` 2,754건으로 구성했다. 나머지 2,754건에는 성분·결과·사람 신호의 귀속이 모호한 경계 사례, 불변식 실패 사례, 200건 배치를 완성하기 위한 고신뢰 대조 사례가 들어 있다.

질문별로 Q01 1,400건, Q02 1,200건, Q03 600건, Q04 1,600건, Q05 200건을 골랐다. 입력에서는 분류기 라벨과 선정 이유를 뺐다. 이 문서를 생성할 때 25개 출력 파일의 수정 시각 범위를 다시 계산했으며, 질문별 마지막 수정 시각은 다음 질문의 첫 수정 시각보다 늦지 않았다. 그러나 실행자/task ID, provider/model, 시작·종료 시각, 선행 질문 영수증을 해시에 묶어 보존하지 않았다. 따라서 파일 수정 시각은 특정 에이전트 귀속, 실제 질문 간 실행 순서, 질문 안의 병렬 처리를 독립 증명하지 않는다.

동결 프롬프트는 `research_v3/otc/literature/v5/prompts/frozen_semantic_adjudication_prompt.md`이며 SHA-256은 `{sha256(V5 / 'prompts' / 'frozen_semantic_adjudication_prompt.md')}`다.

## 재판정 결과

5,000건 중 {disagreement['count']:,}건({percent(disagreement['rate'])})이 분류기 라벨과 달랐다. 경계 중심 표본의 불일치율이며 전체 43,207건의 오류율이 아니다. 이 수치를 숨기지 않고 최종 라벨에 모두 반영했다.

{matrix_table(matrix)}

- 재판정 표본 분포: {distribution_text(adjudication_dist)}
- 최종 43,207건 분포: {distribution_text(final_dist)}
- 최종 결정 SHA-256: `{sha256(SCREEN / 'decisions.csv')}`

### 최종 retain 은 어느 층에서 왔는가

최종 `retain` {retain_final:,}건 가운데 {retain_adjudicated:,}건({percent(retain_adjudicated_rate)})만 재판정을 거쳤고, {retain_classifier_only:,}건({percent(retain_classifier_only_rate)})은 재판정 표본에 들지 않아 분류기 라벨 그대로 남았다. 즉 최종 retain 의 대부분은 두 번째 판정을 받지 않았다.

재판정을 받은 분류기 `retain` {selected_retain:,}건 중 {selected_retain_kept:,}건만 `retain` 을 유지했고 {selected_retain_moved:,}건({percent(selected_retain_moved_rate)})은 다른 라벨로 옮겨졌다.

이 {percent(selected_retain_moved_rate)}를 재판정하지 않은 {retain_classifier_only:,}건에 외삽할 수 없다. 재판정 표본은 경계 사례를 의도적으로 고른 비확률 표본이므로 같은 비율이 나머지에 적용된다는 근거가 없다. 다만 최종 retain 의 큰 쪽이 검증되지 않았고, 검증된 작은 쪽에서는 절반 가까이가 수정되었다는 두 사실은 함께 읽어야 한다. 이 층의 선별 성능을 확률표본으로 추정하려면 별도 채점 arm 이 필요하다.

## 하류 문헌 연결

최종 `retain` 라벨로 v4.0 후보 연결 20개를 다시 검사했다. {downstream['results']['emitted_link_count']}개를 내보냈고 {downstream['results']['rejected_candidate_count']}개를 제외했다. 문헌 연결이 남은 규칙은 {downstream['results']['resolved_rule_count']}/16개이고, 미해결 규칙은 {', '.join(unresolved_rule_ids)}다.

원문 대조는 기존 `scripts/research/otc/build_supporting_literature.py`의 `build()` 검사를 내보낸 규칙 범위에서 읽기 전용으로 실행했다. 모든 출력 연결의 `abstract:sentence:N` 문장과 인용문이 정확히 같았고 사이트 산출물은 바뀌지 않았다.

## 남겨 둔 문제

- Q05 검색 결과는 v4.0 713건에서 v5.0 517건으로 줄었다. P 블록이 과도하게 좁을 수 있지만 이번 실행에서는 검색식을 바꾸지 않았다.
- v4.0 연결 20개 중 6개가 v5 코퍼스에 없다. 프로토콜에 기록된 설명은 v4.0 검색식의 결과 용어 의존이다. 누락 연결별 직접 인과는 이번 실행에서 다시 검증하지 않았다. 영향 규칙은 {', '.join(missing_rule_ids)}다.
- 사람 참조표준은 0건이다. 선별 성능은 측정되지 않았다.
- Phase A/B는 재실행하지 않았고 현재 질의·probe·XML {raw_xml_count}개·체크섬·evidence map의 내부 무결성을 확인했다. 방어 시작 시점 해시 기준선은 없어 그 시점 이후 불변성을 암호학적으로 증명할 수 없다.
- 재판정 입력·출력과 계약 해시는 보존됐지만 실행자와 실행 순서를 증명하는 영수증은 없다. 구체적인 에이전트 귀속은 지원되지 않는다.
- 보호 경로의 기준선 추적 파일 434개는 Git blob과 현재 바이트가 같다. 현재 ignored 파일은 다시 해시했지만 동결 기준선에 ignored 파일 목록과 해시가 없어 과거 내용 동일성은 증명하지 못한다.

공식 v5.0 해시 체인은 로컬 언어모델 출력이나 사람 판단 산출물을 참조하지 않는다. 이전 세션의 폐기된 로컬 모델 시험은 역사 기록으로만 남고 정식 체인에는 들어가지 않는다. 메타분석, 통합 효과크기, RoB, GRADE, 임상 권고, 배포, `git push`도 공식 체인에 없다.
"""

    final_text = f"""# OTC 문헌층 v5.0 실행 결과

## 결론부터 보면

v5.0 문헌 선별 체인은 결정적 분류기와 계약 검사를 통과한 의미 재판정 층을 분리해 설명한다. 분류기 원본 43,207건은 그대로 보존했고, 그중 5,000건의 제목·초록 기반 재판정 라벨을 최종 결정에 덮어썼다. 재판정 파일에는 실행자 식별자가 없어 특정 에이전트 귀속은 지원되지 않는다.

선정 파일의 `independent_blinding_ai`는 실행 영수증 없이 `true`로 기록된 메타데이터 오류였다. `V50-PC-001`에서 값을 `false`로 고쳤고, 5,000개 선정 행과 입력·출력 각 25개는 바꾸지 않았다. 이 정정은 누락된 실행자·순서 영수증을 새로 만들지 않는다.

재판정 5,000건 가운데 {disagreement['count']:,}건({percent(disagreement['rate'])})이 분류기와 달랐다. 경계 사례를 집중적으로 고른 결과라 전체 오류율은 아니다. 다만 경계 사례에서는 분류기 라벨만으로 최종 결정을 내릴 수 없다는 점이 드러났다.

## 무엇이 끝났나

- Phase A: PubMed 검색 43,249건. 이 문서를 생성할 때 `verify_phase_a`가 질의 해시, probe 질의, 질문별 10개 규칙과 합계를 다시 대조했다. 검색은 다시 실행하지 않았다.
- Phase B: 근거 지도 고유 논문 {corpus['totals']['evidence_map_rows_unique_papers']:,}개, 선별 단위 {corpus['totals']['question_membership_units_after_bibliographic_deduplication']:,}개, XML {raw_xml_count}개. 이 문서를 생성할 때 `verify_phase_b`가 105개 XML의 체크섬 매니페스트, 응답 메타데이터 해시, evidence map 해시와 행수를 다시 대조했다.
- Phase C 분류기: 43,207건 보존. 실제 사례 {validation_case_count}건 중 {validation_pass_count}건 일치, {validation_fail_count}건 불일치.
- Phase C 재판정: 5,000/5,000건, {adjudication_batch_count}개 배치. 입력·출력·최종 라벨을 행과 해시로 재구성했다.
- Phase D: 최종 라벨로 규칙–문헌 연결 {downstream['results']['emitted_link_count']}개를 생성했다. 원문 문장 대조는 모두 통과했다.
- 보호 경로: 이 문서를 생성하기 직전에 보호 감사에 기록된 추적·비추적·ignored 파일을 다시 열어 크기와 SHA-256을 대조했다. 기준선 추적 파일 434개는 일치했다. ignored 파일은 동결 기준선에 없으므로 과거 내용 동일성은 증명하지 못한다.

| 질문 | 전체 선별 단위 | 재판정 | 불일치 | 불일치율 | 최종 retain | 최종 deprioritize | 최종 uncertain |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(question_rows)}
| 합계 | 43,207 | 5,000 | {disagreement['count']:,} | {percent(disagreement['rate'])} | {final_dist['retain']:,} | {final_dist['deprioritize']:,} | {final_dist['uncertain']:,} |

### 최종 retain 은 어느 층에서 왔는가

최종 `retain` {retain_final:,}건 가운데 {retain_adjudicated:,}건({percent(retain_adjudicated_rate)})만 재판정을 거쳤고, {retain_classifier_only:,}건({percent(retain_classifier_only_rate)})은 재판정 표본에 들지 않아 분류기 라벨 그대로 남았다. 즉 최종 retain 의 대부분은 두 번째 판정을 받지 않았다.

재판정을 받은 분류기 `retain` {selected_retain:,}건 중 {selected_retain_kept:,}건만 `retain` 을 유지했고 {selected_retain_moved:,}건({percent(selected_retain_moved_rate)})은 다른 라벨로 옮겨졌다.

이 {percent(selected_retain_moved_rate)}를 재판정하지 않은 {retain_classifier_only:,}건에 외삽할 수 없다. 재판정 표본은 경계 사례를 의도적으로 고른 비확률 표본이므로 같은 비율이 나머지에 적용된다는 근거가 없다. 이 층의 선별 품질은 별도 층화 확률표본 채점 arm 으로 측정해야 한다.

## 무엇이 아직 남았나

Q05 검색 결과가 713건에서 517건으로 줄어든 원인은 별도 프로토콜 개정에서 확인해야 한다. v4.0 규칙–문헌 연결 20개 중 v5 코퍼스에 없는 6개도 같은 방식으로 검토해야 한다. 이번 실행에서는 검색식이나 허가원문 규칙을 바꾸지 않았다.

가장 큰 제한은 사람 참조표준이 0건이라는 점이다. 이번 결과는 분류기 층과 의미 재판정 층의 차이를 보여 주지만 사람 기준 선별 성능을 말해 주지는 않는다. 실행자와 순서를 묶은 해시 영수증도 없으므로 특정 에이전트 귀속과 실제 병렬 처리 방식은 독립 증명할 수 없다. Phase A/B의 방어 시작 시점 해시 기준선도 없다. 보호 경로의 ignored 파일도 동결 기준선이 없어 과거 내용 동일성을 증명하지 못한다. `independent_blinding=false`, `release_ready=false`를 유지한다.

다음 작업은 Q05 P 블록과 누락 연결 6개를 새 개정 이력에서 검토하고, 필요하면 사람 참조표준을 별도로 만드는 것이다. 다음 재판정부터는 실행자·모델·시각·선행 질문 해시를 배치 영수증으로 남겨야 한다. 이번 v5.0 산출물은 그때 비교 기준으로 보존한다.

전체 수치·해시·이동 행렬·미해결 규칙은 `research_v3/logs/v50_run_report.json` 하나에서 확인할 수 있다.
"""

    if check_only:
        print(
            json.dumps(
                {
                    "status": "ready_to_write",
                    "phase_a_integrity": phase_a_integrity,
                    "phase_b_integrity": {
                        "current_artifact_integrity_verified": phase_b_integrity[
                            "current_artifact_integrity_verified"
                        ],
                        "raw_xml_files_verified": phase_b_integrity[
                            "raw_xml_files_verified"
                        ],
                        "evidence_map_rows": phase_b_integrity["evidence_map_rows"],
                        "question_memberships": phase_b_integrity["question_memberships"],
                    },
                    "protected_audit_current": protected_audit_current,
                    "selection_provenance_correction": selection_provenance_correction,
                    "adjudication_output_mtime_ranges": adjudication_mtime_ranges,
                    "outputs_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    atomic_text(DECISIONS_MD, decisions_text)
    atomic_text(FINAL_MD, final_text)
    print(
        json.dumps(
            {
                "decision_history": DECISIONS_MD.relative_to(ROOT).as_posix(),
                "final_summary": FINAL_MD.relative_to(ROOT).as_posix(),
                "disagreement_count": disagreement["count"],
                "disagreement_rate": disagreement["rate"],
                "final_distribution": final_dist,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate every input without rewriting the two Markdown outputs",
    )
    arguments = parser.parse_args()
    raise SystemExit(main(check_only=arguments.check))
