from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import RETRIEVED_RECORD_COLUMNS
from .storage import SYSTEMATIC_SEARCH_DIR, ensure_layout, read_csv_rows, write_csv_rows


@dataclass(frozen=True)
class DedupResult:
    total_records: int
    duplicate_records: int


def dedup_retrieved_records(output_root: Path = SYSTEMATIC_SEARCH_DIR) -> DedupResult:
    ensure_layout(output_root)
    path = output_root / "retrieved_records.csv"
    rows = read_csv_rows(path)
    seen: dict[str, str] = {}
    duplicate_count = 0

    for row in rows:
        key = dedup_key(row)
        row["dedup_key"] = key
        row["duplicate_of"] = ""
        row["is_duplicate"] = "false"

        if key and key in seen:
            row["duplicate_of"] = seen[key]
            row["is_duplicate"] = "true"
            duplicate_count += 1
        elif key:
            seen[key] = row.get("record_id", "")

    write_csv_rows(path, rows, RETRIEVED_RECORD_COLUMNS)
    return DedupResult(total_records=len(rows), duplicate_records=duplicate_count)


def dedup_key(row: dict[str, str]) -> str:
    doi = normalize_doi(row.get("doi", ""))
    if doi:
        return f"doi:{doi}"

    pmid = row.get("pmid", "").strip()
    if pmid:
        return f"pmid:{pmid}"

    title = normalize_title(row.get("title", ""))
    year = row.get("year", "").strip()
    if title and year:
        return f"title_year:{title}:{year}"
    if title:
        return f"title:{title}"
    return ""


def normalize_doi(value: str) -> str:
    doi = value.strip().lower()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip().rstrip(".")


def normalize_title(value: str) -> str:
    title = value.lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return " ".join(title.split())
