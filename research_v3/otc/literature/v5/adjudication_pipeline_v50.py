from __future__ import annotations

"""Deterministic preparation, contract checks, and compilation for v5.0 adjudication.

This program performs no model inference.  It prepares blinded inputs for a
separate semantic adjudicator, contract-checks outputs, and applies accepted
labels while retaining the classifier decisions as an immutable source layer.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREENING = V5 / "screening"
CLASSIFIER_DECISIONS = SCREENING / "classifier_decisions.csv"
CLASSIFIER_VALIDATION = SCREENING / "classifier_validation.json"
LIGHT_SCREENING_PIPELINE = V5 / "light_screening_pipeline.py"
DECISIONS = SCREENING / "decisions.csv"
EVIDENCE_MAP = V5 / "evidence_map.csv"
PROMPT = V5 / "prompts" / "frozen_semantic_adjudication_prompt.md"
SELECTION = SCREENING / "adjudication_selection.json"
BATCH_ROOT = SCREENING / "batches" / "adjudication"
OUTPUT_ROOT = SCREENING / "agent_outputs" / "adjudication"
VALIDATION_ROOT = SCREENING / "adjudication_validation"
SEMANTIC_ADJUDICATIONS = SCREENING / "semantic_adjudications.json"
ADJUDICATION_MANIFEST = SCREENING / "adjudication_manifest.json"
PROVENANCE_CORRECTION_BACKUP_ROOT = (
    V5 / "etc" / "superseded" / "selection-provenance-correction"
)
LEGACY_SELECTION_BACKUP = PROVENANCE_CORRECTION_BACKUP_ROOT / "adjudication_selection.json"
PROVENANCE_CORRECTION_RECOVERY_RECEIPT = (
    PROVENANCE_CORRECTION_BACKUP_ROOT / "receipt.json"
)

QUESTION_ORDER = (
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
)
QUESTION_ALIASES = {f"Q{index:02d}": question for index, question in enumerate(QUESTION_ORDER, 1)}
DECISION_VALUES = ("retain", "deprioritize", "uncertain")
CONFIDENCE_VALUES = ("high", "medium", "low")
EVIDENCE_BASES = ("abstract", "title_only")
REASON_CODE_ORDER = (
    "population",
    "exposure",
    "outcome",
    "human_signal",
    "design_signal",
    "animal_term_present",
    "insufficient_abstract",
    "off_topic",
)
REASON_CODES = frozenset(REASON_CODE_ORDER)
CLASSIFIER_FIELDS = (
    "record_id",
    "question_id",
    "decision",
    "reason_codes",
    "confidence",
    "evidence_basis",
)
BATCH_INPUT_FIELDS = (
    "record_id",
    "question_id",
    "title",
    "abstract",
    "publication_types",
    "mesh_terms",
)
ADJUDICATION_FIELDS = CLASSIFIER_FIELDS
BATCH_SIZE = 200
TARGET_ROWS = 5_000
EXPECTED_CLASSIFIER_ROWS = 43_207
EXPECTED_CLASSIFIER_BATCHES = 182
EXPECTED_ADJUDICATION_BATCHES = TARGET_ROWS // BATCH_SIZE
SELECTION_SEED = "v50-semantic-adjudication-boundary-20260729"
LEGACY_SELECTION_SHA256 = "e08cfecf609aff04851a12b1aa915ec49d6b1c096ccfc55b5aba5cefba5fb276"
LEGACY_SELECTED_RECORDS_SHA256 = "df6a37d86bd93a98c66b63e6b8e813a32e8032da9f25da6ace9010f14242cdcc"
LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256 = "470d3601f71bb059635dc3d502221cc765abe48cd4132f4f86230cf66d04e3f0"
LEGACY_INPUT_INVENTORY_SHA256 = "fd6468c413dda35c084b9be46055cab105ba42f3403967c18fe3086d20c793cb"
LEGACY_OUTPUT_INVENTORY_SHA256 = "371a8639b37b4778490074d6df3d84a691012d8b9519d629105a0ce4dca9017d"
LEGACY_ADJUDICATION_MANIFEST_SHA256 = "be32830e94268632f18274f9a2ff8d91b50b7bd137809c5f6d579611875723d0"
PROVENANCE_CORRECTION_ID = "V50-PC-001"
SELECTION_PROVENANCE_VALUES = {
    "independent_blinding_ai": False,
    "independent_blinding": False,
    "release_ready": False,
}
SELECTION_EXECUTION_CONTRACT_EXCLUDED_FIELDS = frozenset(
    {
        "adjudication_input_blinded_to_classifier_labels",
        "agent_identity_recorded",
        "specific_agent_attribution_supported",
        "execution_receipts_recorded",
        "independent_blinding_ai",
        "provenance_correction",
    }
)
PROVENANCE_CORRECTION_FORBIDDEN_SELECTION_FIELDS = frozenset(
    {
        "adjudication_input_blinded_to_classifier_labels",
        "agent_identity_recorded",
        "specific_agent_attribution_supported",
        "execution_receipts_recorded",
    }
)
PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES = (
    "independent_blinding_ai",
    "provenance_correction",
)
REQUIRED_VALIDATION_CATEGORIES = frozenset(
    {
        "assigned_ingredient_match",
        "assigned_ingredient_mismatch",
        "class_exposure",
        "exposure_without_outcome",
        "human_exposure",
        "no_abstract",
        "outcome_without_exposure",
        "preclinical_only",
        "q04_oral_digestive_enzyme_safety",
        "q05_topical_pediatric_exposure",
    }
)


class PipelineError(RuntimeError):
    """Raised when an audit or data-contract invariant fails."""


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise PipelineError(f"required file is missing: {_relative(path)}") from exc
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    )


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(CLASSIFIER_FIELDS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        projected = {field: row[field] for field in CLASSIFIER_FIELDS}
        reasons = projected["reason_codes"]
        if isinstance(reasons, (list, tuple)):
            projected["reason_codes"] = ";".join(reasons)
        writer.writerow(projected)
    return stream.getvalue().encode("utf-8-sig")


def _atomic_replace_many(files: Sequence[tuple[Path, bytes]]) -> None:
    """Stage all files, replace them, and restore prior bytes if publication fails."""
    staged: list[tuple[Path, Path]] = []
    originals: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        for destination, data in files:
            destination.parent.mkdir(parents=True, exist_ok=True)
            originals[destination] = destination.read_bytes() if destination.exists() else None
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            staged.append((temporary, destination))
        for temporary, destination in staged:
            os.replace(temporary, destination)
            replaced.append(destination)
    except BaseException:
        for destination in reversed(replaced):
            prior = originals[destination]
            if prior is None:
                destination.unlink(missing_ok=True)
                continue
            descriptor, restore_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".restore", dir=str(destination.parent)
            )
            restore = Path(restore_name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(prior)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(restore, destination)
            finally:
                restore.unlink(missing_ok=True)
        raise
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_replace_many(((path, _json_bytes(value)),))


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"required file is missing: {_relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"invalid JSON in {_relative(path)}: {exc}") from exc


def _load_failed_invariant_keys(
    classifier_rows: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[frozenset[tuple[str, str]], dict[str, Any]]:
    source: dict[str, Any] = {
        "path": _relative(CLASSIFIER_VALIDATION),
        "exists": CLASSIFIER_VALIDATION.exists(),
        "sha256": None,
        "failed_case_count": 0,
    }
    if not CLASSIFIER_VALIDATION.exists():
        raise PipelineError(f"required file is missing: {_relative(CLASSIFIER_VALIDATION)}")
    source["sha256"] = _sha256(CLASSIFIER_VALIDATION)
    document = _load_json(CLASSIFIER_VALIDATION)
    if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
        raise PipelineError(f"{_relative(CLASSIFIER_VALIDATION)}: cases must be an array")
    cases = document["cases"]
    if len(cases) < 20 or document.get("case_count") != len(cases):
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: at least 20 cases and an exact case_count are required"
        )
    if classifier_rows is None:
        classifier_rows = _load_classifier_rows()
    classifier_by_key = {
        (row["record_id"], row["question_id"]): row for row in classifier_rows
    }
    classifier_layer = document.get("classifier_layer")
    expected_distribution = _ordered_distribution(classifier_rows)
    if not isinstance(classifier_layer, dict) or any(
        (
            classifier_layer.get("path") != _relative(CLASSIFIER_DECISIONS),
            classifier_layer.get("sha256") != _sha256(CLASSIFIER_DECISIONS),
            classifier_layer.get("rows") != EXPECTED_CLASSIFIER_ROWS,
            classifier_layer.get("decision_distribution") != expected_distribution,
        )
    ):
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: classifier_layer is not bound to the current classifier"
        )
    format_contract = document.get("format_contract")
    if not isinstance(format_contract, dict) or any(
        (
            format_contract.get("passed") is not True,
            format_contract.get("batch_count") != EXPECTED_CLASSIFIER_BATCHES,
            format_contract.get("expected_batch_count") != EXPECTED_CLASSIFIER_BATCHES,
            format_contract.get("row_count") != EXPECTED_CLASSIFIER_ROWS,
            format_contract.get("expected_row_count") != EXPECTED_CLASSIFIER_ROWS,
        )
    ):
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: full classifier format contract did not pass"
        )
    source_hashes = document.get("source_hashes")
    expected_source_hashes = {
        "evidence_map.csv": _sha256(EVIDENCE_MAP),
        "classifier_decisions.csv": _sha256(CLASSIFIER_DECISIONS),
        "light_screening_pipeline.py": _sha256(LIGHT_SCREENING_PIPELINE),
    }
    if not isinstance(source_hashes, dict) or any(
        source_hashes.get(name) != value for name, value in expected_source_hashes.items()
    ):
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: recorded source hashes are stale"
        )
    required_categories = document.get("required_categories")
    covered_categories = document.get("covered_categories")
    if not isinstance(required_categories, list) or not REQUIRED_VALIDATION_CATEGORIES <= set(
        required_categories
    ):
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: required validation categories are missing"
        )
    keys: set[tuple[str, str]] = set()
    case_keys: set[tuple[str, str]] = set()
    case_ids: set[str] = set()
    covered_from_cases: set[str] = set()
    pass_count = 0
    fail_count = 0
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise PipelineError(f"{_relative(CLASSIFIER_VALIDATION)}: case {index} must be an object")
        case_id = case.get("case_id")
        record_id = case.get("record_id")
        question_id = case.get("question_id")
        categories = case.get("categories")
        passed = case.get("passed")
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in case_ids
            or not isinstance(record_id, str)
            or not record_id
            or question_id not in QUESTION_ORDER
            or not isinstance(categories, list)
            or not categories
            or any(not isinstance(category, str) or not category for category in categories)
            or not isinstance(passed, bool)
        ):
            raise PipelineError(
                f"{_relative(CLASSIFIER_VALIDATION)}: case {index} has an invalid identity, category, or passed value"
            )
        key = (record_id, question_id)
        if key in case_keys or key not in classifier_by_key:
            raise PipelineError(
                f"{_relative(CLASSIFIER_VALIDATION)}: case {index} key is duplicated or absent from the classifier"
            )
        classifier = classifier_by_key[key]
        observed_fields = {
            "observed_decision": classifier["decision"],
            "observed_reason_codes": classifier["reason_codes"],
            "observed_confidence": classifier["confidence"],
            "observed_evidence_basis": classifier["evidence_basis"],
        }
        for field, expected in observed_fields.items():
            if case.get(field) != expected:
                raise PipelineError(
                    f"{_relative(CLASSIFIER_VALIDATION)}: case {index} {field} is stale"
                )
        expected_decision = case.get("expected")
        if expected_decision not in DECISION_VALUES or passed is not (
            expected_decision == classifier["decision"]
        ):
            raise PipelineError(
                f"{_relative(CLASSIFIER_VALIDATION)}: case {index} passed does not match expected versus observed"
            )
        case_ids.add(case_id)
        case_keys.add(key)
        covered_from_cases.update(categories)
        if passed:
            pass_count += 1
        else:
            fail_count += 1
            keys.add(key)
    if set(covered_categories or ()) != covered_from_cases or not REQUIRED_VALIDATION_CATEGORIES <= covered_from_cases:
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: covered category declaration is incomplete or stale"
        )
    if document.get("pass_count") != pass_count or document.get("fail_count") != fail_count:
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: pass/fail counts do not match cases"
        )
    if document.get("human_reference_rows") != 0 or document.get("independent_blinding") is not False:
        raise PipelineError(
            f"{_relative(CLASSIFIER_VALIDATION)}: human-reference limitations changed"
        )
    if document.get("release_ready") is not False:
        raise PipelineError(f"{_relative(CLASSIFIER_VALIDATION)}: release_ready must remain false")
    source["failed_case_count"] = len(keys)
    return frozenset(keys), source


def _strict_json_object(line: str, context: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PipelineError(f"{context}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(line, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"{context}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"{context}: each JSONL line must be an object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise PipelineError(f"required file is missing: {_relative(path)}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise PipelineError(f"{_relative(path)}:{line_number}: blank JSONL line")
        rows.append(_strict_json_object(line, f"{_relative(path)}:{line_number}"))
    return rows


def _normalise_question_id(question_id: str) -> str:
    canonical = QUESTION_ALIASES.get(question_id.upper(), question_id)
    if canonical not in QUESTION_ORDER:
        valid = ", ".join((*QUESTION_ALIASES, *QUESTION_ORDER))
        raise PipelineError(f"unknown question_id {question_id!r}; expected one of: {valid}")
    return canonical


def _question_index(question_id: str) -> int:
    return QUESTION_ORDER.index(question_id)


def _ordered_distribution(rows: Iterable[Mapping[str, Any]], field: str = "decision") -> dict[str, int]:
    counts = Counter(str(row[field]) for row in rows)
    return {decision: counts.get(decision, 0) for decision in DECISION_VALUES}


def _validate_decision_row(row: Mapping[str, Any], context: str) -> None:
    if row.get("decision") not in DECISION_VALUES:
        raise PipelineError(f"{context}: invalid decision {row.get('decision')!r}")
    if row.get("confidence") not in CONFIDENCE_VALUES:
        raise PipelineError(f"{context}: invalid confidence {row.get('confidence')!r}")
    if row.get("evidence_basis") not in EVIDENCE_BASES:
        raise PipelineError(f"{context}: invalid evidence_basis {row.get('evidence_basis')!r}")
    reasons = row.get("reason_codes")
    if not isinstance(reasons, list) or not reasons:
        raise PipelineError(f"{context}: reason_codes must be a non-empty array")
    if any(not isinstance(reason, str) for reason in reasons):
        raise PipelineError(f"{context}: every reason code must be a string")
    if len(reasons) != len(set(reasons)):
        raise PipelineError(f"{context}: reason_codes must not contain duplicates")
    unknown = sorted(set(reasons) - REASON_CODES)
    if unknown:
        raise PipelineError(f"{context}: unknown reason_codes {unknown}")


def _load_classifier_rows() -> list[dict[str, Any]]:
    try:
        handle = CLASSIFIER_DECISIONS.open("r", encoding="utf-8-sig", newline="")
    except FileNotFoundError as exc:
        raise PipelineError(f"required file is missing: {_relative(CLASSIFIER_DECISIONS)}") from exc
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CLASSIFIER_FIELDS:
            raise PipelineError(
                f"{_relative(CLASSIFIER_DECISIONS)}: fields must be {list(CLASSIFIER_FIELDS)}"
            )
        for line_number, source in enumerate(reader, 2):
            if None in source:
                raise PipelineError(f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}: extra CSV fields")
            question_id = source["question_id"]
            if question_id not in QUESTION_ORDER:
                raise PipelineError(
                    f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}: unknown question_id {question_id!r}"
                )
            record_id = source["record_id"].strip()
            if not record_id:
                raise PipelineError(f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}: empty record_id")
            key = (record_id, question_id)
            if key in seen:
                raise PipelineError(f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}: duplicate key {key}")
            seen.add(key)
            reasons = source["reason_codes"].split(";") if source["reason_codes"] else []
            row: dict[str, Any] = {
                "record_id": record_id,
                "question_id": question_id,
                "decision": source["decision"],
                "reason_codes": reasons,
                "confidence": source["confidence"],
                "evidence_basis": source["evidence_basis"],
            }
            _validate_decision_row(row, f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}")
            if row["evidence_basis"] == "title_only" and row["confidence"] != "low":
                raise PipelineError(
                    f"{_relative(CLASSIFIER_DECISIONS)}:{line_number}: title_only confidence must be low"
                )
            rows.append(row)
    rows.sort(key=lambda row: (_question_index(row["question_id"]), row["record_id"]))
    if len(rows) != EXPECTED_CLASSIFIER_ROWS:
        raise PipelineError(
            f"{_relative(CLASSIFIER_DECISIONS)}: expected exactly {EXPECTED_CLASSIFIER_ROWS} rows, got {len(rows)}"
        )
    return rows


def _load_evidence_rows() -> dict[tuple[str, str], dict[str, str]]:
    required = {
        "record_id",
        "title",
        "abstract",
        "publication_types",
        "mesh_terms",
        "question_ids",
    }
    try:
        handle = EVIDENCE_MAP.open("r", encoding="utf-8-sig", newline="")
    except FileNotFoundError as exc:
        raise PipelineError(f"required file is missing: {_relative(EVIDENCE_MAP)}") from exc
    result: dict[tuple[str, str], dict[str, str]] = {}
    with handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if not required <= fields:
            raise PipelineError(
                f"{_relative(EVIDENCE_MAP)}: missing fields {sorted(required - fields)}"
            )
        for line_number, row in enumerate(reader, 2):
            record_id = row["record_id"].strip()
            if not record_id:
                raise PipelineError(f"{_relative(EVIDENCE_MAP)}:{line_number}: empty record_id")
            question_ids = [value.strip() for value in row["question_ids"].split(";") if value.strip()]
            for question_id in question_ids:
                if question_id not in QUESTION_ORDER:
                    raise PipelineError(
                        f"{_relative(EVIDENCE_MAP)}:{line_number}: unknown question_id {question_id!r}"
                    )
                key = (record_id, question_id)
                if key in result:
                    raise PipelineError(f"{_relative(EVIDENCE_MAP)}:{line_number}: duplicate key {key}")
                result[key] = {
                    "record_id": record_id,
                    "question_id": question_id,
                    "title": row["title"],
                    "abstract": row["abstract"],
                    "publication_types": row["publication_types"],
                    "mesh_terms": row["mesh_terms"],
                }
    if len(result) != EXPECTED_CLASSIFIER_ROWS:
        raise PipelineError(
            f"{_relative(EVIDENCE_MAP)}: expected exactly {EXPECTED_CLASSIFIER_ROWS} question memberships, got {len(result)}"
        )
    return result


def _stable_rank(row: Mapping[str, Any]) -> str:
    material = f"{SELECTION_SEED}\0{row['question_id']}\0{row['record_id']}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _boundary_profile(
    row: Mapping[str, Any], failed_invariant_keys: frozenset[tuple[str, str]] = frozenset()
) -> tuple[int, list[str]]:
    reasons = set(row["reason_codes"])
    triggers: list[str] = []
    if (row["record_id"], row["question_id"]) in failed_invariant_keys:
        triggers.append("failed_invariant_case")
        return 0, triggers
    if row["evidence_basis"] == "title_only":
        triggers.append("title_only")
        return 1, triggers
    if row["confidence"] == "low":
        triggers.append("classifier_confidence_low")
        return 2, triggers
    if row["confidence"] == "medium":
        triggers.append("classifier_confidence_medium")
        return 3, triggers

    core = {"exposure", "outcome", "human_signal"}
    cautions = {"animal_term_present", "insufficient_abstract", "off_topic"}
    if row["decision"] == "retain":
        if reasons & cautions:
            triggers.append("retain_with_caution_signal")
            return 4, triggers
        if not core <= reasons:
            triggers.append("retain_missing_core_signal")
            return 5, triggers
    elif row["decision"] == "deprioritize":
        if reasons & core:
            triggers.append("deprioritize_with_positive_signal")
            return 4, triggers
        if "off_topic" not in reasons:
            triggers.append("deprioritize_without_off_topic_signal")
            return 5, triggers
    triggers.append("high_confidence_boundary_control")
    return 6, triggers


def _allocate_proportional(
    total: int, capacities: Mapping[Any, int], ordered_keys: Sequence[Any]
) -> dict[Any, int]:
    result = {key: 0 for key in ordered_keys}
    available = sum(max(0, capacities.get(key, 0)) for key in ordered_keys)
    total = min(max(0, total), available)
    if total == 0 or available == 0:
        return result
    floors: dict[Any, int] = {}
    remainders: list[tuple[int, int, Any]] = []
    for order_index, key in enumerate(ordered_keys):
        capacity = max(0, capacities.get(key, 0))
        numerator = total * capacity
        floor = min(capacity, numerator // available)
        floors[key] = floor
        remainders.append((numerator % available, -order_index, key))
    result.update(floors)
    leftover = total - sum(result.values())
    for _, _, key in sorted(remainders, reverse=True):
        if leftover == 0:
            break
        if result[key] < capacities.get(key, 0):
            result[key] += 1
            leftover -= 1
    if leftover:
        for key in ordered_keys:
            take = min(leftover, capacities.get(key, 0) - result[key])
            result[key] += take
            leftover -= take
            if leftover == 0:
                break
    if leftover:
        raise PipelineError("internal quota allocation did not reach requested total")
    return result


def _allocate_with_minimum(
    total: int, capacities: Mapping[Any, int], ordered_keys: Sequence[Any]
) -> dict[Any, int]:
    nonempty = [key for key in ordered_keys if capacities.get(key, 0) > 0]
    if total < len(nonempty):
        return _allocate_proportional(total, capacities, ordered_keys)
    base = {key: (1 if key in nonempty else 0) for key in ordered_keys}
    remaining_capacities = {key: capacities.get(key, 0) - base[key] for key in ordered_keys}
    extra = _allocate_proportional(total - len(nonempty), remaining_capacities, ordered_keys)
    return {key: base[key] + extra[key] for key in ordered_keys}


def _allocate_high_by_question(
    base_counts: Mapping[str, int], capacities: Mapping[str, int], needed: int
) -> dict[str, int]:
    allocation = {question: 0 for question in QUESTION_ORDER}
    needed = min(needed, sum(capacities.values()))

    rounding_needs: dict[str, int] = {}
    for question in QUESTION_ORDER:
        base = base_counts.get(question, 0)
        desired = (-base) % BATCH_SIZE if base else 0
        rounding_needs[question] = min(desired, capacities.get(question, 0))
    rounding_total = sum(rounding_needs.values())
    if rounding_total <= needed:
        allocation.update(rounding_needs)
    else:
        allocation.update(_allocate_proportional(needed, rounding_needs, QUESTION_ORDER))

    remaining = needed - sum(allocation.values())
    remaining_capacities = {
        question: capacities.get(question, 0) - allocation[question]
        for question in QUESTION_ORDER
    }
    block_capacities = {
        question: remaining_capacities[question] // BATCH_SIZE for question in QUESTION_ORDER
    }
    block_count = min(remaining // BATCH_SIZE, sum(block_capacities.values()))
    block_allocation = _allocate_proportional(block_count, block_capacities, QUESTION_ORDER)
    for question in QUESTION_ORDER:
        allocation[question] += block_allocation[question] * BATCH_SIZE

    remaining = needed - sum(allocation.values())
    remaining_capacities = {
        question: capacities.get(question, 0) - allocation[question]
        for question in QUESTION_ORDER
    }
    tail = _allocate_proportional(remaining, remaining_capacities, QUESTION_ORDER)
    for question in QUESTION_ORDER:
        allocation[question] += tail[question]
    if sum(allocation.values()) != needed:
        raise PipelineError("internal question quota allocation failed")
    return allocation


def _select_rows(
    classifier_rows: Sequence[dict[str, Any]],
    failed_invariant_keys: frozenset[tuple[str, str]] = frozenset(),
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for source in classifier_rows:
        row = dict(source)
        if row["decision"] == "uncertain":
            row["boundary_tier"] = -1
            row["selection_triggers"] = ["mandatory_classifier_uncertain"]
            if (row["record_id"], row["question_id"]) in failed_invariant_keys:
                row["selection_triggers"].append("failed_invariant_case")
        else:
            tier, triggers = _boundary_profile(row, failed_invariant_keys)
            row["boundary_tier"] = tier
            row["selection_triggers"] = triggers
        row["stable_rank"] = _stable_rank(row)
        annotated.append(row)

    mandatory = [row for row in annotated if row["decision"] == "uncertain"]
    failed_nonuncertain = [
        row
        for row in annotated
        if row["decision"] != "uncertain"
        and (row["record_id"], row["question_id"]) in failed_invariant_keys
    ]
    nonmandatory = [
        row
        for row in annotated
        if row["decision"] != "uncertain"
        and (row["record_id"], row["question_id"]) not in failed_invariant_keys
    ]
    if len(annotated) != EXPECTED_CLASSIFIER_ROWS:
        raise PipelineError(
            f"frozen adjudication selection requires {EXPECTED_CLASSIFIER_ROWS} classifier rows"
        )
    target = TARGET_ROWS
    if len(mandatory) > target:
        raise PipelineError("mandatory uncertain rows exceed the 5,000-row target")
    else:
        if len(mandatory) + len(failed_nonuncertain) > target:
            raise PipelineError(
                "mandatory uncertain rows and failed invariant cases exceed the 5,000-row target"
            )
        slots = target - len(mandatory) - len(failed_nonuncertain)
        primary = [row for row in nonmandatory if row["boundary_tier"] <= 3]
        high = [row for row in nonmandatory if row["boundary_tier"] > 3]
        chosen_primary: list[dict[str, Any]] = []
        if len(primary) <= slots:
            chosen_primary = primary
        else:
            stratum_keys = sorted(
                {
                    (
                        _question_index(row["question_id"]),
                        DECISION_VALUES.index(row["decision"]),
                        EVIDENCE_BASES.index(row["evidence_basis"]),
                        CONFIDENCE_VALUES.index(row["confidence"]),
                        row["boundary_tier"],
                    )
                    for row in primary
                }
            )
            groups: dict[tuple[int, int, int, int, int], list[dict[str, Any]]] = defaultdict(list)
            for row in primary:
                key = (
                    _question_index(row["question_id"]),
                    DECISION_VALUES.index(row["decision"]),
                    EVIDENCE_BASES.index(row["evidence_basis"]),
                    CONFIDENCE_VALUES.index(row["confidence"]),
                    row["boundary_tier"],
                )
                groups[key].append(row)
            quotas = _allocate_with_minimum(slots, {key: len(groups[key]) for key in stratum_keys}, stratum_keys)
            for key in stratum_keys:
                groups[key].sort(key=lambda row: (row["stable_rank"], row["record_id"]))
                chosen_primary.extend(groups[key][: quotas[key]])

        selected = [*mandatory, *failed_nonuncertain, *chosen_primary]
        high_needed = target - len(selected)
        if high_needed:
            base_counts = Counter(row["question_id"] for row in selected)
            high_by_question: dict[str, list[dict[str, Any]]] = {
                question: [row for row in high if row["question_id"] == question]
                for question in QUESTION_ORDER
            }
            question_quotas = _allocate_high_by_question(
                base_counts,
                {question: len(high_by_question[question]) for question in QUESTION_ORDER},
                high_needed,
            )
            for question in QUESTION_ORDER:
                candidates = high_by_question[question]
                decision_groups = {
                    decision: [row for row in candidates if row["decision"] == decision]
                    for decision in DECISION_VALUES[:2]
                }
                decision_quotas = _allocate_with_minimum(
                    question_quotas[question],
                    {decision: len(decision_groups[decision]) for decision in DECISION_VALUES[:2]},
                    DECISION_VALUES[:2],
                )
                for decision in DECISION_VALUES[:2]:
                    decision_groups[decision].sort(
                        key=lambda row: (row["boundary_tier"], row["stable_rank"], row["record_id"])
                    )
                    selected.extend(decision_groups[decision][: decision_quotas[decision]])

    selected.sort(key=lambda row: (_question_index(row["question_id"]), row["record_id"]))
    keys = [(row["record_id"], row["question_id"]) for row in selected]
    if len(keys) != len(set(keys)):
        raise PipelineError("selection contains duplicate keys")
    mandatory_keys = {
        (row["record_id"], row["question_id"])
        for row in classifier_rows
        if row["decision"] == "uncertain"
    }
    if not mandatory_keys <= set(keys):
        raise PipelineError("selection omitted classifier-uncertain rows")
    if len(mandatory_keys) <= TARGET_ROWS and len(selected) != TARGET_ROWS:
        raise PipelineError(f"selection produced {len(selected)} rows instead of {TARGET_ROWS}")
    return selected


def _selection_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_id": row["record_id"],
        "question_id": row["question_id"],
        "classifier_decision": row["decision"],
        "classifier_reason_codes": list(row["reason_codes"]),
        "classifier_confidence": row["confidence"],
        "classifier_evidence_basis": row["evidence_basis"],
        "selection_triggers": list(row["selection_triggers"]),
        "boundary_tier": row["boundary_tier"],
        "stable_rank_sha256": row["stable_rank"],
    }


def prepare() -> dict[str, Any]:
    classifier_hash_before = _sha256(CLASSIFIER_DECISIONS)
    evidence_hash_before = _sha256(EVIDENCE_MAP)
    prompt_hash = _sha256(PROMPT)
    classifier_rows = _load_classifier_rows()
    evidence_rows = _load_evidence_rows()
    failed_invariant_keys, classifier_validation_source = _load_failed_invariant_keys(
        classifier_rows
    )
    classifier_keys = {(row["record_id"], row["question_id"]) for row in classifier_rows}
    evidence_keys = set(evidence_rows)
    missing = classifier_keys - evidence_keys
    extra = evidence_keys - classifier_keys
    if missing or extra:
        raise PipelineError(
            "evidence_map/classifier key mismatch: "
            f"missing_evidence={len(missing)}, extra_evidence_memberships={len(extra)}"
        )
    unknown_failed_keys = failed_invariant_keys - classifier_keys
    if unknown_failed_keys:
        example = sorted(unknown_failed_keys)[:3]
        raise PipelineError(
            f"classifier_validation failed cases are absent from classifier layer: {example}"
        )
    for row in classifier_rows:
        source = evidence_rows[(row["record_id"], row["question_id"])]
        expected_basis = "abstract" if source["abstract"].strip() else "title_only"
        if row["evidence_basis"] != expected_basis:
            raise PipelineError(
                f"classifier/evidence basis mismatch for {(row['record_id'], row['question_id'])}"
            )

    selected = _select_rows(classifier_rows, failed_invariant_keys)
    staged_files: list[tuple[Path, bytes]] = []
    batch_entries: list[dict[str, Any]] = []
    question_manifests: list[dict[str, Any]] = []
    assignment: dict[tuple[str, str], tuple[str, int]] = {}
    for question in QUESTION_ORDER:
        OUTPUT_ROOT.joinpath(question).mkdir(parents=True, exist_ok=True)
        question_rows = [row for row in selected if row["question_id"] == question]
        batches: list[dict[str, Any]] = []
        for offset in range(0, len(question_rows), BATCH_SIZE):
            chunk = question_rows[offset : offset + BATCH_SIZE]
            batch_number = offset // BATCH_SIZE + 1
            batch_id = f"{question}-ADJ-B{batch_number:03d}"
            input_path = BATCH_ROOT / question / f"{batch_id}.jsonl"
            output_path = OUTPUT_ROOT / question / f"{batch_id}.jsonl"
            blinded_rows = [
                {field: evidence_rows[(row["record_id"], question)][field] for field in BATCH_INPUT_FIELDS}
                for row in chunk
            ]
            input_bytes = _jsonl_bytes(blinded_rows)
            batch = {
                "batch_id": batch_id,
                "input_path": _relative(input_path),
                "output_path": _relative(output_path),
                "row_count": len(chunk),
                "input_sha256": _sha256_bytes(input_bytes),
            }
            batches.append(batch)
            batch_entries.append({"question_id": question, **batch})
            staged_files.append((input_path, input_bytes))
            for row_index, row in enumerate(chunk):
                assignment[(row["record_id"], question)] = (batch_id, row_index)

        manifest_path = BATCH_ROOT / question / "manifest.json"
        manifest = {
            "schema_version": "5.0.0",
            "layer": "semantic_adjudication_input",
            "question_id": question,
            "processing_index": _question_index(question) + 1,
            "batch_size": BATCH_SIZE,
            "row_count": len(question_rows),
            "batch_count": len(batches),
            "prompt_path": _relative(PROMPT),
            "prompt_sha256": prompt_hash,
            "classifier_decisions_path": _relative(CLASSIFIER_DECISIONS),
            "classifier_decisions_sha256": classifier_hash_before,
            "evidence_map_path": _relative(EVIDENCE_MAP),
            "evidence_map_sha256": evidence_hash_before,
            "classifier_fields_excluded_from_inputs": True,
            "batches": batches,
        }
        manifest_bytes = _json_bytes(manifest)
        staged_files.append((manifest_path, manifest_bytes))
        question_manifests.append(
            {
                "question_id": question,
                "path": _relative(manifest_path),
                "sha256": _sha256_bytes(manifest_bytes),
                "row_count": len(question_rows),
                "batch_count": len(batches),
            }
        )

    selected_records: list[dict[str, Any]] = []
    for row in selected:
        record = _selection_record(row)
        batch_id, row_index = assignment[(row["record_id"], row["question_id"])]
        record["batch_id"] = batch_id
        record["batch_row_index"] = row_index
        selected_records.append(record)

    all_nonuncertain = [row for row in classifier_rows if row["decision"] != "uncertain"]
    selected_keys = {(row["record_id"], row["question_id"]) for row in selected}
    strata: dict[tuple[Any, ...], dict[str, int]] = defaultdict(lambda: {"available": 0, "selected": 0})
    for row in all_nonuncertain:
        tier, _ = _boundary_profile(row, failed_invariant_keys)
        key = (row["question_id"], row["decision"], row["evidence_basis"], row["confidence"], tier)
        strata[key]["available"] += 1
        if (row["record_id"], row["question_id"]) in selected_keys:
            strata[key]["selected"] += 1
    stratum_quotas = [
        {
            "question_id": key[0],
            "classifier_decision": key[1],
            "classifier_evidence_basis": key[2],
            "classifier_confidence": key[3],
            "boundary_tier": key[4],
            "available_rows": value["available"],
            "quota_rows": value["selected"],
            "selected_rows": value["selected"],
        }
        for key, value in sorted(
            strata.items(),
            key=lambda item: (
                _question_index(item[0][0]),
                DECISION_VALUES.index(item[0][1]),
                EVIDENCE_BASES.index(item[0][2]),
                CONFIDENCE_VALUES.index(item[0][3]),
                item[0][4],
            ),
        )
    ]

    question_quotas: dict[str, Any] = {}
    for question in QUESTION_ORDER:
        population = [row for row in classifier_rows if row["question_id"] == question]
        chosen = [row for row in selected if row["question_id"] == question]
        question_quotas[question] = {
            "candidate_rows": len(population),
            "mandatory_uncertain_rows": sum(row["decision"] == "uncertain" for row in population),
            "primary_boundary_available_rows": sum(
                row["decision"] != "uncertain"
                and (row["record_id"], row["question_id"]) not in failed_invariant_keys
                and _boundary_profile(row, failed_invariant_keys)[0] <= 3
                for row in population
            ),
            "failed_invariant_available_rows": sum(
                (row["record_id"], row["question_id"]) in failed_invariant_keys for row in population
            ),
            "failed_invariant_selected_rows": sum(
                (row["record_id"], row["question_id"]) in failed_invariant_keys for row in chosen
            ),
            "boundary_quota_rows": sum(row["decision"] != "uncertain" for row in chosen),
            "selected_rows": len(chosen),
            "batch_count": sum(entry["question_id"] == question for entry in batch_entries),
            "classifier_selected_distribution": _ordered_distribution(chosen),
        }

    mandatory_count = sum(row["decision"] == "uncertain" for row in classifier_rows)
    selected_mandatory = sum(row["decision"] == "uncertain" for row in selected)
    selection_document = {
        "schema_version": "5.0.0",
        "selection_method": "deterministic_stratified_retain_deprioritize_boundary_sample",
        "processing_order": list(QUESTION_ORDER),
        "target_rows": TARGET_ROWS,
        "candidate_rows": len(classifier_rows),
        "selected_rows": len(selected),
        "selected_count": len(selected),
        "mandatory_uncertain_available_rows": mandatory_count,
        "mandatory_uncertain_selected_rows": selected_mandatory,
        "failed_invariant_available_rows": len(failed_invariant_keys),
        "failed_invariant_selected_rows": sum(
            (row["record_id"], row["question_id"]) in failed_invariant_keys for row in selected
        ),
        "boundary_available_rows": len(all_nonuncertain),
        "boundary_selected_rows": len(selected) - selected_mandatory,
        "batch_size": BATCH_SIZE,
        "batch_count": len(batch_entries),
        "selection_seed": SELECTION_SEED,
        "deterministic_rank": "SHA-256(selection_seed, question_id, record_id)",
        "boundary_criteria": [
            {
                "tier": 0,
                "criterion": "classifier_validation.json case with passed=false; expected adjudication label remains blinded",
            },
            {"tier": 1, "criterion": "classifier evidence_basis is title_only"},
            {"tier": 2, "criterion": "classifier confidence is low with an abstract"},
            {"tier": 3, "criterion": "classifier confidence is medium"},
            {"tier": 4, "criterion": "classifier label and semantic reason signals are in tension"},
            {"tier": 5, "criterion": "classifier reason signals omit a normal boundary-separating signal"},
            {"tier": 6, "criterion": "high-confidence boundary control used only to fill the target"},
        ],
        "quota_policy": {
            "mandatory": "include every classifier-uncertain row",
            "failed_invariant_cases": "after deduplication, include every classifier_validation case with passed=false before the remaining boundary quota",
            "primary_boundary": "include title-only, low-confidence, and medium-confidence retain/deprioritize rows before high-confidence controls",
            "stratification": "question_id, classifier decision, evidence basis, confidence, and boundary tier, with deterministic proportional quotas and minority-stratum minimums when capacity permits",
            "batch_alignment": "allocate high-confidence controls to complete 200-row question batches before assigning further 200-row blocks",
            "frozen_run_contract": "require exactly 43207 candidates, 5000 selected rows, and 25 full 200-row batches",
        },
        "source_files": {
            "classifier_decisions": {
                "path": _relative(CLASSIFIER_DECISIONS),
                "sha256": classifier_hash_before,
                "row_count": len(classifier_rows),
                "immutable": True,
            },
            "evidence_map": {
                "path": _relative(EVIDENCE_MAP),
                "sha256": evidence_hash_before,
                "joined_on": ["record_id", "question_id"],
            },
            "prompt": {"path": _relative(PROMPT), "sha256": prompt_hash, "frozen": True},
            "classifier_validation": classifier_validation_source,
        },
        "classifier_distribution": _ordered_distribution(classifier_rows),
        "question_quotas": question_quotas,
        "stratum_quotas": stratum_quotas,
        "question_manifests": question_manifests,
        "batches": batch_entries,
        "selected_records": selected_records,
        "classifier_fields_excluded_from_batch_inputs": True,
        "selection_triggers_excluded_from_batch_inputs": True,
        "adjudication_input_blinded_to_classifier_labels": True,
        "agent_identity_recorded": False,
        "specific_agent_attribution_supported": False,
        "execution_receipts_recorded": False,
        "independent_blinding_ai": False,
        "independent_blinding": False,
        "release_ready": False,
    }
    if len(selected) != TARGET_ROWS:
        raise PipelineError(f"prepare requires exactly {TARGET_ROWS} selected rows")
    if len(batch_entries) != EXPECTED_ADJUDICATION_BATCHES:
        raise PipelineError(
            f"prepare requires exactly {EXPECTED_ADJUDICATION_BATCHES} full batches for {TARGET_ROWS} rows"
        )
    if any(batch["row_count"] != BATCH_SIZE for batch in batch_entries):
        raise PipelineError(f"every batch must contain exactly {BATCH_SIZE} rows")
    staged_files.append((SELECTION, _json_bytes(selection_document)))

    if _sha256(CLASSIFIER_DECISIONS) != classifier_hash_before:
        raise PipelineError("classifier_decisions.csv changed during prepare")
    if _sha256(EVIDENCE_MAP) != evidence_hash_before:
        raise PipelineError("evidence_map.csv changed during prepare")
    if _sha256(PROMPT) != prompt_hash:
        raise PipelineError("frozen semantic adjudication prompt changed during prepare")
    validation_source = selection_document["source_files"]["classifier_validation"]
    if validation_source["exists"] and _sha256(CLASSIFIER_VALIDATION) != validation_source["sha256"]:
        raise PipelineError("classifier_validation.json changed during prepare")
    if not validation_source["exists"] and CLASSIFIER_VALIDATION.exists():
        raise PipelineError("classifier_validation.json appeared during prepare")
    _atomic_replace_many(staged_files)
    return {
        "command": "prepare",
        "selected_rows": len(selected),
        "mandatory_uncertain_rows": selected_mandatory,
        "boundary_rows": len(selected) - selected_mandatory,
        "batch_size": BATCH_SIZE,
        "batch_count": len(batch_entries),
        "selection_path": _relative(SELECTION),
        "selection_sha256": _sha256(SELECTION),
        "classifier_decisions_unchanged": _sha256(CLASSIFIER_DECISIONS) == classifier_hash_before,
    }


def _legacy_status_backup_path(question_id: str) -> Path:
    return (
        PROVENANCE_CORRECTION_BACKUP_ROOT
        / "adjudication_validation"
        / f"{question_id}.json"
    )


def _selection_selected_records_sha256(selection: Mapping[str, Any]) -> str:
    return _canonical_sha256(selection.get("selected_records"))


def _selection_execution_contract_sha256(selection: Mapping[str, Any]) -> str:
    contract = {
        key: value
        for key, value in selection.items()
        if key not in SELECTION_EXECUTION_CONTRACT_EXCLUDED_FIELDS
    }
    return _canonical_sha256(contract)


def _batch_contract_sha256(batches: Sequence[Mapping[str, Any]]) -> str:
    return _canonical_sha256(list(batches))


def _batch_file_inventory_sha256(
    batches: Sequence[Mapping[str, Any]], role: str
) -> str:
    if role not in {"input", "output"}:
        raise PipelineError(f"invalid batch inventory role: {role}")
    path_field = f"{role}_path"
    hash_field = f"{role}_sha256"
    inventory: list[dict[str, Any]] = []
    for batch in batches:
        path_value = batch.get(path_field)
        sha256 = batch.get(hash_field)
        if not isinstance(path_value, str) or not _is_sha256(sha256):
            raise PipelineError(f"invalid {role} inventory entry")
        path = ROOT / path_value
        if _sha256(path) != sha256:
            raise PipelineError(f"{batch.get('batch_id')}: {role} hash changed")
        inventory.append(
            {
                "role": role,
                "path": path_value,
                "sha256": sha256,
                "bytes": path.stat().st_size,
            }
        )
    if len(inventory) != EXPECTED_ADJUDICATION_BATCHES:
        raise PipelineError(
            f"{role} inventory has {len(inventory)} files; expected {EXPECTED_ADJUDICATION_BATCHES}"
        )
    return _canonical_sha256(inventory)


def _validate_selection_structure(selection: Any) -> dict[str, Any]:
    if not isinstance(selection, dict):
        raise PipelineError(f"{_relative(SELECTION)}: root must be an object")
    if selection.get("processing_order") != list(QUESTION_ORDER):
        raise PipelineError(f"{_relative(SELECTION)}: processing_order changed")
    if selection.get("batch_size") != BATCH_SIZE:
        raise PipelineError(f"{_relative(SELECTION)}: batch_size must be {BATCH_SIZE}")
    if (
        selection.get("target_rows") != TARGET_ROWS
        or selection.get("candidate_rows") != EXPECTED_CLASSIFIER_ROWS
        or selection.get("selected_rows") != TARGET_ROWS
        or selection.get("batch_count") != EXPECTED_ADJUDICATION_BATCHES
    ):
        raise PipelineError(
            f"{_relative(SELECTION)}: frozen 43207/5000/25x200 run counts changed"
        )
    records = selection.get("selected_records")
    if (
        not isinstance(records, list)
        or selection.get("selected_rows") != len(records)
        or selection.get("selected_count") != len(records)
    ):
        raise PipelineError(f"{_relative(SELECTION)}: selected row count is inconsistent")
    keys: list[tuple[str, str]] = []
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            raise PipelineError(f"{_relative(SELECTION)}: selected row {index} is not an object")
        record_id = row.get("record_id")
        question_id = row.get("question_id")
        if not isinstance(record_id, str) or not record_id or question_id not in QUESTION_ORDER:
            raise PipelineError(f"{_relative(SELECTION)}: selected row {index} has an invalid key")
        keys.append((record_id, question_id))
    if len(keys) != len(set(keys)):
        raise PipelineError(f"{_relative(SELECTION)}: selected keys are invalid or duplicated")
    expected_order = sorted(keys, key=lambda key: (_question_index(key[1]), key[0]))
    if keys != expected_order:
        raise PipelineError(f"{_relative(SELECTION)}: selected records are not in stable question/key order")
    return selection


def _verify_selection_provenance_document(selection: Mapping[str, Any]) -> None:
    for field, expected in SELECTION_PROVENANCE_VALUES.items():
        if selection.get(field) is not expected:
            raise PipelineError(
                f"{_relative(SELECTION)}: provenance field {field} must be {expected!r}"
            )
    correction = selection.get("provenance_correction")
    if correction is None:
        return
    if not isinstance(correction, dict):
        raise PipelineError(f"{_relative(SELECTION)}: provenance_correction must be an object")
    unexpected_provenance_fields = sorted(
        PROVENANCE_CORRECTION_FORBIDDEN_SELECTION_FIELDS & set(selection)
    )
    if unexpected_provenance_fields:
        raise PipelineError(
            f"{_relative(SELECTION)}: V50-PC-001 must leave legacy-absent provenance "
            f"fields absent: {unexpected_provenance_fields}"
        )
    expected_fields = {
        "schema_version",
        "correction_id",
        "correction_type",
        "old_selection_sha256",
        "selected_records_sha256",
        "old_execution_contract_sha256",
        "new_execution_contract_sha256",
        "execution_contract_changed",
        "selected_records_changed",
        "batch_inputs_changed",
        "batch_outputs_changed",
        "allowed_selection_changes",
        "input_file_count",
        "output_file_count",
        "input_inventory_sha256",
        "output_inventory_sha256",
        "question_batch_contract_sha256",
    }
    if set(correction) != expected_fields:
        raise PipelineError(
            f"{_relative(SELECTION)}: provenance_correction fields differ from the frozen contract"
        )
    selected_records_hash = _selection_selected_records_sha256(selection)
    execution_contract_hash = _selection_execution_contract_sha256(selection)
    if selected_records_hash != LEGACY_SELECTED_RECORDS_SHA256:
        raise PipelineError(f"{_relative(SELECTION)}: selected_records canonical hash changed")
    if execution_contract_hash != LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256:
        raise PipelineError(f"{_relative(SELECTION)}: execution-contract canonical hash changed")
    expected_values = {
        "schema_version": "1.0.0",
        "correction_id": PROVENANCE_CORRECTION_ID,
        "correction_type": "metadata_only_selection_provenance_correction",
        "old_selection_sha256": LEGACY_SELECTION_SHA256,
        "selected_records_sha256": selected_records_hash,
        "old_execution_contract_sha256": execution_contract_hash,
        "new_execution_contract_sha256": execution_contract_hash,
        "execution_contract_changed": False,
        "selected_records_changed": False,
        "batch_inputs_changed": False,
        "batch_outputs_changed": False,
        "allowed_selection_changes": list(PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES),
        "input_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "output_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "input_inventory_sha256": LEGACY_INPUT_INVENTORY_SHA256,
        "output_inventory_sha256": LEGACY_OUTPUT_INVENTORY_SHA256,
    }
    for field, expected in expected_values.items():
        if correction.get(field) != expected:
            raise PipelineError(
                f"{_relative(SELECTION)}: provenance_correction {field} is invalid"
            )
    batch_contracts = correction.get("question_batch_contract_sha256")
    if (
        not isinstance(batch_contracts, dict)
        or set(batch_contracts) != set(QUESTION_ORDER)
        or any(not _is_sha256(batch_contracts.get(question)) for question in QUESTION_ORDER)
    ):
        raise PipelineError(
            f"{_relative(SELECTION)}: corrected question batch-contract hashes are invalid"
        )


def validate_selection_provenance_correction(
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the corrected canonical selection and its live 25x200 I/O contract."""
    validated = _validate_selection_structure(selection)
    _verify_selection_provenance_document(validated)
    correction = validated.get("provenance_correction")
    if not isinstance(correction, dict):
        raise PipelineError("selection provenance correction is not present")
    all_batches: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        _, batches = _validate_question_payload(validated, question)
        batch_contract_hash = _batch_contract_sha256(batches)
        if batch_contract_hash != correction["question_batch_contract_sha256"][question]:
            raise PipelineError(f"{question}: live batch contract differs from correction receipt")
        all_batches.extend(batches)
    input_inventory_hash = _batch_file_inventory_sha256(all_batches, "input")
    output_inventory_hash = _batch_file_inventory_sha256(all_batches, "output")
    if input_inventory_hash != correction["input_inventory_sha256"]:
        raise PipelineError("live 25-file input inventory differs from correction receipt")
    if output_inventory_hash != correction["output_inventory_sha256"]:
        raise PipelineError("live 25-file output inventory differs from correction receipt")
    return {
        "valid": True,
        "schema_version": correction["schema_version"],
        "correction_id": correction["correction_id"],
        "old_selection_sha256": correction["old_selection_sha256"],
        "selected_records_sha256": correction["selected_records_sha256"],
        "execution_contract_sha256": correction["new_execution_contract_sha256"],
        "input_file_count": correction["input_file_count"],
        "output_file_count": correction["output_file_count"],
        "input_inventory_sha256": input_inventory_hash,
        "output_inventory_sha256": output_inventory_hash,
        "question_batch_contract_sha256": dict(
            correction["question_batch_contract_sha256"]
        ),
        "allowed_selection_changes": list(correction["allowed_selection_changes"]),
        "independent_blinding_ai": False,
        "selected_records_changed": False,
        "execution_contract_changed": False,
        "batch_inputs_changed": False,
        "batch_outputs_changed": False,
    }


