#!/usr/bin/env python3
"""Read-only v5.1 boundary and v5.0 baseline audit.

The trust anchor is pinned in this module, not delegated to the mutable JSON
manifest.  The pinned digest commits to the capture date used as the freshness
lower bound, baseline metadata, preservation boundary, core artifact byte/hash
records, external artifact byte/hash records, and verified counts.  This
self-contained audit cannot detect a coordinated change to both this source
file and its tests, or replacement of the repository and Git object database;
that requires an independently stored signed attestation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple


REPO = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO / "research_v51" / "audit" / "baseline_manifest.json"
DOSE_OR_INTERVAL_RULES = {"max_daily_dose", "minimum_interval"}
EXPECTED_BASELINE_COMMIT = "6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9"
EXPECTED_RESEARCH_V3_TREE_OID = "325001631c37e6fe8749a021c13a2ccc75bdf5b9"
EXPECTED_PROTECTED_PATH = "research_v3"
EXPECTED_CAPTURED_AT = "2026-07-31"
# SHA-256 of canonical JSON containing baseline, boundary, core_artifacts,
# external_canonical_artifacts, verified_counts, and captured_at. The date is
# the lower timestamp bound consumed by downstream freshness checks. This
# independently pins every declared contract value without treating the
# manifest as its own root of trust.
EXPECTED_CONTRACT_SHA256 = (
    "2dd0c0781c187700ae784f31c4a9d3fd2e55a1b71f7935671b2e6b6f40843f17"
)
CONTRACT_KEYS = (
    "captured_at",
    "baseline",
    "boundary",
    "core_artifacts",
    "external_canonical_artifacts",
    "verified_counts",
)
WINDOWS_FILE_SUPPORTS_HARD_LINKS = 0x00400000


class ExternalFileSnapshot(NamedTuple):
    identity: os.stat_result
    bytes: int
    sha256: str


class WindowsExternalHandleInfo(NamedTuple):
    volume_serial: int
    file_index: int
    bytes: int
    link_count: int
    hard_links_supported: bool


class ExternalSnapshotError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))


def load_json_bytes(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _external_stat_metadata(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _windows_volume_supports_hard_links(path: Path) -> bool:
    """Return the Windows volume capability instead of trusting virtual st_nlink."""

    import ctypes
    from ctypes import wintypes

    volume_root = path.anchor
    if not volume_root:
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_LINK_POLICY_UNAVAILABLE",
            f"path_has_no_volume_root path={path}",
        )
    flags = wintypes.DWORD()
    volume_name = ctypes.create_unicode_buffer(261)
    filesystem_name = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    maximum_component_length = wintypes.DWORD()
    get_volume_information = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).GetVolumeInformationW
    get_volume_information.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    get_volume_information.restype = wintypes.BOOL
    if not get_volume_information(
        volume_root,
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(maximum_component_length),
        ctypes.byref(flags),
        filesystem_name,
        len(filesystem_name),
    ):
        error = ctypes.get_last_error()
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_LINK_POLICY_UNAVAILABLE",
            f"volume={volume_root} winerror={error}",
        )
    return bool(flags.value & WINDOWS_FILE_SUPPORTS_HARD_LINKS)


def _windows_external_handle_info(stream: Any, path: Path) -> WindowsExternalHandleInfo:
    """Read stable Windows file identity and native link metadata."""

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("link_count", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]

    get_file_information = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).GetFileInformationByHandle
    get_file_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    ]
    get_file_information.restype = wintypes.BOOL
    information = ByHandleFileInformation()
    native_handle = msvcrt.get_osfhandle(stream.fileno())
    if not get_file_information(native_handle, ctypes.byref(information)):
        error = ctypes.get_last_error()
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_SNAPSHOT_FAILED",
            f"phase=windows_native_metadata winerror={error}",
        )
    return WindowsExternalHandleInfo(
        volume_serial=information.volume_serial,
        file_index=(information.file_index_high << 32) | information.file_index_low,
        bytes=(information.file_size_high << 32) | information.file_size_low,
        link_count=information.link_count,
        hard_links_supported=_windows_volume_supports_hard_links(path),
    )


def _validate_windows_link_policy(
    *,
    native_count: int,
    hard_links_supported: bool,
    stat_counts: tuple[int, ...],
) -> None:
    if any(count not in (0, 1) for count in stat_counts):
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_LINK_COUNT_MISMATCH",
            f"unsafe stat link counts observed={stat_counts}",
        )
    if native_count == 1:
        return
    if (
        native_count == 0
        and not hard_links_supported
        and all(count == 0 for count in stat_counts)
    ):
        return
    if native_count == 0 and hard_links_supported:
        detail = "native link count is unavailable on a hard-link-capable volume"
    else:
        detail = (
            f"unsafe native link count observed={native_count} "
            f"stat_counts={stat_counts}"
        )
    raise ExternalSnapshotError(
        "EXTERNAL_CANONICAL_LINK_COUNT_MISMATCH",
        detail,
    )


def _validate_external_file_stat(
    value: os.stat_result, *, source: str, path: Path
) -> None:
    if not stat.S_ISREG(value.st_mode):
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_NOT_REGULAR",
            f"source={source} mode={value.st_mode}",
        )
    link_count_is_safe = value.st_nlink == 1
    if os.name == "nt" and value.st_nlink == 0:
        # Google Drive's FAT32-compatible virtual volume reports an unknown
        # link count as zero. Accept it only when the volume cannot create
        # hardlinks; an unavailable capability query remains fail-closed.
        link_count_is_safe = not _windows_volume_supports_hard_links(path)
    if not link_count_is_safe:
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_LINK_COUNT_MISMATCH",
            f"source={source} expected=1 observed={value.st_nlink}",
        )


def _snapshot_external_file(path: Path) -> ExternalFileSnapshot:
    """Read one stable regular-file snapshot from one binary handle."""

    try:
        path_before = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_SNAPSHOT_FAILED",
            f"phase=path_lstat_before detail={exc}",
        ) from exc
    _validate_external_file_stat(path_before, source="path_before", path=path)

    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            _validate_external_file_stat(
                handle_before, source="handle_before", path=path
            )
            windows_before = (
                _windows_external_handle_info(stream, path) if os.name == "nt" else None
            )
            if not os.path.samestat(path_before, handle_before):
                raise ExternalSnapshotError(
                    "EXTERNAL_CANONICAL_IDENTITY_CHANGED",
                    "phase=open",
                )

            digest = hashlib.sha256()
            observed_bytes = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                observed_bytes += len(chunk)
                digest.update(chunk)

            handle_after = os.fstat(stream.fileno())
            _validate_external_file_stat(handle_after, source="handle_after", path=path)
            if not os.path.samestat(handle_before, handle_after) or (
                _external_stat_metadata(handle_before)
                != _external_stat_metadata(handle_after)
            ):
                raise ExternalSnapshotError(
                    "EXTERNAL_CANONICAL_SNAPSHOT_UNSTABLE",
                    "phase=handle_metadata_changed",
                )
            if observed_bytes != handle_after.st_size:
                raise ExternalSnapshotError(
                    "EXTERNAL_CANONICAL_SNAPSHOT_UNSTABLE",
                    "phase=handle_size_changed "
                    f"read={observed_bytes} stat={handle_after.st_size}",
                )

            try:
                path_after = path.lstat()
            except FileNotFoundError as exc:
                raise ExternalSnapshotError(
                    "EXTERNAL_CANONICAL_IDENTITY_CHANGED",
                    "phase=path_missing_after_read",
                ) from exc
            _validate_external_file_stat(path_after, source="path_after", path=path)
            if not os.path.samestat(handle_after, path_after):
                raise ExternalSnapshotError(
                    "EXTERNAL_CANONICAL_IDENTITY_CHANGED",
                    "phase=path_after_read",
                )
            if windows_before is not None:
                windows_after = _windows_external_handle_info(stream, path)
                if windows_before != windows_after:
                    raise ExternalSnapshotError(
                        "EXTERNAL_CANONICAL_SNAPSHOT_UNSTABLE",
                        "phase=windows_native_metadata_changed",
                    )
                if windows_after.bytes != observed_bytes:
                    raise ExternalSnapshotError(
                        "EXTERNAL_CANONICAL_SNAPSHOT_UNSTABLE",
                        "phase=windows_native_size_changed "
                        f"read={observed_bytes} native={windows_after.bytes}",
                    )
                _validate_windows_link_policy(
                    native_count=windows_after.link_count,
                    hard_links_supported=windows_after.hard_links_supported,
                    stat_counts=(
                        path_before.st_nlink,
                        handle_before.st_nlink,
                        handle_after.st_nlink,
                        path_after.st_nlink,
                    ),
                )
    except FileNotFoundError as exc:
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_IDENTITY_CHANGED",
            "phase=open_missing_after_lstat",
        ) from exc
    except ExternalSnapshotError:
        raise
    except OSError as exc:
        raise ExternalSnapshotError(
            "EXTERNAL_CANONICAL_SNAPSHOT_FAILED",
            f"phase=open_or_read detail={exc}",
        ) from exc

    return ExternalFileSnapshot(
        identity=handle_after,
        bytes=observed_bytes,
        sha256=digest.hexdigest(),
    )


def canonical_contract_sha256(manifest: dict[str, Any]) -> str:
    contract = {key: manifest.get(key) for key in CONTRACT_KEYS}
    payload = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def manifest_contract_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    observed_captured_at = manifest.get("captured_at")
    if observed_captured_at != EXPECTED_CAPTURED_AT:
        errors.append(
            "MANIFEST_CAPTURED_AT_MISMATCH "
            f"expected={EXPECTED_CAPTURED_AT} observed={observed_captured_at}"
        )

    baseline = manifest.get("baseline")
    observed_commit = baseline.get("commit") if isinstance(baseline, dict) else None
    if observed_commit != EXPECTED_BASELINE_COMMIT:
        errors.append(
            "MANIFEST_BASELINE_COMMIT_MISMATCH "
            f"expected={EXPECTED_BASELINE_COMMIT} observed={observed_commit}"
        )

    boundary = manifest.get("boundary")
    protected_paths = (
        boundary.get("protected_paths") if isinstance(boundary, dict) else None
    )
    expected_protected_paths = [
        {
            "path": EXPECTED_PROTECTED_PATH,
            "baseline_tree_oid": EXPECTED_RESEARCH_V3_TREE_OID,
        }
    ]
    if protected_paths != expected_protected_paths:
        errors.append(
            "MANIFEST_PROTECTED_PATHS_MISMATCH "
            f"expected={expected_protected_paths!r} observed={protected_paths!r}"
        )

    observed_digest = canonical_contract_sha256(manifest)
    if observed_digest != EXPECTED_CONTRACT_SHA256:
        errors.append(
            "MANIFEST_CONTRACT_DIGEST_MISMATCH "
            f"expected={EXPECTED_CONTRACT_SHA256} observed={observed_digest}"
        )
    return errors


def pinned_boundary_manifest() -> dict[str, Any]:
    return {
        "baseline": {"commit": EXPECTED_BASELINE_COMMIT},
        "boundary": {
            "protected_paths": [
                {
                    "path": EXPECTED_PROTECTED_PATH,
                    "baseline_tree_oid": EXPECTED_RESEARCH_V3_TREE_OID,
                }
            ]
        },
    }


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_value(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_blob_oid(repo: Path, commit: str, relative: str) -> str:
    """Return the blob OID for an exact path at a pinned commit."""

    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError(f"commit must be a full lowercase Git OID: {commit!r}")
    normalized = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or "\x00" in relative
        or normalized.is_absolute()
        or ".." in normalized.parts
        or normalized.as_posix() != relative
    ):
        raise ValueError(
            f"path must be a normalized repository-relative POSIX path: {relative!r}"
        )
    oid = git_value(repo, "rev-parse", f"{commit}:{relative}")
    object_type = git_value(repo, "cat-file", "-t", oid)
    if object_type != "blob":
        raise RuntimeError(
            f"git object is not a blob: commit={commit} path={relative} type={object_type}"
        )
    return oid


def git_blob_bytes(repo: Path, commit: str, relative: str) -> bytes:
    """Read exact repository bytes without checkout or text-filter conversion."""

    oid = git_blob_oid(repo, commit, relative)
    result = subprocess.run(
        ["git", "cat-file", "blob", oid],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git cat-file blob failed ({result.returncode}): {detail}")
    return result.stdout


def git_boundary_errors(repo: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    baseline = manifest["baseline"]["commit"]

    resolved = run_git(repo, "rev-parse", f"{baseline}^{{commit}}")
    if resolved.returncode != 0:
        return [f"BASELINE_COMMIT_UNAVAILABLE commit={baseline}"]
    if resolved.stdout.strip() != baseline:
        errors.append(
            f"BASELINE_COMMIT_MISMATCH expected={baseline} observed={resolved.stdout.strip()}"
        )

    ancestor = run_git(repo, "merge-base", "--is-ancestor", baseline, "HEAD")
    if ancestor.returncode != 0:
        errors.append(f"BASELINE_NOT_ANCESTOR_OF_HEAD commit={baseline}")

    for protected in manifest["boundary"]["protected_paths"]:
        relative = protected["path"]
        expected_tree = protected["baseline_tree_oid"]

        baseline_tree = run_git(repo, "rev-parse", f"{baseline}:{relative}")
        if baseline_tree.returncode != 0:
            errors.append(f"PROTECTED_BASELINE_PATH_MISSING path={relative}")
            continue
        if baseline_tree.stdout.strip() != expected_tree:
            errors.append(
                "PROTECTED_BASELINE_TREE_MISMATCH "
                f"path={relative} expected={expected_tree} observed={baseline_tree.stdout.strip()}"
            )

        head_tree = run_git(repo, "rev-parse", f"HEAD:{relative}")
        if head_tree.returncode != 0:
            errors.append(f"PROTECTED_HEAD_PATH_MISSING path={relative}")
        elif head_tree.stdout.strip() != expected_tree:
            errors.append(
                "PROTECTED_HEAD_DIVERGED "
                f"path={relative} baseline_tree={expected_tree} head_tree={head_tree.stdout.strip()}"
            )

        tracked_status = run_git(
            repo, "status", "--porcelain=v1", "--untracked-files=no", "--", relative
        )
        if tracked_status.returncode != 0:
            errors.append(f"PROTECTED_STATUS_CHECK_FAILED path={relative}")
        elif tracked_status.stdout.strip():
            changed = " | ".join(tracked_status.stdout.splitlines())
            errors.append(f"PROTECTED_WORKTREE_DIRTY path={relative} files={changed}")

        untracked = run_git(
            repo, "ls-files", "--others", "--exclude-standard", "--", relative
        )
        if untracked.returncode != 0:
            errors.append(f"PROTECTED_UNTRACKED_CHECK_FAILED path={relative}")
        elif untracked.stdout.strip():
            paths = " | ".join(untracked.stdout.splitlines())
            errors.append(f"PROTECTED_UNTRACKED_FILES path={relative} files={paths}")

    return errors


def artifact_errors(repo: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for artifact in manifest["core_artifacts"]:
        try:
            payload = git_blob_bytes(repo, EXPECTED_BASELINE_COMMIT, artifact["path"])
        except RuntimeError as exc:
            errors.append(
                f"CORE_ARTIFACT_BLOB_UNAVAILABLE path={artifact['path']} detail={exc}"
            )
            continue
        observed_bytes = len(payload)
        if observed_bytes != artifact["bytes"]:
            errors.append(
                "CORE_ARTIFACT_BYTES_MISMATCH "
                f"path={artifact['path']} expected={artifact['bytes']} observed={observed_bytes}"
            )
        observed_hash = hashlib.sha256(payload).hexdigest()
        if observed_hash != artifact["sha256"]:
            errors.append(
                "CORE_ARTIFACT_HASH_MISMATCH "
                f"path={artifact['path']} expected={artifact['sha256']} observed={observed_hash}"
            )
    return errors


def external_artifact_results(
    manifest: dict[str, Any], *, check_external: bool
) -> tuple[list[str], list[str], bool, int]:
    errors: list[str] = []
    warnings: list[str] = []
    verified_artifacts = 0
    candidates: list[tuple[dict[str, Any], Path, ExternalFileSnapshot]] = []
    for artifact in manifest["external_canonical_artifacts"]:
        if not check_external:
            warnings.append(f"EXTERNAL_ARTIFACT_CHECK_SKIPPED path={artifact['path']}")
            continue
        path = Path(artifact["path"])
        drive_root = Path(artifact["drive_root"])
        try:
            snapshot = _snapshot_external_file(path)
        except FileNotFoundError:
            if os.name == "nt" and drive_root.exists():
                errors.append(f"EXTERNAL_CANONICAL_MISSING path={artifact['path']}")
            else:
                warnings.append(
                    f"EXTERNAL_ENVIRONMENT_UNAVAILABLE path={artifact['path']}"
                )
            continue
        except ExternalSnapshotError as exc:
            errors.append(f"{exc.code} path={artifact['path']} detail={exc.detail}")
            continue
        if snapshot.bytes != artifact["bytes"]:
            errors.append(
                "EXTERNAL_CANONICAL_BYTES_MISMATCH "
                f"path={artifact['path']} expected={artifact['bytes']} "
                f"observed={snapshot.bytes}"
            )
        if snapshot.sha256 != artifact["sha256"]:
            errors.append(
                "EXTERNAL_CANONICAL_HASH_MISMATCH "
                f"path={artifact['path']} expected={artifact['sha256']} "
                f"observed={snapshot.sha256}"
            )
        if (
            snapshot.bytes == artifact["bytes"]
            and snapshot.sha256 == artifact["sha256"]
        ):
            candidates.append((artifact, path, snapshot))

    # Re-open each candidate immediately before returning. A path replacement
    # must fail even when the replacement has the same canonical bytes.
    for artifact, path, initial in candidates:
        try:
            final = _snapshot_external_file(path)
        except (FileNotFoundError, ExternalSnapshotError) as exc:
            if isinstance(exc, ExternalSnapshotError):
                detail = f"code={exc.code} {exc.detail}"
            else:
                detail = "path_missing"
            errors.append(
                "EXTERNAL_CANONICAL_REVALIDATION_FAILED "
                f"path={artifact['path']} detail={detail}"
            )
            continue
        if not os.path.samestat(initial.identity, final.identity):
            errors.append(
                "EXTERNAL_CANONICAL_IDENTITY_CHANGED "
                f"path={artifact['path']} phase=final_revalidation"
            )
            continue
        if final.bytes != initial.bytes or final.bytes != artifact["bytes"]:
            errors.append(
                "EXTERNAL_CANONICAL_BYTES_CHANGED "
                f"path={artifact['path']} initial={initial.bytes} final={final.bytes}"
            )
            continue
        if final.sha256 != initial.sha256 or final.sha256 != artifact["sha256"]:
            errors.append(
                "EXTERNAL_CANONICAL_HASH_CHANGED "
                f"path={artifact['path']} initial={initial.sha256} final={final.sha256}"
            )
            continue
        verified_artifacts += 1
    verification_complete = (
        check_external
        and not errors
        and not warnings
        and verified_artifacts == len(manifest["external_canonical_artifacts"])
    )
    return errors, warnings, verification_complete, verified_artifacts


def baseline_runtime(repo: Path, commit: str) -> dict[str, Any]:
    payload = git_blob_bytes(repo, commit, "src/generated/otc-runtime.json")
    return load_json_bytes(payload)


def collect_counts(repo: Path, baseline_commit: str) -> dict[str, Any]:
    def protected_csv(relative: str) -> list[dict[str, str]]:
        return read_csv_bytes(git_blob_bytes(repo, baseline_commit, relative))

    def protected_json(relative: str) -> dict[str, Any]:
        return load_json_bytes(git_blob_bytes(repo, baseline_commit, relative))

    products = protected_csv("research_v3/otc/normalized/product_master.csv")
    ingredients = protected_csv("research_v3/otc/normalized/ingredient_master.csv")
    product_ingredients = protected_csv(
        "research_v3/otc/normalized/product_ingredient.csv"
    )
    constraints = protected_csv(
        "research_v3/otc/normalized/administration_constraints.csv"
    )
    rules = protected_csv("research_v3/otc/rules/rules.csv")
    shortlist = protected_csv("research_v3/otc/rules/rule_evidence_shortlist.csv")
    candidates = protected_csv("research_v3/otc/rules/official_evidence_candidates.csv")

    product_status = Counter(row["analysis_status"] for row in products)
    rule_status = Counter(row["status"] for row in rules)
    shortlist_status = Counter(row["review_status"] for row in shortlist)
    candidate_status = Counter(row["review_status"] for row in candidates)
    selected_bindings = [
        row
        for row in product_ingredients
        if row["selected_for_calculation"].lower() == "true"
    ]

    runtime = baseline_runtime(repo, baseline_commit)
    product_rule_bindings = sum(
        len(product["supportedRuleTypes"]) for product in runtime["products"]
    )
    dose_only = sum(
        set(product["supportedRuleTypes"]) <= DOSE_OR_INTERVAL_RULES
        for product in runtime["products"]
    )

    link_manifest = protected_json(
        "research_v3/otc/literature/v5/downstream/literature_link_manifest.json"
    )["results"]
    direct_links = protected_csv(
        "research_v3/otc/literature/v5/downstream/supporting_literature.csv"
    )
    run = protected_json("research_v3/logs/v50_run_report.json")
    scoring = protected_json("research_v3/logs/v50_scoring_report.json")

    phase_a = run["phases"]["A"]["full_record"]
    phase_b = run["phases"]["B"]["full_record"]
    phase_c = run["phases"]["C"]
    adjudication = phase_c["semantic_adjudication_layer"]
    final = phase_c["final_layer"]["decision_distribution"]
    weighted = scoring["layers"]["overall"]["weighted_metrics"]

    return {
        "authorization_layer": {
            "product_master_rows": len(products),
            "analysis_products": product_status["included"],
            "ineligible_products": product_status["ineligible"],
            "excluded_products": product_status["excluded"],
            "ingredient_master_rows": len(ingredients),
            "calculation_ingredients": len(
                {row["ingredient_id"] for row in selected_bindings}
            ),
            "product_ingredient_rows": len(product_ingredients),
            "selected_product_ingredient_bindings": len(selected_bindings),
            "administration_constraints": len(constraints),
            "rules_total": len(rules),
            "rules_released": rule_status["released"],
            "rules_draft": rule_status["draft"],
        },
        "runtime_baseline_snapshot": {
            "products": len(runtime["products"]),
            "rules_released": runtime["rulesReleased"],
            "product_rule_bindings": product_rule_bindings,
            "dose_or_interval_only_products": dose_only,
            "disease_or_medication_capable_products": len(runtime["products"])
            - dose_only,
        },
        "candidate_evidence": {
            "shortlist_rows": len(shortlist),
            "shortlist_human_expert_verified": shortlist_status[
                "human_expert_verified"
            ],
            "shortlist_not_expert_verified": shortlist_status[
                "codex_recommended_not_expert_verified"
            ],
            "official_candidate_rows": len(candidates),
            "official_candidates_not_expert_verified": candidate_status[
                "codex_candidate_not_expert_verified"
            ],
        },
        "v50_literature": {
            "rules_total": link_manifest["rule_count"],
            "rules_with_direct_links": link_manifest["resolved_rule_count"],
            "rules_without_direct_links": link_manifest["unresolved_rule_count"],
            "direct_links": len(direct_links),
            "unique_linked_pmids": len({row["pmid"] for row in direct_links}),
            "rejected_candidates": link_manifest["rejected_candidate_count"],
            "not_in_v5_corpus": link_manifest["rejection_counts"]["not_in_v5_corpus"],
            "no_retain_decision_for_rule_question": link_manifest["rejection_counts"][
                "no_retain_decision_for_rule_question"
            ],
        },
        "v50_screening": {
            "pubmed_hits": phase_a["totals"][
                "hit_count_before_cross_question_deduplication"
            ],
            "unique_papers": phase_b["totals"]["evidence_map_rows_unique_papers"],
            "screening_units": phase_b["totals"][
                "question_membership_units_after_bibliographic_deduplication"
            ],
            "semantic_adjudication_rows": adjudication["reviewed_rows"],
            "semantic_disagreements": adjudication["disagreement_count"],
            "semantic_disagreement_rate": adjudication["disagreement_rate"],
            "final_retain": final["retain"],
            "final_deprioritize": final["deprioritize"],
            "final_uncertain": final["uncertain"],
        },
        "v50_scoring_ai_reference": {
            "sample_rows": scoring["layers"]["overall"]["sample_n"],
            "agreement_vs_ai_reference": weighted["agreement_vs_ai_reference"],
            "sensitivity_vs_ai_reference": weighted["sensitivity_vs_ai_reference"],
            "specificity_vs_ai_reference": weighted["specificity_vs_ai_reference"],
            "cohen_kappa_vs_ai_reference_weighted": weighted[
                "cohen_kappa_vs_ai_reference_weighted"
            ],
        },
        "state": {
            "human_reference_rows": run["state_flags"]["human_reference_rows"],
            "independent_blinding": run["state_flags"]["independent_blinding"],
            "semantic_adjudication_independent_blinding_ai": run["state_flags"][
                "semantic_adjudication_independent_blinding_ai"
            ],
            "release_ready": run["state_flags"]["release_ready"],
            "overall_execution_status": run["overall_execution_status"],
        },
    }


def compare_expected(expected: Any, observed: Any, prefix: str = "counts") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return [f"COUNT_TYPE_MISMATCH path={prefix}"]
        for key, value in expected.items():
            if key not in observed:
                errors.append(f"COUNT_MISSING path={prefix}.{key}")
                continue
            errors.extend(compare_expected(value, observed[key], f"{prefix}.{key}"))
        return errors
    if observed != expected:
        errors.append(
            f"COUNT_MISMATCH path={prefix} expected={expected!r} observed={observed!r}"
        )
    return errors


def audit(
    *,
    repo: Path = REPO,
    manifest_path: Path = DEFAULT_MANIFEST,
    check_external: bool = True,
) -> dict[str, Any]:
    repo = repo.resolve()
    manifest = load_json(manifest_path)
    contract_errors = manifest_contract_errors(manifest)
    errors = list(contract_errors)
    errors.extend(git_boundary_errors(repo, pinned_boundary_manifest()))
    warnings: list[str] = []
    verification_complete = False
    verified_external_artifacts = 0

    # Artifact and count declarations are safe to consume only after the
    # independently pinned contract digest matches.
    if not contract_errors:
        errors.extend(artifact_errors(repo, manifest))
        (
            external_errors,
            warnings,
            verification_complete,
            verified_external_artifacts,
        ) = external_artifact_results(manifest, check_external=check_external)
        errors.extend(external_errors)
    else:
        warnings.append("MANIFEST_DECLARATIONS_NOT_CONSUMED_UNTRUSTED_CONTRACT")

    observed_counts: dict[str, Any] = {}
    if not contract_errors:
        try:
            observed_counts = collect_counts(repo, EXPECTED_BASELINE_COMMIT)
            errors.extend(
                compare_expected(manifest["verified_counts"], observed_counts)
            )
        except (
            KeyError,
            OSError,
            RuntimeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(f"COUNT_RECOMPUTE_FAILED detail={exc}")

    # Close the time-of-check/time-of-use gap around every manifest and blob read.
    for error in git_boundary_errors(repo, pinned_boundary_manifest()):
        if error not in errors:
            errors.append(error)

    return {
        "schema_version": "1.1.0",
        "audit": "v5.1_boundary_and_v5.0_baseline",
        "baseline_commit": EXPECTED_BASELINE_COMMIT,
        "valid": not errors,
        "verification_complete": verification_complete,
        "external_verification": {
            "requested": check_external,
            "required_artifacts": (
                len(manifest.get("external_canonical_artifacts", []))
                if not contract_errors
                else 0
            ),
            "verified_artifacts": verified_external_artifacts,
        },
        "errors": errors,
        "warnings": warnings,
        "observed_counts": observed_counts,
        "trust_limit": (
            "This audit cannot detect coordinated modification of its pinned "
            "source contract and tests, or replacement of the Git object database; "
            "an independently stored signed attestation is required for that threat."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--skip-external",
        action="store_true",
        help="G 드라이브 논문 검증을 건너뛰고 환경 경고만 남깁니다.",
    )
    args = parser.parse_args()
    result = audit(
        manifest_path=args.manifest.resolve(), check_external=not args.skip_external
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
