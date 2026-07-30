"""Verify protected v4 and authorization-source files against the frozen baseline.

The baseline was captured while the protected paths were clean at one Git HEAD.
This verifier compares every tracked file's Git-normalized bytes with that commit,
rehashes current raw working-tree bytes, and enumerates untracked and ignored files.
The v5 subtree is deliberately excluded from the protected literature path.
"""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASELINE = ROOT / "research_v3" / "logs" / "v50_protected_baseline.json"
OUTPUT = ROOT / "research_v3" / "logs" / "v50_protected_final_audit.json"

PATHS = {
    "research_v3/otc/normalized": "research_v3/otc/normalized",
    "research_v3/otc/rules": "research_v3/otc/rules",
    "research_v3/otc/literature (excluding v5)": "research_v3/otc/literature",
    "research_v3/search/provisional_pubmed_20260710": (
        "research_v3/search/provisional_pubmed_20260710"
    ),
}

REQUIRED_FINAL_ARTIFACTS = (
    "research_v3/otc/literature/v5/screening/classifier_decisions.csv",
    "research_v3/otc/literature/v5/screening/classifier_validation.json",
    "research_v3/otc/literature/v5/screening/classifier_validation_cross_layer.json",
    "research_v3/otc/literature/v5/screening/adjudication_selection.json",
    "research_v3/otc/literature/v5/screening/semantic_adjudications.json",
    "research_v3/otc/literature/v5/screening/adjudication_manifest.json",
    "research_v3/otc/literature/v5/screening/decisions.csv",
    "research_v3/otc/literature/v5/downstream/supporting_literature.csv",
    "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
    "research_v3/otc/literature/v5/downstream/locator_verification.json",
    "research_v3/logs/DECISIONS_v50.md",
    "research_v3/logs/v50_FINAL.md",
    "research_v3/protocol/amendments.csv",
)


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


def git_bytes(*args: str, env: dict[str, str] | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env=env,
    )
    return completed.stdout


def lines(value: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in value.splitlines() if line.strip()]