def _load_selection() -> dict[str, Any]:
    selection = _validate_selection_structure(_load_json(SELECTION))
    if selection.get("provenance_correction") is None:
        _verify_selection_provenance_document(selection)
    else:
        validate_selection_provenance_correction(selection)
    return selection


def _assert_frozen_sources(selection: Mapping[str, Any]) -> dict[str, str]:
    expected_paths = {
        "classifier_decisions": CLASSIFIER_DECISIONS,
        "evidence_map": EVIDENCE_MAP,
        "prompt": PROMPT,
    }
    hashes: dict[str, str] = {}
    sources = selection.get("source_files")
    if not isinstance(sources, dict):
        raise PipelineError(f"{_relative(SELECTION)}: source_files is missing")
    for name, path in expected_paths.items():
        source = sources.get(name)
        if not isinstance(source, dict) or source.get("path") != _relative(path):
            raise PipelineError(f"{_relative(SELECTION)}: frozen {name} path changed")
        current_hash = _sha256(path)
        if source.get("sha256") != current_hash:
            raise PipelineError(f"frozen {name} hash mismatch")
        hashes[name] = current_hash
    if sources["classifier_decisions"].get("immutable") is not True:
        raise PipelineError(f"{_relative(SELECTION)}: classifier layer is not marked immutable")
    if sources["prompt"].get("frozen") is not True:
        raise PipelineError(f"{_relative(SELECTION)}: prompt is not marked frozen")
    validation_source = sources.get("classifier_validation")
    if not isinstance(validation_source, dict):
        raise PipelineError(f"{_relative(SELECTION)}: classifier_validation source is missing")
    if validation_source.get("path") != _relative(CLASSIFIER_VALIDATION):
        raise PipelineError(f"{_relative(SELECTION)}: classifier_validation path changed")
    expected_exists = validation_source.get("exists")
    if not isinstance(expected_exists, bool) or CLASSIFIER_VALIDATION.exists() != expected_exists:
        raise PipelineError("frozen classifier_validation presence changed")
    if expected_exists:
        validation_hash = _sha256(CLASSIFIER_VALIDATION)
        if validation_source.get("sha256") != validation_hash:
            raise PipelineError("frozen classifier_validation hash mismatch")
        hashes["classifier_validation"] = validation_hash
    return hashes


