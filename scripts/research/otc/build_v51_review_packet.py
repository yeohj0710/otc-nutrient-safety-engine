from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import re
import stat
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from scripts.research.otc.validate_v51_shortlist_triage import (
        FORBIDDEN_CLAIMS as TRIAGE_FORBIDDEN_CLAIMS,
    )
except ModuleNotFoundError:  # direct script execution from this directory
    from validate_v51_shortlist_triage import (  # type: ignore[no-redef]
        FORBIDDEN_CLAIMS as TRIAGE_FORBIDDEN_CLAIMS,
    )


ROOT = Path(__file__).resolve().parents[3]
QUEUE_RELATIVE = Path("research_v51/review/expert_review_queue.csv")
TRIAGE_RELATIVE = Path("research_v51/review/shortlist_semantic_triage.csv")
PACKET_RELATIVE = Path("research_v51/review/expert_review_packet.md")
AUDIT_RELATIVE = Path("research_v51/audit/review_packet_audit.json")
EVIDENCE_INVENTORY_RELATIVE = Path(
    "research_v51/audit/evidence_inventory.json"
)
TRIAGE_VALIDATOR_RELATIVE = Path(
    "scripts/research/otc/validate_v51_shortlist_triage.py"
)
GENERATOR_RELATIVE = Path("scripts/research/otc/build_v51_review_packet.py")
QUEUE_PATH = ROOT / QUEUE_RELATIVE
TRIAGE_PATH = ROOT / TRIAGE_RELATIVE
PACKET_PATH = ROOT / PACKET_RELATIVE
AUDIT_PATH = ROOT / AUDIT_RELATIVE
EVIDENCE_INVENTORY_PATH = ROOT / EVIDENCE_INVENTORY_RELATIVE

EXPECTED_ITEMS = 33
OFFICIAL_SOURCE_PATTERN = re.compile(
    r"https://nedrug\.mfds\.go\.kr/dsie/pdf/drb/"
    r"(?P<item_sequence>[0-9]+)/(?:NB|UD)"
)
SOURCE_VERSION_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
HANGUL_PATTERN = re.compile(r"[가-힣]")
ALLOWED_RECOMMENDED_STATUSES = {
    "needs_expert_review",
    "provisional",
    "rejected",
}
REGRESSION_TEST_LABELS = {
    "normal": "정상",
    "boundary": "경계",
    "non_target": "비대상",
    "false_positive": "오탐 방지",
}

QUEUE_REQUIRED_FIELDS = (
    "evidence_candidate_id",
    "rule_id",
    "rule_type",
    "referenced_rule_status",
    "candidate_operational_status",
    "product_name",
    "item_sequence",
    "current_rule_scope",
    "referenced_runtime_condition",
    "proposed_message_ko",
    "proposed_next_action_ko",
    "source_id",
    "source_url",
    "source_version",
    "raw_candidate_source_locator",
    "raw_candidate_evidence_text",
    "proposed_review_source_locator",
    "proposed_review_evidence_text",
    "reviewed_source_locator",
    "reviewed_evidence_text",
    "operational_source_locator",
    "operational_evidence_text",
    "referenced_code_link",
    "review_status",
    "required_regression_tests",
    "review_decision",
    "review_comment",
    "reviewer_id",
    "reviewer_role",
    "reviewed_at",
)

TRIAGE_REQUIRED_FIELDS = (
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

KOREAN_TRIAGE_FIELDS = (
    "expected_decision_ko",
    "decision_reason_ko",
    "expert_question_ko",
)

IDENTITY_FIELDS = (
    ("rule_id", "rule_id"),
    ("rule_type", "rule_type"),
    ("product_name", "product_name"),
    ("item_sequence", "item_sequence"),
    ("current_rule_scope", "current_scope"),
)

HUMAN_REVIEW_FIELDS = (
    "review_decision",
    "review_comment",
    "reviewer_id",
    "reviewer_role",
    "reviewed_at",
)

INACTIVE_EVIDENCE_FIELDS = (
    "reviewed_source_locator",
    "reviewed_evidence_text",
    "operational_source_locator",
    "operational_evidence_text",
)

ALLOWED_RENDERED_PACKET_DISCLAIMER_LINES = frozenset(
    {
        "경고: `release_ready=true`로 간주하지 않는다.",
        "경고: `human_expert_verified`가 아니다.",
        "경고: 전문가 검토 완료로 간주하지 않는다.",
    }
)


def _absolute_lexical_path(path: Path) -> Path:
    if ".." in path.parts:
        raise ValueError(f"output path aliases are not allowed: {path}")
    return Path(os.path.abspath(path))


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    )


def _validate_canonical_output(
    path: Path,
    *,
    root: Path,
    relative: Path,
    label: str,
) -> Path:
    root_path = _absolute_lexical_path(root)
    expected = _absolute_lexical_path(root_path / relative)
    requested = _absolute_lexical_path(path)
    if requested != expected:
        raise ValueError(
            f"{label} output must be the canonical path {expected}; got {requested}"
        )

    current = root_path
    if _is_link_or_junction(current):
        raise ValueError(f"{label} output root cannot be a symlink or junction: {current}")
    for part in relative.parts:
        current = current / part
        if _is_link_or_junction(current):
            raise ValueError(
                f"{label} output cannot traverse a symlink or junction: {current}"
            )
    if requested.exists() and requested.stat().st_nlink > 1:
        raise ValueError(
            f"{label} output cannot overwrite a hardlink/samefile alias: {requested}"
        )
    return requested


def validate_review_output_paths(
    *,
    packet_path: Path,
    audit_path: Path,
    root: Path = ROOT,
) -> tuple[Path, Path]:
    packet = _validate_canonical_output(
        packet_path,
        root=root,
        relative=PACKET_RELATIVE,
        label="review packet",
    )
    audit = _validate_canonical_output(
        audit_path,
        root=root,
        relative=AUDIT_RELATIVE,
        label="review packet audit",
    )
    if packet.exists() and audit.exists() and os.path.samefile(packet, audit):
        raise ValueError("review packet outputs cannot be samefile aliases")
    return packet, audit