def excluded(path: str, label: str) -> bool:
    return label == "research_v3/otc/literature (excluding v5)" and path.startswith(
        "research_v3/otc/literature/v5/"
    )


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def git_tree_entries(revision: str, path: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    output = git("ls-tree", "-r", revision, "--", path)
    for line in output.splitlines():
        metadata, relative = line.split("\t", 1)
        _mode, object_type, object_id = metadata.split()
        if object_type != "blob":
            continue
        entries[relative.replace("\\", "/")] = object_id
    return entries


def normalized_worktree_blob(
    relative: str, temporary_object_directory: Path, alternate_object_directory: Path
) -> tuple[str, bytes]:
    env = os.environ.copy()
    env["GIT_OBJECT_DIRECTORY"] = str(temporary_object_directory)
    env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(alternate_object_directory)
    object_id = subprocess.run(
        ["git", "hash-object", "-w", f"--path={relative}", "--", relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    ).stdout.strip()
    content = git_bytes("cat-file", "blob", object_id, env=env)
    return object_id, content


def raw_file_records(paths: list[str]) -> tuple[list[dict[str, object]], list[str]]:
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for relative in sorted(paths):
        path = ROOT / relative
        try:
            stat = path.stat()
            if not path.is_file():
                raise OSError("not a regular file")
            records.append(
                {
                    "path": relative,
                    "bytes": stat.st_size,
                    "sha256": sha256(path),
                    "mtime_utc": datetime.fromtimestamp(
                        stat.st_mtime, UTC
                    ).isoformat(),
                }
            )
        except OSError as exc:
            errors.append(f"{relative}: {exc}")
    return records, errors


def final_artifact_snapshot(captured_at: datetime) -> dict[str, object]:
    records: list[dict[str, object]] = []
    missing: list[str] = []
    newest_mtime = 0.0
    for relative in REQUIRED_FINAL_ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        mtime = path.stat().st_mtime
        newest_mtime = max(newest_mtime, mtime)
        records.append(
            {
                "path": relative,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "mtime_utc": datetime.fromtimestamp(mtime, UTC).isoformat(),
            }
        )
    complete = not missing and len(records) == len(REQUIRED_FINAL_ARTIFACTS)
    return {
        "required_count": len(REQUIRED_FINAL_ARTIFACTS),
        "captured_count": len(records),
        "missing": missing,
        "artifacts": records,
        "newest_artifact_mtime_utc": (
            datetime.fromtimestamp(newest_mtime, UTC).isoformat() if newest_mtime else None
        ),
        "audit_after_required_artifacts": complete and captured_at.timestamp() >= newest_mtime,
    }


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline_head = str(baseline["git"]["head"])
    baseline_captured_at = datetime.fromisoformat(
        str(baseline["captured_at_utc"]).replace("Z", "+00:00")
    ).astimezone(UTC)
    current_head = git("rev-parse", "HEAD")
    git_object_directory_text = git("rev-parse", "--git-path", "objects")
    git_object_directory = Path(git_object_directory_text)
    if not git_object_directory.is_absolute():
        git_object_directory = (ROOT / git_object_directory).resolve()

    baseline_by_label = {item["path"]: item for item in baseline["protected_paths"]}
    results: list[dict[str, object]] = []
    problems: list[str] = []
    combined_baseline_canonical: list[dict[str, object]] = []
    combined_current_canonical: list[dict[str, object]] = []
    combined_current_worktree: list[dict[str, object]] = []
    combined_untracked: list[dict[str, object]] = []
    combined_ignored: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="v50-protected-git-objects-") as object_dir:
        temporary_object_directory = Path(object_dir)
        for label, actual_path in PATHS.items():
            expected = baseline_by_label[label]
            try:
                baseline_tree = git_tree_entries(baseline_head, actual_path)
                baseline_tree = {
                    path: object_id
                    for path, object_id in baseline_tree.items()
                    if not excluded(path, label)
                }
                baseline_tracked = sorted(baseline_tree)
                current_tracked = [
                    path
                    for path in lines(git("ls-files", "--", actual_path))
                    if not excluded(path, label)
                ]
                changed = [
                    path
                    for path in lines(
                        git("diff", "--name-only", baseline_head, "--", actual_path)
                    )
                    if not excluded(path, label)
                ]
                untracked = [
                    path
                    for path in lines(
                        git("ls-files", "--others", "--exclude-standard", "--", actual_path)
                    )
                    if not excluded(path, label)
                ]
                ignored = [
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
                baseline_set = set(baseline_tracked)
                current_set = set(current_tracked)
                missing = sorted(path for path in baseline_set if not (ROOT / path).is_file())
                extra = sorted((current_set | set(untracked)) - baseline_set)
                file_manifest: list[dict[str, object]] = []
                baseline_canonical: list[dict[str, object]] = []
                current_canonical: list[dict[str, object]] = []
                content_mismatches: list[str] = []
                io_errors: list[str] = []
                byte_count = 0
                for relative in sorted(baseline_set):
                    baseline_object_id = baseline_tree[relative]
                    baseline_content = git_bytes(
                        "cat-file", "blob", baseline_object_id
                    )
                    baseline_record = {
                        "path": relative,
                        "bytes": len(baseline_content),
                        "sha256": sha256_bytes(baseline_content),
                    }
                    baseline_canonical.append(baseline_record)
                    path = ROOT / relative
                    if not path.is_file():
                        continue
                    try:
                        stat = path.stat()
                        current_object_id, current_content = normalized_worktree_blob(
                            relative,
                            temporary_object_directory,
                            git_object_directory,
                        )
                        current_record = {
                            "path": relative,
                            "bytes": len(current_content),
                            "sha256": sha256_bytes(current_content),
                        }
                        current_canonical.append(current_record)
                        byte_count += stat.st_size
                        matches = current_record == baseline_record
                        file_manifest.append(
                            {
                                "path": relative,
                                "bytes": stat.st_size,
                                "sha256": sha256(path),
                                "baseline_canonical_bytes": baseline_record["bytes"],
                                "baseline_canonical_sha256": baseline_record["sha256"],
                                "current_canonical_bytes": current_record["bytes"],
                                "current_canonical_sha256": current_record["sha256"],
                                "baseline_git_blob_oid": baseline_object_id,
                                "current_git_blob_oid": current_object_id,
                                "canonical_sha256_matches_baseline": matches,
                            }
                        )
                        if not matches:
                            content_mismatches.append(relative)
                    except (OSError, subprocess.SubprocessError) as exc:
                        io_errors.append(f"{relative}: {exc}")

                untracked_records, untracked_errors = raw_file_records(untracked)
                ignored_records, ignored_errors = raw_file_records(ignored)
                ignored_after_baseline = [
                    str(record["path"])
                    for record in ignored_records
                    if datetime.fromisoformat(str(record["mtime_utc"])).astimezone(UTC)
                    > baseline_captured_at
                ]
                baseline_canonical_sha = canonical_manifest_sha256(baseline_canonical)
                current_canonical_sha = canonical_manifest_sha256(current_canonical)
                current_worktree_sha = canonical_manifest_sha256(file_manifest)
                untracked_manifest_sha = canonical_manifest_sha256(untracked_records)
                ignored_manifest_sha = canonical_manifest_sha256(ignored_records)
                baseline_tree_id = git("rev-parse", f"{baseline_head}:{actual_path}")
                checks = {
                    "baseline_tracked_file_count_matches": len(baseline_tracked)
                    == int(expected["tracked_files"]),
                    "current_tracked_path_set_matches_baseline": current_set == baseline_set,
                    "tracked_byte_count_matches": byte_count == int(expected["bytes"]),
                    "baseline_tree_record_matches": baseline_tree_id == expected["head_tree"],
                    "canonical_per_file_sha256_matches_baseline": not content_mismatches
                    and len(current_canonical) == len(baseline_canonical),
                    "canonical_manifest_sha256_matches_baseline": current_canonical_sha
                    == baseline_canonical_sha,
                    "canonical_content_mismatches": content_mismatches,
                    "working_tree_byte_changes_from_baseline": changed,
                    "missing_baseline_files": missing,
                    "extra_tracked_or_untracked_files": extra,
                    "untracked_files_outside_v5": untracked,
                    "ignored_files_outside_v5": ignored,
                    "ignored_files_with_mtime_after_baseline_capture": ignored_after_baseline,
                    "ignored_files_baseline_content_comparison_supported": not ignored,
                    "file_read_errors": io_errors,
                    "untracked_file_read_errors": untracked_errors,
                    "ignored_file_read_errors": ignored_errors,
                }
                path_ok = (
                    checks["baseline_tracked_file_count_matches"]
                    and checks["current_tracked_path_set_matches_baseline"]
                    and checks["tracked_byte_count_matches"]
                    and checks["baseline_tree_record_matches"]
                    and checks["canonical_per_file_sha256_matches_baseline"]
                    and checks["canonical_manifest_sha256_matches_baseline"]
                    and not changed
                    and not missing
                    and not extra
                    and not untracked
                    and not ignored_after_baseline
                    and not io_errors
                    and not untracked_errors
                    and not ignored_errors
                )
                results.append(
                    {
                        "path": label,
                        "tracked_files": len(file_manifest),
                        "bytes": byte_count,
                        "aggregate_sha256": expected["aggregate_sha256"],
                        "aggregate_sha256_source": "frozen_baseline_legacy_value",
                        "baseline_head_tree": baseline_tree_id,
                        "baseline_canonical_file_manifest_sha256": baseline_canonical_sha,
                        "current_canonical_file_manifest_sha256": current_canonical_sha,
                        "current_file_manifest_sha256": current_worktree_sha,
                        "files": file_manifest,
                        "untracked_files": untracked_records,
                        "untracked_file_manifest_sha256": untracked_manifest_sha,
                        "untracked_file_count": len(untracked_records),
                        "ignored_files": ignored_records,
                        "ignored_file_manifest_sha256": ignored_manifest_sha,
                        "ignored_file_count": len(ignored_records),
                        "ignored_baseline_comparison_supported": not ignored,
                        "status": "pass" if path_ok else "fail",
                        "verification": checks,
                    }
                )
                combined_baseline_canonical.extend(baseline_canonical)
                combined_current_canonical.extend(current_canonical)
                combined_current_worktree.extend(file_manifest)
                combined_untracked.extend(untracked_records)
                combined_ignored.extend(ignored_records)
                if not path_ok:
                    problems.append(label)
            except Exception as exc:  # preserve a fresh fail artifact instead of a stale pass
                problems.append(label)
                results.append(
                    {
                        "path": label,
                        "tracked_files": 0,
                        "bytes": 0,
                        "aggregate_sha256": None,
                        "status": "fail",
                        "verification": {"exception": f"{type(exc).__name__}: {exc}"},
                    }
                )

    # Require two consecutive raw snapshots so a mutation during the first pass
    # cannot be published as a fresh pass.
    for result in results:
        label = str(result["path"])
        actual_path = PATHS.get(label)
        verification = result.get("verification", {})
        if actual_path is None or not isinstance(verification, dict):
            continue
        try:
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
            second_files, second_file_errors = raw_file_records(second_tracked_paths)
            second_untracked, second_untracked_errors = raw_file_records(
                second_untracked_paths
            )
            second_ignored, second_ignored_errors = raw_file_records(
                second_ignored_paths
            )
            consecutive_snapshot_matches = all(
                (
                    sorted(second_tracked_paths)
                    == sorted(str(record["path"]) for record in result.get("files", [])),
                    sorted(second_untracked_paths)
                    == sorted(
                        str(record["path"])
                        for record in result.get("untracked_files", [])
                    ),
                    sorted(second_ignored_paths)
                    == sorted(
                        str(record["path"])
                        for record in result.get("ignored_files", [])
                    ),
                    canonical_manifest_sha256(second_files)
                    == result.get("current_file_manifest_sha256"),
                    canonical_manifest_sha256(second_untracked)
                    == result.get("untracked_file_manifest_sha256"),
                    canonical_manifest_sha256(second_ignored)
                    == result.get("ignored_file_manifest_sha256"),
                    not second_file_errors,
                    not second_untracked_errors,
                    not second_ignored_errors,
                )
            )
            verification["consecutive_raw_snapshot_matches"] = (
                consecutive_snapshot_matches
            )
            verification["second_snapshot_file_read_errors"] = (
                second_file_errors
                + second_untracked_errors
                + second_ignored_errors
            )
            if not consecutive_snapshot_matches:
                result["status"] = "fail"
                if label not in problems:
                    problems.append(label)
        except Exception as exc:
            verification["consecutive_raw_snapshot_matches"] = False
            verification["second_snapshot_exception"] = f"{type(exc).__name__}: {exc}"
            result["status"] = "fail"
            if label not in problems:
                problems.append(label)

    total_files = sum(int(item["tracked_files"]) for item in results)
    total_bytes = sum(int(item["bytes"]) for item in results)
    expected_combined = baseline["combined_protected"]
    combined_baseline_canonical_sha = canonical_manifest_sha256(
        combined_baseline_canonical
    )
    combined_current_canonical_sha = canonical_manifest_sha256(
        combined_current_canonical
    )
    combined_current_worktree_sha = canonical_manifest_sha256(
        combined_current_worktree
    )
    combined_untracked_sha = canonical_manifest_sha256(combined_untracked)
    combined_ignored_sha = canonical_manifest_sha256(combined_ignored)
    combined_ok = (
        not problems
        and total_files == int(expected_combined["tracked_files"])
        and total_bytes == int(expected_combined["bytes"])
        and combined_baseline_canonical_sha == combined_current_canonical_sha
    )
    overall_status = (
        "pass_with_unverified_ignored_files"
        if combined_ok and combined_ignored
        else "pass" if combined_ok else "fail"
    )
    captured_at = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema_version": "1.1.0",
        "captured_at_utc": captured_at.isoformat(),
        "repository_root": ROOT.as_posix(),
        "baseline_path": BASELINE.relative_to(ROOT).as_posix(),
        "git": {
            "baseline_head": baseline_head,
            "current_head": current_head,
            "whole_head_match_required": False,
            "verification_basis": "protected_working_files_compared_with_baseline_commit",
        },
        "comparison_contract": {
            "tracked_file_content_basis": (
                "per_file_sha256_after_git_clean_filters_compared_with_baseline_commit_blobs"
            ),
            "working_tree_bytes_basis": "current_raw_bytes_rehashed_per_file",
            "legacy_aggregate_sha256_basis": (
                "copied_from_frozen_baseline_for_compatibility_only"
            ),
            "ignored_file_baseline_limitation": (
                "the_frozen_baseline_did_not_record_ignored_paths_or_hashes; current_ignored_"
                "files_are_enumerated_and_rehashed_but_baseline_content_equality_is_not_proven"
            ),
        },
        "protected_paths": results,
        "combined_protected": {
            "tracked_files": total_files,
            "bytes": total_bytes,
            "aggregate_sha256": expected_combined["aggregate_sha256"],
            "aggregate_sha256_source": "frozen_baseline_legacy_value",
            "baseline_canonical_file_manifest_sha256": combined_baseline_canonical_sha,
            "current_canonical_file_manifest_sha256": combined_current_canonical_sha,
            "current_file_manifest_sha256": combined_current_worktree_sha,
            "untracked_file_count": len(combined_untracked),
            "untracked_file_manifest_sha256": combined_untracked_sha,
            "ignored_file_count": len(combined_ignored),
            "ignored_file_manifest_sha256": combined_ignored_sha,
            "ignored_baseline_comparison_supported": not combined_ignored,
            "status": "pass" if combined_ok else "fail",
        },
        "status_scope": "434_baseline_tracked_files",
        "ignored_file_baseline_limitation_present": bool(combined_ignored),
        "limitations": (
            [
                {
                    "code": "IGNORED_FILES_NOT_CAPTURED_IN_FROZEN_BASELINE",
                    "file_count": len(combined_ignored),
                    "effect": (
                        "current ignored files are enumerated and hashed, but their content "
                        "cannot be compared with the frozen baseline"
                    ),
                }
            ]
            if combined_ignored
            else []
        ),
        "status": overall_status,
        "problems": problems,
        "final_artifact_snapshot": final_artifact_snapshot(captured_at),
        "independent_blinding": False,
        "release_ready": False,
    }
    atomic_json(OUTPUT, payload)
    if not combined_ok:
        raise RuntimeError(f"protected-path verification failed: {problems}")
    print(
        f"protected_tracked_files=pass overall_status={overall_status} "
        f"tracked_files={total_files} bytes={total_bytes} "
        f"ignored_files={len(combined_ignored)} "
        f"ignored_baseline_comparison_supported={not combined_ignored} "
        f"output={OUTPUT.relative_to(ROOT).as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