def _verify_selection_against_classifier(
    selection: Mapping[str, Any], classifier_rows: Sequence[Mapping[str, Any]]
) -> None:
    by_key = {(row["record_id"], row["question_id"]): row for row in classifier_rows}
    selected_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(selection["selected_records"]):
        key = (record.get("record_id"), record.get("question_id"))
        source = by_key.get(key)
        if source is None:
            raise PipelineError(f"selection row {index}: key is absent from classifier layer: {key}")
        comparisons = {
            "classifier_decision": source["decision"],
            "classifier_reason_codes": source["reason_codes"],
            "classifier_confidence": source["confidence"],
            "classifier_evidence_basis": source["evidence_basis"],
        }
        for field, expected in comparisons.items():
            if record.get(field) != expected:
                raise PipelineError(f"selection row {index}: {field} differs from classifier layer")
        triggers = record.get("selection_triggers")
        if not isinstance(triggers, list) or not triggers or any(not isinstance(item, str) for item in triggers):
            raise PipelineError(f"selection row {index}: invalid selection_triggers")
        selected_keys.add(key)
    uncertain_keys = {
        (row["record_id"], row["question_id"])
        for row in classifier_rows
        if row["decision"] == "uncertain"
    }
    if not uncertain_keys <= selected_keys:
        raise PipelineError("selection does not include every classifier-uncertain row")
    failed_invariant_keys, _ = _load_failed_invariant_keys(classifier_rows)
    if not failed_invariant_keys <= selected_keys:
        raise PipelineError("selection does not include every failed classifier invariant case")
    selected_records_by_key = {
        (record["record_id"], record["question_id"]): record
        for record in selection["selected_records"]
    }
    for key in failed_invariant_keys:
        if "failed_invariant_case" not in selected_records_by_key[key]["selection_triggers"]:
            raise PipelineError(f"selection failed invariant case lacks trigger: {key}")
    expected_rows = _select_rows([dict(row) for row in classifier_rows], failed_invariant_keys)
    expected_keys = [(row["record_id"], row["question_id"]) for row in expected_rows]
    actual_keys = [(record["record_id"], record["question_id"]) for record in selection["selected_records"]]
    if actual_keys != expected_keys:
        raise PipelineError("selection keys/order differ from deterministic quota replay")
    for index, (record, expected) in enumerate(zip(selection["selected_records"], expected_rows)):
        replay_fields = {
            "selection_triggers": expected["selection_triggers"],
            "boundary_tier": expected["boundary_tier"],
            "stable_rank_sha256": expected["stable_rank"],
        }
        for field, value in replay_fields.items():
            if record.get(field) != value:
                raise PipelineError(f"selection row {index}: {field} differs from deterministic replay")
    expected_total = TARGET_ROWS
    if len(uncertain_keys) <= expected_total and len(selected_keys) != expected_total:
        raise PipelineError(f"selection contains {len(selected_keys)} rows; expected {expected_total}")


