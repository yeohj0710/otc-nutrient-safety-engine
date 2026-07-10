#!/usr/bin/env python3
"""Inventory pre-research_v2 assets without modifying source files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".next",
    ".pytest_cache",
    "__pycache__",
    "execution_package",
    "node_modules",
    "research_v2",
}
REUSABLE_CODE_ROOTS = {
    "__tests__",
    "app",
    "public",
    "schemas",
    "scripts",
    "src",
    "tests",
    "tools",
}
FIELDNAMES = [
    "source_root",
    "source_kind",
    "relative_path",
    "absolute_path",
    "extension",
    "item_type",
    "size_bytes",
    "modified_utc",
    "sha256",
    "git_tracked",
    "trust_status",
    "disposition",
    "reason",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def item_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".xlsx", ".xls"}:
        return "tabular_data"
    if suffix in {".json", ".jsonl", ".xml", ".ris"}:
        return "structured_data"
    if suffix in {".pdf", ".docx", ".doc", ".hwp", ".md", ".txt"}:
        return "document"
    if suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".sql"}:
        return "source_code"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
        return "image"
    return "other"


def tracked_paths(repo_root: Path) -> set[str]:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_root), "ls-files"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()}


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, topdown=True):
        directories[:] = sorted(name for name in directories if name not in SKIP_DIRS)
        current_path = Path(current)
        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_file() and not path.is_symlink():
                files.append(path)
    return files


def inventory(roots: list[Path], repo_root: Path) -> list[dict[str, str]]:
    repo_root = repo_root.resolve()
    tracked = tracked_paths(repo_root)
    rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for source in roots:
        source = source.resolve()
        source_kind = "repository" if source == repo_root else "external_archive"
        for path in iter_files(source):
            relative = path.relative_to(source).as_posix()
            if source_kind == "repository" and tracked and relative not in tracked:
                continue
            absolute = str(path.resolve())
            if absolute.casefold() in seen_paths:
                continue
            seen_paths.add(absolute.casefold())
            first_part = relative.split("/", 1)[0]
            reusable = source_kind == "repository" and first_part in REUSABLE_CODE_ROOTS
            stat = path.stat()
            rows.append(
                {
                    "source_root": str(source),
                    "source_kind": source_kind,
                    "relative_path": relative,
                    "absolute_path": absolute,
                    "extension": path.suffix.lower(),
                    "item_type": item_type(path),
                    "size_bytes": str(stat.st_size),
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "sha256": sha256_file(path),
                    "git_tracked": (
                        "true"
                        if source_kind == "repository" and relative in tracked
                        else "false"
                    ),
                    "trust_status": "legacy_untrusted",
                    "disposition": "review_for_reuse" if reusable else "audit_only",
                    "reason": (
                        "pre-v2 code; reuse requires tests and scope review"
                        if reusable
                        else "predates research_v2 evidence lineage"
                    ),
                }
            )
    return rows


def write_inventory(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument(
        "--out", default="research_v2/audit/legacy_inventory.csv"
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    roots = [repo_root, *(Path(value) for value in args.source)]
    missing = [str(path) for path in roots if not path.exists()]
    if missing:
        raise SystemExit(f"Missing inventory roots: {missing}")

    rows = inventory(roots, repo_root=repo_root)
    output = Path(args.out)
    if not output.is_absolute():
        output = repo_root / output
    write_inventory(output, rows)
    print(f"Legacy inventory written: rows={len(rows)} path={output}")


if __name__ == "__main__":
    main()
