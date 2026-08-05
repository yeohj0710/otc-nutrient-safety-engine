from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_LINKS_RELATIVE = Path("research_v51/evidence/evidence_rule_links.csv")
BASELINE_MANIFEST_RELATIVE = Path("research_v51/audit/baseline_manifest.json")
GENERATOR_RELATIVE = Path("scripts/research/otc/audit_v51_source_freshness.py")
OUTPUT_RELATIVE = Path("research_v51/audit/source_freshness_snapshot.json")
EVIDENCE_LINKS = ROOT / EVIDENCE_LINKS_RELATIVE
DEFAULT_OUTPUT = ROOT / OUTPUT_RELATIVE
SCRATCH_PARENT = ROOT / "etc" / "v51-source-freshness"
MFDS_PDF_RE = re.compile(
    r"^https://nedrug\.mfds\.go\.kr/dsie/pdf/drb/(?P<item_sequence>\d+)/"
    r"(?P<document_type>EE|UD|NB)$"
)
USER_AGENT = "Mozilla/5.0 (compatible; Codex-v51-source-audit/1.0)"
EXPECTED_CANDIDATE_LINK_COUNT = 360
EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS = frozenset(
    {
        "SAFE-OTC-01-NB-P1-B12-duplicate_ingredient",
        "SAFE-OTC-01-NB-P1-B24-hepatic_disease",
        "SAFE-OTC-01-NB-P1-B3-alcohol",
        "SAFE-OTC-01-NB-P2-B12-urgent_referral",
        "SAFE-OTC-01-UD-P1-B2-age_restriction",
        "SAFE-OTC-01-UD-P1-B3-minimum_interval",
        "SAFE-OTC-01-UD-P1-B4-max_daily_dose",
        "SAFE-OTC-05-NB-P1-B17-gi_bleeding_ulcer",
        "SAFE-OTC-05-NB-P2-B17-duplicate_pharmacologic_class",
        "SAFE-OTC-05-NB-P2-B9-pregnancy_lactation",
        "SAFE-OTC-05-NB-P3-B2-renal_disease",
        "SAFE-OTC-05-NB-P4-B10-anticoagulant_antiplatelet",
        "SAFE-OTC-10-NB-P1-B20-sedative_medication",
        "SAFE-OTC-10-NB-P2-B4-decongestant_hypertension",
        "SAFE-OTC-10-NB-P3-B8-sedation_driving",
    }
)
EXPECTED_SOURCE_LINK_COUNTS = {
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/196800036/NB": (25, 3),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/197500016/NB": (59, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/197500016/UD": (3, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/198400250/NB": (5, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/198601920/NB": (57, 5),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/198601920/UD": (2, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/198700405/NB": (3, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/199400202/NB": (26, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/199801026/NB": (3, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/199801026/UD": (1, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/199900926/NB": (3, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/200300406/NB": (3, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/200501321/NB": (4, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/200610765/NB": (17, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/200610765/UD": (2, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/201110646/NB": (79, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/NB": (31, 4),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/UD": (3, 3),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202200525/NB": (32, 0),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202200525/UD": (2, 0),
}
EXPECTED_OFFICIAL_SOURCE_URLS = frozenset(EXPECTED_SOURCE_LINK_COUNTS)
EXPECTED_VERIFIED_PRIMARY_IDS_BY_URL = {
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/196800036/NB": frozenset(
        {
            "SAFE-OTC-10-NB-P1-B20-sedative_medication",
            "SAFE-OTC-10-NB-P2-B4-decongestant_hypertension",
            "SAFE-OTC-10-NB-P3-B8-sedation_driving",
        }
    ),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/198601920/NB": frozenset(
        {
            "SAFE-OTC-05-NB-P1-B17-gi_bleeding_ulcer",
            "SAFE-OTC-05-NB-P2-B17-duplicate_pharmacologic_class",
            "SAFE-OTC-05-NB-P2-B9-pregnancy_lactation",
            "SAFE-OTC-05-NB-P3-B2-renal_disease",
            "SAFE-OTC-05-NB-P4-B10-anticoagulant_antiplatelet",
        }
    ),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/NB": frozenset(
        {
            "SAFE-OTC-01-NB-P1-B12-duplicate_ingredient",
            "SAFE-OTC-01-NB-P1-B24-hepatic_disease",
            "SAFE-OTC-01-NB-P1-B3-alcohol",
            "SAFE-OTC-01-NB-P2-B12-urgent_referral",
        }
    ),
    "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/UD": frozenset(
        {
            "SAFE-OTC-01-UD-P1-B2-age_restriction",
            "SAFE-OTC-01-UD-P1-B3-minimum_interval",
            "SAFE-OTC-01-UD-P1-B4-max_daily_dose",
        }
    ),
}
CANDIDATE_SOURCE_IDENTITY_FIELDS = (
    "evidence_candidate_id",
    "rule_id",
    "rule_type",
    "item_sequence",
    "product_id",
    "product_name",
    "document_type",
    "source_id",
    "source_url",
    "source_version",
    "source_pdf_sha256",
    "raw_candidate_source_locator",
    "raw_candidate_evidence_text",
)
EXPECTED_CANDIDATE_SOURCE_INVENTORY_SHA256 = (
    "5fb31f5816864ce8fd8046326353d27896e2f931305343854c603d12d9d0dfce"
)


@dataclass(frozen=True)
class SourceRecord:
    url: str
    item_sequence: str
    product_id: str
    product_name: str
    document_type: str
    pinned_pdf_sha256: str
    evidence_rows: tuple[dict[str, str], ...]


FetchPdf = Callable[[str, float, int], bytes]
ExtractPdfText = Callable[[bytes, SourceRecord, Path], str]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _absolute_lexical_path(path: Path) -> Path:
    if ".." in path.parts:
        raise ValueError(f"output path aliases are not allowed: {path}")
    return Path(os.path.abspath(path))


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    )


def validate_snapshot_output(output: Path, *, root: Path = ROOT) -> Path:
    root_path = _absolute_lexical_path(root)
    expected = _absolute_lexical_path(root_path / OUTPUT_RELATIVE)
    requested = _absolute_lexical_path(output)
    if requested != expected:
        raise ValueError(
            f"freshness output must be the canonical path {expected}; got {requested}"
        )

    current = root_path
    if _is_link_or_junction(current):
        raise ValueError(
            f"freshness output root cannot be a symlink or junction: {current}"
        )
    for part in OUTPUT_RELATIVE.parts:
        current = current / part
        if _is_link_or_junction(current):
            raise ValueError(
                "freshness output cannot traverse a symlink or junction: "
                f"{current}"
            )
    if requested.exists() and requested.stat().st_nlink > 1:
        raise ValueError(
            "freshness output cannot overwrite a hardlink/samefile alias: "
            f"{requested}"
        )
    return requested


@dataclass
class _StagedOutput:
    path: Path
    descriptor: int
    payload: bytes
    device: int
    inode: int


@dataclass
class _HeldOutput:
    path: Path
    descriptor: int
    payload: bytes
    identity: tuple[int, int, int, int, int]


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


def _hold_regular_output(path: Path) -> _HeldOutput:
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"freshness output must be a single-link file: {path}")
    descriptor = _open_delete_shared_read(path)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise ValueError(f"freshness output changed while opening: {path}")
        payload = _read_descriptor(descriptor)
        after = os.fstat(descriptor)
        if _file_identity(opened) != _file_identity(after):
            raise ValueError(f"freshness output changed while reading: {path}")
        current = os.lstat(path)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise ValueError(f"freshness output pathname changed: {path}")
        return _HeldOutput(
            path=path,
            descriptor=descriptor,
            payload=payload,
            identity=_file_identity(after),
        )
    except BaseException:
        os.close(descriptor)
        raise


def _revalidate_held_output(held: _HeldOutput) -> None:
    opened = os.fstat(held.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or _file_identity(opened) != held.identity
        or _read_descriptor(held.descriptor) != held.payload
    ):
        raise ValueError(f"freshness held output identity changed: {held.path}")
    metadata = os.lstat(held.path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != held.identity[:2]
    ):
        raise ValueError(f"freshness held output pathname changed: {held.path}")


def _read_regular_output(path: Path) -> dict[str, Any]:
    held = _hold_regular_output(path)
    try:
        return {"payload": held.payload, "identity": held.identity}
    finally:
        os.close(held.descriptor)


def _validate_staged_output(staged: _StagedOutput) -> None:
    opened = os.fstat(staged.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"unsafe staged freshness output: {staged.path}")
    if opened.st_size != len(staged.payload) or _read_descriptor(
        staged.descriptor
    ) != staged.payload:
        raise ValueError(f"staged freshness payload changed: {staged.path}")
    metadata = os.lstat(staged.path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"staged freshness pathname changed: {staged.path}")


def _verify_published_output(staged: _StagedOutput, destination: Path) -> bytes:
    opened = os.fstat(staged.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (staged.device, staged.inode)
        or _read_descriptor(staged.descriptor) != staged.payload
    ):
        raise ValueError(f"post-replace staged freshness output changed: {destination}")
    metadata = os.lstat(destination)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"post-replace freshness output identity mismatch: {destination}")
    persisted = _read_regular_output(destination)
    if (
        persisted["identity"][:2] != (staged.device, staged.inode)
        or persisted["payload"] != staged.payload
    ):
        raise ValueError(f"post-replace freshness payload mismatch: {destination}")
    return persisted["payload"]


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
            raise ValueError(f"unsafe staged freshness output: {temporary}")
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


def _replace_staged_output(staged: _StagedOutput, destination: Path) -> bytes:
    _validate_staged_output(staged)
    os.replace(staged.path, destination)
    try:
        return _verify_published_output(staged, destination)
    finally:
        os.close(staged.descriptor)
        staged.descriptor = -1


def _close_staged_output(staged: _StagedOutput | None) -> None:
    if staged is None:
        return
    if staged.descriptor >= 0:
        os.close(staged.descriptor)
        staged.descriptor = -1
    staged.path.unlink(missing_ok=True)


def _atomic_write_bytes(path: Path, payload: bytes) -> bytes:
    staged = _stage_output(path, payload)
    prior_payload: bytes | None = None
    backup: _StagedOutput | None = None
    existed = False
    attempted = False
    try:
        try:
            prior = _read_regular_output(path)
        except FileNotFoundError:
            pass
        else:
            existed = True
            prior_payload = prior["payload"]
            backup = _stage_output(path, prior_payload)
        attempted = True
        persisted = _replace_staged_output(staged, path)
        if persisted != payload:
            raise ValueError(f"post-commit freshness payload mismatch: {path}")
        return persisted
    except BaseException as error:
        if attempted:
            try:
                if existed:
                    if backup is None:
                        raise ValueError("missing freshness rollback backup")
                    _replace_staged_output(backup, path)
                    if _read_regular_output(path)["payload"] != prior_payload:
                        raise ValueError("restored freshness bytes differ")
                else:
                    path.unlink(missing_ok=True)
            except Exception as rollback_error:
                raise RuntimeError(
                    f"freshness publish failed and rollback failed: {rollback_error}"
                ) from error
        raise
    finally:
        _close_staged_output(staged)
        _close_staged_output(backup)


def write_snapshot(
    snapshot: dict[str, Any],
    *,
    output: Path = DEFAULT_OUTPUT,
    root: Path = ROOT,
) -> None:
    output = validate_snapshot_output(output, root=root)
    payload = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    _atomic_write_bytes(output, payload)


def read_persisted_snapshot(
    output: Path,
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _read_regular_output(output)["payload"]
    return _parse_persisted_snapshot(payload, expected=expected)


def _parse_persisted_snapshot(
    payload: bytes,
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if expected is not None:
        expected_payload = (
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        if payload != expected_payload:
            raise ValueError("persisted freshness snapshot differs from generated bytes")
    value = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("persisted freshness snapshot root must be an object")
    return value


def candidate_source_inventory_sha256(rows: list[dict[str, str]]) -> str:
    payload = [
        {field: row[field] for field in CANDIDATE_SOURCE_IDENTITY_FIELDS}
        for row in sorted(rows, key=lambda row: row["evidence_candidate_id"])
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def normalize_semantic_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.split())


def normalize_excerpt(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def excerpt_matches_document(excerpt: str, normalized_document: str) -> bool:
    segments = [
        normalize_excerpt(segment)
        for segment in re.split(r"(?:…|\.{3,})", excerpt)
        if normalize_excerpt(segment)
    ]
    if not segments:
        return False
    cursor = 0
    for segment in segments:
        position = normalized_document.find(segment, cursor)
        if position < 0:
            return False
        cursor = position + len(segment)
    return True


def split_pages(value: str) -> list[str]:
    pages = value.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def semantic_text_sha256(value: str) -> str:
    return sha256_bytes(normalize_semantic_text(value).encode("utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    return read_csv_bytes(path.read_bytes())


def read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    handle = io.StringIO(payload.decode("utf-8-sig"), newline="")
    return list(csv.DictReader(handle))


def source_records_from_evidence_bytes(payload: bytes) -> list[SourceRecord]:
    """Validate and parse the fixed evidence inventory from one byte snapshot."""

    rows = read_csv_bytes(payload)
    if len(rows) != EXPECTED_CANDIDATE_LINK_COUNT:
        raise ValueError(
            f"expected {EXPECTED_CANDIDATE_LINK_COUNT} evidence candidate links, "
            f"found {len(rows)}"
        )
    required_fields = set(CANDIDATE_SOURCE_IDENTITY_FIELDS) | {"evidence_status"}
    for index, row in enumerate(rows, start=2):
        missing_fields = sorted(required_fields - set(row))
        if missing_fields:
            raise ValueError(
                f"evidence links row {index} is missing fields: "
                f"{', '.join(missing_fields)}"
            )
        blank_fields = sorted(
            field for field in required_fields if not (row.get(field) or "").strip()
        )
        if blank_fields:
            raise ValueError(
                f"evidence links row {index} has blank fields: "
                f"{', '.join(blank_fields)}"
            )

    candidate_ids = [row["evidence_candidate_id"] for row in rows]
    if len(set(candidate_ids)) != EXPECTED_CANDIDATE_LINK_COUNT:
        raise ValueError("evidence candidate IDs must be unique across all 360 links")

    source_urls = {row["source_url"] for row in rows}
    if source_urls != EXPECTED_OFFICIAL_SOURCE_URLS:
        missing = sorted(EXPECTED_OFFICIAL_SOURCE_URLS - source_urls)
        unexpected = sorted(source_urls - EXPECTED_OFFICIAL_SOURCE_URLS)
        raise ValueError(
            "evidence links do not match the approved 20-URL source inventory: "
            f"missing={missing} unexpected={unexpected}"
        )

    verified_ids = {
        row["evidence_candidate_id"]
        for row in rows
        if row["evidence_status"] == "verified_primary"
    }
    if verified_ids != EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS:
        missing = sorted(EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS - verified_ids)
        unexpected = sorted(verified_ids - EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS)
        raise ValueError(
            "evidence links do not match the approved verified-primary candidate IDs: "
            f"missing={missing} unexpected={unexpected}"
        )

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_url"]].append(row)

    sources: list[SourceRecord] = []
    for url, source_rows in grouped.items():
        match = MFDS_PDF_RE.fullmatch(url)
        if not match:
            raise ValueError(f"non-official or unsupported MFDS PDF URL: {url}")
        item_sequences = {row["item_sequence"] for row in source_rows}
        document_types = {row["document_type"] for row in source_rows}
        source_ids = {row["source_id"] for row in source_rows}
        product_ids = {row["product_id"] for row in source_rows}
        product_names = {row["product_name"] for row in source_rows}
        pinned_hashes = {row["source_pdf_sha256"] for row in source_rows}
        source_versions = {row["source_version"] for row in source_rows}
        if item_sequences != {match.group("item_sequence")}:
            raise ValueError(f"source URL/item sequence mismatch: {url}")
        if document_types != {match.group("document_type")}:
            raise ValueError(f"source URL/document type mismatch: {url}")
        if source_ids != {"MFDS-NEDRUG-DETAIL"}:
            raise ValueError(f"unexpected source identity: {url}")
        expected_product_id = f"MFDS-{match.group('item_sequence')}"
        if product_ids != {expected_product_id} or len(product_names) != 1:
            raise ValueError(f"source URL/product identity mismatch: {url}")
        if len(pinned_hashes) != 1:
            raise ValueError(f"conflicting pinned PDF hashes: {url}")
        pinned_hash = next(iter(pinned_hashes))
        if not re.fullmatch(r"[0-9a-f]{64}", pinned_hash):
            raise ValueError(f"invalid pinned PDF SHA-256: {url}")
        if source_versions != {f"sha256:{pinned_hash}"}:
            raise ValueError(f"source version/PDF hash mismatch: {url}")
        expected_candidate_count, expected_verified_count = (
            EXPECTED_SOURCE_LINK_COUNTS[url]
        )
        if len(source_rows) != expected_candidate_count:
            raise ValueError(
                f"unexpected candidate link count for {url}: "
                f"expected {expected_candidate_count}, found {len(source_rows)}"
            )
        verified_count = sum(
            row["evidence_status"] == "verified_primary" for row in source_rows
        )
        if verified_count != expected_verified_count:
            raise ValueError(
                f"unexpected verified-primary count for {url}: "
                f"expected {expected_verified_count}, found {verified_count}"
            )
        sources.append(
            SourceRecord(
                url=url,
                item_sequence=match.group("item_sequence"),
                product_id=expected_product_id,
                product_name=next(iter(product_names)),
                document_type=match.group("document_type"),
                pinned_pdf_sha256=pinned_hash,
                evidence_rows=tuple(source_rows),
            )
        )

    inventory_sha256 = candidate_source_inventory_sha256(rows)
    if inventory_sha256 != EXPECTED_CANDIDATE_SOURCE_INVENTORY_SHA256:
        raise ValueError(
            "candidate source inventory digest mismatch: "
            f"expected {EXPECTED_CANDIDATE_SOURCE_INVENTORY_SHA256}, "
            f"found {inventory_sha256}"
        )

    return sorted(
        sources,
        key=lambda source: (source.item_sequence, source.document_type),
    )


def load_sources(root: Path = ROOT) -> list[SourceRecord]:
    evidence_path = root / EVIDENCE_LINKS_RELATIVE
    sorted_sources = source_records_from_evidence_bytes(evidence_path.read_bytes())
    for source in sorted_sources:
        raw_pdf_path = (
            root
            / "research_v3"
            / "otc"
            / "raw"
            / "nedrug"
            / source.item_sequence
            / f"{source.document_type}.pdf"
        )
        if not raw_pdf_path.is_file():
            raise ValueError(f"pinned PDF snapshot is missing: {raw_pdf_path}")
        if sha256_file(raw_pdf_path) != source.pinned_pdf_sha256:
            raise ValueError(f"pinned PDF snapshot hash mismatch: {raw_pdf_path}")
        extracted_text_path = pinned_text_path(root, source)
        if not extracted_text_path.is_file() or not extracted_text_path.stat().st_size:
            raise ValueError(f"pinned extracted text is missing or empty: {extracted_text_path}")
    return sorted_sources


def fetch_pdf(url: str, timeout_seconds: float, retries: int) -> bytes:
    if MFDS_PDF_RE.fullmatch(url) is None:
        raise ValueError(f"unsupported MFDS PDF URL: {url}")
    if timeout_seconds <= 0 or retries < 0:
        raise ValueError("timeout must be positive and retries cannot be negative")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/pdf",
                },
            )
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                status = response.status
                content_type = response.headers.get_content_type()
                final_url = response.geturl()
                body = response.read()
            if status != 200:
                raise ValueError(f"HTTP {status}")
            if final_url != url:
                raise ValueError(
                    f"unexpected redirect target: requested={url} final={final_url}"
                )
            if content_type != "application/pdf" or not body.startswith(b"%PDF-"):
                raise ValueError(
                    f"invalid PDF response: content_type={content_type!r} bytes={len(body)}"
                )
            return body
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
    assert last_error is not None
    raise RuntimeError(str(last_error)) from last_error


def extract_pdf_text(
    pdf_bytes: bytes,
    source: SourceRecord,
    scratch: Path,
) -> str:
    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("pdftotext executable not found")
    pdf_path = scratch / f"{source.item_sequence}-{source.document_type}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    result = subprocess.run(
        [executable, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftotext exit {result.returncode}: {error}")
    return result.stdout.decode("utf-8")


def pinned_text_path(root: Path, source: SourceRecord) -> Path:
    return (
        root
        / "research_v3"
        / "otc"
        / "extracted"
        / "nedrug"
        / source.item_sequence
        / f"{source.document_type}.txt"
    )


def compare_texts(pinned_text: str, remote_text: str) -> dict[str, Any]:
    pinned_semantic = normalize_semantic_text(pinned_text)
    remote_semantic = normalize_semantic_text(remote_text)
    pinned_pages = split_pages(pinned_text)
    remote_pages = split_pages(remote_text)
    page_count = max(len(pinned_pages), len(remote_pages))
    mismatched_pages = [
        index + 1
        for index in range(page_count)
        if index >= len(pinned_pages)
        or index >= len(remote_pages)
        or normalize_semantic_text(pinned_pages[index])
        != normalize_semantic_text(remote_pages[index])
    ]
    return {
        "semanticTextMatch": pinned_semantic == remote_semantic,
        "pinnedSemanticTextSha256": sha256_bytes(pinned_semantic.encode("utf-8")),
        "remoteSemanticTextSha256": sha256_bytes(remote_semantic.encode("utf-8")),
        "pinnedSemanticCharacterCount": len(pinned_semantic),
        "remoteSemanticCharacterCount": len(remote_semantic),
        "pinnedPageCount": len(pinned_pages),
        "remotePageCount": len(remote_pages),
        "semanticPageMatch": not mismatched_pages,
        "mismatchedPages": mismatched_pages,
    }


def candidate_excerpt_check(
    source: SourceRecord,
    remote_text: str,
) -> dict[str, Any]:
    remote_normalized = normalize_excerpt(remote_text)
    if any("raw_candidate_evidence_text" not in row for row in source.evidence_rows):
        raise ValueError("evidence links are missing raw_candidate_evidence_text")
    missing_ids = [
        row["evidence_candidate_id"]
        for row in source.evidence_rows
        if not excerpt_matches_document(
            row["raw_candidate_evidence_text"], remote_normalized
        )
    ]
    verified = [
        row
        for row in source.evidence_rows
        if row["evidence_status"] == "verified_primary"
    ]
    verified_mismatch_ids = [
        row["evidence_candidate_id"]
        for row in verified
        if not excerpt_matches_document(
            row["raw_candidate_evidence_text"], remote_normalized
        )
    ]
    return {
        "candidateLinkCount": len(source.evidence_rows),
        "candidateExcerptMatchCount": len(source.evidence_rows) - len(missing_ids),
        "candidateExcerptMismatchIds": missing_ids,
        "verifiedPrimaryLinkCount": len(verified),
        "verifiedPrimaryCandidateIds": sorted(
            row["evidence_candidate_id"] for row in verified
        ),
        "verifiedPrimaryCandidateExcerptMatchCount": (
            len(verified) - len(verified_mismatch_ids)
        ),
        "verifiedPrimaryCandidateExcerptMismatchIds": verified_mismatch_ids,
    }


def audit(
    root: Path = ROOT,
    *,
    timeout_seconds: float = 45,
    retries: int = 1,
    fetcher: FetchPdf = fetch_pdf,
    extractor: ExtractPdfText = extract_pdf_text,
    accessed_at_utc: str | None = None,
) -> dict[str, Any]:
    sources = load_sources(root)
    accessed_at = accessed_at_utc or datetime.now(timezone.utc).isoformat()
    evidence_path = root / EVIDENCE_LINKS.relative_to(ROOT)
    generator_path = root / Path(__file__).resolve().relative_to(ROOT)
    source_results: list[dict[str, Any]] = []
    remote_cache: dict[str, tuple[bytes, str]] = {}

    scratch_parent = root / SCRATCH_PARENT.relative_to(ROOT)
    scratch_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=scratch_parent) as temporary:
        scratch = Path(temporary)
        for source in sources:
            base = {
                "url": source.url,
                "itemSequence": source.item_sequence,
                "productId": source.product_id,
                "productName": source.product_name,
                "documentType": source.document_type,
                "pinnedSnapshotPdfSha256": source.pinned_pdf_sha256,
            }
            try:
                remote_bytes = fetcher(source.url, timeout_seconds, retries)
                if not remote_bytes.startswith(b"%PDF-"):
                    raise RuntimeError("fetcher returned a non-PDF body")
                remote_text = extractor(remote_bytes, source, scratch)
                remote_cache[source.url] = (remote_bytes, remote_text)
                pinned_path = pinned_text_path(root, source)
                pinned_text = pinned_path.read_text(encoding="utf-8")
                comparison = compare_texts(pinned_text, remote_text)
                excerpt = candidate_excerpt_check(source, remote_text)
                semantic_match = comparison["semanticTextMatch"]
                source_results.append(
                    {
                        **base,
                        "status": "semantic_match" if semantic_match else "semantic_drift",
                        "remotePdfSha256": sha256_bytes(remote_bytes),
                        "remotePdfBytes": len(remote_bytes),
                        "snapshotPdfByteMatch": (
                            sha256_bytes(remote_bytes) == source.pinned_pdf_sha256
                        ),
                        "pinnedExtractedTextPath": pinned_path.relative_to(root).as_posix(),
                        **comparison,
                        **excerpt,
                    }
                )
            except Exception as error:  # network and extractor errors belong in the audit
                candidate_ids = [
                    row["evidence_candidate_id"] for row in source.evidence_rows
                ]
                verified_ids = sorted(
                    row["evidence_candidate_id"]
                    for row in source.evidence_rows
                    if row["evidence_status"] == "verified_primary"
                )
                source_results.append(
                    {
                        **base,
                        "status": "unreachable",
                        "error": f"{type(error).__name__}: {error}",
                        "candidateLinkCount": len(source.evidence_rows),
                        "candidateExcerptMatchCount": 0,
                        "candidateExcerptMismatchIds": candidate_ids,
                        "verifiedPrimaryLinkCount": len(verified_ids),
                        "verifiedPrimaryCandidateIds": verified_ids,
                        "verifiedPrimaryCandidateExcerptMatchCount": 0,
                        "verifiedPrimaryCandidateExcerptMismatchIds": verified_ids,
                    }
                )

        volatility_probe: dict[str, Any] = {"status": "not_run"}
        if sources and sources[0].url in remote_cache:
            source = sources[0]
            first_bytes, first_text = remote_cache[source.url]
            try:
                second_bytes = fetcher(source.url, timeout_seconds, retries)
                if not second_bytes.startswith(b"%PDF-"):
                    raise RuntimeError("fetcher returned a non-PDF body")
                second_text = extractor(second_bytes, source, scratch)
                first_text_sha = semantic_text_sha256(first_text)
                second_text_sha = semantic_text_sha256(second_text)
                volatility_probe = {
                    "status": "completed",
                    "url": source.url,
                    "firstPdfSha256": sha256_bytes(first_bytes),
                    "secondPdfSha256": sha256_bytes(second_bytes),
                    "pdfBytesStable": first_bytes == second_bytes,
                    "firstSemanticTextSha256": first_text_sha,
                    "secondSemanticTextSha256": second_text_sha,
                    "semanticTextStable": first_text_sha == second_text_sha,
                    "interpretation": (
                        "semantic_difference_observed"
                        if first_text_sha != second_text_sha
                        else "volatile_pdf_bytes_same_extracted_text"
                        if first_bytes != second_bytes
                        else "no_byte_volatility_observed"
                    ),
                }
            except Exception as error:
                volatility_probe = {
                    "status": "unreachable",
                    "url": source.url,
                    "error": f"{type(error).__name__}: {error}",
                }

    status_counts = {
        status: sum(result["status"] == status for result in source_results)
        for status in ("semantic_match", "semantic_drift", "unreachable")
    }
    candidate_link_count = sum(
        result.get("candidateLinkCount", 0) for result in source_results
    )
    candidate_excerpt_matches = sum(
        result.get("candidateExcerptMatchCount", 0) for result in source_results
    )
    verified_primary_count = sum(
        result.get("verifiedPrimaryLinkCount", 0) for result in source_results
    )
    verified_primary_matches = sum(
        result.get("verifiedPrimaryCandidateExcerptMatchCount", 0)
        for result in source_results
    )
    return {
        "schemaVersion": "1.0.0",
        "auditType": "mfds_official_pdf_semantic_freshness",
        "accessedAtUtc": accessed_at,
        "sourceLineage": "v5.1_audit_of_v5.0_read_only_snapshots",
        "generator": generator_path.relative_to(root).as_posix(),
        "generatorSha256": sha256_file(generator_path),
        "inputs": {
            "evidenceRuleLinks": {
                "path": evidence_path.relative_to(root).as_posix(),
                "bytes": evidence_path.stat().st_size,
                "sha256": sha256_file(evidence_path),
            }
        },
        "methodology": {
            "downloadValidation": (
                "canonical MFDS request URL equals final response URL, HTTP 200, "
                "application/pdf, %PDF- magic"
            ),
            "textExtraction": "pdftotext -layout -enc UTF-8",
            "semanticNormalization": "Unicode NFKC then remove all whitespace",
            "freshnessDecision": "semantic extracted-text equality, not remote PDF byte equality",
            "inventoryDecision": (
                "exact approved 20 URLs, 360 unique candidate links, and 15 approved "
                "verified-primary candidate IDs"
            ),
            "successGate": (
                "all semantic and page comparisons, all candidate and verified-primary "
                "excerpts, and the repeated-download semantic probe must pass"
            ),
            "snapshotVersionMeaning": (
                "pinned PDF SHA-256 identifies the archived 2026-07-14 bytes; "
                "MFDS may regenerate byte-distinct PDFs with identical text"
            ),
        },
        "summary": {
            "officialSourceUrlCount": len(sources),
            **status_counts,
            "candidateLinkCount": candidate_link_count,
            "candidateExcerptMatchCount": candidate_excerpt_matches,
            "candidateExcerptMismatchCount": (
                candidate_link_count - candidate_excerpt_matches
            ),
            "verifiedPrimaryLinkCount": verified_primary_count,
            "verifiedPrimaryCandidateExcerptMatchCount": verified_primary_matches,
            "newRulesActivated": 0,
            "releaseReady": False,
        },
        "volatilityProbe": volatility_probe,
        "sources": source_results,
    }


def _require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise ValueError(f"{label}: expected={expected!r}, observed={observed!r}")


def _parse_utc_timestamp(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"{label} must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{label} must use an explicit UTC offset")
    return parsed


def _parse_baseline_timestamp(baseline_manifest_bytes: bytes) -> datetime:
    try:
        manifest = json.loads(baseline_manifest_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("baseline manifest must be valid UTF-8 JSON") from error
    if not isinstance(manifest, dict) or not str(manifest.get("captured_at", "")):
        raise ValueError("baseline manifest captured_at is missing")
    try:
        captured_at = datetime.fromisoformat(str(manifest["captured_at"]))
    except ValueError as error:
        raise ValueError("baseline manifest captured_at must be ISO-8601") from error
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    elif captured_at.utcoffset() != timezone.utc.utcoffset(captured_at):
        raise ValueError("baseline manifest captured_at must use UTC")
    return captured_at


def expected_pinned_text_paths(
    sources: list[SourceRecord],
) -> set[str]:
    return {
        "research_v3/otc/extracted/nedrug/"
        f"{source.item_sequence}/{source.document_type}.txt"
        for source in sources
    }


def validate_freshness_snapshot(
    snapshot: dict[str, Any],
    *,
    evidence_links_bytes: bytes,
    pinned_text_bytes: Mapping[str, bytes],
    generator_bytes: bytes,
    baseline_manifest_bytes: bytes,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate one snapshot exclusively against caller-supplied input bytes."""

    sources_from_evidence = source_records_from_evidence_bytes(evidence_links_bytes)
    expected_source_by_url = {
        source.url: source for source in sources_from_evidence
    }
    expected_paths = expected_pinned_text_paths(sources_from_evidence)
    _require_equal(
        set(pinned_text_bytes),
        expected_paths,
        "freshness pinned text byte paths",
    )

    if snapshot.get("schemaVersion") != "1.0.0":
        raise ValueError("freshness schemaVersion must be 1.0.0")
    if snapshot.get("auditType") != "mfds_official_pdf_semantic_freshness":
        raise ValueError("freshness auditType is invalid")
    if snapshot.get("sourceLineage") != "v5.1_audit_of_v5.0_read_only_snapshots":
        raise ValueError("freshness sourceLineage is invalid")

    accessed_at = _parse_utc_timestamp(
        snapshot.get("accessedAtUtc"),
        "freshness accessedAtUtc",
    )
    baseline_at = _parse_baseline_timestamp(baseline_manifest_bytes)
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() != timezone.utc.utcoffset(current):
        raise ValueError("freshness validation now_utc must use an explicit UTC offset")
    if accessed_at < baseline_at or accessed_at > current:
        raise ValueError(
            "freshness accessedAtUtc is outside the valid audit window: "
            f"baseline={baseline_at.isoformat()} accessed={accessed_at.isoformat()} "
            f"now={current.isoformat()}"
        )

    _require_equal(
        snapshot.get("generator"),
        GENERATOR_RELATIVE.as_posix(),
        "freshness generator path",
    )
    _require_equal(
        snapshot.get("generatorSha256"),
        sha256_bytes(generator_bytes),
        "freshness generator hash",
    )
    inputs = snapshot.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"evidenceRuleLinks"}:
        raise ValueError("freshness inputs must contain only evidenceRuleLinks")
    evidence_input = inputs["evidenceRuleLinks"]
    if not isinstance(evidence_input, dict) or set(evidence_input) != {
        "path",
        "bytes",
        "sha256",
    }:
        raise ValueError("freshness evidenceRuleLinks input fields are invalid")
    _require_equal(
        evidence_input.get("path"),
        EVIDENCE_LINKS_RELATIVE.as_posix(),
        "freshness evidence input path",
    )
    if type(evidence_input.get("bytes")) is not int:
        raise ValueError("freshness evidence input bytes must be an integer")
    _require_equal(
        evidence_input["bytes"],
        len(evidence_links_bytes),
        "freshness evidence input bytes",
    )
    _require_equal(
        evidence_input.get("sha256"),
        sha256_bytes(evidence_links_bytes),
        "freshness evidence input sha256",
    )

    sources = snapshot.get("sources")
    if not isinstance(sources, list) or len(sources) != len(
        EXPECTED_OFFICIAL_SOURCE_URLS
    ):
        raise ValueError("source freshness sources must contain exactly 20 rows")
    if not all(isinstance(source, dict) for source in sources):
        raise ValueError("source freshness rows must be objects")
    source_by_url = {str(source.get("url", "")): source for source in sources}
    if len(source_by_url) != len(sources):
        raise ValueError("source freshness URLs must be unique")
    _require_equal(
        set(source_by_url),
        set(expected_source_by_url),
        "freshness/evidence source URLs",
    )

    status_counts: Counter[str] = Counter()
    candidate_links = 0
    candidate_matches = 0
    verified_links = 0
    verified_matches = 0
    byte_match_count = 0
    snapshot_verified_ids: set[str] = set()
    sha_fields = (
        "pinnedSnapshotPdfSha256",
        "remotePdfSha256",
        "pinnedSemanticTextSha256",
        "remoteSemanticTextSha256",
    )
    for url, source in sorted(source_by_url.items()):
        expected_source = expected_source_by_url[url]
        _require_equal(
            source.get("itemSequence"),
            expected_source.item_sequence,
            f"freshness source {url} item",
        )
        _require_equal(
            source.get("documentType"),
            expected_source.document_type,
            f"freshness source {url} document type",
        )
        _require_equal(
            source.get("productId"),
            expected_source.product_id,
            f"freshness source {url} product ID",
        )
        _require_equal(
            source.get("productName"),
            expected_source.product_name,
            f"freshness source {url} product name",
        )
        for field in sha_fields:
            if re.fullmatch(r"[0-9a-f]{64}", str(source.get(field, ""))) is None:
                raise ValueError(f"invalid SHA-256 in freshness source {url}: {field}")
        _require_equal(
            source.get("pinnedSnapshotPdfSha256"),
            expected_source.pinned_pdf_sha256,
            f"freshness source {url} pinned PDF hash",
        )
        _require_equal(source.get("status"), "semantic_match", f"freshness {url} status")
        _require_equal(
            source.get("semanticTextMatch"),
            True,
            f"freshness {url} semantic text",
        )
        if source.get("semanticTextMatch") is not True:
            raise ValueError(f"freshness {url} semanticTextMatch must be boolean true")
        if source.get("semanticPageMatch") is not True:
            raise ValueError(f"freshness {url} semanticPageMatch must be boolean true")
        _require_equal(source.get("mismatchedPages"), [], f"freshness {url} page drift")
        _require_equal(
            source.get("pinnedSemanticTextSha256"),
            source.get("remoteSemanticTextSha256"),
            f"freshness {url} semantic hash",
        )
        byte_match = (
            source["pinnedSnapshotPdfSha256"] == source["remotePdfSha256"]
        )
        if source.get("snapshotPdfByteMatch") is not byte_match:
            raise ValueError(f"freshness {url} PDF byte-match flag is inconsistent")
        _require_equal(
            source.get("pinnedSemanticCharacterCount"),
            source.get("remoteSemanticCharacterCount"),
            f"freshness {url} semantic character count",
        )
        _require_equal(
            source.get("pinnedPageCount"),
            source.get("remotePageCount"),
            f"freshness {url} page count",
        )
        expected_path = (
            "research_v3/otc/extracted/nedrug/"
            f"{expected_source.item_sequence}/{expected_source.document_type}.txt"
        )
        _require_equal(
            source.get("pinnedExtractedTextPath"),
            expected_path,
            f"freshness {url} pinned text path",
        )
        pinned_payload = pinned_text_bytes[expected_path]
        if not isinstance(pinned_payload, bytes) or not pinned_payload:
            raise ValueError(f"freshness pinned text bytes are empty: {expected_path}")
        try:
            pinned_text = pinned_payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"freshness pinned text is not UTF-8: {expected_path}"
            ) from error
        pinned_semantic = normalize_semantic_text(pinned_text)
        _require_equal(
            source.get("pinnedSemanticTextSha256"),
            sha256_bytes(pinned_semantic.encode("utf-8")),
            f"freshness {url} recomputed pinned semantic hash",
        )
        _require_equal(
            source.get("pinnedSemanticCharacterCount"),
            len(pinned_semantic),
            f"freshness {url} recomputed pinned character count",
        )
        _require_equal(
            source.get("pinnedPageCount"),
            len(split_pages(pinned_text)),
            f"freshness {url} recomputed pinned page count",
        )
        if type(source.get("remotePdfBytes")) is not int or source["remotePdfBytes"] <= 0:
            raise ValueError(f"invalid remote PDF byte count for freshness source: {url}")

        expected_candidate_count, expected_verified_count = (
            EXPECTED_SOURCE_LINK_COUNTS[url]
        )
        expected_counts = {
            "candidateLinkCount": expected_candidate_count,
            "candidateExcerptMatchCount": expected_candidate_count,
            "verifiedPrimaryLinkCount": expected_verified_count,
            "verifiedPrimaryCandidateExcerptMatchCount": expected_verified_count,
        }
        for field, expected in expected_counts.items():
            if type(source.get(field)) is not int:
                raise ValueError(f"invalid freshness integer count {url}: {field}")
            _require_equal(source[field], expected, f"freshness {url} {field}")
        _require_equal(
            source.get("candidateExcerptMismatchIds"),
            [],
            f"freshness {url} candidate mismatch IDs",
        )
        _require_equal(
            source.get("verifiedPrimaryCandidateExcerptMismatchIds"),
            [],
            f"freshness {url} verified mismatch IDs",
        )
        verified_ids = source.get("verifiedPrimaryCandidateIds")
        if not isinstance(verified_ids, list) or len(verified_ids) != len(
            set(verified_ids)
        ):
            raise ValueError(f"freshness {url} verified-primary IDs are invalid")
        expected_verified_ids = sorted(
            row["evidence_candidate_id"]
            for row in expected_source.evidence_rows
            if row["evidence_status"] == "verified_primary"
        )
        _require_equal(
            verified_ids,
            expected_verified_ids,
            f"freshness {url} verified-primary IDs",
        )
        duplicate_verified_ids = snapshot_verified_ids & set(verified_ids)
        if duplicate_verified_ids:
            raise ValueError(
                "duplicate verified-primary IDs across freshness sources: "
                f"{sorted(duplicate_verified_ids)}"
            )
        snapshot_verified_ids.update(verified_ids)

        status_counts[str(source["status"])] += 1
        candidate_links += source["candidateLinkCount"]
        candidate_matches += source["candidateExcerptMatchCount"]
        verified_links += source["verifiedPrimaryLinkCount"]
        verified_matches += source["verifiedPrimaryCandidateExcerptMatchCount"]
        byte_match_count += int(byte_match)

    _require_equal(
        snapshot_verified_ids,
        set(EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS),
        "freshness global verified-primary candidate IDs",
    )
    summary = snapshot.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("source freshness summary must be an object")
    expected_summary = {
        "officialSourceUrlCount": len(EXPECTED_OFFICIAL_SOURCE_URLS),
        "semantic_match": len(EXPECTED_OFFICIAL_SOURCE_URLS),
        "semantic_drift": 0,
        "unreachable": 0,
        "candidateLinkCount": EXPECTED_CANDIDATE_LINK_COUNT,
        "candidateExcerptMatchCount": EXPECTED_CANDIDATE_LINK_COUNT,
        "candidateExcerptMismatchCount": 0,
        "verifiedPrimaryLinkCount": len(EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS),
        "verifiedPrimaryCandidateExcerptMatchCount": len(
            EXPECTED_VERIFIED_PRIMARY_CANDIDATE_IDS
        ),
        "newRulesActivated": 0,
        "releaseReady": False,
    }
    if set(summary) != set(expected_summary):
        raise ValueError("source freshness summary fields are invalid")
    for field, expected in expected_summary.items():
        if field != "releaseReady" and type(summary.get(field)) is not int:
            raise ValueError(f"source freshness summary {field} must be an integer")
        if field == "releaseReady" and type(summary.get(field)) is not bool:
            raise ValueError("source freshness summary releaseReady must be a boolean")
        _require_equal(summary[field], expected, f"source freshness summary {field}")

    probe = snapshot.get("volatilityProbe")
    if not isinstance(probe, dict) or probe.get("status") != "completed":
        raise ValueError("source freshness volatility probe must be completed")
    if probe.get("url") not in source_by_url:
        raise ValueError("volatility probe URL is not an audited source")
    for field in (
        "firstPdfSha256",
        "secondPdfSha256",
        "firstSemanticTextSha256",
        "secondSemanticTextSha256",
    ):
        if re.fullmatch(r"[0-9a-f]{64}", str(probe.get(field, ""))) is None:
            raise ValueError(f"invalid volatility probe SHA-256: {field}")
    if type(probe.get("pdfBytesStable")) is not bool:
        raise ValueError("volatility probe pdfBytesStable must be a boolean")
    if probe.get("semanticTextStable") is not True:
        raise ValueError("volatility probe semanticTextStable must be boolean true")
    _require_equal(
        probe["firstSemanticTextSha256"],
        probe["secondSemanticTextSha256"],
        "volatility probe semantic hash",
    )
    pdf_bytes_stable = probe["firstPdfSha256"] == probe["secondPdfSha256"]
    _require_equal(
        probe["pdfBytesStable"],
        pdf_bytes_stable,
        "volatility probe PDF byte stability flag",
    )
    expected_interpretation = (
        "no_byte_volatility_observed"
        if pdf_bytes_stable
        else "volatile_pdf_bytes_same_extracted_text"
    )
    _require_equal(
        probe.get("interpretation"),
        expected_interpretation,
        "volatility probe interpretation",
    )
    probed_source = source_by_url[str(probe["url"])]
    _require_equal(
        probe["firstPdfSha256"],
        probed_source["remotePdfSha256"],
        "volatility probe/source PDF hash",
    )
    _require_equal(
        probe["firstSemanticTextSha256"],
        probed_source["remoteSemanticTextSha256"],
        "volatility probe/source semantic hash",
    )

    return {
        "accessed_at_utc": snapshot["accessedAtUtc"],
        "generator": snapshot["generator"],
        "generator_sha256": snapshot["generatorSha256"],
        "input_artifacts": inputs,
        "official_source_urls": len(sources),
        "status_counts": dict(sorted(status_counts.items())),
        "semantic_match_source_urls": status_counts.get("semantic_match", 0),
        "semantic_drift_source_urls": status_counts.get("semantic_drift", 0),
        "unreachable_source_urls": status_counts.get("unreachable", 0),
        "candidate_links": candidate_links,
        "candidate_excerpt_matches": candidate_matches,
        "candidate_excerpt_mismatches": candidate_links - candidate_matches,
        "verified_primary_links": verified_links,
        "verified_primary_candidate_excerpt_matches": verified_matches,
        "verified_primary_candidate_excerpt_mismatches": (
            verified_links - verified_matches
        ),
        "snapshot_pdf_byte_match_source_urls": byte_match_count,
        "snapshot_pdf_byte_mismatch_source_urls": len(sources) - byte_match_count,
        "volatility_probe": {
            "pdf_bytes_stable": probe["pdfBytesStable"],
            "semantic_text_stable": probe["semanticTextStable"],
            "interpretation": probe["interpretation"],
        },
        "new_rules_activated": summary["newRulesActivated"],
        "release_ready": summary["releaseReady"],
        "freshness_decision_basis": "semantic_extracted_text_equality",
        "remote_pdf_byte_mismatch_is_semantic_drift": False,
    }


def audit_passed(
    snapshot: dict[str, Any],
    root: Path = ROOT,
    *,
    now_utc: datetime | None = None,
) -> bool:
    """Return true only when the shared byte-snapshot validator succeeds."""

    try:
        evidence_bytes = (root / EVIDENCE_LINKS_RELATIVE).read_bytes()
        generator_bytes = (root / GENERATOR_RELATIVE).read_bytes()
        baseline_bytes = (root / BASELINE_MANIFEST_RELATIVE).read_bytes()
        sources = source_records_from_evidence_bytes(evidence_bytes)
        pinned_bytes = {
            relative: (root / relative).read_bytes()
            for relative in sorted(expected_pinned_text_paths(sources))
        }
        validate_freshness_snapshot(
            snapshot,
            evidence_links_bytes=evidence_bytes,
            pinned_text_bytes=pinned_bytes,
            generator_bytes=generator_bytes,
            baseline_manifest_bytes=baseline_bytes,
            now_utc=now_utc,
        )
    except (KeyError, OSError, TypeError, ValueError):
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit current MFDS PDF text against pinned v5.1 evidence snapshots."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=45)
    parser.add_argument("--retries", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0 or args.retries < 0:
        raise SystemExit("timeout must be positive and retries cannot be negative")
    try:
        output = validate_snapshot_output(args.output, root=ROOT)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    snapshot = audit(
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
    )
    write_snapshot(snapshot, output=output, root=ROOT)
    held_output = _hold_regular_output(output)
    try:
        persisted_snapshot = _parse_persisted_snapshot(
            held_output.payload,
            expected=snapshot,
        )
        summary = persisted_snapshot["summary"]
        passed = audit_passed(persisted_snapshot, root=ROOT)
        _revalidate_held_output(held_output)
        print(
            f"sources={summary['officialSourceUrlCount']} "
            f"semantic_match={summary['semantic_match']} "
            f"semantic_drift={summary['semantic_drift']} "
            f"unreachable={summary['unreachable']} "
            f"candidate_excerpts={summary['candidateExcerptMatchCount']}/"
            f"{summary['candidateLinkCount']} "
            f"passed={str(passed).lower()}"
        )
        return 0 if passed else 1
    finally:
        os.close(held_output.descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