def _question_manifest_entry(selection: Mapping[str, Any], question_id: str) -> Mapping[str, Any]:
    entries = selection.get("question_manifests")
    if not isinstance(entries, list):
        raise PipelineError(f"{_relative(SELECTION)}: question_manifests is missing")
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("question_id") == question_id]
    if len(matches) != 1:
        raise PipelineError(f"{_relative(SELECTION)}: expected one manifest for {question_id}")
    return matches[0]


def _load_verified_question_manifest(
    selection: Mapping[str, Any], question_id: str
) -> tuple[dict[str, Any], list[list[dict[str, Any]]]]:
    entry = _question_manifest_entry(selection, question_id)
    expected_path = BATCH_ROOT / question_id / "manifest.json"
    if entry.get("path") != _relative(expected_path):
        raise PipelineError(f"{question_id}: question manifest path changed")
    if _sha256(expected_path) != entry.get("sha256"):
        raise PipelineError(f"{question_id}: question manifest hash mismatch")
    manifest = _load_json(expected_path)
    if not isinstance(manifest, dict) or manifest.get("question_id") != question_id:
        raise PipelineError(f"{question_id}: malformed question manifest")
    if manifest.get("batch_size") != BATCH_SIZE:
        raise PipelineError(f"{question_id}: batch_size must be {BATCH_SIZE}")
    sources = selection["source_files"]
    expected_manifest_values = {
        "prompt_path": sources["prompt"]["path"],
        "prompt_sha256": sources["prompt"]["sha256"],
        "classifier_decisions_path": sources["classifier_decisions"]["path"],
        "classifier_decisions_sha256": sources["classifier_decisions"]["sha256"],
        "evidence_map_path": sources["evidence_map"]["path"],
        "evidence_map_sha256": sources["evidence_map"]["sha256"],
    }
    for field, expected in expected_manifest_values.items():
        if manifest.get(field) != expected:
            raise PipelineError(f"{question_id}: manifest {field} differs from frozen selection")
    if manifest.get("classifier_fields_excluded_from_inputs") is not True:
        raise PipelineError(f"{question_id}: inputs are not declared classifier-blinded")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or manifest.get("batch_count") != len(batches):
        raise PipelineError(f"{question_id}: invalid batch list/count")
    selected_records = [
        row for row in selection["selected_records"] if row.get("question_id") == question_id
    ]
    if manifest.get("row_count") != len(selected_records) or entry.get("row_count") != len(selected_records):
        raise PipelineError(f"{question_id}: selected and manifested row counts differ")

    expected_input_paths: set[Path] = set()
    input_groups: list[list[dict[str, Any]]] = []
    combined_keys: list[tuple[str, str]] = []
    for batch_index, batch in enumerate(batches):
        if not isinstance(batch, dict):
            raise PipelineError(f"{question_id}: batch {batch_index + 1} is not an object")
        batch_id = f"{question_id}-ADJ-B{batch_index + 1:03d}"
        expected_input = BATCH_ROOT / question_id / f"{batch_id}.jsonl"
        expected_output = OUTPUT_ROOT / question_id / f"{batch_id}.jsonl"
        if batch.get("batch_id") != batch_id:
            raise PipelineError(f"{question_id}: batch IDs/order differ")
        if batch.get("input_path") != _relative(expected_input):
            raise PipelineError(f"{batch_id}: input path changed")
        if batch.get("output_path") != _relative(expected_output):
            raise PipelineError(f"{batch_id}: output path changed")
        expected_input_paths.add(expected_input.resolve())
        current_hash = _sha256(expected_input)
        if current_hash != batch.get("input_sha256"):
            raise PipelineError(f"{batch_id}: input hash mismatch")
        rows = _load_jsonl(expected_input)
        if len(rows) != batch.get("row_count"):
            raise PipelineError(f"{batch_id}: input row count differs from manifest")
        if len(rows) != BATCH_SIZE or batch.get("row_count") != BATCH_SIZE:
            raise PipelineError(f"{batch_id}: frozen run batches must contain exactly {BATCH_SIZE} rows")
        for row_index, row in enumerate(rows):
            context = f"{batch_id}:input:{row_index + 1}"
            if tuple(row) != BATCH_INPUT_FIELDS:
                raise PipelineError(f"{context}: fields/order must be {list(BATCH_INPUT_FIELDS)}")
            if row["question_id"] != question_id:
                raise PipelineError(f"{context}: question_id mismatch")
            combined_keys.append((row["record_id"], row["question_id"]))
        input_groups.append(rows)

    actual_input_paths = {
        path.resolve() for path in (BATCH_ROOT / question_id).glob("*.jsonl") if path.is_file()
    }
    if actual_input_paths != expected_input_paths:
        raise PipelineError(f"{question_id}: input JSONL file set differs from manifest")
    selected_keys = [(row["record_id"], row["question_id"]) for row in selected_records]
    if combined_keys != selected_keys:
        raise PipelineError(f"{question_id}: batch input keys/order differ from selection")
    return manifest, input_groups


