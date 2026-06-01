from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .schemas import (
    EVIDENCE_EXTRACTION_COLUMNS,
    RETRIEVED_RECORD_COLUMNS,
    SCREENING_LOG_COLUMNS,
    SEARCH_RUN_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMATIC_SEARCH_DIR = REPO_ROOT / "data" / "systematic_search"

CSV_LAYOUT = {
    "search_runs.csv": SEARCH_RUN_COLUMNS,
    "retrieved_records.csv": RETRIEVED_RECORD_COLUMNS,
    "screening_log.csv": SCREENING_LOG_COLUMNS,
    "evidence_extraction.csv": EVIDENCE_EXTRACTION_COLUMNS,
}


def ensure_layout(root: Path = SYSTEMATIC_SEARCH_DIR) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "raw" / "pubmed").mkdir(parents=True, exist_ok=True)
    (root / "raw" / "embase").mkdir(parents=True, exist_ok=True)
    for filename, columns in CSV_LAYOUT.items():
        path = root / filename
        if not path.exists():
            write_csv_rows(path, [], columns)


def timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def slugify(value: str, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return (slug or "query")[:max_length].strip("-") or "query"


def to_repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv_rows(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def append_csv_rows(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def upsert_csv_rows(
    path: Path,
    rows: Iterable[dict[str, object]],
    columns: list[str],
    key_column: str,
) -> None:
    existing = read_csv_rows(path)
    by_key = {row.get(key_column, ""): row for row in existing if row.get(key_column)}
    order = [row.get(key_column, "") for row in existing if row.get(key_column)]

    for row in rows:
        key = str(row.get(key_column, ""))
        if not key:
            continue
        if key not in by_key:
            order.append(key)
        merged = dict(by_key.get(key, {}))
        merged.update({column: row.get(column, "") for column in columns})
        by_key[key] = merged

    write_csv_rows(path, [by_key[key] for key in order if key in by_key], columns)
