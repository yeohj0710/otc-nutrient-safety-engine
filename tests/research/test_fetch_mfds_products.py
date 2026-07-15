import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from scripts.research.otc.fetch_mfds_products import (
    build_url,
    collect,
    fetch_page,
    preserve_snapshot,
    response_items,
)
from scripts.research.otc.hash_snapshot import sha256_bytes, sha256_file


def sample_payload() -> bytes:
    return json.dumps(
        {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
            "body": {
                "pageNo": 1,
                "numOfRows": 2,
                "totalCount": 2,
                "items": [
                    {"ITEM_SEQ": "200000001", "ITEM_NAME": "검증용일반정"},
                    {"ITEM_SEQ": "200000002", "ITEM_NAME": "검증용복합정"},
                ],
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def test_build_url_uses_current_mfds_endpoint_and_parameters() -> None:
    url = build_url("products", "secret key", page_no=3, num_of_rows=250)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07")
    assert query == {
        "serviceKey": ["secret key"],
        "pageNo": ["3"],
        "numOfRows": ["250"],
        "type": ["json"],
    }


def test_preserve_snapshot_is_byte_exact_and_hashed(tmp_path: Path) -> None:
    payload = sample_payload()
    record = preserve_snapshot(
        payload,
        output_dir=tmp_path,
        endpoint="products",
        page_no=1,
        request_url_without_key="https://example.test?serviceKey=<REDACTED>",
    )
    path = Path(record.raw_path)
    assert path.read_bytes() == payload
    assert record.response_sha256 == sha256_bytes(payload) == sha256_file(path)
    assert record.item_count == 2
    assert record.total_count == 2
    assert "secret" not in json.dumps(record.__dict__)


def test_response_items_accepts_gateway_wrapper() -> None:
    payload = {"response": json.loads(sample_payload().decode("utf-8"))}
    assert len(response_items(payload)) == 2


def test_fixture_collection_needs_no_key_and_writes_manifest(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_bytes(sample_payload())
    records = collect(
        endpoint="products",
        output_dir=tmp_path / "raw",
        service_key="",
        pages=1,
        num_of_rows=100,
        fixture=fixture,
    )
    manifest = json.loads((tmp_path / "raw" / "products_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert len(records) == 1
    assert manifest["records"][0]["request_url_without_key"].endswith("serviceKey=%3CREDACTED%3E&pageNo=1&numOfRows=100&type=json")


def test_live_collection_requires_environment_key(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="DATA_GO_KR_SERVICE_KEY"):
        collect(endpoint="products", output_dir=tmp_path, service_key="", pages=1, num_of_rows=1)


def test_fetch_retries_then_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    class Response:
        content = sample_payload()

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise requests.ConnectionError("temporary")
        return Response()

    monkeypatch.setattr("time.sleep", lambda _: None)
    assert fetch_page("https://example.test", attempts=3, get=fake_get) == sample_payload()
    assert attempts == 3