def _validation_path(question_id: str) -> Path:
    return VALIDATION_ROOT / f"{question_id}.json"


def _completed_status(selection: Mapping[str, Any], question_id: str) -> dict[str, Any]:
    path = _validation_path(question_id)
    status = _load_json(path)
    if not isinstance(status, dict) or status.get("question_id") != question_id or status.get("complete") is not True:
        raise PipelineError(f"{question_id}: contract check is not complete")
    if status.get("selection_sha256") != _sha256(SELECTION):
        raise PipelineError(f"{question_id}: contract-check selection hash is stale")
    manifest, _ = _load_verified_question_manifest(selection, question_id)
    expected_rows = manifest["row_count"]
    if (
        status.get("expected_rows") != expected_rows
        or status.get("contract_checked_rows") != expected_rows
        or status.get("batch_count") != manifest["batch_count"]
    ):
        raise PipelineError(f"{question_id}: contract-check counts differ from frozen manifest")
    sources = selection["source_files"]
    expected_source_hashes = {
        "prompt_sha256": sources["prompt"]["sha256"],
        "classifier_decisions_sha256": sources["classifier_decisions"]["sha256"],
        "evidence_map_sha256": sources["evidence_map"]["sha256"],
    }
    for field, expected in expected_source_hashes.items():
        if status.get(field) != expected:
            raise PipelineError(f"{question_id}: contract-check {field} differs from frozen source")
    if status.get("agent_identity_recorded") is not False or status.get("agent_identity") is not None:
        raise PipelineError(f"{question_id}: unsupported agent identity appears in contract-check status")
    batches = status.get("batches")
    if not isinstance(batches, list) or len(batches) != len(manifest["batches"]):
        raise PipelineError(f"{question_id}: contract-check batch hashes are missing")
    for index, (batch, expected_batch) in enumerate(zip(batches, manifest["batches"])):
        if not isinstance(batch, dict):
            raise PipelineError(f"{question_id}: invalid contract-check batch entry")
        expected_fields = {
            "batch_id": expected_batch["batch_id"],
            "input_path": expected_batch["input_path"],
            "output_path": expected_batch["output_path"],
            "row_count": expected_batch["row_count"],
            "input_sha256": expected_batch["input_sha256"],
        }
        for field, expected in expected_fields.items():
            if batch.get(field) != expected:
                raise PipelineError(
                    f"{question_id}: contract-check batch {index + 1} {field} differs from manifest"
                )
        if not isinstance(batch.get("output_sha256"), str):
            raise PipelineError(f"{question_id}: contract-check batch output hash is missing")
        input_path = ROOT / batch["input_path"]
        output_path = ROOT / batch["output_path"]
        if _sha256(input_path) != batch.get("input_sha256"):
            raise PipelineError(f"{batch.get('batch_id')}: checked input changed")
        if _sha256(output_path) != batch.get("output_sha256"):
            raise PipelineError(f"{batch.get('batch_id')}: accepted output changed")
    correction = selection.get("provenance_correction")
    if correction is not None:
        recorded_batch_hash = correction["question_batch_contract_sha256"][question_id]
        if _batch_contract_sha256(batches) != recorded_batch_hash:
            raise PipelineError(f"{question_id}: corrected batch contract differs from legacy receipt")
    return status


