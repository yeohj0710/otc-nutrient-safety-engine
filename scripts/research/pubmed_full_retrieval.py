#!/usr/bin/env python3
"""Retrieve every PubMed UID and record with date segmentation and raw hashes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Protocol

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.search_pipeline.pubmed_adapter import parse_pubmed_xml
from tools.search_pipeline.schemas import RETRIEVED_RECORD_COLUMNS


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "kwon_pubmed_feasibility"
UID_LIMIT = 9_999


class CountClient(Protocol):
    def count(self, query: str) -> int: ...


@dataclass(frozen=True)
class Segment:
    start: str
    end: str
    count: int
    query: str


def dated_query(query: str, start: date, end: date) -> str:
    return f'({query}) AND ("{start.isoformat()}"[Date - Publication] : "{end.isoformat()}"[Date - Publication])'


def plan_segments(
    client: CountClient,
    query: str,
    start: date,
    end: date,
    limit: int = UID_LIMIT,
) -> list[Segment]:
    scoped = dated_query(query, start, end)
    count = client.count(scoped)
    if count <= limit:
        return [Segment(start.isoformat(), end.isoformat(), count, scoped)]
    if start >= end:
        raise RuntimeError(f"single publication day exceeds PubMed UID limit: {start} count={count}")
    midpoint = start + timedelta(days=(end - start).days // 2)
    return plan_segments(client, query, start, midpoint, limit) + plan_segments(
        client, query, midpoint + timedelta(days=1), end, limit
    )


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def resolve_email() -> tuple[str, str]:
    value = os.getenv("NCBI_EMAIL", "").strip()
    source = "environment"
    if not value:
        value = subprocess.check_output(
            ["git", "config", "user.email"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        source = "git_config_user_email"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise RuntimeError("No valid NCBI contact email in environment or git config")
    return value, source


class EUtilsClient:
    def __init__(self, email: str, api_key: str = "", session: requests.Session | None = None) -> None:
        self.email = email
        self.api_key = api_key
        self.session = session or requests.Session()
        self.last_request = 0.0

    def request(self, endpoint: str, data: dict[str, Any]) -> requests.Response:
        minimum_interval = 0.11 if self.api_key else 0.4
        elapsed = time.monotonic() - self.last_request
        if elapsed < minimum_interval:
            time.sleep(minimum_interval - elapsed)
        payload = {"tool": TOOL, "email": self.email, **data}
        if self.api_key:
            payload["api_key"] = self.api_key
        last: requests.Response | None = None
        for attempt in range(6):
            response = self.session.post(f"{BASE_URL}/{endpoint}", data=payload, timeout=90)
            self.last_request = time.monotonic()
            last = response
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else min(30.0, 2**attempt)
            time.sleep(delay)
        assert last is not None
        last.raise_for_status()
        return last

    def count(self, query: str) -> int:
        response = self.request(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmode": "json", "rettype": "count", "retmax": 0},
        )
        return int(response.json()["esearchresult"]["count"])

    def ids(self, query: str, expected: int) -> list[str]:
        if expected > UID_LIMIT:
            raise ValueError("segment exceeds UID limit")
        response = self.request(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmode": "json", "retmax": expected},
        )
        ids = response.json()["esearchresult"]["idlist"]
        if len(ids) != expected:
            raise RuntimeError(f"segment UID mismatch expected={expected} actual={len(ids)}")
        return ids

    def fetch(self, ids: list[str]) -> str:
        return self.request(
            "efetch.fcgi",
            {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
        ).text


def file_manifest(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "raw_manifest.json"):
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return result


def raw_files_sha256(files: list[dict[str, Any]]) -> str:
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_records(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RETRIEVED_RECORD_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.csv_row(RETRIEVED_RECORD_COLUMNS))


def retrieve_node(
    client: EUtilsClient,
    node: str,
    query: str,
    research_root: Path,
    contact_source: str,
    today: date,
) -> dict[str, Any]:
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    raw_dir = research_root / "search" / "raw" / "pubmed" / node / query_hash[:12]
    raw_dir.mkdir(parents=True, exist_ok=True)
    original_count = client.count(query)
    (raw_dir / "query.txt").write_text(query + "\n", encoding="utf-8")
    (raw_dir / "esearch_count.json").write_text(
        json.dumps({"count": original_count, "query_sha256": query_hash}, indent=2) + "\n",
        encoding="utf-8",
    )
    if original_count <= UID_LIMIT:
        segments = [Segment("unbounded", "unbounded", original_count, query)]
    else:
        segments = plan_segments(client, query, date(1800, 1, 1), today)
    (raw_dir / "segments.json").write_text(
        json.dumps([asdict(item) for item in segments], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    all_ids: list[str] = []
    for index, segment in enumerate(segments, start=1):
        ids = client.ids(segment.query, segment.count)
        (raw_dir / f"uids_{index:03}.json").write_text(
            json.dumps(ids, indent=2) + "\n", encoding="utf-8"
        )
        all_ids.extend(ids)
    unique_ids = list(dict.fromkeys(all_ids))
    if len(unique_ids) != original_count:
        raise RuntimeError(
            f"full UID reconciliation failed node={node} count={original_count} unique={len(unique_ids)}"
        )
    records = []
    run_id = f"pubmed_{node}_{today.isoformat()}_{query_hash[:8]}"
    for index, batch in enumerate(chunks(unique_ids, 200), start=1):
        xml = client.fetch(batch)
        (raw_dir / f"efetch_{index:04}.xml").write_text(xml, encoding="utf-8")
        records.extend(parse_pubmed_xml(xml, target_id=node, search_run_id=run_id))
    record_pmids = {record.pmid for record in records}
    if len(records) != original_count or record_pmids != set(unique_ids):
        raise RuntimeError(
            f"record reconciliation failed node={node} ids={len(unique_ids)} records={len(records)} unique_pmids={len(record_pmids)}"
        )
    write_records(research_root / "search" / "normalized" / f"{node}_pubmed_records.csv", records)
    manifest = {
        "node_id": node,
        "query_sha256": query_hash,
        "search_date": today.isoformat(),
        "hit_count": original_count,
        "exported_count": len(unique_ids),
        "imported_count": len(records),
        "segment_count": len(segments),
        "contact_source": contact_source,
        "contact_value_stored": False,
        "tool": TOOL,
        "request_rate_limit_per_second": 2.5 if not client.api_key else 9,
        "raw_files": file_manifest(raw_dir),
    }
    manifest["raw_files_sha256"] = raw_files_sha256(manifest["raw_files"])
    (raw_dir / "raw_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", default="research_v2")
    parser.add_argument("--node", action="append", choices=["K1", "K2", "K3", "K4", "K5"])
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.research_root)
    email, source = resolve_email()
    client = EUtilsClient(email, os.getenv("NCBI_API_KEY", ""))
    nodes = args.node or ["K1", "K2", "K3", "K4", "K5"]
    results = []
    for node in nodes:
        query = (root / "search" / "pubmed_queries" / f"{node}.txt").read_text(encoding="utf-8").strip()
        if args.count_only:
            results.append({"node_id": node, "count": client.count(query)})
        else:
            results.append(retrieve_node(client, node, query, root, source, date.today()))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
