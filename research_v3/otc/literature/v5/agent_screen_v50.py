"""Formal Codex-agent batch orchestrator for v5 literature screening.

The screening unit is the exact ``(record_id, question_id)`` pair.  Primary
and blinded-adjudication decisions are append-only.  ``checkpoints.jsonl`` is
an atomic materialized projection containing one final decision per eligible
screening unit.

This module deliberately performs no model inference.  It prepares immutable
evidence batches, validates JSONL returned by Codex subagents, and maintains
the auditable screening ledgers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


EXECUTION_MODE = "codex_frontier_agent_batch_v1"
SCHEMA_VERSION = "5.0.0"
QUESTION_ORDER = (
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
)
QUESTION_SHORT = {question_id: f"Q{index:02d}" for index, question_id in enumerate(QUESTION_ORDER, 1)}

DECISIONS = frozenset({"retain", "deprioritize", "uncertain"})
CONFIDENCES = frozenset({"high", "medium", "low"})
EVIDENCE_BASES = frozenset({"abstract", "title_only"})
REASON_CODES = frozenset(
    {
        "exposure_outcome_direct",
        "exposure_outcome_class_level",
        "case_report_relevant",
        "exposure_only",
        "outcome_only",
        "off_topic",
        "animal_or_in_vitro_only",
        "mechanism_or_assay_only",
        "population_mismatch",
        "route_or_formulation_mismatch",
        "insufficient_detail",
        "title_only_probable_relevant",
        "title_only_probable_off_topic",
        "title_only_insufficient",
    }
)

GATE_ORDER = (
    "source",
    "exposure",
    "route",
    "risk_context",
    "result_type",
    "attribution",
    "publication_role",
)
GATE_VALUES: dict[str, frozenset[str]] = {
    "source": frozenset(
        {
            "human_primary",
            "human_case",
            "pharmacovigilance_or_population",
            "human_evidence_review",
            "preclinical_only",
            "unclear",
        }
    ),
    "exposure": frozenset(
        {"direct_actual", "class_actual", "mention_only", "absent", "unclear"}
    ),
    "route": frozenset(
        {
            "in_scope_or_unspecified",
            "mixed_includes_in_scope",
            "out_of_scope_only",
            "unclear",
        }
    ),
    "risk_context": frozenset({"in_scope", "absent", "unclear"}),
    "result_type": frozenset(
        {
            "observed_safety_or_harm",
            "efficacy_or_pk_only",
            "process_or_method_only",
            "no_result",
            "unclear",
        }
    ),
    "attribution": frozenset(
        {
            "direct_exposure",
            "allowed_class",
            "other_drug_or_condition",
            "unlinked",
            "unclear",
        }
    ),
    "publication_role": frozenset({"case_report", "review", "other", "unclear"}),
}

AGENT_OUTPUT_FIELDS = frozenset(
    {
        "record_id",
        "question_id",
        "decision",
        "reason_codes",
        "confidence",
        "evidence_basis",
        "gates",
        "evidence_quotes",
        "uncertain_gate",
        "rationale",
    }
)
BATCH_RECORD_FIELDS = frozenset(
    {
        "record_id",
        "pmid",
        "question_id",
        "title",
        "abstract",
        "has_abstract",
        "publication_types",
        "mesh_terms",
        "input_sha256",
    }
)
STAGE_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "record_id",
        "question_id",
        "decision",
        "reason_codes",
        "confidence",
        "evidence_basis",
        "gates",
        "evidence_quotes",
        "evidence_quote_locators",
        "uncertain_gate",
        "rationale",
        "status",
        "stage",
        "batch_id",
        "agent_id",
        "execution_mode",
        "screened_at_utc",
        "prompt_sha256",
        "corpus_sha256",
        "validator_contract_sha256",
        "batch_input_sha256",
        "input_sha256",
        "agent_output_sha256",
    }
)

CANDIDATE_TRIGGER_ORDER = (
    "uncertain",
    "title_only_retain",
    "route_out_of_scope",
    "iv_only",
    "class_retain",
    "case_report_relevant",
    "bare_apap_actual",
    "retain_superset_for_multi_drug",
)

_THREAD_LOCK = threading.Lock()
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,127}$")
_STANDALONE_APAP = re.compile(r"(?<![A-Za-z0-9])APAP(?![A-Za-z0-9])", re.IGNORECASE)
_FULL_ACETAMINOPHEN_NAMES = re.compile(
    r"acetaminophen|paracetamol|tylenol|panadol|calpol|ofirmev|perfalgan",
    re.IGNORECASE,
)
_IV_TERMS = re.compile(
    r"(?<![A-Za-z0-9])(?:IV|intravenous|infusion|injection|Ofirmev|Perfalgan)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def repo_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _replace_with_retry(temporary: Path, destination: Path) -> None:
    for attempt in range(8):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.025 * (2**attempt))


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    atomic_write_bytes(path, content)


def atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    content = b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    atomic_write_bytes(path, content)


def atomic_write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    atomic_write_bytes(path, stream.getvalue().encode("utf-8-sig"))


def append_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Append a complete JSONL block while the caller holds the workspace lock."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    with path.open("ab", buffering=0) as handle:
        handle.write(payload)
        os.fsync(handle.fileno())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"required file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object in {path}")
    return value


def load_jsonl(path: Path, *, missing_ok: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if missing_ok:
            return []
        raise RuntimeError(f"required JSONL file is missing: {path}")
    content = path.read_bytes()
    if content and not content.endswith(b"\n"):
        raise RuntimeError(f"JSONL file has a non-newline torn tail: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(content.decode("utf-8").splitlines(), 1):
        if not line.strip():
            raise RuntimeError(f"blank JSONL line at {path}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid JSONL at {path}:{line_number}: {error}") from error
        if not isinstance(value, dict):
            raise RuntimeError(f"JSONL row is not an object at {path}:{line_number}")
        rows.append(value)
    return rows


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def v5(self) -> Path:
        return self.root / "research_v3" / "otc" / "literature" / "v5"

    @property
    def screening(self) -> Path:
        return self.v5 / "screening"

    @property
    def evidence_map(self) -> Path:
        return self.v5 / "evidence_map.csv"

    @property
    def corpus_manifest(self) -> Path:
        return self.v5 / "corpus_manifest.json"

    @property
    def source_prompt(self) -> Path:
        return self.v5 / "prompts" / "agent_screening_prompt_v50.md"

    @property
    def frozen_prompt(self) -> Path:
        return self.screening / "agent_screening_prompt_v50.frozen.md"

    @property
    def prompt_lock(self) -> Path:
        return self.screening / "prompt_lock.json"

    @property
    def primary_checkpoints(self) -> Path:
        return self.screening / "primary_checkpoints.jsonl"

    @property
    def adjudication_checkpoints(self) -> Path:
        return self.screening / "adjudication_checkpoints.jsonl"

    @property
    def final_checkpoints(self) -> Path:
        return self.screening / "checkpoints.jsonl"

    @property
    def candidate_list(self) -> Path:
        return self.screening / "adjudication_candidates.jsonl"

    @property
    def batches(self) -> Path:
        return self.screening / "batches.jsonl"

    @property
    def decisions_csv(self) -> Path:
        return self.screening / "decisions.csv"

    @property
    def screening_manifest(self) -> Path:
        return self.screening / "screening_manifest.json"

    @property
    def progress(self) -> Path:
        return self.root / "research_v3" / "logs" / "v50_progress.json"

    @property
    def lock_file(self) -> Path:
        return self.screening / ".agent_screen_v50.lock"

    def input_root(self, stage: str) -> Path:
        name = "inputs" if stage == "primary" else "adjudication_inputs"
        return self.screening / "agent_batches" / name

    def output_root(self, stage: str) -> Path:
        name = "outputs" if stage == "primary" else "adjudication_outputs"
        return self.screening / "agent_batches" / name

    def input_path(self, stage: str, question_id: str, batch_id: str) -> Path:
        return self.input_root(stage) / question_id / f"{batch_id}.json"

    def output_path(self, stage: str, question_id: str, batch_id: str) -> Path:
        return self.output_root(stage) / question_id / f"{batch_id}.jsonl"


SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_WORKSPACE = Workspace(SCRIPT_PATH.parents[4])


@contextmanager
def workspace_lock(workspace: Workspace, *, timeout_seconds: float = 120.0) -> Iterator[None]:
    """Cross-process byte lock plus an in-process guard.

    The one-byte sentinel is never removed or replaced.  Process termination
    releases the kernel lock; timestamps are never used to steal it.
    """

    deadline = time.monotonic() + timeout_seconds
    if not _THREAD_LOCK.acquire(timeout=timeout_seconds):
        raise TimeoutError("timed out waiting for the in-process screening lock")
    handle = None
    acquired = False
    try:
        workspace.screening.mkdir(parents=True, exist_ok=True)
        handle = workspace.lock_file.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        while not acquired:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for the screening workspace lock")
                time.sleep(0.05)
        yield
    finally:
        if handle is not None:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        _THREAD_LOCK.release()


@dataclass(frozen=True)
class Corpus:
    sha256: str
    units: dict[tuple[str, str], dict[str, Any]]
    per_question: dict[str, tuple[tuple[str, str], ...]]

    @property
    def total_units(self) -> int:
        return len(self.units)


def _split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _parse_bool(value: str, context: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise RuntimeError(f"{context}: has_abstract must be true or false, got {value!r}")


def load_corpus(workspace: Workspace) -> Corpus:
    path = workspace.evidence_map
    if not path.is_file():
        raise RuntimeError(f"evidence map is missing: {path}")
    corpus_sha = sha256_file(path)
    required = {
        "record_id",
        "pmid",
        "title",
        "abstract",
        "has_abstract",
        "publication_types",
        "mesh_terms",
        "question_ids",
        "input_sha256",
    }
    units: dict[tuple[str, str], dict[str, Any]] = {}
    per_question_lists: dict[str, list[tuple[str, str]]] = {qid: [] for qid in QUESTION_ORDER}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"{path}: missing required columns {sorted(missing)}")
        for row_number, row in enumerate(reader, 2):
            record_id = (row.get("record_id") or "").strip()
            if not record_id:
                raise RuntimeError(f"{path}:{row_number}: empty record_id")
            source_input_sha = (row.get("input_sha256") or "").strip().lower()
            if not _HEX64.fullmatch(source_input_sha):
                raise RuntimeError(f"{path}:{row_number}: invalid input_sha256")
            has_abstract = _parse_bool(row.get("has_abstract") or "", f"{path}:{row_number}")
            abstract = row.get("abstract") or ""
            if has_abstract != bool(abstract.strip()):
                raise RuntimeError(
                    f"{path}:{row_number}: has_abstract disagrees with abstract content"
                )
            question_ids = _split_semicolon(row.get("question_ids") or "")
            if not question_ids:
                raise RuntimeError(f"{path}:{row_number}: no question_ids")
            unknown = sorted(set(question_ids) - set(QUESTION_ORDER))
            if unknown:
                raise RuntimeError(f"{path}:{row_number}: unknown question_ids {unknown}")
            for question_id in question_ids:
                key = (record_id, question_id)
                if key in units:
                    raise RuntimeError(f"duplicate corpus screening unit {key}")
                unit = {
                    "record_id": record_id,
                    "pmid": (row.get("pmid") or "").strip(),
                    "question_id": question_id,
                    "title": row.get("title") or "",
                    "abstract": abstract,
                    "has_abstract": has_abstract,
                    "publication_types": _split_semicolon(row.get("publication_types") or ""),
                    "mesh_terms": _split_semicolon(row.get("mesh_terms") or ""),
                    "input_sha256": source_input_sha,
                }
                units[key] = unit
                per_question_lists[question_id].append(key)
    for question_id, keys in per_question_lists.items():
        keys.sort(key=lambda key: (key[0].casefold(), key[0]))

    if workspace.corpus_manifest.is_file():
        manifest = load_json(workspace.corpus_manifest)
        manifest_evidence = manifest.get("evidence_map", {})
        if manifest_evidence.get("sha256") != corpus_sha:
            raise RuntimeError("corpus_manifest.json evidence-map hash mismatch")
        expected_counts = manifest.get("per_question_membership_rows", {})
        for question_id in QUESTION_ORDER:
            if question_id in expected_counts and int(expected_counts[question_id]) != len(
                per_question_lists[question_id]
            ):
                raise RuntimeError(f"corpus manifest count mismatch for {question_id}")
    return Corpus(
        sha256=corpus_sha,
        units=units,
        per_question={qid: tuple(keys) for qid, keys in per_question_lists.items()},
    )


def validator_contract() -> dict[str, Any]:
    return {
        "schema_version": "agent-screen-validator-v2",
        "agent_output_fields": sorted(AGENT_OUTPUT_FIELDS),
        "decision_values": sorted(DECISIONS),
        "reason_code_values": sorted(REASON_CODES),
        "confidence_values": sorted(CONFIDENCES),
        "evidence_basis_values": sorted(EVIDENCE_BASES),
        "gate_order": list(GATE_ORDER),
        "gate_values": {key: sorted(GATE_VALUES[key]) for key in GATE_ORDER},
        "mapping": "frozen_prompt_priority_1_through_11_then_title_only_overlay",
        "adjudication_resolution": "same_decision_uses_second_pass_else_conservative_uncertain",
        "candidate_policy": (
            "all_uncertain,title-only-retain,out-of-scope-route,class-retain,case-report,"
            "bare-APAP-actual,and-all-retain-superset-to-guarantee-multi-drug-retain"
        ),
    }


def validator_contract_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(validator_contract()))


def validate_prompt_lock(workspace: Workspace, corpus: Corpus | None = None) -> dict[str, Any]:
    lock = load_json(workspace.prompt_lock)
    if lock.get("execution_mode") != EXECUTION_MODE:
        raise RuntimeError("prompt lock execution_mode mismatch")
    prompt_sha = str(lock.get("prompt_sha256", ""))
    corpus_sha = str(lock.get("corpus_sha256", ""))
    if not _HEX64.fullmatch(prompt_sha) or not _HEX64.fullmatch(corpus_sha):
        raise RuntimeError("prompt lock contains an invalid prompt/corpus hash")
    if not workspace.frozen_prompt.is_file() or sha256_file(workspace.frozen_prompt) != prompt_sha:
        raise RuntimeError("frozen prompt is absent or differs from prompt_lock.json")
    if lock.get("validator_contract_sha256") != validator_contract_sha256():
        raise RuntimeError("validator contract differs from the frozen prompt lock")
    if lock.get("orchestrator_sha256") != sha256_file(SCRIPT_PATH):
        raise RuntimeError("orchestrator source differs from the frozen prompt lock")
    if tuple(lock.get("question_order", [])) != QUESTION_ORDER:
        raise RuntimeError("prompt lock question order mismatch")
    if corpus is None:
        corpus = load_corpus(workspace)
    if corpus.sha256 != corpus_sha:
        raise RuntimeError("current evidence_map.csv differs from the frozen corpus hash")
    return lock


def freeze(workspace: Workspace) -> dict[str, Any]:
    with workspace_lock(workspace):
        corpus = load_corpus(workspace)
        if workspace.prompt_lock.exists():
            lock = validate_prompt_lock(workspace, corpus)
            lock = dict(lock)
            lock["idempotent"] = True
            lock["source_prompt_current_sha256"] = (
                sha256_file(workspace.source_prompt) if workspace.source_prompt.is_file() else None
            )
            lock["source_prompt_matches_frozen"] = (
                lock["source_prompt_current_sha256"] == lock["prompt_sha256"]
            )
            return lock
        active_artifacts = [
            workspace.primary_checkpoints,
            workspace.adjudication_checkpoints,
            workspace.final_checkpoints,
            workspace.batches,
            workspace.screening_manifest,
        ]
        present = [str(path) for path in active_artifacts if path.exists()]
        if present:
            raise RuntimeError(
                "cannot freeze without a prompt lock while active formal artifacts exist: "
                + ", ".join(present)
            )
        if workspace.frozen_prompt.exists():
            raise RuntimeError("frozen prompt exists without prompt_lock.json; refusing overwrite")
        if not workspace.source_prompt.is_file():
            raise RuntimeError(f"source screening prompt is missing: {workspace.source_prompt}")
        prompt_bytes = workspace.source_prompt.read_bytes()
        prompt_sha = sha256_bytes(prompt_bytes)
        atomic_write_bytes(workspace.frozen_prompt, prompt_bytes)
        lock = {
            "schema_version": SCHEMA_VERSION,
            "phase": "C",
            "execution_mode": EXECUTION_MODE,
            "frozen_at_utc": utc_now(),
            "source_prompt_path": repo_relative(workspace.source_prompt, workspace.root),
            "frozen_prompt_path": repo_relative(workspace.frozen_prompt, workspace.root),
            "prompt_sha256": prompt_sha,
            "corpus_path": repo_relative(workspace.evidence_map, workspace.root),
            "corpus_sha256": corpus.sha256,
            "corpus_manifest_path": repo_relative(workspace.corpus_manifest, workspace.root),
            "corpus_manifest_sha256": (
                sha256_file(workspace.corpus_manifest) if workspace.corpus_manifest.is_file() else None
            ),
            "validator_contract": validator_contract(),
            "validator_contract_sha256": validator_contract_sha256(),
            "orchestrator_path": repo_relative(SCRIPT_PATH, DEFAULT_WORKSPACE.root)
            if workspace.root.resolve() == DEFAULT_WORKSPACE.root.resolve()
            else None,
            "orchestrator_sha256": sha256_file(SCRIPT_PATH),
            "question_order": list(QUESTION_ORDER),
            "screening_units": corpus.total_units,
            "independent_blinding": False,
            "ai_second_pass_blinded": True,
            "release_ready": False,
        }
        atomic_write_json(workspace.prompt_lock, lock)
        return lock


def _batch_record(unit: Mapping[str, Any]) -> dict[str, Any]:
    return {field: unit[field] for field in (
        "record_id",
        "pmid",
        "question_id",
        "title",
        "abstract",
        "has_abstract",
        "publication_types",
        "mesh_terms",
        "input_sha256",
    )}


def _batch_base(
    stage: str,
    question_id: str,
    records: Sequence[Mapping[str, Any]],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_kind": stage,
        "execution_mode": EXECUTION_MODE,
        "question_id": question_id,
        "prompt_sha256": lock["prompt_sha256"],
        "corpus_sha256": lock["corpus_sha256"],
        "validator_contract_sha256": lock["validator_contract_sha256"],
        "records": [dict(record) for record in records],
    }


def build_batch_payload(
    stage: str,
    question_id: str,
    records: Sequence[Mapping[str, Any]],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    base = _batch_base(stage, question_id, records, lock)
    input_sha = sha256_bytes(canonical_json_bytes(base))
    prefix = "AGP" if stage == "primary" else "AGA"
    batch_id = f"{prefix}-{QUESTION_SHORT[question_id]}-{input_sha[:16]}"
    return {
        **base,
        "batch_id": batch_id,
        "record_count": len(records),
        "batch_input_sha256": input_sha,
    }


def validate_batch_payload(
    payload: Mapping[str, Any],
    *,
    expected_stage: str,
    corpus: Corpus,
    lock: Mapping[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    context = str(path) if path else "batch payload"
    expected_top = {
        "schema_version",
        "batch_kind",
        "execution_mode",
        "question_id",
        "prompt_sha256",
        "corpus_sha256",
        "validator_contract_sha256",
        "records",
        "batch_id",
        "record_count",
        "batch_input_sha256",
    }
    if set(payload) != expected_top:
        raise RuntimeError(f"{context}: batch fields mismatch: {sorted(set(payload) ^ expected_top)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise RuntimeError(f"{context}: schema_version mismatch")
    if payload["batch_kind"] != expected_stage:
        raise RuntimeError(f"{context}: batch_kind mismatch")
    question_id = payload["question_id"]
    if question_id not in QUESTION_ORDER:
        raise RuntimeError(f"{context}: invalid question_id")
    for field in ("execution_mode", "prompt_sha256", "corpus_sha256", "validator_contract_sha256"):
        expected = EXECUTION_MODE if field == "execution_mode" else lock[field]
        if payload[field] != expected:
            raise RuntimeError(f"{context}: {field} mismatch")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"{context}: records must be a nonempty list")
    if payload["record_count"] != len(records):
        raise RuntimeError(f"{context}: record_count mismatch")
    keys: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != BATCH_RECORD_FIELDS:
            raise RuntimeError(f"{context}: record {index} fields mismatch")
        key = (record["record_id"], record["question_id"])
        if key[1] != question_id or key not in corpus.units:
            raise RuntimeError(f"{context}: record {index} is not a corpus unit for the batch question")
        if record != _batch_record(corpus.units[key]):
            raise RuntimeError(f"{context}: record {index} differs from evidence_map.csv")
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{context}: duplicate screening units")
    base = _batch_base(expected_stage, question_id, records, lock)
    expected_input_sha = sha256_bytes(canonical_json_bytes(base))
    expected_prefix = "AGP" if expected_stage == "primary" else "AGA"
    expected_batch_id = f"{expected_prefix}-{QUESTION_SHORT[question_id]}-{expected_input_sha[:16]}"
    if payload["batch_input_sha256"] != expected_input_sha or payload["batch_id"] != expected_batch_id:
        raise RuntimeError(f"{context}: deterministic batch hash/id mismatch")
    return dict(payload)


def load_batch_inputs(
    workspace: Workspace,
    stage: str,
    corpus: Corpus,
    lock: Mapping[str, Any],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    occupied: dict[tuple[str, str], str] = {}
    root = workspace.input_root(stage)
    if not root.exists():
        return result
    for path in sorted(root.glob("*/*.json")):
        payload = validate_batch_payload(
            load_json(path), expected_stage=stage, corpus=corpus, lock=lock, path=path
        )
        batch_id = payload["batch_id"]
        if path.stem != batch_id:
            raise RuntimeError(f"batch filename/id mismatch: {path}")
        if batch_id in result:
            raise RuntimeError(f"duplicate batch_id across input files: {batch_id}")
        for record in payload["records"]:
            key = (record["record_id"], record["question_id"])
            if key in occupied:
                raise RuntimeError(
                    f"screening unit {key} is reserved by both {occupied[key]} and {batch_id}"
                )
            occupied[key] = batch_id
        result[batch_id] = (path, payload)
    return result


def _expected_mapping(
    gates: Mapping[str, str], evidence_basis: str, quotes: Mapping[str, str]
) -> tuple[str, list[str], str]:
    actual_exposure = gates["exposure"] in {"direct_actual", "class_actual"}
    rule_reason: str | None = None
    decision: str | None = None
    confidence: str | None = None

    if gates["source"] == "preclinical_only":
        decision, rule_reason, confidence = "deprioritize", "animal_or_in_vitro_only", "high"
    elif actual_exposure and gates["route"] == "out_of_scope_only":
        decision, rule_reason, confidence = "deprioritize", "route_or_formulation_mismatch", "high"
    elif actual_exposure and gates["risk_context"] == "absent":
        decision, rule_reason, confidence = "deprioritize", "population_mismatch", "medium"
    elif actual_exposure and gates["result_type"] == "process_or_method_only":
        decision, rule_reason, confidence = "deprioritize", "mechanism_or_assay_only", "high"
    elif actual_exposure and gates["result_type"] in {"efficacy_or_pk_only", "no_result"}:
        decision, rule_reason, confidence = "deprioritize", "exposure_only", "high"
    elif actual_exposure and gates["attribution"] in {"other_drug_or_condition", "unlinked"}:
        decision, rule_reason, confidence = "deprioritize", "exposure_only", "high"
    elif gates["exposure"] in {"absent", "mention_only"} and gates[
        "result_type"
    ] == "observed_safety_or_harm":
        decision, rule_reason, confidence = "deprioritize", "outcome_only", "medium"
    elif gates["exposure"] in {"absent", "mention_only"} and gates[
        "result_type"
    ] not in {"observed_safety_or_harm", "unclear"}:
        decision, rule_reason, confidence = "deprioritize", "off_topic", "high"
    elif (
        gates["exposure"] == "direct_actual"
        and gates["route"] in {"in_scope_or_unspecified", "mixed_includes_in_scope"}
        and gates["risk_context"] == "in_scope"
        and gates["result_type"] == "observed_safety_or_harm"
        and gates["attribution"] == "direct_exposure"
    ):
        decision, rule_reason = "retain", "exposure_outcome_direct"
        required_quotes = ("source", "exposure", "risk_context", "result_type", "attribution")
        confidence = "high" if all(quotes[name] for name in required_quotes) else "medium"
    elif (
        gates["exposure"] == "class_actual"
        and gates["route"] in {"in_scope_or_unspecified", "mixed_includes_in_scope"}
        and gates["risk_context"] == "in_scope"
        and gates["result_type"] == "observed_safety_or_harm"
        and gates["attribution"] == "allowed_class"
    ):
        decision, rule_reason = "retain", "exposure_outcome_class_level"
        required_quotes = ("source", "exposure", "risk_context", "result_type", "attribution")
        confidence = "high" if all(quotes[name] for name in required_quotes) else "medium"
    elif any(gates[name] == "unclear" for name in GATE_ORDER):
        decision, rule_reason, confidence = "uncertain", "insufficient_detail", "medium"
    else:
        raise RuntimeError(
            "gate combination is not mapped by the frozen deterministic priority rules"
        )

    assert decision is not None and rule_reason is not None and confidence is not None
    reasons = [rule_reason]
    if decision == "retain" and gates["publication_role"] == "case_report":
        reasons.append("case_report_relevant")

    if evidence_basis == "title_only":
        confidence = "low"
        if decision == "retain":
            exposure_reason = (
                "exposure_outcome_class_level"
                if gates["exposure"] == "class_actual"
                else "exposure_outcome_direct"
            )
            reasons = ["title_only_probable_relevant", exposure_reason]
            if gates["publication_role"] == "case_report":
                reasons.append("case_report_relevant")
        elif decision == "uncertain":
            reasons = ["title_only_insufficient"]
        else:
            reasons = ["title_only_probable_off_topic"]
            if rule_reason == "route_or_formulation_mismatch":
                reasons.append("route_or_formulation_mismatch")
    return decision, reasons, confidence


def _quote_locator(quote: str, unit: Mapping[str, Any]) -> str:
    if not quote:
        return ""
    fields: list[tuple[str, str]] = [
        ("title", unit["title"]),
        ("abstract", unit["abstract"]),
    ]
    fields.extend((f"publication_types:{index}", value) for index, value in enumerate(unit["publication_types"]))
    fields.extend((f"mesh_terms:{index}", value) for index, value in enumerate(unit["mesh_terms"]))
    for field, value in fields:
        offset = value.find(quote)
        if offset >= 0:
            return f"{field}:chars:{offset}-{offset + len(quote)}"
    raise RuntimeError(f"evidence quote is not an exact source substring: {quote!r}")


def validate_agent_decision(
    value: Mapping[str, Any], unit: Mapping[str, Any], *, context: str
) -> tuple[dict[str, Any], dict[str, str]]:
    if set(value) != AGENT_OUTPUT_FIELDS:
        raise RuntimeError(
            f"{context}: output fields mismatch: {sorted(set(value) ^ AGENT_OUTPUT_FIELDS)}"
        )
    key = (value.get("record_id"), value.get("question_id"))
    expected_key = (unit["record_id"], unit["question_id"])
    if key != expected_key:
        raise RuntimeError(f"{context}: output key {key} != expected {expected_key}")
    decision = value["decision"]
    confidence = value["confidence"]
    evidence_basis = value["evidence_basis"]
    if decision not in DECISIONS:
        raise RuntimeError(f"{context}: invalid decision {decision!r}")
    if confidence not in CONFIDENCES:
        raise RuntimeError(f"{context}: invalid confidence {confidence!r}")
    expected_basis = "abstract" if unit["has_abstract"] else "title_only"
    if evidence_basis != expected_basis:
        raise RuntimeError(
            f"{context}: evidence_basis {evidence_basis!r} != {expected_basis!r}"
        )

    gates = value["gates"]
    quotes = value["evidence_quotes"]
    if not isinstance(gates, dict) or tuple(gates.keys()) != GATE_ORDER:
        if not isinstance(gates, dict) or set(gates) != set(GATE_ORDER):
            raise RuntimeError(f"{context}: gates must contain exactly {list(GATE_ORDER)}")
        gates = {name: gates[name] for name in GATE_ORDER}
    if not isinstance(quotes, dict) or set(quotes) != set(GATE_ORDER):
        raise RuntimeError(f"{context}: evidence_quotes must contain exactly {list(GATE_ORDER)}")
    quotes = {name: quotes[name] for name in GATE_ORDER}
    locators: dict[str, str] = {}
    for name in GATE_ORDER:
        if gates[name] not in GATE_VALUES[name]:
            raise RuntimeError(f"{context}: invalid {name} gate value {gates[name]!r}")
        quote = quotes[name]
        if not isinstance(quote, str):
            raise RuntimeError(f"{context}: evidence quote for {name} must be a string")
        locators[name] = _quote_locator(quote, unit)

    uncertain_gate = value["uncertain_gate"]
    if not isinstance(uncertain_gate, list) or any(not isinstance(item, str) for item in uncertain_gate):
        raise RuntimeError(f"{context}: uncertain_gate must be a string list")
    if len(uncertain_gate) != len(set(uncertain_gate)):
        raise RuntimeError(f"{context}: uncertain_gate contains duplicates")
    if any(name not in GATE_ORDER for name in uncertain_gate):
        raise RuntimeError(f"{context}: uncertain_gate contains an unknown gate")
    if any(gates[name] != "unclear" for name in uncertain_gate):
        raise RuntimeError(f"{context}: uncertain_gate names a gate that is not unclear")
    actual_unclear_gates = [name for name in GATE_ORDER if gates[name] == "unclear"]
    if decision == "uncertain":
        if uncertain_gate != actual_unclear_gates:
            raise RuntimeError(
                f"{context}: uncertain_gate must list every unclear gate in canonical order; "
                f"expected {actual_unclear_gates}"
            )
    elif uncertain_gate:
        raise RuntimeError(f"{context}: non-uncertain decision requires an empty uncertain_gate")

    reason_codes = value["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or not 1 <= len(reason_codes) <= 3
        or any(not isinstance(item, str) for item in reason_codes)
        or len(reason_codes) != len(set(reason_codes))
    ):
        raise RuntimeError(f"{context}: reason_codes must contain 1-3 unique strings")
    unknown_reasons = sorted(set(reason_codes) - REASON_CODES)
    if unknown_reasons:
        raise RuntimeError(f"{context}: unknown reason_codes {unknown_reasons}")

    rationale = value["rationale"]
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 1000:
        raise RuntimeError(f"{context}: rationale must be a nonempty string of at most 1000 chars")
    if "\n" in rationale or "\r" in rationale:
        raise RuntimeError(f"{context}: rationale must be one physical line")

    expected_decision, expected_reasons, expected_confidence = _expected_mapping(
        gates, evidence_basis, quotes
    )
    if decision != expected_decision:
        raise RuntimeError(
            f"{context}: decision {decision!r} disagrees with gate replay {expected_decision!r}"
        )
    if reason_codes != expected_reasons:
        raise RuntimeError(
            f"{context}: reason_codes {reason_codes!r} disagree with gate replay {expected_reasons!r}"
        )
    allowed_confidences = (
        {"high", "medium"}
        if expected_decision == "retain" and evidence_basis == "abstract"
        else {expected_confidence}
    )
    if confidence not in allowed_confidences:
        raise RuntimeError(
            f"{context}: confidence {confidence!r} disagrees with gate replay "
            f"{sorted(allowed_confidences)!r}"
        )
    canonical = {
        "record_id": unit["record_id"],
        "question_id": unit["question_id"],
        "decision": decision,
        "reason_codes": list(reason_codes),
        "confidence": confidence,
        "evidence_basis": evidence_basis,
        "gates": {name: gates[name] for name in GATE_ORDER},
        "evidence_quotes": {name: quotes[name] for name in GATE_ORDER},
        "uncertain_gate": list(uncertain_gate),
        "rationale": rationale.strip(),
    }
    return canonical, locators


def _agent_output_rows(path: Path) -> tuple[list[dict[str, Any]], str]:
    if not path.is_file():
        raise RuntimeError(f"agent output is missing: {path}")
    raw_sha = sha256_file(path)
    return load_jsonl(path, missing_ok=False), raw_sha


def _canonical_stage_row(
    decision: Mapping[str, Any],
    locators: Mapping[str, str],
    *,
    stage: str,
    batch: Mapping[str, Any],
    agent_id: str,
    output_sha: str,
    unit: Mapping[str, Any],
    screened_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        **dict(decision),
        "evidence_quote_locators": dict(locators),
        "status": "screened",
        "stage": stage,
        "batch_id": batch["batch_id"],
        "agent_id": agent_id,
        "execution_mode": EXECUTION_MODE,
        "screened_at_utc": screened_at,
        "prompt_sha256": batch["prompt_sha256"],
        "corpus_sha256": batch["corpus_sha256"],
        "validator_contract_sha256": batch["validator_contract_sha256"],
        "batch_input_sha256": batch["batch_input_sha256"],
        "input_sha256": unit["input_sha256"],
        "agent_output_sha256": output_sha,
    }


def _stage_path(workspace: Workspace, stage: str) -> Path:
    return workspace.primary_checkpoints if stage == "primary" else workspace.adjudication_checkpoints


def validate_stage_checkpoints(
    workspace: Workspace,
    stage: str,
    corpus: Corpus,
    lock: Mapping[str, Any],
    batches: Mapping[str, tuple[Path, dict[str, Any]]] | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    if batches is None:
        batches = load_batch_inputs(workspace, stage, corpus, lock)
    rows = load_jsonl(_stage_path(workspace, stage))
    result: dict[tuple[str, str], dict[str, Any]] = {}
    events = load_jsonl(workspace.batches)
    committed_by_id = _batch_event_commits(stage, events)
    for line_number, row in enumerate(rows, 1):
        context = f"{_stage_path(workspace, stage)}:{line_number}"
        if set(row) != STAGE_CHECKPOINT_FIELDS:
            raise RuntimeError(f"{context}: canonical checkpoint fields mismatch")
        if row.get("schema_version") != SCHEMA_VERSION:
            raise RuntimeError(f"{context}: schema_version mismatch")
        if row.get("stage") != stage or row.get("status") != "screened":
            raise RuntimeError(f"{context}: stage/status mismatch")
        if row.get("execution_mode") != EXECUTION_MODE:
            raise RuntimeError(f"{context}: execution_mode mismatch")
        for field in ("prompt_sha256", "corpus_sha256", "validator_contract_sha256"):
            if row.get(field) != lock[field]:
                raise RuntimeError(f"{context}: {field} mismatch")
        key = (row.get("record_id"), row.get("question_id"))
        if key not in corpus.units:
            raise RuntimeError(f"{context}: checkpoint key is absent from corpus")
        if key in result:
            raise RuntimeError(f"{context}: duplicate append-only checkpoint key {key}")
        batch_id = row.get("batch_id")
        if batch_id not in batches:
            raise RuntimeError(f"{context}: missing immutable input batch {batch_id}")
        batch = batches[batch_id][1]
        if key not in {(item["record_id"], item["question_id"]) for item in batch["records"]}:
            raise RuntimeError(f"{context}: key is not in its input batch")
        if row.get("batch_input_sha256") != batch["batch_input_sha256"]:
            raise RuntimeError(f"{context}: batch_input_sha256 mismatch")
        if row.get("input_sha256") != corpus.units[key]["input_sha256"]:
            raise RuntimeError(f"{context}: source input_sha256 mismatch")
        pseudo_output = {field: row[field] for field in AGENT_OUTPUT_FIELDS}
        canonical, expected_locators = validate_agent_decision(
            pseudo_output, corpus.units[key], context=context
        )
        if canonical != {field: row[field] for field in canonical}:
            raise RuntimeError(f"{context}: canonical decision mismatch")
        if row["evidence_quote_locators"] != expected_locators:
            raise RuntimeError(f"{context}: evidence quote locator mismatch")
        if batch_id not in committed_by_id:
            raise RuntimeError(
                f"{context}: checkpoint batch has no committed audit event; rerun ingest to recover"
            )
        result[key] = row

    rows_by_batch: dict[str, list[dict[str, Any]]] = {}
    for row in result.values():
        rows_by_batch.setdefault(row["batch_id"], []).append(row)
    for batch_id, event in committed_by_id.items():
        if batch_id not in batches:
            raise RuntimeError(f"committed event references an unknown {stage} batch: {batch_id}")
        _, batch = batches[batch_id]
        batch_rows = rows_by_batch.get(batch_id, [])
        expected_keys = {
            (record["record_id"], record["question_id"]) for record in batch["records"]
        }
        actual_keys = {(row["record_id"], row["question_id"]) for row in batch_rows}
        if actual_keys != expected_keys:
            raise RuntimeError(
                f"committed batch {batch_id} checkpoint keys differ from its immutable input"
            )
        static_expectations = {
            "batch_kind": stage,
            "question_id": batch["question_id"],
            "execution_mode": EXECUTION_MODE,
            "requested_rows": batch["record_count"],
            "new_rows": batch["record_count"],
            "input_sha256": batch["batch_input_sha256"],
            "corpus_sha256": lock["corpus_sha256"],
            "prompt_sha256": lock["prompt_sha256"],
            "validator_contract_sha256": lock["validator_contract_sha256"],
        }
        for field, expected in static_expectations.items():
            if event.get(field) != expected:
                raise RuntimeError(f"committed batch {batch_id} event {field} mismatch")
        agents = {row["agent_id"] for row in batch_rows}
        output_hashes = {row["agent_output_sha256"] for row in batch_rows}
        if agents != {event.get("assigned_agent")} or output_hashes != {
            event.get("output_sha256")
        }:
            raise RuntimeError(f"committed batch {batch_id} agent/output provenance mismatch")
        output_path = workspace.output_path(stage, batch["question_id"], batch_id)
        if not output_path.is_file() or sha256_file(output_path) != event.get("output_sha256"):
            raise RuntimeError(f"committed batch {batch_id} agent output is missing or changed")
    return result


def _batch_event_commits(stage: str, events: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    event_name = "committed" if stage == "primary" else "adjudication_committed"
    result: dict[str, Mapping[str, Any]] = {}
    for event in events:
        if event.get("event") == event_name and event.get("batch_kind") == stage:
            batch_id = str(event.get("batch_id", ""))
            if batch_id in result:
                raise RuntimeError(f"duplicate {event_name} event for {batch_id}")
            result[batch_id] = event
    return result


def _keys_for_batch(rows: Mapping[tuple[str, str], Mapping[str, Any]], batch_id: str) -> set[tuple[str, str]]:
    return {key for key, row in rows.items() if row.get("batch_id") == batch_id}


def _stage_rows_without_commit(
    workspace: Workspace, stage: str
) -> list[dict[str, Any]]:
    """Read stage rows for ingest recovery before committed-event validation."""
    rows = load_jsonl(_stage_path(workspace, stage))
    seen: set[tuple[str, str]] = set()
    for line_number, row in enumerate(rows, 1):
        if set(row) != STAGE_CHECKPOINT_FIELDS or row.get("stage") != stage:
            raise RuntimeError(f"invalid {stage} checkpoint at line {line_number}")
        key = (row.get("record_id"), row.get("question_id"))
        if key in seen:
            raise RuntimeError(f"duplicate {stage} checkpoint key {key}")
        seen.add(key)
    return rows


def _predecessors_complete(
    workspace: Workspace,
    question_id: str,
    corpus: Corpus,
    lock: Mapping[str, Any],
) -> None:
    target_index = QUESTION_ORDER.index(question_id)
    if target_index == 0:
        return
    primary_batches = load_batch_inputs(workspace, "primary", corpus, lock)
    adjud_batches = load_batch_inputs(workspace, "adjudication", corpus, lock)
    primary = validate_stage_checkpoints(workspace, "primary", corpus, lock, primary_batches)
    adjud = validate_stage_checkpoints(workspace, "adjudication", corpus, lock, adjud_batches)
    candidates = derive_candidates(primary, corpus, lock)
    expected_final = build_expected_final(primary, adjud, candidates, corpus, lock)
    actual_final = validate_final_projection(workspace, expected_final, corpus, lock)
    for predecessor in QUESTION_ORDER[:target_index]:
        total = len(corpus.per_question[predecessor])
        primary_count = sum(key[1] == predecessor for key in primary)
        candidate_keys = {key for key in candidates if key[1] == predecessor}
        adjud_count = sum(key in adjud for key in candidate_keys)
        final_count = sum(key[1] == predecessor for key in actual_final)
        if not (
            primary_count == total
            and adjud_count == len(candidate_keys)
            and final_count == total
        ):
            raise RuntimeError(
                f"strict predecessor gate blocks {question_id}: {predecessor} "
                f"primary={primary_count}/{total}, adjudication={adjud_count}/{len(candidate_keys)}, "
                f"final={final_count}/{total}"
            )


def prepare_batches(
    workspace: Workspace,
    *,
    question_id: str,
    batch_size: int,
    stage: str = "primary",
    max_batches: int | None = None,
) -> dict[str, Any]:
    if question_id not in QUESTION_ORDER:
        raise RuntimeError(f"unknown question_id: {question_id}")
    if batch_size <= 0:
        raise RuntimeError("batch_size must be positive")
    if max_batches is not None and max_batches <= 0:
        raise RuntimeError("max_batches must be positive")
    with workspace_lock(workspace):
        corpus = load_corpus(workspace)
        lock = validate_prompt_lock(workspace, corpus)
        _predecessors_complete(workspace, question_id, corpus, lock)
        stage_batches = load_batch_inputs(workspace, stage, corpus, lock)
        reserved = {
            (record["record_id"], record["question_id"])
            for _, payload in stage_batches.values()
            for record in payload["records"]
        }
        events = load_jsonl(workspace.batches)
        commits = _batch_event_commits(stage, events)

        if stage == "primary":
            stage_rows = _stage_rows_without_commit(workspace, stage)
            committed_keys = {
                (row["record_id"], row["question_id"])
                for row in stage_rows
                if row["batch_id"] in commits
            }
            eligible = list(corpus.per_question[question_id])
        else:
            primary_batches = load_batch_inputs(workspace, "primary", corpus, lock)
            primary = validate_stage_checkpoints(
                workspace, "primary", corpus, lock, primary_batches
            )
            total_primary = sum(key[1] == question_id for key in primary)
            total_units = len(corpus.per_question[question_id])
            if total_primary != total_units:
                raise RuntimeError(
                    f"adjudication preparation requires 100% primary coverage for {question_id}: "
                    f"{total_primary}/{total_units}"
                )
            candidates = derive_candidates(primary, corpus, lock)
            materialize_candidate_list(workspace, candidates)
            stage_rows = _stage_rows_without_commit(workspace, stage)
            committed_keys = {
                (row["record_id"], row["question_id"])
                for row in stage_rows
                if row["batch_id"] in commits
            }
            eligible = sorted(
                (key for key in candidates if key[1] == question_id),
                key=lambda key: (key[0].casefold(), key[0]),
            )

        pending = [key for key in eligible if key not in committed_keys and key not in reserved]
        chunks = [pending[index : index + batch_size] for index in range(0, len(pending), batch_size)]
        if max_batches is not None:
            chunks = chunks[:max_batches]
        created: list[dict[str, Any]] = []
        prepared_events: list[dict[str, Any]] = []
        for keys in chunks:
            records = [_batch_record(corpus.units[key]) for key in keys]
            payload = build_batch_payload(stage, question_id, records, lock)
            path = workspace.input_path(stage, question_id, payload["batch_id"])
            if path.exists():
                existing = validate_batch_payload(
                    load_json(path), expected_stage=stage, corpus=corpus, lock=lock, path=path
                )
                if existing != payload:
                    raise RuntimeError(f"immutable batch collision: {path}")
            else:
                atomic_write_json(path, payload)
            prepared_at = utc_now()
            created.append(
                {
                    "batch_id": payload["batch_id"],
                    "path": repo_relative(path, workspace.root),
                    "row_count": payload["record_count"],
                    "batch_input_sha256": payload["batch_input_sha256"],
                }
            )
            if not any(
                event.get("event") == "prepared"
                and event.get("batch_kind") == stage
                and event.get("batch_id") == payload["batch_id"]
                for event in events
            ):
                prepared_events.append(
                    {
                        "event": "prepared",
                        "batch_kind": stage,
                        "batch_id": payload["batch_id"],
                        "question_id": question_id,
                        "execution_mode": EXECUTION_MODE,
                        "prepared_at_utc": prepared_at,
                        "requested_rows": payload["record_count"],
                        "first_record_id": records[0]["record_id"],
                        "last_record_id": records[-1]["record_id"],
                        "input_path": repo_relative(path, workspace.root),
                        "input_file_sha256": sha256_file(path),
                        "input_sha256": payload["batch_input_sha256"],
                        "corpus_sha256": lock["corpus_sha256"],
                        "prompt_sha256": lock["prompt_sha256"],
                        "validator_contract_sha256": lock["validator_contract_sha256"],
                    }
                )
        append_jsonl(workspace.batches, prepared_events)
        return {
            "stage": stage,
            "question_id": question_id,
            "batch_size": batch_size,
            "eligible_units": len(eligible),
            "already_checkpointed_units": len(set(eligible) & committed_keys),
            "already_reserved_units": len(set(eligible) & reserved),
            "new_batches": len(created),
            "new_units": sum(item["row_count"] for item in created),
            "remaining_unreserved_units": len(pending) - sum(item["row_count"] for item in created),
            "batches": created,
        }


def _canonical_rows_equal_for_recovery(existing: Mapping[str, Any], planned: Mapping[str, Any]) -> bool:
    ignored = {"screened_at_utc"}
    return {key: value for key, value in existing.items() if key not in ignored} == {
        key: value for key, value in planned.items() if key not in ignored
    }


def ingest_batch(
    workspace: Workspace,
    *,
    batch_id: str,
    agent_id: str,
    stage: str = "primary",
) -> dict[str, Any]:
    if not _AGENT_ID.fullmatch(agent_id):
        raise RuntimeError("agent_id has an invalid format")
    # Read the immutable input and untrusted output before taking the state lock.
    corpus = load_corpus(workspace)
    lock = validate_prompt_lock(workspace, corpus)
    batches = load_batch_inputs(workspace, stage, corpus, lock)
    if batch_id not in batches:
        raise RuntimeError(f"unknown {stage} batch_id: {batch_id}")
    input_path, batch = batches[batch_id]
    question_id = batch["question_id"]
    output_path = workspace.output_path(stage, question_id, batch_id)
    output_rows, output_sha = _agent_output_rows(output_path)
    if len(output_rows) != batch["record_count"]:
        raise RuntimeError(
            f"{output_path}: row count {len(output_rows)} != expected {batch['record_count']}"
        )
    input_by_key = {
        (record["record_id"], record["question_id"]): record for record in batch["records"]
    }
    seen: set[tuple[str, str]] = set()
    validated: dict[tuple[str, str], tuple[dict[str, Any], dict[str, str]]] = {}
    for line_number, value in enumerate(output_rows, 1):
        key = (value.get("record_id"), value.get("question_id"))
        if key in seen:
            raise RuntimeError(f"{output_path}:{line_number}: duplicate output key {key}")
        if key not in input_by_key:
            raise RuntimeError(f"{output_path}:{line_number}: unexpected output key {key}")
        seen.add(key)
        validated[key] = validate_agent_decision(
            value, input_by_key[key], context=f"{output_path}:{line_number}"
        )
    if seen != set(input_by_key):
        missing = sorted(set(input_by_key) - seen)
        raise RuntimeError(f"{output_path}: missing output keys {missing[:10]}")

    with workspace_lock(workspace):
        # Revalidate all frozen state and reservations after lock acquisition.
        corpus = load_corpus(workspace)
        lock = validate_prompt_lock(workspace, corpus)
        _predecessors_complete(workspace, question_id, corpus, lock)
        batches = load_batch_inputs(workspace, stage, corpus, lock)
        if batch_id not in batches or batches[batch_id][1] != batch:
            raise RuntimeError("input batch changed during ingest")
        if sha256_file(output_path) != output_sha:
            raise RuntimeError("agent output changed during ingest validation")
        if stage == "adjudication":
            primary_batches = load_batch_inputs(workspace, "primary", corpus, lock)
            primary = validate_stage_checkpoints(
                workspace, "primary", corpus, lock, primary_batches
            )
            primary_question_count = sum(
                key[1] == question_id for key in primary
            )
            question_total = len(corpus.per_question[question_id])
            if primary_question_count != question_total:
                raise RuntimeError(
                    f"adjudication ingest requires 100% primary coverage for {question_id}: "
                    f"{primary_question_count}/{question_total}"
                )
            candidates = derive_candidates(primary, corpus, lock)
            batch_keys = {
                (record["record_id"], record["question_id"])
                for record in batch["records"]
            }
            if not batch_keys <= set(candidates):
                raise RuntimeError("adjudication batch contains a non-candidate screening unit")
            same_agent_keys = sorted(
                key for key in batch_keys if primary[key]["agent_id"] == agent_id
            )
            if same_agent_keys:
                raise RuntimeError(
                    "blind adjudication agent must differ from the primary agent; "
                    f"same-agent units include {same_agent_keys[:5]}"
                )
        screened_at = utc_now()
        planned_rows: list[dict[str, Any]] = []
        for record in batch["records"]:
            key = (record["record_id"], record["question_id"])
            decision, locators = validated[key]
            planned_rows.append(
                _canonical_stage_row(
                    decision,
                    locators,
                    stage=stage,
                    batch=batch,
                    agent_id=agent_id,
                    output_sha=output_sha,
                    unit=corpus.units[key],
                    screened_at=screened_at,
                )
            )
        existing_rows = _stage_rows_without_commit(workspace, stage)
        existing_by_key = {
            (row["record_id"], row["question_id"]): row for row in existing_rows
        }
        expected_keys = [(row["record_id"], row["question_id"]) for row in planned_rows]
        overlapping = [key for key in expected_keys if key in existing_by_key]
        events = load_jsonl(workspace.batches)
        commits = _batch_event_commits(stage, events)
        has_prepared_event = any(
            event.get("event") == "prepared"
            and event.get("batch_kind") == stage
            and event.get("batch_id") == batch_id
            for event in events
        )
        if not has_prepared_event and batch_id not in commits:
            recovered_prepared = {
                "event": "prepared",
                "batch_kind": stage,
                "batch_id": batch_id,
                "question_id": question_id,
                "execution_mode": EXECUTION_MODE,
                "prepared_at_utc": utc_now(),
                "recovered_from_immutable_input": True,
                "requested_rows": batch["record_count"],
                "first_record_id": batch["records"][0]["record_id"],
                "last_record_id": batch["records"][-1]["record_id"],
                "input_path": repo_relative(input_path, workspace.root),
                "input_file_sha256": sha256_file(input_path),
                "input_sha256": batch["batch_input_sha256"],
                "corpus_sha256": lock["corpus_sha256"],
                "prompt_sha256": lock["prompt_sha256"],
                "validator_contract_sha256": lock["validator_contract_sha256"],
            }
            append_jsonl(workspace.batches, [recovered_prepared])
            events.append(recovered_prepared)

        if batch_id in commits:
            if set(overlapping) != set(expected_keys):
                raise RuntimeError(f"committed batch {batch_id} has incomplete checkpoint rows")
            if any(
                not _canonical_rows_equal_for_recovery(existing_by_key[key], planned)
                for key, planned in zip(expected_keys, planned_rows)
            ):
                raise RuntimeError(f"committed batch {batch_id} output differs from existing checkpoints")
            return {
                "status": "already_committed",
                "stage": stage,
                "batch_id": batch_id,
                "question_id": question_id,
                "rows": len(planned_rows),
                "output_sha256": output_sha,
            }

        if overlapping and set(overlapping) != set(expected_keys):
            raise RuntimeError(
                f"batch {batch_id} has a partial append-only checkpoint transaction; manual audit required"
            )
        if overlapping:
            if any(
                not _canonical_rows_equal_for_recovery(existing_by_key[key], planned)
                for key, planned in zip(expected_keys, planned_rows)
            ):
                raise RuntimeError(f"batch {batch_id} recovery output differs from existing rows")
            appended_rows = 0
            recovery = True
        else:
            append_jsonl(_stage_path(workspace, stage), planned_rows)
            appended_rows = len(planned_rows)
            recovery = False

        event_name = "committed" if stage == "primary" else "adjudication_committed"
        append_jsonl(
            workspace.batches,
            [
                {
                    "event": event_name,
                    "batch_kind": stage,
                    "batch_id": batch_id,
                    "question_id": question_id,
                    "assigned_agent": agent_id,
                    "execution_mode": EXECUTION_MODE,
                    "started_at_utc": None,
                    "completed_at_utc": utc_now(),
                    "requested_rows": batch["record_count"],
                    "new_rows": len(planned_rows),
                    "appended_rows": appended_rows,
                    "recovered_checkpoint_only_transaction": recovery,
                    "first_record_id": batch["records"][0]["record_id"],
                    "last_record_id": batch["records"][-1]["record_id"],
                    "input_path": repo_relative(input_path, workspace.root),
                    "output_path": repo_relative(output_path, workspace.root),
                    "input_sha256": batch["batch_input_sha256"],
                    "input_file_sha256": sha256_file(input_path),
                    "output_sha256": output_sha,
                    "corpus_sha256": lock["corpus_sha256"],
                    "prompt_sha256": lock["prompt_sha256"],
                    "validator_contract_sha256": lock["validator_contract_sha256"],
                }
            ],
        )
        return {
            "status": "committed",
            "stage": stage,
            "batch_id": batch_id,
            "question_id": question_id,
            "rows": len(planned_rows),
            "appended_rows": appended_rows,
            "recovered": recovery,
            "output_sha256": output_sha,
        }


def _evidence_text(unit: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            unit["title"],
            unit["abstract"],
            *unit["publication_types"],
            *unit["mesh_terms"],
        ]
    )


def derive_candidates(
    primary: Mapping[tuple[str, str], Mapping[str, Any]],
    corpus: Corpus,
    lock: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for key, row in primary.items():
        triggers: list[str] = []
        if row["decision"] == "uncertain":
            triggers.append("uncertain")
        if row["evidence_basis"] == "title_only" and row["decision"] == "retain":
            triggers.append("title_only_retain")
        if row["gates"]["route"] == "out_of_scope_only":
            triggers.append("route_out_of_scope")
            if _IV_TERMS.search(_evidence_text(corpus.units[key])):
                triggers.append("iv_only")
        if row["decision"] == "retain" and "exposure_outcome_class_level" in row["reason_codes"]:
            triggers.append("class_retain")
        if row["decision"] == "retain" and "case_report_relevant" in row["reason_codes"]:
            triggers.append("case_report_relevant")
        text = _evidence_text(corpus.units[key])
        if (
            key[1] == QUESTION_ORDER[0]
            and row["gates"]["exposure"] == "direct_actual"
            and _STANDALONE_APAP.search(text)
            and not _FULL_ACETAMINOPHEN_NAMES.search(text)
        ):
            triggers.append("bare_apap_actual")
        # The 10-field frozen output has no structured multi-drug flag.  A
        # retain superset guarantees that every multi-drug retain receives a
        # blind second pass without a brittle semantic regex deciding which
        # chemical names count as drugs.
        if row["decision"] == "retain":
            triggers.append("retain_superset_for_multi_drug")
        ordered = [name for name in CANDIDATE_TRIGGER_ORDER if name in set(triggers)]
        if ordered:
            candidates[key] = {
                "schema_version": SCHEMA_VERSION,
                "record_id": key[0],
                "question_id": key[1],
                "candidate_triggers": ordered,
                "primary_batch_id": row["batch_id"],
                "primary_agent_id": row["agent_id"],
                "primary_checkpoint_sha256": sha256_bytes(canonical_json_bytes(row)),
                "prompt_sha256": lock["prompt_sha256"],
                "corpus_sha256": lock["corpus_sha256"],
                "ai_second_pass_blinded": True,
            }
    return candidates


def materialize_candidate_list(
    workspace: Workspace, candidates: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    # This artifact is safe to hand to a blind adjudication dispatcher.  The
    # mere target IDs are necessary, but primary decisions, gates, reasons,
    # trigger names, agents, batches, and hashes of primary rows are excluded.
    rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "record_id": key[0],
            "question_id": key[1],
            "prompt_sha256": candidates[key]["prompt_sha256"],
            "corpus_sha256": candidates[key]["corpus_sha256"],
            "ai_second_pass_blinded": True,
        }
        for key in sorted(candidates, key=lambda key: (QUESTION_ORDER.index(key[1]), key[0]))
    ]
    atomic_write_jsonl(workspace.candidate_list, rows)


def _final_from_stage(
    row: Mapping[str, Any], *, final_source: str, candidate_triggers: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": row["record_id"],
        "question_id": row["question_id"],
        "decision": row["decision"],
        "reason_codes": list(row["reason_codes"]),
        "confidence": row["confidence"],
        "evidence_basis": row["evidence_basis"],
        "gates": dict(row["gates"]),
        "evidence_quotes": dict(row["evidence_quotes"]),
        "evidence_quote_locators": dict(row["evidence_quote_locators"]),
        "uncertain_gate": list(row["uncertain_gate"]),
        "rationale": row["rationale"],
        "status": "screened",
        "stage": "final",
        "final_source": final_source,
        "resolution": "single_primary" if final_source == "primary" else "blind_second_pass_agreement",
        "candidate_triggers": list(candidate_triggers),
        "source_batch_id": row["batch_id"],
        "source_agent_id": row["agent_id"],
        "execution_mode": EXECUTION_MODE,
        "prompt_sha256": row["prompt_sha256"],
        "corpus_sha256": row["corpus_sha256"],
        "validator_contract_sha256": row["validator_contract_sha256"],
        "input_sha256": row["input_sha256"],
        "primary_checkpoint_sha256": None,
        "adjudication_checkpoint_sha256": None,
        "materialized_at_utc": None,
    }


def _disagreement_final(
    primary: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    candidate_triggers: Sequence[str],
) -> dict[str, Any]:
    basis = primary["evidence_basis"]
    row = _final_from_stage(
        adjudication, final_source="adjudication", candidate_triggers=candidate_triggers
    )
    row.update(
        {
            "decision": "uncertain",
            "reason_codes": ["title_only_insufficient" if basis == "title_only" else "insufficient_detail"],
            "confidence": "low" if basis == "title_only" else "medium",
            "gates": {name: "unclear" for name in GATE_ORDER},
            "evidence_quotes": {name: "" for name in GATE_ORDER},
            "evidence_quote_locators": {name: "" for name in GATE_ORDER},
            "uncertain_gate": list(GATE_ORDER),
            "rationale": "1차와 블라인드 2차 판정이 달라 입력만으로 차이를 해소하지 못했다.",
            "resolution": "blind_second_pass_disagreement_conservative_uncertain",
        }
    )
    return row


def build_expected_final(
    primary: Mapping[tuple[str, str], Mapping[str, Any]],
    adjudication: Mapping[tuple[str, str], Mapping[str, Any]],
    candidates: Mapping[tuple[str, str], Mapping[str, Any]],
    corpus: Corpus,
    lock: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    del corpus, lock
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key, primary_row in primary.items():
        candidate = candidates.get(key)
        if candidate is None:
            row = _final_from_stage(primary_row, final_source="primary", candidate_triggers=[])
            row["primary_checkpoint_sha256"] = sha256_bytes(canonical_json_bytes(primary_row))
            result[key] = row
            continue
        if key not in adjudication:
            continue
        adjudication_row = adjudication[key]
        if primary_row["decision"] == adjudication_row["decision"]:
            row = _final_from_stage(
                adjudication_row,
                final_source="adjudication",
                candidate_triggers=candidate["candidate_triggers"],
            )
        else:
            row = _disagreement_final(
                primary_row, adjudication_row, candidate["candidate_triggers"]
            )
        row["primary_checkpoint_sha256"] = sha256_bytes(canonical_json_bytes(primary_row))
        row["adjudication_checkpoint_sha256"] = sha256_bytes(
            canonical_json_bytes(adjudication_row)
        )
        result[key] = row
    return result


def _final_comparison_core(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "materialized_at_utc"}


def validate_final_projection(
    workspace: Workspace,
    expected: Mapping[tuple[str, str], Mapping[str, Any]],
    corpus: Corpus,
    lock: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    rows = load_jsonl(workspace.final_checkpoints)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for line_number, row in enumerate(rows, 1):
        context = f"{workspace.final_checkpoints}:{line_number}"
        key = (row.get("record_id"), row.get("question_id"))
        if key not in corpus.units:
            raise RuntimeError(f"{context}: final key is absent from corpus")
        if key in result:
            raise RuntimeError(f"{context}: duplicate final key {key}")
        if key not in expected:
            raise RuntimeError(f"{context}: final key is not currently eligible")
        if row.get("prompt_sha256") != lock["prompt_sha256"] or row.get(
            "corpus_sha256"
        ) != lock["corpus_sha256"]:
            raise RuntimeError(f"{context}: final provenance hash mismatch")
        if _final_comparison_core(row) != _final_comparison_core(expected[key]):
            raise RuntimeError(f"{context}: final materialization differs from stage ledgers")
        result[key] = row
    return result


def _counter(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows).items()))


def _reason_counter(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(row["reason_codes"])
    return dict(sorted(counter.items()))


def question_metrics(
    corpus: Corpus,
    primary: Mapping[tuple[str, str], Mapping[str, Any]],
    adjudication: Mapping[tuple[str, str], Mapping[str, Any]],
    candidates: Mapping[tuple[str, str], Mapping[str, Any]],
    final: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    predecessors_complete = True
    for question_id in QUESTION_ORDER:
        total = len(corpus.per_question[question_id])
        primary_rows = [row for key, row in primary.items() if key[1] == question_id]
        candidate_keys = [key for key in candidates if key[1] == question_id]
        adjudicated_candidates = [key for key in candidate_keys if key in adjudication]
        final_rows = [row for key, row in final.items() if key[1] == question_id]
        primary_complete = len(primary_rows) == total
        adjudication_complete = primary_complete and len(adjudicated_candidates) == len(candidate_keys)
        final_materialization_complete = adjudication_complete and len(final_rows) == total
        own_complete = primary_complete and adjudication_complete and final_materialization_complete
        complete = predecessors_complete and own_complete
        coverage = len(final_rows) / total if total else 1.0
        metrics[question_id] = {
            "total_memberships": total,
            "primary_screened_memberships": len(primary_rows),
            "primary_remaining_memberships": max(total - len(primary_rows), 0),
            "primary_coverage": len(primary_rows) / total if total else 1.0,
            "adjudication_candidate_memberships": len(candidate_keys),
            "adjudicated_candidate_memberships": len(adjudicated_candidates),
            "adjudication_remaining_memberships": max(
                len(candidate_keys) - len(adjudicated_candidates), 0
            ),
            "adjudication_coverage": (
                len(adjudicated_candidates) / len(candidate_keys)
                if candidate_keys
                else (1.0 if primary_complete else 0.0)
            ),
            "screened_memberships": len(final_rows),
            "remaining_memberships": max(total - len(final_rows), 0),
            "coverage": coverage,
            "primary_complete": primary_complete,
            "adjudication_complete": adjudication_complete,
            "final_materialization_complete": final_materialization_complete,
            "own_complete": own_complete,
            "predecessors_complete": predecessors_complete,
            "complete": complete,
            "decision_distribution": _counter(final_rows, "decision"),
            "label_distribution": _counter(final_rows, "decision"),
            "confidence_distribution": _counter(final_rows, "confidence"),
            "evidence_basis_distribution": _counter(final_rows, "evidence_basis"),
            "reason_code_distribution": _reason_counter(final_rows),
        }
        predecessors_complete = predecessors_complete and own_complete
    return metrics


def _validate_global_question_order(
    metrics: Mapping[str, Mapping[str, Any]], primary: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    predecessor_complete = True
    for question_id in QUESTION_ORDER:
        has_primary = any(key[1] == question_id for key in primary)
        if has_primary and not predecessor_complete:
            raise RuntimeError(
                f"strict question order violated: {question_id} has primary rows before predecessor completion"
            )
        predecessor_complete = predecessor_complete and bool(metrics[question_id]["own_complete"])


DECISION_FIELDS = (
    "record_id",
    "question_id",
    "decision",
    "reason_codes",
    "confidence",
    "evidence_basis",
    "rationale",
    "gates",
    "evidence_quotes",
    "uncertain_gate",
    "resolution",
    "candidate_triggers",
    "source_batch_id",
    "source_agent_id",
    "execution_mode",
    "prompt_sha256",
    "corpus_sha256",
    "input_sha256",
)


def _decision_csv_rows(final: Mapping[tuple[str, str], Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(final, key=lambda item: (QUESTION_ORDER.index(item[1]), item[0])):
        row = final[key]
        rows.append(
            {
                **{field: row.get(field, "") for field in DECISION_FIELDS},
                "reason_codes": json.dumps(row["reason_codes"], ensure_ascii=False, separators=(",", ":")),
                "gates": json.dumps(row["gates"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "evidence_quotes": json.dumps(
                    row["evidence_quotes"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
                "uncertain_gate": json.dumps(
                    row["uncertain_gate"], ensure_ascii=False, separators=(",", ":")
                ),
                "candidate_triggers": json.dumps(
                    row["candidate_triggers"], ensure_ascii=False, separators=(",", ":")
                ),
            }
        )
    return rows


def _state_sha(
    workspace: Workspace, lock: Mapping[str, Any], primary_count: int, adjudication_count: int
) -> str:
    value = {
        "prompt_sha256": lock["prompt_sha256"],
        "corpus_sha256": lock["corpus_sha256"],
        "validator_contract_sha256": lock["validator_contract_sha256"],
        "primary_checkpoint_sha256": (
            sha256_file(workspace.primary_checkpoints) if workspace.primary_checkpoints.exists() else None
        ),
        "adjudication_checkpoint_sha256": (
            sha256_file(workspace.adjudication_checkpoints)
            if workspace.adjudication_checkpoints.exists()
            else None
        ),
        "batches_sha256": sha256_file(workspace.batches) if workspace.batches.exists() else None,
        "primary_rows": primary_count,
        "adjudication_rows": adjudication_count,
    }
    return sha256_bytes(canonical_json_bytes(value))


def _load_valid_state(
    workspace: Workspace,
) -> tuple[
    Corpus,
    dict[str, Any],
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    corpus = load_corpus(workspace)
    lock = validate_prompt_lock(workspace, corpus)
    primary_batches = load_batch_inputs(workspace, "primary", corpus, lock)
    adjudication_batches = load_batch_inputs(workspace, "adjudication", corpus, lock)
    primary = validate_stage_checkpoints(
        workspace, "primary", corpus, lock, primary_batches
    )
    adjudication = validate_stage_checkpoints(
        workspace, "adjudication", corpus, lock, adjudication_batches
    )
    candidates = derive_candidates(primary, corpus, lock)
    extra_adjudication = sorted(set(adjudication) - set(candidates))
    if extra_adjudication:
        raise RuntimeError(
            "adjudication checkpoints contain non-candidate units: "
            f"{extra_adjudication[:10]}"
        )
    expected_final = build_expected_final(primary, adjudication, candidates, corpus, lock)
    actual_final = validate_final_projection(workspace, expected_final, corpus, lock)
    metrics = question_metrics(corpus, primary, adjudication, candidates, actual_final)
    _validate_global_question_order(metrics, primary)
    return corpus, lock, primary, adjudication, candidates, expected_final, actual_final


def status(workspace: Workspace, *, write: bool) -> dict[str, Any]:
    with workspace_lock(workspace):
        corpus, lock, primary, adjudication, candidates, expected_final, actual_final = _load_valid_state(
            workspace
        )
        state_sha = _state_sha(workspace, lock, len(primary), len(adjudication))
        if write:
            # Reuse a verified materialization when the append-only source state is unchanged.
            if workspace.screening_manifest.is_file():
                existing_manifest = load_json(workspace.screening_manifest)
                if existing_manifest.get("source_state_sha256") == state_sha:
                    expected_files = {
                        workspace.final_checkpoints: existing_manifest.get("checkpoint_sha256"),
                        workspace.decisions_csv: existing_manifest.get("decisions_csv_sha256"),
                        workspace.candidate_list: existing_manifest.get("adjudication_candidates_sha256"),
                        workspace.progress: existing_manifest.get("progress_sha256"),
                    }
                    if all(
                        path.is_file() and sha256_file(path) == expected_hash
                        for path, expected_hash in expected_files.items()
                    ):
                        return {**existing_manifest, "idempotent": True}

            materialized_at = utc_now()
            final_rows: list[dict[str, Any]] = []
            for key in sorted(expected_final, key=lambda item: (QUESTION_ORDER.index(item[1]), item[0])):
                row = dict(expected_final[key])
                row["materialized_at_utc"] = materialized_at
                final_rows.append(row)
            atomic_write_jsonl(workspace.final_checkpoints, final_rows)
            materialize_candidate_list(workspace, candidates)
            actual_final = {(
                row["record_id"], row["question_id"]
            ): row for row in final_rows}
            decision_rows = _decision_csv_rows(actual_final)
            atomic_write_csv(workspace.decisions_csv, DECISION_FIELDS, decision_rows)

            metrics = question_metrics(corpus, primary, adjudication, candidates, actual_final)
            _validate_global_question_order(metrics, primary)
            completed = sum(bool(metrics[qid]["complete"]) for qid in QUESTION_ORDER)
            active = next((qid for qid in QUESTION_ORDER if not metrics[qid]["complete"]), None)
            progress = {
                "schema_version": SCHEMA_VERSION,
                "updated_at_utc": materialized_at,
                "phase": "C",
                "execution_mode": EXECUTION_MODE,
                "source_state_sha256": state_sha,
                "prompt_sha256": lock["prompt_sha256"],
                "corpus_path": repo_relative(workspace.evidence_map, workspace.root),
                "corpus_sha256": lock["corpus_sha256"],
                "validator_contract_sha256": lock["validator_contract_sha256"],
                "question_order": list(QUESTION_ORDER),
                "questions_completed": completed,
                "active_question": active,
                "questions": metrics,
                "all_questions_complete": completed == len(QUESTION_ORDER),
                "human_decisions": 0,
                "independent_blinding": False,
                "ai_second_pass_blinded": True,
                "release_ready": False,
            }
            atomic_write_json(workspace.progress, progress)
            all_final_rows = list(actual_final.values())
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "updated_at_utc": materialized_at,
                "phase": "C",
                "status": "complete" if progress["all_questions_complete"] else "partial",
                "execution_mode": EXECUTION_MODE,
                "semantic_agent_screening": True,
                "source_state_sha256": state_sha,
                "prompt_path": repo_relative(workspace.source_prompt, workspace.root),
                "frozen_prompt_path": repo_relative(workspace.frozen_prompt, workspace.root),
                "prompt_sha256": lock["prompt_sha256"],
                "input_path": repo_relative(workspace.evidence_map, workspace.root),
                "input_sha256": lock["corpus_sha256"],
                "validator_contract_sha256": lock["validator_contract_sha256"],
                "primary_checkpoint_path": repo_relative(workspace.primary_checkpoints, workspace.root),
                "primary_checkpoint_sha256": (
                    sha256_file(workspace.primary_checkpoints)
                    if workspace.primary_checkpoints.exists()
                    else None
                ),
                "primary_checkpoint_rows": len(primary),
                "adjudication_checkpoint_path": repo_relative(
                    workspace.adjudication_checkpoints, workspace.root
                ),
                "adjudication_checkpoint_sha256": (
                    sha256_file(workspace.adjudication_checkpoints)
                    if workspace.adjudication_checkpoints.exists()
                    else None
                ),
                "adjudication_checkpoint_rows": len(adjudication),
                "checkpoint_path": repo_relative(workspace.final_checkpoints, workspace.root),
                "checkpoint_sha256": sha256_file(workspace.final_checkpoints),
                "checkpoint_rows": len(actual_final),
                "decisions_csv_path": repo_relative(workspace.decisions_csv, workspace.root),
                "decisions_csv_sha256": sha256_file(workspace.decisions_csv),
                "decisions_csv_rows": len(actual_final),
                "adjudication_candidates_path": repo_relative(workspace.candidate_list, workspace.root),
                "adjudication_candidates_sha256": sha256_file(workspace.candidate_list),
                "adjudication_candidate_rows": len(candidates),
                "batches_path": repo_relative(workspace.batches, workspace.root),
                "batches_sha256": sha256_file(workspace.batches) if workspace.batches.exists() else None,
                "progress_path": repo_relative(workspace.progress, workspace.root),
                "progress_sha256": sha256_file(workspace.progress),
                "question_order": list(QUESTION_ORDER),
                "questions": metrics,
                "total_memberships": corpus.total_units,
                "screened_memberships": len(actual_final),
                "remaining_memberships": corpus.total_units - len(actual_final),
                "coverage": len(actual_final) / corpus.total_units if corpus.total_units else 1.0,
                "decision_distribution": _counter(all_final_rows, "decision"),
                "confidence_distribution": _counter(all_final_rows, "confidence"),
                "evidence_basis_distribution": _counter(all_final_rows, "evidence_basis"),
                "reason_code_distribution": _reason_counter(all_final_rows),
                "append_only_primary_checkpoints": True,
                "append_only_adjudication_checkpoints": True,
                "final_checkpoints_materialization": "atomic_projection",
                "ai_second_pass_candidate_policy": validator_contract()["candidate_policy"],
                "ai_second_pass_blinded": True,
                "independent_blinding": False,
                "human_decisions": 0,
                "release_ready": False,
            }
            # The manifest is the final commit marker for this materialized state.
            atomic_write_json(workspace.screening_manifest, manifest)
            return manifest

        metrics = question_metrics(corpus, primary, adjudication, candidates, actual_final)
        return {
            "schema_version": SCHEMA_VERSION,
            "execution_mode": EXECUTION_MODE,
            "source_state_sha256": state_sha,
            "prompt_sha256": lock["prompt_sha256"],
            "corpus_sha256": lock["corpus_sha256"],
            "total_memberships": corpus.total_units,
            "primary_checkpoint_rows": len(primary),
            "adjudication_checkpoint_rows": len(adjudication),
            "adjudication_candidate_rows": len(candidates),
            "eligible_final_rows": len(expected_final),
            "materialized_final_rows": len(actual_final),
            "questions": metrics,
            "independent_blinding": False,
            "ai_second_pass_blinded": True,
            "release_ready": False,
        }


def batch_status(
    workspace: Workspace,
    *,
    question_id: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    with workspace_lock(workspace):
        corpus = load_corpus(workspace)
        lock = validate_prompt_lock(workspace, corpus)
        events = load_jsonl(workspace.batches)
        stages = [stage] if stage else ["primary", "adjudication"]
        records: list[dict[str, Any]] = []
        known_outputs: set[Path] = set()
        for current_stage in stages:
            inputs = load_batch_inputs(workspace, current_stage, corpus, lock)
            stage_rows = _stage_rows_without_commit(workspace, current_stage)
            commits = _batch_event_commits(current_stage, events)
            for batch_id, (input_path, payload) in sorted(inputs.items()):
                output_path = workspace.output_path(
                    current_stage, payload["question_id"], batch_id
                )
                known_outputs.add(output_path.resolve())
                if question_id and payload["question_id"] != question_id:
                    continue
                checkpoint_rows = [row for row in stage_rows if row["batch_id"] == batch_id]
                committed = batch_id in commits
                if committed and len(checkpoint_rows) != payload["record_count"]:
                    state = "integrity_error"
                elif committed:
                    state = "committed"
                elif checkpoint_rows:
                    state = "checkpoints_present_commit_missing"
                elif output_path.is_file():
                    state = "output_ready"
                else:
                    state = "prepared"
                records.append(
                    {
                        "batch_id": batch_id,
                        "batch_kind": current_stage,
                        "question_id": payload["question_id"],
                        "state": state,
                        "expected_rows": payload["record_count"],
                        "checkpoint_rows": len(checkpoint_rows),
                        "input_path": repo_relative(input_path, workspace.root),
                        "input_sha256": payload["batch_input_sha256"],
                        "output_path": repo_relative(output_path, workspace.root),
                        "output_exists": output_path.is_file(),
                        "output_sha256": sha256_file(output_path) if output_path.is_file() else None,
                        "assigned_agent": commits.get(batch_id, {}).get("assigned_agent"),
                        "completed_at_utc": commits.get(batch_id, {}).get("completed_at_utc"),
                    }
                )
        orphan_outputs: list[str] = []
        for current_stage in stages:
            root = workspace.output_root(current_stage)
            if root.exists():
                for path in root.glob("*/*.jsonl"):
                    if path.resolve() not in known_outputs:
                        orphan_outputs.append(repo_relative(path, workspace.root))
        return {
            "execution_mode": EXECUTION_MODE,
            "question_id": question_id,
            "batch_kind": stage,
            "batch_count": len(records),
            "state_distribution": dict(sorted(Counter(row["state"] for row in records).items())),
            "batches": records,
            "orphan_outputs": sorted(orphan_outputs),
        }


def _self_test_decision(unit: Mapping[str, Any], *, uncertain: bool = False) -> dict[str, Any]:
    if uncertain:
        gates = {
            "source": "human_primary",
            "exposure": "direct_actual",
            "route": "in_scope_or_unspecified",
            "risk_context": "unclear",
            "result_type": "unclear",
            "attribution": "unclear",
            "publication_role": "other",
        }
        quotes = {name: "" for name in GATE_ORDER}
        quotes["source"] = "adult"
        quotes["exposure"] = "acetaminophen"
        decision, reasons, confidence = _expected_mapping(
            gates, "abstract" if unit["has_abstract"] else "title_only", quotes
        )
        uncertain_gate = ["risk_context", "result_type", "attribution"]
    else:
        gates = {
            "source": "human_primary",
            "exposure": "direct_actual",
            "route": "in_scope_or_unspecified",
            "risk_context": "in_scope",
            "result_type": "observed_safety_or_harm",
            "attribution": "direct_exposure",
            "publication_role": "other",
        }
        quotes = {
            "source": "older adults",
            "exposure": "acetaminophen",
            "route": "oral acetaminophen",
            "risk_context": "older adults",
            "result_type": "no adverse events",
            "attribution": "oral acetaminophen caused no adverse events",
            "publication_role": "",
        }
        decision, reasons, confidence = _expected_mapping(gates, "abstract", quotes)
        uncertain_gate = []
    return {
        "record_id": unit["record_id"],
        "question_id": unit["question_id"],
        "decision": decision,
        "reason_codes": reasons,
        "confidence": confidence,
        "evidence_basis": "abstract" if unit["has_abstract"] else "title_only",
        "gates": gates,
        "evidence_quotes": quotes,
        "uncertain_gate": uncertain_gate,
        "rationale": "입력에 명시된 노출과 결과를 기준으로 판정했다.",
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-screen-v50-") as temporary:
        workspace = Workspace(Path(temporary))
        workspace.source_prompt.parent.mkdir(parents=True)
        workspace.source_prompt.write_text("# frozen test prompt\n", encoding="utf-8")
        workspace.evidence_map.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "record_id",
            "pmid",
            "title",
            "abstract",
            "has_abstract",
            "publication_types",
            "mesh_terms",
            "question_ids",
            "input_sha256",
        ]
        source_rows = [
            {
                "record_id": "TEST-1",
                "pmid": "1",
                "title": "Oral acetaminophen in older adults",
                "abstract": "older adults received oral acetaminophen; oral acetaminophen caused no adverse events",
                "has_abstract": "true",
                "publication_types": "Journal Article",
                "mesh_terms": "Humans",
                "question_ids": QUESTION_ORDER[0],
                "input_sha256": "1" * 64,
            },
            {
                "record_id": "TEST-2",
                "pmid": "2",
                "title": "Acetaminophen safety",
                "abstract": "adult acetaminophen safety was described",
                "has_abstract": "true",
                "publication_types": "Journal Article",
                "mesh_terms": "Humans",
                "question_ids": QUESTION_ORDER[0],
                "input_sha256": "2" * 64,
            },
        ]
        atomic_write_csv(workspace.evidence_map, fieldnames, source_rows)
        evidence_sha = sha256_file(workspace.evidence_map)
        atomic_write_json(
            workspace.corpus_manifest,
            {
                "evidence_map": {"sha256": evidence_sha},
                "per_question_membership_rows": {
                    qid: (2 if qid == QUESTION_ORDER[0] else 0) for qid in QUESTION_ORDER
                },
            },
        )
        freeze(workspace)
        prepared = prepare_batches(
            workspace,
            question_id=QUESTION_ORDER[0],
            batch_size=2,
            stage="primary",
        )
        batch_id = prepared["batches"][0]["batch_id"]
        corpus = load_corpus(workspace)
        primary_output = [
            _self_test_decision(corpus.units[("TEST-1", QUESTION_ORDER[0])]),
            _self_test_decision(corpus.units[("TEST-2", QUESTION_ORDER[0])], uncertain=True),
        ]
        output_path = workspace.output_path("primary", QUESTION_ORDER[0], batch_id)
        atomic_write_jsonl(output_path, primary_output)
        ingest_batch(workspace, batch_id=batch_id, agent_id="self-test-primary", stage="primary")
        adjud_prepared = prepare_batches(
            workspace,
            question_id=QUESTION_ORDER[0],
            batch_size=2,
            stage="adjudication",
        )
        if adjud_prepared["new_units"] != 2:
            raise RuntimeError("self-test candidate policy did not select both retain and uncertain")
        adjud_batch_id = adjud_prepared["batches"][0]["batch_id"]
        adjud_output_path = workspace.output_path(
            "adjudication", QUESTION_ORDER[0], adjud_batch_id
        )
        atomic_write_jsonl(adjud_output_path, primary_output)
        ingest_batch(
            workspace,
            batch_id=adjud_batch_id,
            agent_id="self-test-adjudicator",
            stage="adjudication",
        )
        manifest = status(workspace, write=True)
        if manifest["screened_memberships"] != 2:
            raise RuntimeError("self-test final materialization row count mismatch")
        if not manifest["questions"][QUESTION_ORDER[0]]["complete"]:
            raise RuntimeError("self-test Q01 did not become complete")
        return {
            "status": "passed",
            "primary_rows": manifest["primary_checkpoint_rows"],
            "adjudication_rows": manifest["adjudication_checkpoint_rows"],
            "final_rows": manifest["screened_memberships"],
            "q01_complete": manifest["questions"][QUESTION_ORDER[0]]["complete"],
            "temporary_workspace_removed": True,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("freeze", help="freeze the formal screening prompt and corpus hashes")

    prepare_parser = subparsers.add_parser("prepare", help="prepare primary agent batches")
    prepare_parser.add_argument("--question-id", required=True, choices=QUESTION_ORDER)
    prepare_parser.add_argument("--batch-size", type=int, default=60)
    prepare_parser.add_argument("--max-batches", type=int)

    ingest_parser = subparsers.add_parser("ingest", help="validate and ingest one primary output")
    ingest_parser.add_argument("--batch-id", required=True)
    ingest_parser.add_argument("--agent-id", required=True)

    adjud_prepare = subparsers.add_parser(
        "prepare-adjudication", help="prepare blind second-pass batches"
    )
    adjud_prepare.add_argument("--question-id", required=True, choices=QUESTION_ORDER)
    adjud_prepare.add_argument("--batch-size", type=int, default=60)
    adjud_prepare.add_argument("--max-batches", type=int)

    adjud_ingest = subparsers.add_parser(
        "ingest-adjudication", help="validate and ingest one blind second-pass output"
    )
    adjud_ingest.add_argument("--batch-id", required=True)
    adjud_ingest.add_argument("--agent-id", required=True)

    status_parser = subparsers.add_parser("status", help="validate formal screening state")
    status_parser.add_argument("--write", action="store_true")

    batch_parser = subparsers.add_parser("batch-status", help="show prepared/committed batches")
    batch_parser.add_argument("--question-id", choices=QUESTION_ORDER)
    batch_parser.add_argument("--batch-kind", choices=("primary", "adjudication"))

    subparsers.add_parser("self-test", help="run an end-to-end test in a temporary workspace")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = DEFAULT_WORKSPACE
    if args.command == "freeze":
        result = freeze(workspace)
    elif args.command == "prepare":
        result = prepare_batches(
            workspace,
            question_id=args.question_id,
            batch_size=args.batch_size,
            stage="primary",
            max_batches=args.max_batches,
        )
    elif args.command == "ingest":
        result = ingest_batch(
            workspace, batch_id=args.batch_id, agent_id=args.agent_id, stage="primary"
        )
    elif args.command == "prepare-adjudication":
        result = prepare_batches(
            workspace,
            question_id=args.question_id,
            batch_size=args.batch_size,
            stage="adjudication",
            max_batches=args.max_batches,
        )
    elif args.command == "ingest-adjudication":
        result = ingest_batch(
            workspace,
            batch_id=args.batch_id,
            agent_id=args.agent_id,
            stage="adjudication",
        )
    elif args.command == "status":
        result = status(workspace, write=args.write)
    elif args.command == "batch-status":
        result = batch_status(
            workspace, question_id=args.question_id, stage=args.batch_kind
        )
    elif args.command == "self-test":
        result = self_test()
    else:  # pragma: no cover - argparse guarantees this is unreachable.
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, TimeoutError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