def _validate_question_payload(
    selection: Mapping[str, Any], question_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest, input_groups = _load_verified_question_manifest(selection, question_id)
    batches = manifest["batches"]
    expected_output_paths = {(ROOT / batch["output_path"]).resolve() for batch in batches}
    actual_output_paths = {
        path.resolve() for path in (OUTPUT_ROOT / question_id).glob("*.jsonl") if path.is_file()
    }
    if actual_output_paths != expected_output_paths:
        missing = len(expected_output_paths - actual_output_paths)
        extra = len(actual_output_paths - expected_output_paths)
        raise PipelineError(f"{question_id}: output JSONL file set differs (missing={missing}, extra={extra})")

    all_outputs: list[dict[str, Any]] = []
    batch_statuses: list[dict[str, Any]] = []
    for batch, inputs in zip(batches, input_groups):
        batch_id = batch["batch_id"]
        input_path = ROOT / batch["input_path"]
        output_path = ROOT / batch["output_path"]
        outputs = _load_jsonl(output_path)
        if len(outputs) != len(inputs):
            raise PipelineError(f"{batch_id}: {len(outputs)} outputs != {len(inputs)} inputs")
        for row_index, (source, output) in enumerate(zip(inputs, outputs), 1):
            context = f"{batch_id}:output:{row_index}"
            if tuple(output) != ADJUDICATION_FIELDS:
                raise PipelineError(f"{context}: fields/order must be {list(ADJUDICATION_FIELDS)}")
            expected_key = (source["record_id"], source["question_id"])
            actual_key = (output["record_id"], output["question_id"])
            if actual_key != expected_key:
                raise PipelineError(f"{context}: key/order differs from batch input")
            _validate_decision_row(output, context)
            expected_basis = "abstract" if source["abstract"].strip() else "title_only"
            if output["evidence_basis"] != expected_basis:
                raise PipelineError(
                    f"{context}: evidence_basis must be {expected_basis!r} for the source abstract"
                )
            if expected_basis == "title_only" and output["confidence"] != "low":
                raise PipelineError(f"{context}: title-only decisions must use low confidence")
        all_outputs.extend(outputs)
        batch_statuses.append(
            {
                "batch_id": batch_id,
                "input_path": _relative(input_path),
                "output_path": _relative(output_path),
                "row_count": len(outputs),
                "input_sha256": _sha256(input_path),
                "output_sha256": _sha256(output_path),
            }
        )
    return all_outputs, batch_statuses


def validate_question(question_id: str) -> dict[str, Any]:
    question_id = _normalise_question_id(question_id)
    status_path = _validation_path(question_id)
    existing: dict[str, Any] | None = None
    if status_path.exists():
        loaded = _load_json(status_path)
        if isinstance(loaded, dict):
            existing = loaded
    try:
        selection = _load_selection()
        source_hashes = _assert_frozen_sources(selection)
        classifier_rows = _load_classifier_rows()
        _verify_selection_against_classifier(selection, classifier_rows)
        for predecessor in QUESTION_ORDER[: _question_index(question_id)]:
            _completed_status(selection, predecessor)
        outputs, batch_statuses = _validate_question_payload(selection, question_id)
        if existing and existing.get("complete") is True:
            # A completed receipt belongs to the exact frozen selection, source,
            # input, and output hashes that produced it.  Never rewrite it onto a
            # different generation merely because output bytes happen to match.
            _completed_status(selection, question_id)
            old_hashes = [batch.get("output_sha256") for batch in existing.get("batches", [])]
            new_hashes = [batch["output_sha256"] for batch in batch_statuses]
            if old_hashes != new_hashes:
                raise PipelineError(f"{question_id}: output changed after completed contract check")
        selected_records = [
            row for row in selection["selected_records"] if row["question_id"] == question_id
        ]
        classifier_distribution = {
            decision: sum(row["classifier_decision"] == decision for row in selected_records)
            for decision in DECISION_VALUES
        }
        status = {
            "schema_version": "5.0.0",
            "question_id": question_id,
            "processing_index": _question_index(question_id) + 1,
            "complete": True,
            "contract_check_method": "deterministic_schema_order_count_basis_and_hash_check",
            "expected_rows": len(selected_records),
            "contract_checked_rows": len(outputs),
            "batch_count": len(batch_statuses),
            "classifier_selected_distribution": classifier_distribution,
            "adjudication_distribution": _ordered_distribution(outputs),
            "selection_sha256": _sha256(SELECTION),
            "prompt_sha256": source_hashes["prompt"],
            "classifier_decisions_sha256": source_hashes["classifier_decisions"],
            "evidence_map_sha256": source_hashes["evidence_map"],
            "agent_identity_recorded": False,
            "agent_identity": None,
            "specific_agent_attribution_supported": False,
            "execution_receipt_recorded": False,
            "batches": batch_statuses,
        }
        if _sha256(PROMPT) != source_hashes["prompt"]:
            raise PipelineError("frozen semantic adjudication prompt changed during contract check")
        _atomic_json(status_path, status)
        return {"command": "validate-question", **status, "status_path": _relative(status_path)}
    except (PipelineError, OSError) as exc:
        if not (existing and existing.get("complete") is True):
            failure = {
                "schema_version": "5.0.0",
                "question_id": question_id,
                "processing_index": _question_index(question_id) + 1,
                "complete": False,
                "contract_check_error": str(exc),
                "agent_identity_recorded": False,
                "agent_identity": None,
            }
            _atomic_json(status_path, failure)
        raise


def _top_level_changed_fields(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> set[str]:
    missing = object()
    return {
        key
        for key in set(before) | set(after)
        if before.get(key, missing) != after.get(key, missing)
    }


def _verify_legacy_selection_document(
    selection: Any, selection_sha256: str
) -> dict[str, Any]:
    if selection_sha256 != LEGACY_SELECTION_SHA256:
        raise PipelineError(
            "provenance correction requires the exact frozen legacy selection SHA-256"
        )
    validated = _validate_selection_structure(selection)
    expected_legacy_values = {
        "independent_blinding_ai": True,
        "independent_blinding": False,
        "release_ready": False,
    }
    for field, expected in expected_legacy_values.items():
        if validated.get(field) is not expected:
            raise PipelineError(f"legacy selection field {field} is not {expected!r}")
    forbidden_fields = set(PROVENANCE_CORRECTION_FORBIDDEN_SELECTION_FIELDS) | {
        "provenance_correction"
    }
    unexpected = sorted(forbidden_fields & set(validated))
    if unexpected:
        raise PipelineError(
            f"legacy selection already contains post-correction fields: {unexpected}"
        )
    if _selection_selected_records_sha256(validated) != LEGACY_SELECTED_RECORDS_SHA256:
        raise PipelineError("legacy selected_records canonical hash mismatch")
    if (
        _selection_execution_contract_sha256(validated)
        != LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256
    ):
        raise PipelineError("legacy selection execution-contract hash mismatch")
    return validated


def _build_corrected_selection(
    legacy_selection: Mapping[str, Any],
    question_batch_contracts: Mapping[str, str],
) -> dict[str, Any]:
    corrected = dict(legacy_selection)
    corrected["independent_blinding_ai"] = False
    old_contract_hash = _selection_execution_contract_sha256(legacy_selection)
    selected_records_hash = _selection_selected_records_sha256(legacy_selection)
    corrected["provenance_correction"] = {
        "schema_version": "1.0.0",
        "correction_id": PROVENANCE_CORRECTION_ID,
        "correction_type": "metadata_only_selection_provenance_correction",
        "old_selection_sha256": LEGACY_SELECTION_SHA256,
        "selected_records_sha256": selected_records_hash,
        "old_execution_contract_sha256": old_contract_hash,
        "new_execution_contract_sha256": _selection_execution_contract_sha256(corrected),
        "execution_contract_changed": False,
        "selected_records_changed": False,
        "batch_inputs_changed": False,
        "batch_outputs_changed": False,
        "allowed_selection_changes": list(PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES),
        "input_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "output_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "input_inventory_sha256": LEGACY_INPUT_INVENTORY_SHA256,
        "output_inventory_sha256": LEGACY_OUTPUT_INVENTORY_SHA256,
        "question_batch_contract_sha256": dict(question_batch_contracts),
    }
    changed = _top_level_changed_fields(legacy_selection, corrected)
    if changed != set(PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES):
        raise PipelineError(
            f"selection provenance correction would change forbidden fields: {sorted(changed)}"
        )
    if _selection_selected_records_sha256(corrected) != selected_records_hash:
        raise PipelineError("selection provenance correction would change selected_records")
    new_contract_hash = _selection_execution_contract_sha256(corrected)
    if old_contract_hash != new_contract_hash:
        raise PipelineError("selection provenance correction would change execution contract")
    _verify_selection_provenance_document(corrected)
    return corrected


def _rebind_status_selection_sha(
    legacy_status: Mapping[str, Any], new_selection_sha256: str
) -> dict[str, Any]:
    rebound = dict(legacy_status)
    rebound["selection_sha256"] = new_selection_sha256
    changed = _top_level_changed_fields(legacy_status, rebound)
    if changed != {"selection_sha256"}:
        raise PipelineError(
            f"status provenance correction would change forbidden fields: {sorted(changed)}"
        )
    return rebound


def _hash_snapshot(paths: Iterable[Path]) -> dict[Path, str]:
    unique = {path.resolve() for path in paths}
    return {path: _sha256(path) for path in sorted(unique, key=lambda item: item.as_posix())}


def _assert_hash_snapshot(snapshot: Mapping[Path, str]) -> None:
    for path, expected in snapshot.items():
        if _sha256(path) != expected:
            raise PipelineError(f"file changed during provenance correction: {_relative(path)}")


def _adjudication_jsonl_file_set(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path.resolve() for path in root.rglob("*.jsonl") if path.is_file()),
            key=lambda path: path.as_posix(),
        )
    )


def _provenance_correction_dependency_paths(
    legacy_selection: Mapping[str, Any],
) -> list[Path]:
    paths = [
        SELECTION,
        SEMANTIC_ADJUDICATIONS,
        DECISIONS,
        ADJUDICATION_MANIFEST,
        *(_validation_path(question) for question in QUESTION_ORDER),
    ]
    for source in legacy_selection["source_files"].values():
        if isinstance(source, dict) and isinstance(source.get("path"), str):
            paths.append(ROOT / source["path"])
    for entry in legacy_selection["question_manifests"]:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.append(ROOT / entry["path"])
    for batch in legacy_selection["batches"]:
        if not isinstance(batch, dict):
            raise PipelineError("legacy selection contains a malformed batch dependency")
        for field in ("input_path", "output_path"):
            path_value = batch.get(field)
            if not isinstance(path_value, str):
                raise PipelineError(f"legacy selection batch lacks {field}")
            paths.append(ROOT / path_value)
    return paths


def _provenance_correction_dependency_snapshot(
    legacy_selection: Mapping[str, Any],
) -> dict[str, Any]:
    file_hashes = _hash_snapshot(
        _provenance_correction_dependency_paths(legacy_selection)
    )
    if file_hashes.get(SELECTION.resolve()) != LEGACY_SELECTION_SHA256:
        raise PipelineError("legacy selection changed before dependency snapshot")
    if (
        file_hashes.get(ADJUDICATION_MANIFEST.resolve())
        != LEGACY_ADJUDICATION_MANIFEST_SHA256
    ):
        raise PipelineError("legacy adjudication manifest SHA-256 mismatch")
    return {
        "file_hashes": file_hashes,
        "input_file_set": _adjudication_jsonl_file_set(BATCH_ROOT),
        "output_file_set": _adjudication_jsonl_file_set(OUTPUT_ROOT),
    }


def _assert_provenance_correction_dependency_snapshot(
    snapshot: Mapping[str, Any],
) -> None:
    file_hashes = snapshot.get("file_hashes")
    if not isinstance(file_hashes, Mapping):
        raise PipelineError("provenance-correction dependency snapshot is malformed")
    _assert_hash_snapshot(file_hashes)
    if _adjudication_jsonl_file_set(BATCH_ROOT) != snapshot.get("input_file_set"):
        raise PipelineError("adjudication input file set changed during provenance correction")
    if _adjudication_jsonl_file_set(OUTPUT_ROOT) != snapshot.get("output_file_set"):
        raise PipelineError("adjudication output file set changed during provenance correction")