@dataclass
class _StagedOutput:
    path: Path
    descriptor: int
    payload: bytes
    device: int
    inode: int


@dataclass
class _PriorOutput:
    existed: bool
    payload: bytes | None
    backup: _StagedOutput | None


@dataclass(frozen=True)
class _InputSnapshot:
    path: Path
    relative: str
    identity: tuple[int, int, int, int, int]
    payload: bytes
    sha256: str


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_delete_shared_read(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if os.name != "nt":
        return os.open(path, flags)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path.absolute()),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x00000080 | 0x00200000,  # NORMAL | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(int(handle), flags)
    except BaseException:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _validate_review_input_path(path: Path, root: Path, label: str) -> Path:
    root_path = _absolute_lexical_path(root)
    requested = _absolute_lexical_path(path)
    try:
        relative = requested.relative_to(root_path)
    except ValueError as error:
        raise ValueError(
            f"review packet {label} input leaves repository: {requested}"
        ) from error

    current = root_path
    if _is_link_or_junction(current):
        raise ValueError(
            f"review packet {label} input root cannot be a symlink or junction: "
            f"{current}"
        )
    for part in relative.parts:
        current = current / part
        if _is_link_or_junction(current):
            raise ValueError(
                f"review packet {label} input cannot traverse a symlink or "
                f"junction: {current}"
            )
    return requested


def _capture_review_input_set_once(
    root: Path,
    paths: dict[str, Path],
) -> dict[str, _InputSnapshot]:
    root_path = _absolute_lexical_path(root)
    opened_inputs: dict[
        str,
        tuple[Path, str, os.stat_result, int, os.stat_result],
    ] = {}
    lexical_paths: set[Path] = set()
    opened_identities: set[tuple[int, int]] = set()
    try:
        # Open the complete set before reading any member. The held descriptors
        # bind every parsed byte to one file identity for the lifetime of capture.
        for label, path in paths.items():
            lexical = _validate_review_input_path(path, root_path, label)
            relative = lexical.relative_to(root_path).as_posix()
            if lexical in lexical_paths:
                raise ValueError(f"review packet input path is reused: {label}")
            before = os.lstat(lexical)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError(
                    f"review packet {label} input must be a single-link regular "
                    f"file: {lexical}"
                )
            descriptor = _open_delete_shared_read(lexical)
            try:
                opened = os.fstat(descriptor)
                identity = (opened.st_dev, opened.st_ino)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1
                    or (before.st_dev, before.st_ino) != identity
                ):
                    raise ValueError(
                        f"review packet {label} input changed while opening: "
                        f"{lexical}"
                    )
                if identity in opened_identities:
                    raise ValueError(
                        f"review packet input aliases another input: {label}"
                    )
                lexical_paths.add(lexical)
                opened_identities.add(identity)
                opened_inputs[label] = (
                    lexical,
                    relative,
                    before,
                    descriptor,
                    opened,
                )
            except BaseException:
                os.close(descriptor)
                raise

        snapshots: dict[str, _InputSnapshot] = {}
        for label, (
            lexical,
            relative,
            _before,
            descriptor,
            opened,
        ) in opened_inputs.items():
            payload = _read_descriptor(descriptor)
            after = os.fstat(descriptor)
            if _file_identity(opened) != _file_identity(after) or len(payload) != (
                after.st_size
            ):
                raise ValueError(
                    f"review packet {label} input changed while reading: {lexical}"
                )
            snapshots[label] = _InputSnapshot(
                path=lexical,
                relative=relative,
                identity=_file_identity(after),
                payload=payload,
                sha256=sha256_bytes(payload),
            )

        # Revalidate every pathname only after all payloads have been read, while
        # all five identity-bearing descriptors are still held open.
        for label, snapshot in snapshots.items():
            descriptor = opened_inputs[label][3]
            held = os.fstat(descriptor)
            current = os.lstat(snapshot.path)
            if (
                not stat.S_ISREG(held.st_mode)
                or held.st_nlink != 1
                or _file_identity(held) != snapshot.identity
                or not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or (current.st_dev, current.st_ino) != snapshot.identity[:2]
                or _read_descriptor(descriptor) != snapshot.payload
            ):
                raise ValueError(
                    f"review packet {label} input pathname changed: "
                    f"{snapshot.path}"
                )
        return snapshots
    finally:
        for _lexical, _relative, _before, descriptor, _opened in (
            opened_inputs.values()
        ):
            os.close(descriptor)


def _revalidate_review_input_snapshots(
    snapshots: dict[str, _InputSnapshot],
    root: Path,
) -> None:
    try:
        observed_snapshots = _capture_review_input_set_once(
            root,
            {label: snapshot.path for label, snapshot in snapshots.items()},
        )
    except (OSError, ValueError) as error:
        raise ValueError("review packet input snapshot set changed") from error
    for label, expected in snapshots.items():
        observed = observed_snapshots[label]
        if (
            observed.relative != expected.relative
            or observed.path != expected.path
            or observed.identity != expected.identity
            or observed.sha256 != expected.sha256
            or observed.payload != expected.payload
        ):
            raise ValueError(f"review packet input changed: {label}")


def _capture_review_input_set(
    root: Path,
    paths: dict[str, Path],
) -> dict[str, _InputSnapshot]:
    snapshots = _capture_review_input_set_once(root, paths)
    _revalidate_review_input_snapshots(snapshots, root)
    return snapshots


