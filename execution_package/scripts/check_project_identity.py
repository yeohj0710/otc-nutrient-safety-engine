#!/usr/bin/env python3
"""Fail-closed identity check for the Kwon research repository.

The check deliberately ignores audit and quarantined legacy material, because those
areas are expected to document the package identity correction. It fails when
Yeo-specific identity markers leak into active research, data, UI, or release paths.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".ts", ".tsx", ".js", ".jsx", ".txt", ".csv", ".yml", ".yaml", ".toml"}
SKIP_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "legacy_untrusted",
    "audit",
    "__pycache__",
}
ACTIVE_ROOTS = {"app", "data", "research_v2", "src"}
DISALLOWED_MARKERS = (
    "여형준",
    "2020194025",
    "항응고제 복용자와 신장결석 고위험군",
)


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception:
        return ""


def is_skipped(path: Path, root: Path, package_dir_name: str | None) -> bool:
    rel = path.relative_to(root)
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    if package_dir_name and package_dir_name in rel.parts:
        return True
    return False


def iter_text_files(root: Path, package_dir_name: str | None) -> Iterable[Path]:
    identity_exceptions = {
        root / "research_v2" / "project_identity.json",
        root / "research_v2" / "config" / "project_identity.json",
        root / "research_v2" / "DECISIONS.md",
        root / "research_v2" / "CHANGELOG_RESEARCH.md",
        root / "research_v2" / "HUMAN_ACTION_REQUIRED.md",
        root / "research_v2" / "protocol" / "reference" / "reference_manifest.json",
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path in identity_exceptions:
            continue
        if is_skipped(path, root, package_dir_name):
            continue
        rel = path.relative_to(root)
        if not rel.parts or rel.parts[0] not in ACTIVE_ROOTS:
            continue
        try:
            if path.stat().st_size > 5_000_000:
                continue
        except OSError:
            continue
        yield path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--config",
        default=None,
        help="project_identity.json; defaults to <root>/research_v2/config/project_identity.json",
    )
    parser.add_argument(
        "--out", default=None, help="Output path; defaults to research_v2/audit/repo_identity.json"
    )
    parser.add_argument(
        "--package-dir-name",
        default="execution_package",
        help="Directory to ignore when the execution package is copied into the repo",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config_path = (
        Path(args.config)
        if args.config
        else root / "research_v2" / "config" / "project_identity.json"
    )
    fallback_config = root / "config" / "project_identity.json"
    if not config_path.exists() and fallback_config.exists():
        config_path = fallback_config

    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {
            "student_name": "권혁찬",
            "student_id": "2021194024",
            "recommended_repo": "otc-nutrient-safety-engine",
        }

    remote = git(root, "remote", "get-url", "origin")
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")

    marker_files: list[dict[str, object]] = []
    for path in iter_text_files(root, args.package_dir_name):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        matched = [marker for marker in DISALLOWED_MARKERS if marker.casefold() in text.casefold()]
        if matched:
            marker_files.append(
                {"path": str(path.relative_to(root)), "markers": matched}
            )

    active_identity_path = root / "research_v2" / "project_identity.json"
    active_identity: dict[str, object] | None = None
    identity_error: str | None = None
    if active_identity_path.exists():
        try:
            active_identity = json.loads(active_identity_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report malformed audit input
            identity_error = str(exc)

    expected_name = str(config.get("student_name", "권혁찬"))
    expected_id = str(config.get("student_id", "2021194024"))
    recommended_repo = str(config.get("recommended_repo", "otc-nutrient-safety-engine"))

    active_identity_text = " ".join(
        str(active_identity.get(key, ""))
        for key in ("student_name", "student_id", "study_slug", "title_ko", "title_en", "mode")
    ) if active_identity else ""
    identity_matches = bool(
        active_identity
        and str(active_identity.get("student_name")) == expected_name
        and str(active_identity.get("student_id")) == expected_id
        and str(active_identity.get("study_slug", "")).strip()
        and not any(marker.casefold() in active_identity_text.casefold() for marker in DISALLOWED_MARKERS)
    )
    remote_matches = bool(
        remote
        and recommended_repo in remote
    )

    failures: list[str] = []
    if marker_files:
        failures.append("yeo_markers_in_active_paths")
    if identity_error:
        failures.append("malformed_active_project_identity")
    if not identity_matches:
        failures.append("missing_or_mismatched_active_project_identity")
    if not remote_matches:
        failures.append("git_remote_not_kwon_primary_repo")

    result = {
        "student_name": expected_name,
        "student_id": expected_id,
        "recommended_repo": recommended_repo,
        "repo_root": str(root),
        "remote": remote,
        "branch": branch,
        "head_commit": head,
        "active_project_identity_path": str(active_identity_path.relative_to(root)),
        "active_project_identity": active_identity,
        "marker_files": marker_files,
        "checks": {
            "active_identity_matches": identity_matches,
            "remote_matches_recommended_repo": remote_matches,
            "yeo_markers_absent_from_active_paths": not marker_files,
        },
        "failures": failures,
        "pass": not failures,
    }

    out = (
        Path(args.out)
        if args.out
        else root / "research_v2" / "audit" / "repo_identity.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