def _build_recovery_receipt(
    legacy_selection_bytes: bytes,
    legacy_status_bytes: Mapping[str, bytes],
    corrected_selection_bytes: bytes,
    corrected_status_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    legacy_artifacts = [
        {
            "role": "adjudication_selection",
            "original_path": _relative(SELECTION),
            "backup_path": _relative(LEGACY_SELECTION_BACKUP),
            "sha256": _sha256_bytes(legacy_selection_bytes),
            "bytes": len(legacy_selection_bytes),
        }
    ]
    for question in QUESTION_ORDER:
        data = legacy_status_bytes[question]
        legacy_artifacts.append(
            {
                "role": "contract_check_status",
                "question_id": question,
                "original_path": _relative(_validation_path(question)),
                "backup_path": _relative(_legacy_status_backup_path(question)),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
            }
        )
    return {
        "schema_version": "1.0.0",
        "correction_id": PROVENANCE_CORRECTION_ID,
        "correction_type": "pre_correction_recovery_backups",
        "artifact_count": len(legacy_artifacts),
        "legacy_artifacts": legacy_artifacts,
        "corrected_selection": {
            "path": _relative(SELECTION),
            "sha256": _sha256_bytes(corrected_selection_bytes),
        },
        "corrected_contract_check_status_sha256": {
            question: _sha256_bytes(corrected_status_bytes[question])
            for question in QUESTION_ORDER
        },
        "selected_records_sha256": LEGACY_SELECTED_RECORDS_SHA256,
        "selection_execution_contract_sha256": LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256,
        "input_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "output_file_count": EXPECTED_ADJUDICATION_BATCHES,
        "input_inventory_sha256": LEGACY_INPUT_INVENTORY_SHA256,
        "output_inventory_sha256": LEGACY_OUTPUT_INVENTORY_SHA256,
        "allowed_selection_changes": list(PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES),
        "allowed_status_changes": ["selection_sha256"],
        "selected_records_changed": False,
        "execution_contract_changed": False,
        "batch_inputs_changed": False,
        "batch_outputs_changed": False,
    }


def _backup_publication_state(
    backup_files: Sequence[tuple[Path, bytes]], *, require_present: bool
) -> str:
    existing = [path.exists() for path, _ in backup_files]
    if any(existing) and not all(existing):
        raise PipelineError("provenance-correction recovery backup set is partial")
    if not any(existing):
        if require_present:
            raise PipelineError("provenance-correction recovery backups are missing")
        return "absent"
    for path, expected_bytes in backup_files:
        if path.read_bytes() != expected_bytes:
            raise PipelineError(
                f"existing recovery backup differs; refusing overwrite: {_relative(path)}"
            )
    return "verified_existing"


def _collect_legacy_provenance_correction() -> dict[str, Any]:
    legacy_selection_bytes = SELECTION.read_bytes()
    legacy_selection_sha256 = _sha256_bytes(legacy_selection_bytes)
    if legacy_selection_sha256 != LEGACY_SELECTION_SHA256:
        raise PipelineError(
            "provenance correction requires the exact frozen legacy selection SHA-256"
        )
    try:
        legacy_selection_document = json.loads(
            legacy_selection_bytes.decode("utf-8-sig")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError("legacy selection bytes are not valid UTF-8 JSON") from exc
    legacy_selection = _verify_legacy_selection_document(
        legacy_selection_document, legacy_selection_sha256
    )
    if _json_bytes(legacy_selection) != legacy_selection_bytes:
        raise PipelineError("legacy selection JSON serialization differs from the frozen bytes")
    dependency_snapshot = _provenance_correction_dependency_snapshot(
        legacy_selection
    )
    _assert_frozen_sources(legacy_selection)
    classifier_rows = _load_classifier_rows()
    _verify_selection_against_classifier(legacy_selection, classifier_rows)
    legacy_manifest = _load_json(ADJUDICATION_MANIFEST)
    if not _compiled_artifacts_are_current(
        legacy_selection, classifier_rows, legacy_manifest
    ):
        raise PipelineError("legacy compiled adjudication generation is not current")

    legacy_statuses: dict[str, dict[str, Any]] = {}
    legacy_status_bytes: dict[str, bytes] = {}
    current_batches_by_question: dict[str, list[dict[str, Any]]] = {}
    all_batches: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        status_path = _validation_path(question)
        status = _completed_status(legacy_selection, question)
        outputs, current_batches = _validate_question_payload(legacy_selection, question)
        if status.get("schema_version") != "5.0.0":
            raise PipelineError(f"{question}: legacy status schema_version changed")
        if status.get("processing_index") != _question_index(question) + 1:
            raise PipelineError(f"{question}: legacy status processing_index changed")
        if status.get("contract_check_method") != (
            "deterministic_schema_order_count_basis_and_hash_check"
        ):
            raise PipelineError(f"{question}: legacy contract-check method changed")
        if status.get("batches") != current_batches:
            raise PipelineError(f"{question}: legacy status batch contract changed")
        selected_records = [
            row
            for row in legacy_selection["selected_records"]
            if row["question_id"] == question
        ]
        expected_classifier_distribution = {
            decision: sum(
                row["classifier_decision"] == decision for row in selected_records
            )
            for decision in DECISION_VALUES
        }
        if status.get("classifier_selected_distribution") != expected_classifier_distribution:
            raise PipelineError(f"{question}: legacy classifier distribution changed")
        if status.get("adjudication_distribution") != _ordered_distribution(outputs):
            raise PipelineError(f"{question}: legacy adjudication distribution changed")
        data = status_path.read_bytes()
        if _json_bytes(status) != data:
            raise PipelineError(f"{question}: legacy status serialization changed")
        legacy_statuses[question] = status
        legacy_status_bytes[question] = data
        current_batches_by_question[question] = current_batches
        all_batches.extend(current_batches)

    input_inventory_hash = _batch_file_inventory_sha256(all_batches, "input")
    output_inventory_hash = _batch_file_inventory_sha256(all_batches, "output")
    if input_inventory_hash != LEGACY_INPUT_INVENTORY_SHA256:
        raise PipelineError("legacy 25-file input inventory hash mismatch")
    if output_inventory_hash != LEGACY_OUTPUT_INVENTORY_SHA256:
        raise PipelineError("legacy 25-file output inventory hash mismatch")
    question_batch_contracts = {
        question: _batch_contract_sha256(current_batches_by_question[question])
        for question in QUESTION_ORDER
    }
    corrected_selection = _build_corrected_selection(
        legacy_selection, question_batch_contracts
    )
    corrected_selection_bytes = _json_bytes(corrected_selection)
    corrected_selection_sha256 = _sha256_bytes(corrected_selection_bytes)
    corrected_statuses = {
        question: _rebind_status_selection_sha(
            legacy_statuses[question], corrected_selection_sha256
        )
        for question in QUESTION_ORDER
    }
    corrected_status_bytes = {
        question: _json_bytes(corrected_statuses[question])
        for question in QUESTION_ORDER
    }
    recovery_receipt = _build_recovery_receipt(
        legacy_selection_bytes,
        legacy_status_bytes,
        corrected_selection_bytes,
        corrected_status_bytes,
    )
    backup_files: list[tuple[Path, bytes]] = [
        (LEGACY_SELECTION_BACKUP, legacy_selection_bytes),
        *(
            (_legacy_status_backup_path(question), legacy_status_bytes[question])
            for question in QUESTION_ORDER
        ),
        (PROVENANCE_CORRECTION_RECOVERY_RECEIPT, _json_bytes(recovery_receipt)),
    ]
    staged_files: list[tuple[Path, bytes]] = [
        *(
            (_validation_path(question), corrected_status_bytes[question])
            for question in QUESTION_ORDER
        ),
        (SELECTION, corrected_selection_bytes),
    ]
    _assert_provenance_correction_dependency_snapshot(dependency_snapshot)
    return {
        "selection": corrected_selection,
        "selection_sha256": corrected_selection_sha256,
        "statuses": corrected_statuses,
        "question_batch_contracts": question_batch_contracts,
        "backup_files": backup_files,
        "staged_files": staged_files,
        "snapshot": dependency_snapshot,
    }


def _check_corrected_selection_provenance() -> dict[str, Any]:
    selection = _load_selection()
    correction = selection.get("provenance_correction")
    if not isinstance(correction, dict):
        raise PipelineError("selection provenance correction is not applied")
    source_hashes = _assert_frozen_sources(selection)
    classifier_rows = _load_classifier_rows()
    _verify_selection_against_classifier(selection, classifier_rows)
    statuses: dict[str, dict[str, Any]] = {}
    all_batches: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        status = _completed_status(selection, question)
        _, current_batches = _validate_question_payload(selection, question)
        if status.get("batches") != current_batches:
            raise PipelineError(f"{question}: corrected status batch contract changed")
        statuses[question] = status
        all_batches.extend(current_batches)
    if _batch_file_inventory_sha256(all_batches, "input") != LEGACY_INPUT_INVENTORY_SHA256:
        raise PipelineError("corrected input inventory hash mismatch")
    if _batch_file_inventory_sha256(all_batches, "output") != LEGACY_OUTPUT_INVENTORY_SHA256:
        raise PipelineError("corrected output inventory hash mismatch")

    receipt = _load_json(PROVENANCE_CORRECTION_RECOVERY_RECEIPT)
    legacy_selection_bytes = LEGACY_SELECTION_BACKUP.read_bytes()
    legacy_status_bytes = {
        question: _legacy_status_backup_path(question).read_bytes()
        for question in QUESTION_ORDER
    }
    corrected_status_bytes = {
        question: _validation_path(question).read_bytes() for question in QUESTION_ORDER
    }
    expected_receipt = _build_recovery_receipt(
        legacy_selection_bytes,
        legacy_status_bytes,
        SELECTION.read_bytes(),
        corrected_status_bytes,
    )
    backup_files: list[tuple[Path, bytes]] = [
        (LEGACY_SELECTION_BACKUP, legacy_selection_bytes),
        *(
            (_legacy_status_backup_path(question), legacy_status_bytes[question])
            for question in QUESTION_ORDER
        ),
        (PROVENANCE_CORRECTION_RECOVERY_RECEIPT, _json_bytes(expected_receipt)),
    ]
    _backup_publication_state(backup_files, require_present=True)
    if receipt != expected_receipt:
        raise PipelineError("recovery receipt differs from corrected artifacts")
    legacy_selection = _verify_legacy_selection_document(
        json.loads(legacy_selection_bytes.decode("utf-8-sig")),
        _sha256_bytes(legacy_selection_bytes),
    )
    if _top_level_changed_fields(legacy_selection, selection) != set(
        PROVENANCE_MIGRATION_ALLOWED_SELECTION_CHANGES
    ):
        raise PipelineError("corrected selection changed fields outside the migration allowlist")
    for question in QUESTION_ORDER:
        legacy_status = json.loads(legacy_status_bytes[question].decode("utf-8-sig"))
        if _top_level_changed_fields(legacy_status, statuses[question]) != {
            "selection_sha256"
        }:
            raise PipelineError(f"{question}: corrected status changed forbidden fields")
        expected_status = _rebind_status_selection_sha(
            legacy_status, _sha256(SELECTION)
        )
        if statuses[question] != expected_status:
            raise PipelineError(f"{question}: corrected status differs from exact rebind")
    return {
        "command": "correct-selection-provenance",
        "mode": "check",
        "correction_id": PROVENANCE_CORRECTION_ID,
        "selection_sha256": _sha256(SELECTION),
        "selected_rows": TARGET_ROWS,
        "batch_count": EXPECTED_ADJUDICATION_BATCHES,
        "status_count": len(statuses),
        "selected_records_sha256": LEGACY_SELECTED_RECORDS_SHA256,
        "execution_contract_sha256": LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256,
        "input_inventory_sha256": LEGACY_INPUT_INVENTORY_SHA256,
        "output_inventory_sha256": LEGACY_OUTPUT_INVENTORY_SHA256,
        "recovery_receipt_path": _relative(PROVENANCE_CORRECTION_RECOVERY_RECEIPT),
        "frozen_source_hashes": source_hashes,
        "valid": True,
        "wrote_files": False,
    }


def correct_selection_provenance(
    *, dry_run: bool = False, check: bool = False, apply: bool = False
) -> dict[str, Any]:
    if sum(mode is True for mode in (dry_run, check, apply)) != 1:
        raise PipelineError("exactly one of dry_run, check, or apply must be true")
    if check:
        return _check_corrected_selection_provenance()
    correction = _collect_legacy_provenance_correction()
    backup_state = _backup_publication_state(
        correction["backup_files"], require_present=False
    )
    if dry_run:
        return {
            "command": "correct-selection-provenance",
            "mode": "dry-run",
            "correction_id": PROVENANCE_CORRECTION_ID,
            "old_selection_sha256": LEGACY_SELECTION_SHA256,
            "new_selection_sha256": correction["selection_sha256"],
            "selected_rows": TARGET_ROWS,
            "batch_count": EXPECTED_ADJUDICATION_BATCHES,
            "status_count": len(QUESTION_ORDER),
            "selected_records_sha256": LEGACY_SELECTED_RECORDS_SHA256,
            "execution_contract_sha256": LEGACY_SELECTION_EXECUTION_CONTRACT_SHA256,
            "input_inventory_sha256": LEGACY_INPUT_INVENTORY_SHA256,
            "output_inventory_sha256": LEGACY_OUTPUT_INVENTORY_SHA256,
            "backup_state": backup_state,
            "recovery_receipt_path": _relative(PROVENANCE_CORRECTION_RECOVERY_RECEIPT),
            "would_write_file_count": len(correction["backup_files"])
            + len(correction["staged_files"]),
            "wrote_files": False,
        }
    if backup_state == "absent":
        _atomic_replace_many(correction["backup_files"])
        _backup_publication_state(
            correction["backup_files"], require_present=True
        )
        backup_state = "created"
    _assert_provenance_correction_dependency_snapshot(correction["snapshot"])
    _atomic_replace_many(correction["staged_files"])
    checked = _check_corrected_selection_provenance()
    return {
        **checked,
        "mode": "applied",
        "old_selection_sha256": LEGACY_SELECTION_SHA256,
        "backup_state": backup_state,
        "wrote_files": True,
    }


def _movement_matrix(
    classifier_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    adjudications: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    matrix = {
        source: {destination: 0 for destination in DECISION_VALUES}
        for source in DECISION_VALUES
    }
    for row in adjudications:
        key = (row["record_id"], row["question_id"])
        matrix[classifier_by_key[key]["decision"]][row["decision"]] += 1
    return matrix


def _disagreement_count(
    classifier_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    adjudications: Sequence[Mapping[str, Any]],
) -> int:
    return sum(
        classifier_by_key[(row["record_id"], row["question_id"])]["decision"] != row["decision"]
        for row in adjudications
    )


def compile_adjudications() -> dict[str, Any]:
    selection = _load_selection()
    source_hashes = _assert_frozen_sources(selection)
    classifier_rows = _load_classifier_rows()
    _verify_selection_against_classifier(selection, classifier_rows)
    selection_hash = _sha256(SELECTION)
    statuses: dict[str, dict[str, Any]] = {}
    adjudications: list[dict[str, Any]] = []
    batch_hashes: list[dict[str, Any]] = []
    for question in QUESTION_ORDER:
        status = _completed_status(selection, question)
        rows, current_batches = _validate_question_payload(selection, question)
        recorded_hashes = [batch["output_sha256"] for batch in status["batches"]]
        current_hashes = [batch["output_sha256"] for batch in current_batches]
        if recorded_hashes != current_hashes:
            raise PipelineError(f"{question}: accepted output hashes changed")
        statuses[question] = status
        adjudications.extend(rows)
        batch_hashes.extend({"question_id": question, **batch} for batch in current_batches)

    selected_keys = [
        (row["record_id"], row["question_id"]) for row in selection["selected_records"]
    ]
    adjudication_keys = [(row["record_id"], row["question_id"]) for row in adjudications]
    if adjudication_keys != selected_keys:
        raise PipelineError("compiled adjudication keys/order differ from selection")
    if len(adjudications) != selection["selected_rows"]:
        raise PipelineError("not every selected row has an accepted adjudication")

    classifier_by_key = {
        (row["record_id"], row["question_id"]): row for row in classifier_rows
    }
    adjudication_by_key = {
        (row["record_id"], row["question_id"]): row for row in adjudications
    }
    compiled_rows: list[dict[str, Any]] = []
    for classifier in classifier_rows:
        key = (classifier["record_id"], classifier["question_id"])
        source = adjudication_by_key.get(key, classifier)
        compiled_rows.append({field: source[field] for field in CLASSIFIER_FIELDS})

    semantic_document = {
        "schema_version": "5.0.0",
        "layer": "semantic_adjudication",
        "row_count": len(adjudications),
        "processing_order": list(QUESTION_ORDER),
        "selection_path": _relative(SELECTION),
        "selection_sha256": selection_hash,
        "prompt_path": _relative(PROMPT),
        "prompt_sha256": source_hashes["prompt"],
        "adjudication_input_blinded_to_classifier_labels": True,
        "agent_identity_recorded": False,
        "specific_agent_attribution_supported": False,
        "execution_receipts_recorded": False,
        "question_sequence_receipt_recorded": False,
        "records": adjudications,
    }
    semantic_bytes = _json_bytes(semantic_document)
    decisions_bytes = _csv_bytes(compiled_rows)
    disagreement_count = _disagreement_count(classifier_by_key, adjudications)
    movement = _movement_matrix(classifier_by_key, adjudications)

    classifier_selected = [classifier_by_key[key] for key in selected_keys]
    per_question: dict[str, Any] = {}
    for question in QUESTION_ORDER:
        classifier_all_q = [row for row in classifier_rows if row["question_id"] == question]
        adjudication_q = [row for row in adjudications if row["question_id"] == question]
        compiled_q = [row for row in compiled_rows if row["question_id"] == question]
        classifier_selected_q = [
            classifier_by_key[(row["record_id"], row["question_id"])] for row in adjudication_q
        ]
        disagreements_q = _disagreement_count(classifier_by_key, adjudication_q)
        per_question[question] = {
            "classifier_rows": len(classifier_all_q),
            "selected_rows": len(adjudication_q),
            "adjudicated_rows": len(adjudication_q),
            "compiled_decision_rows": len(compiled_q),
            "classifier_all_distribution": _ordered_distribution(classifier_all_q),
            "classifier_selected_distribution": _ordered_distribution(classifier_selected_q),
            "adjudication_distribution": _ordered_distribution(adjudication_q),
            "compiled_decisions_distribution": _ordered_distribution(compiled_q),
            "disagreement_count": disagreements_q,
            "disagreement_rate": disagreements_q / len(adjudication_q) if adjudication_q else 0.0,
            "movement_matrix": _movement_matrix(classifier_by_key, adjudication_q),
            "batch_count": statuses[question]["batch_count"],
        }

    manifest = {
        "schema_version": "5.0.0",
        "run_complete": True,
        "processing_order": list(QUESTION_ORDER),
        "counts": {
            "classifier_rows": len(classifier_rows),
            "selected_rows": len(selected_keys),
            "adjudicated_rows": len(adjudications),
            "unadjudicated_classifier_rows": len(classifier_rows) - len(adjudications),
            "compiled_decision_rows": len(compiled_rows),
        },
        "layers": {
            "classifier": {
                "path": _relative(CLASSIFIER_DECISIONS),
                "sha256": source_hashes["classifier_decisions"],
                "immutable": True,
                "row_count": len(classifier_rows),
            },
            "semantic_adjudication": {
                "path": _relative(SEMANTIC_ADJUDICATIONS),
                "sha256": _sha256_bytes(semantic_bytes),
                "row_count": len(adjudications),
            },
            "compiled_decisions": {
                "path": _relative(DECISIONS),
                "sha256": _sha256_bytes(decisions_bytes),
                "row_count": len(compiled_rows),
                "adjudication_labels_applied": True,
            },
        },
        "layer_distributions": {
            "classifier_all": _ordered_distribution(classifier_rows),
            "classifier_selected": _ordered_distribution(classifier_selected),
            "semantic_adjudication": _ordered_distribution(adjudications),
            "compiled_decisions": _ordered_distribution(compiled_rows),
        },
        "disagreement": {
            "count": disagreement_count,
            "rate": disagreement_count / len(adjudications) if adjudications else 0.0,
            "denominator": len(adjudications),
        },
        "movement_matrix": movement,
        "per_question": per_question,
        "batch_hashes": batch_hashes,
        "hashes": {
            "prompt_sha256": source_hashes["prompt"],
            "evidence_map_sha256": source_hashes["evidence_map"],
            "classifier_decisions_sha256": source_hashes["classifier_decisions"],
            "adjudication_selection_sha256": selection_hash,
            "semantic_adjudications_sha256": _sha256_bytes(semantic_bytes),
            "decisions_csv_sha256": _sha256_bytes(decisions_bytes),
            "contract_check_status_sha256": {
                question: _sha256(_validation_path(question)) for question in QUESTION_ORDER
            },
        },
        "classifier_decisions_unchanged": True,
        "adjudication_input_blinded_to_classifier_labels": True,
        "agent_identity_recorded": False,
        "specific_agent_attribution_supported": False,
        "execution_receipts_recorded": False,
        "question_sequence_receipt_recorded": False,
        "independent_blinding_ai": False,
        "independent_blinding": False,
        "release_ready": False,
    }
    if "classifier_validation" in source_hashes:
        manifest["hashes"]["classifier_validation_sha256"] = source_hashes[
            "classifier_validation"
        ]
    manifest_bytes = _json_bytes(manifest)
    if _sha256(CLASSIFIER_DECISIONS) != source_hashes["classifier_decisions"]:
        raise PipelineError("classifier_decisions.csv changed during compile")
    _atomic_replace_many(
        (
            (SEMANTIC_ADJUDICATIONS, semantic_bytes),
            (DECISIONS, decisions_bytes),
            (ADJUDICATION_MANIFEST, manifest_bytes),
        )
    )
    if _sha256(CLASSIFIER_DECISIONS) != source_hashes["classifier_decisions"]:
        raise PipelineError("classifier_decisions.csv changed during compile")
    return {
        "command": "compile",
        "run_complete": True,
        "adjudicated_rows": len(adjudications),
        "disagreement_count": disagreement_count,
        "disagreement_rate": manifest["disagreement"]["rate"],
        "semantic_adjudications_path": _relative(SEMANTIC_ADJUDICATIONS),
        "decisions_path": _relative(DECISIONS),
        "manifest_path": _relative(ADJUDICATION_MANIFEST),
        "manifest_sha256": _sha256(ADJUDICATION_MANIFEST),
        "classifier_decisions_unchanged": True,
        "agent_identity_recorded": False,
        "specific_agent_attribution_supported": False,
        "execution_receipts_recorded": False,
        "independent_blinding_ai": False,
        "independent_blinding": False,
        "release_ready": False,
    }


def _compiled_artifacts_are_current(
    selection: Mapping[str, Any],
    classifier_rows: Sequence[Mapping[str, Any]],
    manifest: Any,
) -> bool:
    """Reconstruct the compiled layers read-only from every accepted raw batch."""
    try:
        if not isinstance(manifest, dict) or manifest.get("run_complete") is not True:
            return False
        source_hashes = _assert_frozen_sources(selection)
        selection_hash = _sha256(SELECTION)
        expected_counts = {
            "classifier_rows": EXPECTED_CLASSIFIER_ROWS,
            "selected_rows": TARGET_ROWS,
            "adjudicated_rows": TARGET_ROWS,
            "unadjudicated_classifier_rows": EXPECTED_CLASSIFIER_ROWS - TARGET_ROWS,
            "compiled_decision_rows": EXPECTED_CLASSIFIER_ROWS,
        }
        if manifest.get("processing_order") != list(QUESTION_ORDER):
            return False
        if manifest.get("counts") != expected_counts:
            return False
        hashes = manifest.get("hashes")
        if not isinstance(hashes, dict):
            return False
        expected_hashes = {
            "prompt_sha256": source_hashes["prompt"],
            "evidence_map_sha256": source_hashes["evidence_map"],
            "classifier_decisions_sha256": source_hashes["classifier_decisions"],
            "adjudication_selection_sha256": selection_hash,
            "classifier_validation_sha256": source_hashes["classifier_validation"],
        }
        if any(hashes.get(name) != value for name, value in expected_hashes.items()):
            return False

        adjudications: list[dict[str, Any]] = []
        current_batch_hashes: list[dict[str, Any]] = []
        expected_status_hashes: dict[str, str] = {}
        for question in QUESTION_ORDER:
            accepted = _completed_status(selection, question)
            rows, batches = _validate_question_payload(selection, question)
            if [batch["output_sha256"] for batch in accepted["batches"]] != [
                batch["output_sha256"] for batch in batches
            ]:
                return False
            adjudications.extend(rows)
            current_batch_hashes.extend(
                {"question_id": question, **batch} for batch in batches
            )
            expected_status_hashes[question] = _sha256(_validation_path(question))
        if len(adjudications) != TARGET_ROWS:
            return False
        if manifest.get("batch_hashes") != current_batch_hashes:
            return False
        if hashes.get("contract_check_status_sha256") != expected_status_hashes:
            return False

        semantic = _load_json(SEMANTIC_ADJUDICATIONS)
        if (
            not isinstance(semantic, dict)
            or semantic.get("row_count") != TARGET_ROWS
            or semantic.get("selection_sha256") != selection_hash
            or semantic.get("prompt_sha256") != source_hashes["prompt"]
            or semantic.get("records") != adjudications
        ):
            return False
        semantic_hash = _sha256(SEMANTIC_ADJUDICATIONS)
        if hashes.get("semantic_adjudications_sha256") != semantic_hash:
            return False

        adjudication_by_key = {
            (row["record_id"], row["question_id"]): row for row in adjudications
        }
        compiled_rows = []
        for classifier in classifier_rows:
            key = (classifier["record_id"], classifier["question_id"])
            source = adjudication_by_key.get(key, classifier)
            compiled_rows.append({field: source[field] for field in CLASSIFIER_FIELDS})
        expected_decisions_hash = _sha256_bytes(_csv_bytes(compiled_rows))
        if expected_decisions_hash != _sha256(DECISIONS):
            return False
        if hashes.get("decisions_csv_sha256") != expected_decisions_hash:
            return False

        layers = manifest.get("layers")
        if not isinstance(layers, dict):
            return False
        expected_layers = {
            "classifier": (_relative(CLASSIFIER_DECISIONS), source_hashes["classifier_decisions"], EXPECTED_CLASSIFIER_ROWS),
            "semantic_adjudication": (_relative(SEMANTIC_ADJUDICATIONS), semantic_hash, TARGET_ROWS),
            "compiled_decisions": (_relative(DECISIONS), expected_decisions_hash, EXPECTED_CLASSIFIER_ROWS),
        }
        for name, (path, sha256, rows) in expected_layers.items():
            layer = layers.get(name)
            if not isinstance(layer, dict) or (
                layer.get("path"), layer.get("sha256"), layer.get("row_count")
            ) != (path, sha256, rows):
                return False
        return True
    except (KeyError, OSError, PipelineError, TypeError, ValueError):
        return False


def status() -> dict[str, Any]:
    result: dict[str, Any] = {
        "command": "status",
        "prepared": SELECTION.exists(),
        "processing_order": list(QUESTION_ORDER),
        "questions": {},
        "ready_to_compile": False,
        "agent_identity_recorded": False,
        "specific_agent_attribution_supported": False,
        "execution_receipts_recorded": False,
        "independent_blinding_ai": False,
        "independent_blinding": False,
        "release_ready": False,
    }
    if not SELECTION.exists():
        result["next_action"] = "prepare"
        return result
    try:
        selection = _load_selection()
        _assert_frozen_sources(selection)
        classifier_rows = _load_classifier_rows()
        _verify_selection_against_classifier(selection, classifier_rows)
        result["selected_rows"] = selection["selected_rows"]
        result["batch_count"] = selection["batch_count"]
        result["selection_sha256"] = _sha256(SELECTION)
        result["frozen_sources_valid"] = True
    except (PipelineError, OSError) as exc:
        result["frozen_sources_valid"] = False
        result["error"] = str(exc)
        result["next_action"] = "repair_frozen_inputs_before_continuing"
        return result

    complete_prefix = True
    next_question: str | None = None
    for question in QUESTION_ORDER:
        question_result: dict[str, Any]
        path = _validation_path(question)
        if not path.exists():
            question_result = {"state": "pending", "complete": False}
        else:
            try:
                current = _completed_status(selection, question)
                question_result = {
                    "state": "complete",
                    "complete": True,
                    "contract_checked_rows": current["contract_checked_rows"],
                    "batch_count": current["batch_count"],
                }
            except (PipelineError, OSError) as exc:
                loaded: dict[str, Any] = {}
                unreadable_error: str | None = None
                try:
                    candidate = _load_json(path)
                    if isinstance(candidate, dict):
                        loaded = candidate
                except (PipelineError, OSError) as status_exc:
                    unreadable_error = str(status_exc)
                question_result = {
                    "state": "failed" if loaded.get("complete") is False else "stale",
                    "complete": False,
                    "error": loaded.get("contract_check_error", unreadable_error or str(exc)),
                }
        if not question_result["complete"] and next_question is None and complete_prefix:
            next_question = question
        if not question_result["complete"]:
            complete_prefix = False
        result["questions"][question] = question_result
    result["ready_to_compile"] = all(
        result["questions"][question]["complete"] for question in QUESTION_ORDER
    )
    result["next_question"] = None if result["ready_to_compile"] else next_question
    result["next_action"] = "compile" if result["ready_to_compile"] else (
        f"validate-question --question-id {next_question}"
        if next_question
        else "complete_predecessor_contract_check"
    )
    if ADJUDICATION_MANIFEST.exists():
        try:
            manifest = _load_json(ADJUDICATION_MANIFEST)
            result["compiled"] = bool(
                result["ready_to_compile"]
                and _compiled_artifacts_are_current(selection, classifier_rows, manifest)
            )
        except (PipelineError, OSError):
            result["compiled"] = False
    else:
        result["compiled"] = False
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare, contract-check, and compile deterministic v5.0 semantic adjudications."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare", help="prepare the frozen 5,000-row blinded adjudication sample")
    validate = subparsers.add_parser("validate-question", help="contract-check one question in Q01-Q05 order")
    validate.add_argument("--question-id", required=True)
    correction = subparsers.add_parser(
        "correct-selection-provenance",
        help="one-time fail-closed correction of the frozen legacy selection provenance",
    )
    correction_mode = correction.add_mutually_exclusive_group(required=True)
    correction_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and stage the exact correction in memory without writing files",
    )
    correction_mode.add_argument(
        "--check",
        action="store_true",
        help="verify an already-applied correction and recovery backups without writing files",
    )
    correction_mode.add_argument(
        "--apply",
        action="store_true",
        help="apply the exact one-time correction after fail-closed preflight checks",
    )
    subparsers.add_parser("compile", help="compile all accepted adjudications")
    subparsers.add_parser("status", help="show preparation, contract-check, and compile state")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare()
        elif args.command == "validate-question":
            result = validate_question(args.question_id)
        elif args.command == "correct-selection-provenance":
            result = correct_selection_provenance(
                dry_run=args.dry_run,
                check=args.check,
                apply=args.apply,
            )
        elif args.command == "compile":
            result = compile_adjudications()
        else:
            result = status()
    except (PipelineError, OSError) as exc:
        print(json.dumps({"ok": False, "command": args.command, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
