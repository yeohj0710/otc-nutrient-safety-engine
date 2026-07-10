from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .schemas import RetrievedRecord
from .storage import stable_hash


def parse_ris_file(
    path: Path,
    *,
    source: str,
    target_id: str,
    search_run_id: str,
) -> list[RetrievedRecord]:
    text = path.read_text(encoding="utf-8-sig")
    entries = _parse_with_rispy(text) or _parse_ris_fallback(text)
    return [
        _entry_to_record(
            entry,
            source=source,
            target_id=target_id,
            search_run_id=search_run_id,
            index=index,
        )
        for index, entry in enumerate(entries, start=1)
        if _first(entry, "title", "primary_title", "T1", "TI")
    ]


def _parse_with_rispy(text: str) -> list[dict[str, Any]]:
    try:
        import rispy  # type: ignore
    except ImportError:
        return []

    try:
        return list(rispy.loads(text))
    except Exception:
        return []


def _parse_ris_fallback(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    last_tag = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        match = re.match(r"^([A-Z0-9]{2})  - ?(.*)$", line)
        if match:
            tag = match.group(1)
            value = match.group(2).strip()

            if tag == "TY":
                current = {"TY": value}
                last_tag = tag
                continue

            if current is None:
                current = {}

            if tag == "ER":
                records.append(current)
                current = None
                last_tag = ""
                continue

            _append_value(current, tag, value)
            last_tag = tag
        elif current is not None and last_tag:
            previous = current.get(last_tag)
            if isinstance(previous, list) and previous:
                previous[-1] = f"{previous[-1]} {line.strip()}".strip()
            elif isinstance(previous, str):
                current[last_tag] = f"{previous} {line.strip()}".strip()

    if current:
        records.append(current)

    return records


def _entry_to_record(
    entry: dict[str, Any],
    *,
    source: str,
    target_id: str,
    search_run_id: str,
    index: int,
) -> RetrievedRecord:
    title = _first(entry, "title", "primary_title", "T1", "TI")
    abstract = _first(entry, "abstract", "notes_abstract", "AB", "N2")
    year = _year(_first(entry, "year", "publication_year", "PY", "Y1", "DA"))
    journal = _first(
        entry,
        "journal_name",
        "secondary_title",
        "alternate_title3",
        "JF",
        "JO",
        "T2",
    )
    doi = _normalize_doi(_first(entry, "doi", "DO"))
    pmid = _first(entry, "pmid", "PMID")
    url = _first(entry, "url", "urls", "UR", "LK")
    raw_record_id = _first(
        entry,
        "id",
        "accession_number",
        "accession_numbers",
        "AN",
        "M1",
        "U1",
    )
    if not raw_record_id:
        raw_record_id = doi or pmid or stable_hash(f"{title}|{year}|{index}")

    return RetrievedRecord(
        record_id=f"{source}:{raw_record_id}:{search_run_id}",
        source=source,
        target_id=target_id,
        search_run_id=search_run_id,
        title=title,
        abstract_or_summary=abstract,
        year=year,
        journal_or_source=journal,
        doi=doi,
        pmid=pmid,
        url=url,
        raw_record_id=raw_record_id,
    )


def _append_value(record: dict[str, Any], key: str, value: str) -> None:
    if key in record:
        existing = record[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            record[key] = [existing, value]
    else:
        record[key] = value


def _first(entry: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, list):
            value = next((item for item in value if item), "")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _year(value: str) -> str:
    for index in range(0, max(len(value) - 3, 0)):
        candidate = value[index : index + 4]
        if candidate.isdigit():
            return candidate
    return value if value.isdigit() and len(value) == 4 else ""


def _normalize_doi(value: str) -> str:
    doi = value.strip().lower()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()