def _revalidate_package_input_snapshots(package: dict[str, Any]) -> None:
    snapshots = package.get("_input_snapshots")
    if snapshots is None:
        return
    root = package.get("_input_root")
    if not isinstance(root, Path):
        raise ValueError("review packet input snapshot root is missing")
    _revalidate_review_input_snapshots(snapshots, root)


def _read_regular_output(path: Path) -> dict[str, Any]:
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"review packet output must be a single-link file: {path}")
    descriptor = _open_delete_shared_read(path)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise ValueError(f"review packet output changed while opening: {path}")
        payload = _read_descriptor(descriptor)
        after = os.fstat(descriptor)
        if _file_identity(opened) != _file_identity(after):
            raise ValueError(f"review packet output changed while reading: {path}")
        current = os.lstat(path)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise ValueError(f"review packet output pathname changed: {path}")
        return {"payload": payload, "identity": _file_identity(after)}
    finally:
        os.close(descriptor)


def _validate_staged_output(staged: _StagedOutput) -> None:
    opened = os.fstat(staged.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"unsafe staged review packet output: {staged.path}")
    if opened.st_size != len(staged.payload) or _read_descriptor(
        staged.descriptor
    ) != staged.payload:
        raise ValueError(f"staged review packet payload changed: {staged.path}")
    metadata = os.lstat(staged.path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"staged review packet pathname changed: {staged.path}")


def _verify_published_output(staged: _StagedOutput, destination: Path) -> None:
    opened = os.fstat(staged.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (staged.device, staged.inode)
        or _read_descriptor(staged.descriptor) != staged.payload
    ):
        raise ValueError(f"post-replace staged review packet changed: {destination}")
    metadata = os.lstat(destination)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"post-replace review packet identity mismatch: {destination}")
    persisted = _read_regular_output(destination)
    if (
        persisted["identity"][:2] != (staged.device, staged.inode)
        or persisted["payload"] != staged.payload
    ):
        raise ValueError(f"post-replace review packet payload mismatch: {destination}")


def _verify_published_output_set(
    staged_outputs: dict[Path, _StagedOutput],
    payloads: dict[Path, bytes],
) -> None:
    identities: set[tuple[int, int]] = set()
    for destination, expected in payloads.items():
        staged = staged_outputs[destination]
        opened = os.fstat(staged.descriptor)
        identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or identity != (staged.device, staged.inode)
            or _read_descriptor(staged.descriptor) != expected
        ):
            raise ValueError(
                f"post-commit review packet descriptor changed: {destination}"
            )
        metadata = os.lstat(destination)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or (metadata.st_dev, metadata.st_ino) != identity
        ):
            raise ValueError(
                f"post-commit review packet pathname identity changed: {destination}"
            )
        if identity in identities:
            raise ValueError(
                f"post-commit review packet outputs alias each other: {destination}"
            )
        identities.add(identity)


def _stage_output(path: Path, payload: bytes) -> _StagedOutput:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    held_descriptor: int | None = None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = os.lstat(temporary)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(f"unsafe staged review packet output: {temporary}")
        held_descriptor = _open_delete_shared_read(temporary)
        staged = _StagedOutput(
            path=temporary,
            descriptor=held_descriptor,
            payload=payload,
            device=metadata.st_dev,
            inode=metadata.st_ino,
        )
        _validate_staged_output(staged)
        return staged
    except BaseException:
        if held_descriptor is not None:
            os.close(held_descriptor)
        temporary.unlink(missing_ok=True)
        raise


def _replace_staged_output(
    staged: _StagedOutput,
    destination: Path,
    *,
    keep_open: bool = False,
) -> None:
    _validate_staged_output(staged)
    os.replace(staged.path, destination)
    try:
        _verify_published_output(staged, destination)
    finally:
        if not keep_open:
            os.close(staged.descriptor)
            staged.descriptor = -1


def _close_staged_output(staged: _StagedOutput) -> None:
    if staged.descriptor >= 0:
        os.close(staged.descriptor)
        staged.descriptor = -1
    staged.path.unlink(missing_ok=True)


def _capture_prior_outputs(paths: list[Path]) -> dict[Path, _PriorOutput]:
    prior: dict[Path, _PriorOutput] = {}
    for path in paths:
        try:
            snapshot = _read_regular_output(path)
        except FileNotFoundError:
            prior[path] = _PriorOutput(False, None, None)
            continue
        payload = snapshot["payload"]
        prior[path] = _PriorOutput(True, payload, _stage_output(path, payload))
    return prior


def _rollback_outputs(
    attempted: list[Path],
    prior: dict[Path, _PriorOutput],
) -> None:
    errors: list[str] = []
    for destination in reversed(attempted):
        previous = prior[destination]
        try:
            if previous.existed:
                if previous.backup is None:
                    raise ValueError(f"missing review packet rollback backup: {destination}")
                _replace_staged_output(previous.backup, destination)
            else:
                destination.unlink(missing_ok=True)
        except Exception as error:
            errors.append(f"{destination}: {type(error).__name__}: {error}")
    for destination in attempted:
        previous = prior[destination]
        try:
            if previous.existed:
                observed = _read_regular_output(destination)["payload"]
                if observed != previous.payload:
                    raise ValueError("restored bytes differ")
            elif destination.exists():
                raise ValueError("new output still exists")
        except Exception as error:
            errors.append(f"{destination}: {type(error).__name__}: {error}")
    if errors:
        raise RuntimeError(f"review packet rollback failed: {errors}")


_RE_FLAG_NAMES = {
    "NOFLAG": re.NOFLAG,
    "ASCII": re.ASCII,
    "IGNORECASE": re.IGNORECASE,
    "LOCALE": re.LOCALE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


def _regex_flags_from_ast(node: ast.expr | None) -> re.RegexFlag:
    if node is None:
        return re.NOFLAG
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return re.RegexFlag(node.value)
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "re"
        and node.attr in _RE_FLAG_NAMES
    ):
        return _RE_FLAG_NAMES[node.attr]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _regex_flags_from_ast(node.left) | _regex_flags_from_ast(node.right)
    raise ValueError("unsupported FORBIDDEN_CLAIMS regular-expression flags")


