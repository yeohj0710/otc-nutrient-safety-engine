from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.research.otc.catalog_candidate_bridge import build_bridge, write_bridge


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    catalog = [
        {
            "id": "SKU-001",
            "name": "닥터베아제",
            "capacity": "10T",
            "category": "소화기",
            "price": "비공개값",
            "displayed_price_krw": 1,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
        {
            "id": "SKU-002",
            "name": "어린이타이레놀현탄액",
            "capacity": "100ml",
            "category": "키즈",
            "price": "비공개값",
            "displayed_price_krw": 2,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
        {
            "id": "SKU-003",
            "name": "테스트감기시럽",
            "capacity": "100ml",
            "category": "호흡기",
            "price": "비공개값",
            "displayed_price_krw": 3,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
        {
            "id": "SKU-004",
            "name": "테스트감기시럽",
            "capacity": "200ml",
            "category": "호흡기",
            "price": "비공개값",
            "displayed_price_krw": 4,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
        {
            "id": "SKU-005",
            "name": "테스트 비타민정",
            "capacity": "30정",
            "category": "비타민",
            "price": "비공개값",
            "displayed_price_krw": 5,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
        {
            "id": "SKU-006",
            "name": "상위정",
            "capacity": "60포",
            "category": "소화기",
            "price": "비공개값",
            "displayed_price_krw": 6,
            "verification_status": "Firestore 원본 확인",
            "recorded_at": "2026-07-15",
        },
    ]
    queue = [
        {
            "id": row["id"],
            "duplicate_group_id": "DUP-test" if row["id"] in {"SKU-003", "SKU-004"} else "",
            "duplicate_group_size": 2 if row["id"] in {"SKU-003", "SKU-004"} else 1,
            "official_match_status": "pending",
        }
        for row in catalog
    ]
    products = [
        {
            "product_id": "MFDS-200300406",
            "item_sequence": "200300406",
            "product_name": "닥터베아제정",
            "analysis_status": "included",
        },
        {
            "product_id": "MFDS-202200525",
            "item_sequence": "202200525",
            "product_name": "어린이타이레놀현탁액(아세트아미노펜)",
            "analysis_status": "included",
        },
    ]
    policy = {
        "possible_otc_categories": ["소화기", "호흡기", "키즈"],
        "category_indicates_non_otc": ["비타민"],
        "candidate_form_tokens": ["정", "캡슐", "시럽", "현탁액", "액", "산", "연고", "크림", "겔", "파프"],
        "official_form_suffixes": ["연질캡슐", "캡슐", "현탁액", "시럽", "정", "액", "산"],
        "non_drug_name_tokens": ["비타민", "유산균"],
        "form_capacity_patterns": {
            "정": ["(?:정|t|tab)$"],
            "캡슐": ["(?:캡슐|c|cap)$"],
            "시럽": ["(?:ml|병|포|p)"],
            "현탁액": ["(?:ml|병|포|p)"],
            "액": ["(?:ml|병|포|p)"],
            "산": ["(?:g|그램|포|p)"],
            "연고": ["(?:g|그램|ml)"],
            "크림": ["(?:g|그램|ml)"],
            "겔": ["(?:g|그램|ml)"],
            "파프": ["(?:매|ea|팩|p)"],
        },
        "fuzzy_match_threshold": 0.9,
        "fuzzy_match_margin": 0.05,
        "minimum_fuzzy_name_length": 6,
    }
    catalog_path = tmp_path / "products.json"
    queue_path = tmp_path / "enrichment-queue.json"
    product_master_path = tmp_path / "product_master.csv"
    policy_path = tmp_path / "policy.json"
    official_summary_path = tmp_path / "official-data-summary.json"
    write_json(catalog_path, catalog)
    write_json(queue_path, queue)
    with product_master_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(products[0]))
        writer.writeheader()
        writer.writerows(products)
    write_json(policy_path, policy)
    write_json(
        official_summary_path,
        {
            "status": "blocked_missing_key",
            "product_count": 6,
            "official_product_count": 0,
            "processed_count": 0,
        },
    )
    return catalog_path, queue_path, product_master_path, policy_path, official_summary_path


def test_bridge_matches_existing_products_without_promoting_them(tmp_path: Path) -> None:
    result = build_bridge(*fixture_paths(tmp_path))
    assert result["summary"]["source_product_count"] == 6
    assert result["summary"]["exact_intersection_sku_count"] == 1
    assert result["summary"]["exact_intersection_existing_product_count"] == 1
    assert result["summary"]["fuzzy_review_sku_count"] == 1
    assert {row["match_method"] for row in result["intersections"]} == {"exact_normalized_alias"}
    assert {row["match_method"] for row in result["fuzzy_reviews"]} == {"fuzzy_normalized_alias"}
    review_rows = result["intersections"] + result["fuzzy_reviews"]
    assert all(row["promotion_allowed"] == "false" for row in review_rows)
    assert all(row["review_status"] == "requires_official_match_review" for row in review_rows)


def test_bridge_recomputes_duplicates_and_builds_screening_only_candidates(tmp_path: Path) -> None:
    result = build_bridge(*fixture_paths(tmp_path))
    assert result["summary"]["duplicate_group_count"] == 1
    assert result["summary"]["products_in_duplicate_groups"] == 2
    assert result["audit"]["source_duplicate_metadata_matches"] is True
    assert {row["catalog_source_id"] for row in result["candidates"]} == {"SKU-003", "SKU-004"}
    assert all(row["screening_status"] == "candidate_requires_official_domain_and_item_match" for row in result["candidates"])
    assert all(row["promotion_allowed"] == "false" for row in result["candidates"])


def test_bridge_outputs_no_price_or_private_source_copy(tmp_path: Path) -> None:
    paths = fixture_paths(tmp_path)
    result = build_bridge(*paths)
    output = tmp_path / "output"
    audit = tmp_path / "audit"
    product_master = paths[2]
    product_master_before = product_master.read_bytes()
    write_bridge(result, output, audit)

    for path in output.iterdir():
        text = path.read_text(encoding="utf-8-sig")
        assert "비공개값" not in text
        if path.suffix == ".csv":
            header = text.splitlines()[0].lower()
            assert "price" not in header
    assert result["summary"]["price_fields_exported"] is False
    assert result["summary"]["full_source_records_exported"] is False
    assert result["summary"]["official_enrichment_status"] == "blocked_missing_key"
    assert product_master.read_bytes() == product_master_before


def test_bridge_rejects_catalog_schema_or_duplicate_drift(tmp_path: Path) -> None:
    catalog_path, queue_path, product_master_path, policy_path, official_summary_path = fixture_paths(tmp_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    del catalog[0]["verification_status"]
    write_json(catalog_path, catalog)
    try:
        build_bridge(catalog_path, queue_path, product_master_path, policy_path, official_summary_path)
    except ValueError as exc:
        assert str(exc) == "catalog_schema_invalid:SKU-001:verification_status"
    else:
        raise AssertionError("missing schema field must fail")

    catalog_path, queue_path, product_master_path, policy_path, official_summary_path = fixture_paths(tmp_path)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue[2]["duplicate_group_size"] = 1
    write_json(queue_path, queue)
    try:
        build_bridge(catalog_path, queue_path, product_master_path, policy_path, official_summary_path)
    except ValueError as exc:
        assert str(exc) == "catalog_duplicate_metadata_mismatch"
    else:
        raise AssertionError("duplicate metadata drift must fail")


def test_bridge_verifies_json_and_csv_are_the_same_catalog(tmp_path: Path) -> None:
    paths = fixture_paths(tmp_path)
    catalog = json.loads(paths[0].read_text(encoding="utf-8"))
    catalog_csv = tmp_path / "catalog.csv"
    fields = ["id", "name", "capacity", "category"]
    with catalog_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row[field] for field in fields} for row in catalog])
    result = build_bridge(*paths, catalog_csv_path=catalog_csv)
    assert result["audit"]["catalog_csv_equivalent_to_json"] is True

    rows = list(csv.DictReader(catalog_csv.open(encoding="utf-8-sig", newline="")))
    rows[0]["name"] = "다른 이름"
    with catalog_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    try:
        build_bridge(*paths, catalog_csv_path=catalog_csv)
    except ValueError as exc:
        assert str(exc) == "catalog_json_csv_mismatch"
    else:
        raise AssertionError("JSON/CSV mismatch must fail")
