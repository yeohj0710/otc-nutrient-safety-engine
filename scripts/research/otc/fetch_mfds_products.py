from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from scripts.research.otc.hash_snapshot import sha256_bytes


BASE_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07"
ENDPOINTS = {
    "products": "getDrugPrdtPrmsnInq07",
    "details": "getDrugPrdtPrmsnDtlInq06",
    "ingredients": "getDrugPrdtMcpnDtlInq07",
}


@dataclass(frozen=True)
class SnapshotRecord:
    endpoint: str
    page_no: int
    request_url_without_key: str
    retrieved_at_utc: str
    response_sha256: str
    response_bytes: int
    raw_path: str
    item_count: int
    total_count: int | None


def build_url(
    endpoint: str,
    service_key: str,
    *,
    page_no: int = 1,
    num_of_rows: int = 100,
    item_sequence: str | None = None,
) -> str:
    if endpoint not in ENDPOINTS:
        raise ValueError(f"unsupported MFDS endpoint: {endpoint}")
    params = {
        "serviceKey": service_key,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "json",
    }
    if item_sequence:
        params["ITEM_SEQ"] = item_sequence
    return f"{BASE_URL}/{ENDPOINTS[endpoint]}?{urlencode(params)}"


def redact_service_key(url: str, service_key: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "<REDACTED>" if key == "serviceKey" else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def response_body(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("body")
    if body is None:
        body = payload.get("response", {}).get("body")
    if not isinstance(body, dict):
        raise ValueError("MFDS response has no object body")
    return body


def response_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = response_body(payload)
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if not isinstance(items, list):
        raise ValueError("MFDS response items are not a list")
    return items


def fetch_page(
    url: str,
    *,
    timeout_seconds: int = 30,
    attempts: int = 3,
    get: Callable[..., requests.Response] = requests.get,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = get(url, timeout=timeout_seconds)
            response.raise_for_status()
            return response.content
        except (requests.RequestException, TimeoutError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(0.25 * (2**attempt))
    raise RuntimeError(f"MFDS request failed after {attempts} attempts") from last_error


def preserve_snapshot(
    payload: bytes,
    *,
    output_dir: Path,
    endpoint: str,
    page_no: int,
    request_url_without_key: str,
) -> SnapshotRecord:
    parsed = json.loads(payload.decode("utf-8"))
    body = response_body(parsed)
    items = response_items(parsed)
    digest = sha256_bytes(payload)
    endpoint_dir = output_dir / endpoint
    endpoint_dir.mkdir(parents=True, exist_ok=True)
    raw_path = endpoint_dir / f"page-{page_no:05d}-{digest[:12]}.json"
    if raw_path.exists() and raw_path.read_bytes() != payload:
        raise RuntimeError(f"immutable snapshot collision: {raw_path}")
    raw_path.write_bytes(payload)
    total_count = body.get("totalCount")
    if total_count is not None:
        total_count = int(total_count)
    return SnapshotRecord(
        endpoint=endpoint,
        page_no=page_no,
        request_url_without_key=request_url_without_key,
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        response_sha256=digest,
        response_bytes=len(payload),
        raw_path=raw_path.as_posix(),
        item_count=len(items),
        total_count=total_count,
    )


def collect(
    *,
    endpoint: str,
    output_dir: Path,
    service_key: str,
    pages: int,
    num_of_rows: int,
    fixture: Path | None = None,
) -> list[SnapshotRecord]:
    if not service_key and fixture is None:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required for live acquisition")
    records = []
    for page_no in range(1, pages + 1):
        url = build_url(endpoint, service_key or "fixture", page_no=page_no, num_of_rows=num_of_rows)
        payload = fixture.read_bytes() if fixture else fetch_page(url)
        records.append(
            preserve_snapshot(
                payload,
                output_dir=output_dir,
                endpoint=endpoint,
                page_no=page_no,
                request_url_without_key=redact_service_key(url, service_key or "fixture"),
            )
        )
    manifest = output_dir / f"{endpoint}_snapshot_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "source": "MFDS DrugPrdtPrmsnInfoService07",
                "endpoint": endpoint,
                "records": [asdict(record) for record in records],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch immutable MFDS authorization snapshots")
    parser.add_argument("--endpoint", choices=sorted(ENDPOINTS), default="products")
    parser.add_argument("--output-dir", type=Path, default=Path("research_v3/otc/raw/mfds"))
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--num-of-rows", type=int, default=100)
    parser.add_argument("--fixture", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = collect(
        endpoint=args.endpoint,
        output_dir=args.output_dir,
        service_key=os.environ.get("DATA_GO_KR_SERVICE_KEY", ""),
        pages=args.pages,
        num_of_rows=args.num_of_rows,
        fixture=args.fixture,
    )
    print(json.dumps({"snapshots": len(records), "items": sum(r.item_count for r in records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