def forbidden_claims_from_validator_bytes(
    payload: bytes,
) -> tuple[re.Pattern[str], ...]:
    try:
        source = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("triage validator must be UTF-8") from error
    try:
        module = ast.parse(source, filename=TRIAGE_VALIDATOR_RELATIVE.as_posix())
    except SyntaxError as error:
        raise ValueError("triage validator source is not valid Python") from error

    declaration: ast.expr | None = None
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "FORBIDDEN_CLAIMS"
            for target in statement.targets
        ):
            if declaration is not None:
                raise ValueError("triage validator defines FORBIDDEN_CLAIMS twice")
            declaration = statement.value
    if not isinstance(declaration, (ast.Tuple, ast.List)):
        raise ValueError("triage validator FORBIDDEN_CLAIMS must be a tuple or list")

    patterns: list[re.Pattern[str]] = []
    for expression in declaration.elts:
        if not (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Attribute)
            and isinstance(expression.func.value, ast.Name)
            and expression.func.value.id == "re"
            and expression.func.attr == "compile"
        ):
            raise ValueError(
                "triage validator FORBIDDEN_CLAIMS entries must use re.compile"
            )
        if not expression.args or len(expression.args) > 2:
            raise ValueError("unsupported FORBIDDEN_CLAIMS re.compile arguments")
        pattern_node = expression.args[0]
        if not (
            isinstance(pattern_node, ast.Constant)
            and isinstance(pattern_node.value, str)
        ):
            raise ValueError("FORBIDDEN_CLAIMS patterns must be string literals")
        flags_node = expression.args[1] if len(expression.args) == 2 else None
        for keyword in expression.keywords:
            if keyword.arg != "flags" or flags_node is not None:
                raise ValueError("unsupported FORBIDDEN_CLAIMS re.compile keyword")
            flags_node = keyword.value
        patterns.append(
            re.compile(pattern_node.value, _regex_flags_from_ast(flags_node))
        )
    if not patterns:
        raise ValueError("triage validator FORBIDDEN_CLAIMS cannot be empty")
    return tuple(patterns)


def forbidden_claim_patterns(
    value: str,
    forbidden_claims: tuple[re.Pattern[str], ...] = TRIAGE_FORBIDDEN_CLAIMS,
) -> list[str]:
    return [
        pattern.pattern
        for pattern in forbidden_claims
        if pattern.search(value)
    ]


def validate_inactive_triage_claims(
    row: dict[str, str],
    *,
    forbidden_claims: tuple[
        re.Pattern[str], ...
    ] = TRIAGE_FORBIDDEN_CLAIMS,
) -> None:
    candidate_id = row.get("evidence_candidate_id", "").strip()
    joined_text = "\n".join(row.get(field, "") for field in TRIAGE_REQUIRED_FIELDS)
    matches = forbidden_claim_patterns(joined_text, forbidden_claims)
    if matches:
        raise ValueError(
            "FORBIDDEN_REVIEW_OR_ACTIVATION_CLAIM "
            f"id={candidate_id} patterns={matches}"
        )


def validate_rendered_packet_claims(
    markdown: str,
    *,
    forbidden_claims: tuple[
        re.Pattern[str], ...
    ] = TRIAGE_FORBIDDEN_CLAIMS,
) -> None:
    prohibited: list[str] = []
    for raw_line in markdown.splitlines():
        if raw_line in ALLOWED_RENDERED_PACKET_DISCLAIMER_LINES:
            continue
        scan_line = raw_line
        for escaped in (r"\_", r"\*", r"\[", r"\]", r"\<", r"\>"):
            scan_line = scan_line.replace(escaped, escaped[1:])
        prohibited.extend(forbidden_claim_patterns(scan_line, forbidden_claims))
    if prohibited:
        raise ValueError(
            "rendered packet contains prohibited approval/activation claims: "
            f"{sorted(set(prohibited))}"
        )


def parse_csv_bytes(
    payload: bytes,
    path: Path,
    required_fields: tuple[str, ...],
) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"CSV input must be UTF-8: {path}") from error
    with io.StringIO(text, newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError(f"duplicate columns in {path}")
        missing = sorted(set(required_fields) - set(fields))
        if missing:
            raise ValueError(f"missing columns in {path}: {missing}")
        return fields, list(reader)


def read_csv(
    path: Path, required_fields: tuple[str, ...]
) -> tuple[list[str], list[dict[str, str]]]:
    return parse_csv_bytes(path.read_bytes(), path, required_fields)


def parse_json_bytes(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"JSON input is invalid: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    return parse_json_bytes(path.read_bytes(), path)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def duplicate_ids(rows: list[dict[str, str]]) -> list[str]:
    counts = Counter(row.get("evidence_candidate_id", "").strip() for row in rows)
    return sorted(value for value, count in counts.items() if value and count > 1)


def require_fields_present(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
    label: str,
) -> None:
    missing: list[str] = []
    for row_number, row in enumerate(rows, 2):
        for field in fields:
            if field not in row:
                missing.append(f"row={row_number} field={field}")
    if missing:
        raise ValueError(f"missing required fields in {label}: {missing}")


def require_values(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
    label: str,
) -> None:
    missing: list[str] = []
    for row_number, row in enumerate(rows, 2):
        for field in fields:
            if not row.get(field, "").strip():
                missing.append(f"row={row_number} field={field}")
    if missing:
        raise ValueError(f"blank required values in {label}: {missing}")


def validate_queue_inventory(
    *,
    root: Path,
    queue_path: Path,
    queue_fields: list[str],
    queue_rows: list[dict[str, str]],
    inventory: dict[str, Any],
    queue_payload: bytes | None = None,
    queue_relative: str | None = None,
) -> None:
    relative = queue_relative or relative_path(queue_path, root)
    record = inventory.get("artifacts", {}).get(relative)
    if record is None:
        raise ValueError(f"evidence inventory has no expert queue artifact: {relative}")
    if queue_payload is None:
        queue_payload = queue_path.read_bytes()
    observed = {
        "rows": len(queue_rows),
        "bytes": len(queue_payload),
        "sha256": sha256_bytes(queue_payload),
        "fields": queue_fields,
    }
    if record != observed:
        raise ValueError(
            f"expert queue does not match evidence inventory: expected={record}, "
            f"observed={observed}"
        )
    counts = inventory.get("counts", {})
    if counts.get("candidate_operational_status_counts") != {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }:
        raise ValueError("evidence inventory operational status counts are invalid")
    review_boundary = inventory.get("review_boundary", {})
    if review_boundary.get(
        "expert_review_queue_operational_status"
    ) != "inactive_candidate":
        raise ValueError("evidence inventory does not mark the expert queue inactive")
    if (
        review_boundary.get("existing_human_expert_verified_primary_rows") != 15
        or review_boundary.get("new_human_expert_reviews") != 0
    ):
        raise ValueError("evidence inventory human review boundary is invalid")
    if review_boundary.get("expert_review_queue_human_fields") != list(
        HUMAN_REVIEW_FIELDS
    ):
        raise ValueError("evidence inventory human review fields are invalid")


def join_rows(
    queue_rows: list[dict[str, str]],
    triage_rows: list[dict[str, str]],
    *,
    expected_items: int = EXPECTED_ITEMS,
    forbidden_claims: tuple[
        re.Pattern[str], ...
    ] = TRIAGE_FORBIDDEN_CLAIMS,
) -> list[dict[str, dict[str, str]]]:
    require_fields_present(
        queue_rows,
        QUEUE_REQUIRED_FIELDS,
        "expert review queue",
    )
    require_fields_present(
        triage_rows,
        TRIAGE_REQUIRED_FIELDS,
        "semantic triage",
    )
    require_values(
        queue_rows,
        tuple(
            field
            for field in QUEUE_REQUIRED_FIELDS
            if field not in (*HUMAN_REVIEW_FIELDS, *INACTIVE_EVIDENCE_FIELDS)
        ),
        "expert review queue",
    )
    require_values(triage_rows, TRIAGE_REQUIRED_FIELDS, "semantic triage")

    queue_duplicates = duplicate_ids(queue_rows)
    triage_duplicates = duplicate_ids(triage_rows)
    if queue_duplicates:
        raise ValueError(f"duplicate queue candidate IDs: {queue_duplicates}")
    if triage_duplicates:
        raise ValueError(f"duplicate triage candidate IDs: {triage_duplicates}")

    queue_by_id = {row["evidence_candidate_id"].strip(): row for row in queue_rows}
    triage_by_id = {row["evidence_candidate_id"].strip(): row for row in triage_rows}
    if len(queue_by_id) != expected_items:
        raise ValueError(
            f"expected {expected_items} unique queue items, found {len(queue_by_id)}"
        )
    if len(triage_by_id) != expected_items:
        raise ValueError(
            f"expected {expected_items} unique triage items, found {len(triage_by_id)}"
        )

    queue_without_triage = sorted(set(queue_by_id) - set(triage_by_id))
    triage_without_queue = sorted(set(triage_by_id) - set(queue_by_id))
    if queue_without_triage or triage_without_queue:
        raise ValueError(
            "queue/triage candidate mismatch: "
            f"queue_without_triage={queue_without_triage}, "
            f"triage_without_queue={triage_without_queue}"
        )

    joined: list[dict[str, dict[str, str]]] = []
    for candidate_id in sorted(queue_by_id):
        queue = queue_by_id[candidate_id]
        triage = triage_by_id[candidate_id]
        if queue["review_status"] != "needs_expert_review":
            raise ValueError(
                f"queue item is not awaiting expert review: {candidate_id}"
            )
        if queue["candidate_operational_status"] != "inactive_candidate":
            raise ValueError(
                f"queue item is operationally active: {candidate_id}"
            )
        evidence_leaks = [
            field
            for field in INACTIVE_EVIDENCE_FIELDS
            if queue.get(field, "").strip()
        ]
        if evidence_leaks:
            raise ValueError(
                "inactive queue item carries reviewed or operational evidence for "
                f"{candidate_id}: {evidence_leaks}"
            )
        prefilled = [
            field for field in HUMAN_REVIEW_FIELDS if queue.get(field, "").strip()
        ]
        if prefilled:
            raise ValueError(
                f"human review fields are prefilled for {candidate_id}: {prefilled}"
            )
        source_match = OFFICIAL_SOURCE_PATTERN.fullmatch(queue["source_url"])
        if source_match is None:
            raise ValueError(
                f"non-official source URL for {candidate_id}: {queue['source_url']}"
            )
        if source_match.group("item_sequence") != queue["item_sequence"]:
            raise ValueError(
                f"source product mismatch for {candidate_id}: "
                f"item_sequence={queue['item_sequence']}, "
                f"source_url={queue['source_url']}"
            )
        if SOURCE_VERSION_PATTERN.fullmatch(queue["source_version"]) is None:
            raise ValueError(
                f"source version is not SHA-256 pinned for {candidate_id}: "
                f"{queue['source_version']}"
            )
        for queue_field, triage_field in IDENTITY_FIELDS:
            if queue[queue_field] != triage[triage_field]:
                raise ValueError(
                    f"identity mismatch for {candidate_id}: "
                    f"queue.{queue_field}={queue[queue_field]!r}, "
                    f"triage.{triage_field}={triage[triage_field]!r}"
                )
        status = triage["recommended_status"]
        if status not in ALLOWED_RECOMMENDED_STATUSES:
            raise ValueError(
                f"invalid recommended status for {candidate_id}: {status}"
            )
        validate_inactive_triage_claims(
            triage,
            forbidden_claims=forbidden_claims,
        )
        non_korean = [
            field
            for field in KOREAN_TRIAGE_FIELDS
            if HANGUL_PATTERN.search(triage[field]) is None
        ]
        if non_korean:
            raise ValueError(
                f"Korean triage fields contain no Hangul for {candidate_id}: "
                f"{non_korean}"
            )
        joined.append({"queue": queue, "triage": triage})
    return joined


def one_line(value: str) -> str:
    return " ".join(value.split())


def regression_test_text(value: str) -> str:
    tokens = [token.strip() for token in value.split("|") if token.strip()]
    if len(tokens) != len(set(tokens)):
        raise ValueError(f"duplicate regression test token: {value}")
    unknown = sorted(set(tokens) - set(REGRESSION_TEST_LABELS))
    if unknown:
        raise ValueError(f"unknown regression test tokens: {unknown}")
    if set(tokens) != set(REGRESSION_TEST_LABELS):
        missing = sorted(set(REGRESSION_TEST_LABELS) - set(tokens))
        raise ValueError(f"missing regression test tokens: {missing}")
    return "·".join(REGRESSION_TEST_LABELS[token] for token in tokens)


def markdown_text(value: str) -> str:
    output = one_line(value)
    for character in ("\\", "`", "*", "_", "[", "]", "<", ">"):
        output = output.replace(character, f"\\{character}")
    return output


def inline_code(value: str) -> str:
    return one_line(value).replace("`", "\\`")


def sorted_counts(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {key: counts[key] for key in sorted(counts)}


def render_markdown(
    items: list[dict[str, dict[str, str]]],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# v5.1 전문가 검토 패킷",
        "",
        "> 이 패킷의 모든 항목은 사람 전문가가 검증하기 전까지 비활성이다. "
        "권고 상태는 자동 검토 결과이며 승인 기록이 아니다.",
        "",
        "## 검토 범위와 사용 금지",
        "",
        "이 패킷은 v5.0의 미검증 후보 목록(shortlist) 33개를 검토하기 위한 "
        "읽기 전용 자료다. "
        "사람 전문가가 원문, 적용 범위, 판정문을 확인하고 승인하기 전에는 어떤 항목도 "
        "엔진, 실행 데이터(runtime), 사용자 화면(UI) 또는 운영 판정에 연결하지 않는다.",
        "",
        "`provisional`, `needs_expert_review`, `rejected`는 자동 권고 상태다. "
        "`provisional`도 사람 전문가 검증 전에는 활성 상태가 아니다.",
        "",
        "## 결합 감사 요약",
        "",
        f"- 전문가 검토 큐: {summary['queue_rows']}개",
        f"- 의미 검토 행: {summary['triage_rows']}개",
        f"- 패킷 수록 항목: {summary['packet_items']}개",
        f"- 큐 중복 ID: {summary['queue_duplicate_ids']}개",
        f"- 의미 검토 중복 ID: {summary['triage_duplicate_ids']}개",
        f"- 의미 검토가 없는 큐 항목: {summary['queue_without_triage']}개",
        f"- 큐에 없는 의미 검토 항목: {summary['triage_without_queue']}개",
        f"- 사람 승인 입력: {summary['human_review_prefilled']}개",
        f"- 활성 항목: {summary['activated_items']}개",
        f"- 비활성 후보: {summary['inactive_candidate_items']}개",
        "- 채택 시 필수 회귀 테스트를 적은 항목: "
        f"{summary['items_with_required_regression_tests']}개",
        "",
        "### 권고 상태별 수",
        "",
        "| 권고 상태 | 항목 수 |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| `{status}` | {count} |"
        for status, count in summary["recommended_status_counts"].items()
    )
    lines.extend(
        [
            "",
            "### 의미 관계별 수",
            "",
            "| 의미 관계 | 항목 수 |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| `{relation}` | {count} |"
        for relation, count in summary["semantic_relation_counts"].items()
    )
    lines.extend(
        [
            "",
            "## 전문가 검토 항목",
            "",
            "각 항목에서 공식 허가 원문과 위치를 먼저 확인한다. 그다음 제안 조건이 "
            "참조 규칙 범위를 부당하게 넓히지 않는지 판단한다.",
            "",
        ]
    )

    for index, item in enumerate(items, 1):
        queue = item["queue"]
        triage = item["triage"]
        required_tests = regression_test_text(queue["required_regression_tests"])
        lines.extend(
            [
                f"## {index}. {markdown_text(queue['evidence_candidate_id'])}",
                "",
                f"- 권고 상태: `{triage['recommended_status']}`",
                f"- 의미 관계: `{triage['semantic_relation']}`",
                f"- 규칙: `{inline_code(queue['rule_id'])}` / "
                f"`{inline_code(queue['rule_type'])}`",
                "- 후보 운영 상태: "
                f"`{inline_code(queue['candidate_operational_status'])}`",
                "- 참조 규칙 상태: "
                f"`{inline_code(queue['referenced_rule_status'])}`",
                f"- 제품: {markdown_text(queue['product_name'])} "
                f"(`{inline_code(queue['item_sequence'])}`)",
                f"- 공식 허가 원문: [{markdown_text(queue['source_id'])}]"
                f"({queue['source_url']})",
                f"- 원문 버전: `{inline_code(queue['source_version'])}`",
                "- 원시 후보 원문 위치: "
                f"{markdown_text(queue['raw_candidate_source_locator'])}",
                "- 검토 제안 원문 위치: "
                f"{markdown_text(queue['proposed_review_source_locator'])}",
                f"- 참조 규칙 범위: `{inline_code(queue['current_rule_scope'])}`",
                "- 참조 규칙 실행 조건: "
                f"`{inline_code(queue['referenced_runtime_condition'])}`",
                "- 참조 코드 위치: "
                f"`{inline_code(queue['referenced_code_link'])}`",
                "- 제안 적용 범위·판정 조건: "
                f"{markdown_text(triage['proposed_trigger'])}",
                f"- 후보 판정문: {markdown_text(triage['expected_decision_ko'])}",
                f"- 현재 후보 사용자 문구: {markdown_text(queue['proposed_message_ko'])}",
                f"- 현재 후보 다음 행동: {markdown_text(queue['proposed_next_action_ko'])}",
                f"- 판단 근거: {markdown_text(triage['decision_reason_ko'])}",
                f"- 전문가 확인 질문: {markdown_text(triage['expert_question_ko'])}",
                "- 원시 후보 원문: "
                f"{markdown_text(queue['raw_candidate_evidence_text'])}",
                "- 검토 제안 원문: "
                f"{markdown_text(queue['proposed_review_evidence_text'])}",
                f"- 채택 시 필수 회귀 테스트: {required_tests}",
                "- 사람 검토 결과: ☐ 채택 ☐ 수정 후 채택 ☐ 기각",
                "- 검토자 ID:",
                "- 검토자 역할:",
                "- 검토일:",
                "- 검토 의견:",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_from_rows(
    queue_rows: list[dict[str, str]],
    triage_rows: list[dict[str, str]],
    *,
    expected_items: int = EXPECTED_ITEMS,
    forbidden_claims: tuple[
        re.Pattern[str], ...
    ] = TRIAGE_FORBIDDEN_CLAIMS,
) -> dict[str, Any]:
    items = join_rows(
        queue_rows,
        triage_rows,
        expected_items=expected_items,
        forbidden_claims=forbidden_claims,
    )
    candidate_operational_status_counts = sorted_counts(
        [item["queue"]["candidate_operational_status"] for item in items]
    )
    summary = {
        "queue_rows": len(queue_rows),
        "triage_rows": len(triage_rows),
        "packet_items": len(items),
        "unique_candidate_ids": len(
            {item["queue"]["evidence_candidate_id"] for item in items}
        ),
        "recommended_status_counts": sorted_counts(
            [item["triage"]["recommended_status"] for item in items]
        ),
        "semantic_relation_counts": sorted_counts(
            [item["triage"]["semantic_relation"] for item in items]
        ),
        "queue_duplicate_ids": 0,
        "triage_duplicate_ids": 0,
        "queue_without_triage": 0,
        "triage_without_queue": 0,
        "human_review_prefilled": 0,
        "candidate_operational_status_counts": candidate_operational_status_counts,
        "activated_items": candidate_operational_status_counts.get(
            "active_existing_released_primary_evidence", 0
        ),
        "inactive_candidate_items": candidate_operational_status_counts.get(
            "inactive_candidate", 0
        ),
        "items_with_required_regression_tests": len(items),
    }
    markdown = render_markdown(items, summary)
    validate_rendered_packet_claims(
        markdown,
        forbidden_claims=forbidden_claims,
    )
    return {
        "items": items,
        "summary": summary,
        "markdown": markdown,
    }


def build(
    root: Path = ROOT,
    queue_path: Path | None = None,
    triage_path: Path | None = None,
    packet_path: Path | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    root = _absolute_lexical_path(root)
    queue_path = queue_path or root / QUEUE_RELATIVE
    triage_path = triage_path or root / TRIAGE_RELATIVE
    packet_path = packet_path or root / PACKET_RELATIVE
    inventory_path = inventory_path or root / EVIDENCE_INVENTORY_RELATIVE
    packet_path = _validate_canonical_output(
        packet_path,
        root=root,
        relative=PACKET_RELATIVE,
        label="review packet",
    )
    snapshots = _capture_review_input_set(
        root,
        {
            "queue": queue_path,
            "triage": triage_path,
            "inventory": inventory_path,
            "generator": root / GENERATOR_RELATIVE,
            "validator": root / TRIAGE_VALIDATOR_RELATIVE,
        },
    )
    queue_snapshot = snapshots["queue"]
    triage_snapshot = snapshots["triage"]
    inventory_snapshot = snapshots["inventory"]
    generator_snapshot = snapshots["generator"]
    validator_snapshot = snapshots["validator"]

    queue_fields, queue_rows = parse_csv_bytes(
        queue_snapshot.payload,
        queue_snapshot.path,
        QUEUE_REQUIRED_FIELDS,
    )
    triage_fields, triage_rows = parse_csv_bytes(
        triage_snapshot.payload,
        triage_snapshot.path,
        TRIAGE_REQUIRED_FIELDS,
    )
    evidence_inventory = parse_json_bytes(
        inventory_snapshot.payload,
        inventory_snapshot.path,
    )
    forbidden_claims = forbidden_claims_from_validator_bytes(
        validator_snapshot.payload
    )
    validate_queue_inventory(
        root=root,
        queue_path=queue_snapshot.path,
        queue_fields=queue_fields,
        queue_rows=queue_rows,
        inventory=evidence_inventory,
        queue_payload=queue_snapshot.payload,
        queue_relative=queue_snapshot.relative,
    )
    package = build_from_rows(
        queue_rows,
        triage_rows,
        forbidden_claims=forbidden_claims,
    )
    packet_bytes = package["markdown"].encode("utf-8")
    package["audit"] = {
        "schema_version": "1.0.0",
        "release_lineage": "v5.1",
        "source_lineage": "v5.0_read_only",
        "generator": GENERATOR_RELATIVE.as_posix(),
        "generator_sha256": generator_snapshot.sha256,
        "inputs": {
            queue_snapshot.relative: {
                "rows": len(queue_rows),
                "fields": queue_fields,
                "bytes": len(queue_snapshot.payload),
                "sha256": queue_snapshot.sha256,
            },
            triage_snapshot.relative: {
                "rows": len(triage_rows),
                "fields": triage_fields,
                "bytes": len(triage_snapshot.payload),
                "sha256": triage_snapshot.sha256,
            },
            inventory_snapshot.relative: {
                "bytes": len(inventory_snapshot.payload),
                "sha256": inventory_snapshot.sha256,
            },
            generator_snapshot.relative: {
                "bytes": len(generator_snapshot.payload),
                "sha256": generator_snapshot.sha256,
            },
            validator_snapshot.relative: {
                "bytes": len(validator_snapshot.payload),
                "sha256": validator_snapshot.sha256,
            },
        },
        "artifact": {
            "path": PACKET_RELATIVE.as_posix(),
            "items": package["summary"]["packet_items"],
            "bytes": len(packet_bytes),
            "sha256": sha256_bytes(packet_bytes),
        },
        "counts": package["summary"],
        "checks": {
            "expected_items": EXPECTED_ITEMS,
            "expert_queue_matches_evidence_inventory": True,
            "all_queue_items_joined_exactly_once": True,
            "queue_duplicate_ids": [],
            "triage_duplicate_ids": [],
            "queue_without_triage": [],
            "triage_without_queue": [],
            "identity_mismatches": [],
            "non_official_source_urls": [],
            "prefilled_human_review_items": [],
            "all_human_review_fields_blank": True,
            "operationally_active_queue_items": [],
            "reviewed_or_operational_evidence_on_queue_items": [],
            "all_source_versions_sha256_pinned": True,
            "all_items_include_required_regression_tests": True,
            "triage_forbidden_claim_validator_shared": True,
            "rendered_packet_forbidden_claim_scan": True,
        },
        "activation_boundary": {
            "human_expert_verification_required": True,
            "recommended_status_is_not_human_approval": True,
            "candidate_operational_status_field": "candidate_operational_status",
            "candidate_operational_status_counts": package["summary"][
                "candidate_operational_status_counts"
            ],
            "activated_items": package["summary"]["activated_items"],
            "inactive_candidate_items": package["summary"][
                "inactive_candidate_items"
            ],
            "required_human_review_fields": list(HUMAN_REVIEW_FIELDS),
            "context_only_fields": [
                "referenced_rule_status",
                "referenced_runtime_condition",
                "referenced_code_link",
            ],
            "prohibited_targets_before_approval": [
                "engine",
                "runtime",
                "UI",
                "operational_decision",
            ],
        },
    }
    package["_input_snapshots"] = snapshots
    package["_input_root"] = root
    _revalidate_package_input_snapshots(package)
    return package


def write(
    package: dict[str, Any],
    packet_path: Path = PACKET_PATH,
    audit_path: Path = AUDIT_PATH,
    *,
    root: Path = ROOT,
) -> None:
    packet_path, audit_path = validate_review_output_paths(
        packet_path=packet_path,
        audit_path=audit_path,
        root=root,
    )
    packet_payload = package["markdown"].encode("utf-8")
    audit_payload = (
        json.dumps(package["audit"], ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    payloads = {
        packet_path: packet_payload,
        audit_path: audit_payload,
    }
    publish_order = [packet_path, audit_path]
    staged: dict[Path, _StagedOutput] = {}
    prior: dict[Path, _PriorOutput] = {}
    attempted: list[Path] = []
    try:
        _revalidate_package_input_snapshots(package)
        for path, payload in payloads.items():
            staged[path] = _stage_output(path, payload)
        prior = _capture_prior_outputs(publish_order)
        validate_review_output_paths(
            packet_path=packet_path,
            audit_path=audit_path,
            root=root,
        )
        _revalidate_package_input_snapshots(package)
        for path in publish_order:
            validate_review_output_paths(
                packet_path=packet_path,
                audit_path=audit_path,
                root=root,
            )
            _revalidate_package_input_snapshots(package)
            attempted.append(path)
            _replace_staged_output(staged[path], path, keep_open=True)
        validate_review_output_paths(
            packet_path=packet_path,
            audit_path=audit_path,
            root=root,
        )
        for path, payload in payloads.items():
            if _read_regular_output(path)["payload"] != payload:
                raise ValueError(f"post-commit review packet payload mismatch: {path}")
        _revalidate_package_input_snapshots(package)
        _verify_published_output_set(staged, payloads)
    except BaseException as error:
        for path in attempted:
            published = staged[path]
            if published.descriptor >= 0:
                os.close(published.descriptor)
                published.descriptor = -1
        try:
            _rollback_outputs(attempted, prior)
        except Exception as rollback_error:
            raise RuntimeError(
                f"review packet publish failed and rollback failed: {rollback_error}"
            ) from error
        raise
    finally:
        all_staged = [*staged.values()]
        all_staged.extend(
            previous.backup
            for previous in prior.values()
            if previous.backup is not None
        )
        for temporary in all_staged:
            _close_staged_output(temporary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--triage", type=Path, default=TRIAGE_PATH)
    parser.add_argument("--packet", type=Path, default=PACKET_PATH)
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument(
        "--evidence-inventory", type=Path, default=EVIDENCE_INVENTORY_PATH
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet_path, audit_path = validate_review_output_paths(
            packet_path=args.packet,
            audit_path=args.audit,
            root=ROOT,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    package = build(
        queue_path=args.queue.resolve(),
        triage_path=args.triage.resolve(),
        packet_path=packet_path,
        inventory_path=args.evidence_inventory.resolve(),
    )
    write(package, packet_path, audit_path, root=ROOT)
    print(
        json.dumps(
            {
                "packet": relative_path(packet_path, ROOT),
                "audit": relative_path(audit_path, ROOT),
                "counts": package["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
