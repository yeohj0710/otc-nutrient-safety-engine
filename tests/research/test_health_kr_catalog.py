import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.research.otc.health_kr_catalog import (
    SafetyProfile,
    classify_product,
    dur_minimum_age_years,
    ingredient_form_group_id,
    research_use_status,
    search_research_candidates,
    validate_records,
)
from scripts.research.otc.import_health_kr_catalog import (
    build_import,
    read_csv_bytes,
    write_import,
)


def fixture_row(
    *,
    source_id: str = "retail-1",
    official_match_status: str = "confirmed",
    official_product_key: str = "H001",
    official_item_seq: str = "H001",
    official_dosage_form: str = "정제",
    official_category: str = "해열, 진통, 소염제",
    ingredient_codes: list[str] | None = None,
    price: str = "5000",
    **overrides,
) -> dict:
    ingredient_codes = ingredient_codes or ["I001"]
    row = {
        "id": source_id,
        "document_id": f"doc-{source_id}",
        "name": f"판매상품 {source_id}",
        "normalized_name": f"판매상품{source_id}",
        "capacity": "10정",
        "category": "일반의약품",
        "price": price,
        "displayed_price_krw": int(price),
        "verification_status": "Firestore 원본 확인",
        "official_match_status": official_match_status,
        "official_product_key": official_product_key,
        "official_item_seq": official_item_seq,
        "official_item_name": f"공식제품 {official_item_seq}",
        "official_manufacturer": "테스트제약",
        "official_source_type": "약학정보원 의약품 상세정보",
        "official_source_url": f"https://www.health.kr/searchDrug/result_drug.asp?drug_cd={official_item_seq}",
        "official_domain": "health.kr",
        "official_content_status": "complete",
        "official_category": official_category,
        "official_dosage_form": official_dosage_form,
        "official_route": "경구",
        "official_atc_code": "N02BE01",
        "official_kpic_atc": "해열진통제",
        "official_pack_unit": "10정",
        "official_storage": "기밀용기",
        "official_valid_term": "36개월",
        "official_insurance": "비급여",
        "official_efficacy": "감기로 인한 발열과 통증의 완화",
        "official_dosage": "1회 1정, 1일 3회 복용",
        "official_precautions": "위궤양 환자와 와파린 복용자는 복용 전 상담",
        "official_professional_precautions": "전문가 주의사항",
        "official_active_ingredients": ["Acetaminophen 아세트아미노펜 500mg /"],
        "official_ingredients": ["Acetaminophen 아세트아미노펜 500mg /"],
        "official_interactions": [{"cells": ["와파린", "병용 주의"], "table_index": 1}],
        "official_same_ingredient_products": [],
        "official_dur_contraindications": "위궤양 환자 금기",
        "official_dur_age": "12세 미만 주의",
        "official_dur_pregnancy": "임부 주의",
        "official_dur_senior": "고령자 주의",
        "official_dur_max_dose": "1일 4000mg",
        "official_dur_max_period": "10일",
        "official_dur_split_dosage": "분할 주의",
        "official_medication_guide": "복약지도",
        "official_standard_codes": ["880000000001"],
        "official_barcode": "880000000001",
        "official_section_evidence": {
            "detail_page_verified": True,
            "ajax_payload_verified": True,
            "match_reasons": ["exact_name"],
            "conflicts": [],
            "source_urls": [f"https://www.health.kr/searchDrug/result_drug.asp?drug_cd={official_item_seq}"],
            "verified_fields": [
                "ingredients",
                "efficacy",
                "dosage",
                "precautions",
                "storage",
                "manufacturer",
                "dosage_form",
                "route",
                "package",
            ],
        },
        "official_additional_data": {
            "health_kr_raw": {
                "drug_cls": "2",
                "drug_code": official_item_seq,
                "ingredient_details": [
                    {
                        "label": f"Ingredient {code} 100mg /",
                        "ingredient_code": code,
                        "source_url": f"https://health.kr/searchIngredient/detail.asp?ingd_code={code}",
                    }
                    for code in ingredient_codes
                ],
            }
        },
    }
    row.update(overrides)
    return row


def write_source_trio(tmp_path: Path, rows: list[dict]) -> tuple[Path, Path, Path]:
    queue = tmp_path / "enrichment-queue.json"
    public = tmp_path / "public-enrichment-queue.json"
    csv_path = tmp_path / "enrichment-queue.csv"
    payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    queue.write_bytes(payload)
    public.write_bytes(payload)
    scalar_fields = [
        "id",
        "document_id",
        "name",
        "official_match_status",
        "official_product_key",
        "official_item_seq",
        "official_source_url",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=scalar_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in scalar_fields})
    return queue, csv_path, public


def test_confirmed_requires_stable_official_identity() -> None:
    row = fixture_row(official_product_key="")
    with pytest.raises(ValueError, match="confirmed_missing_stable_identity"):
        validate_records([row])


def test_confirmed_requires_url_drug_code() -> None:
    row = fixture_row()
    row["official_source_url"] = "https://www.health.kr/searchDrug/result_drug.asp"
    with pytest.raises(ValueError, match="confirmed_source_identifier_missing"):
        validate_records([row])


@pytest.mark.parametrize("mismatch", ["product_key", "url", "raw_drug_code"])
def test_confirmed_identifiers_must_agree(mismatch: str) -> None:
    row = fixture_row()
    if mismatch == "product_key":
        row["official_product_key"] = "DIFFERENT"
    elif mismatch == "url":
        row["official_source_url"] = (
            "https://www.health.kr/searchDrug/result_drug.asp?drug_cd=DIFFERENT"
        )
    else:
        row["official_additional_data"]["health_kr_raw"]["drug_code"] = "DIFFERENT"
    with pytest.raises(ValueError, match="confirmed_source_identifier_mismatch"):
        validate_records([row])


def test_unconfirmed_rows_never_become_research_candidates() -> None:
    for status in ("review_required", "not_found", "not_applicable"):
        row = fixture_row(official_match_status=status)
        assert research_use_status(row) == "excluded_unconfirmed"


def test_group_uses_ingredient_codes_and_dosage_form() -> None:
    first = fixture_row(ingredient_codes=["I001", "I002"], official_dosage_form="정제")
    second = fixture_row(ingredient_codes=["I002", "I001"], official_dosage_form="정제")
    third = fixture_row(ingredient_codes=["I001", "I002"], official_dosage_form="시럽")
    assert ingredient_form_group_id(first) == ingredient_form_group_id(second)
    assert ingredient_form_group_id(first) != ingredient_form_group_id(third)


def test_classification_uses_official_fields() -> None:
    row = fixture_row(official_category="해열, 진통, 소염제")
    assert classify_product(row) == "analgesic_antiinflammatory"


def test_red_flag_returns_no_candidates_and_referral() -> None:
    result = search_research_candidates(
        [fixture_row()],
        "해열",
        SafetyProfile(red_flags=("의식 저하",)),
    )
    assert result["candidates"] == []
    assert result["disposition"] == "refer_to_pharmacist_or_clinician"
    assert result["decisionMode"] == "deterministic"


def test_pregnancy_age_contraindication_and_interaction_exclude_candidates() -> None:
    row = fixture_row()
    profiles = [
        SafetyProfile(pregnant=True),
        SafetyProfile(age_years=10),
        SafetyProfile(conditions=("위궤양",)),
        SafetyProfile(medications=("와파린",)),
    ]
    for profile in profiles:
        result = search_research_candidates([row], "해열", profile)
        assert result["candidates"] == []
        assert result["excludedCount"] == 1


def test_age_dur_uses_the_recorded_boundary() -> None:
    row = fixture_row(official_dur_age="12세 미만")
    assert dur_minimum_age_years(row["official_dur_age"]) == 12
    assert dur_minimum_age_years("6개월 미만") == 0.5
    assert search_research_candidates(
        [row], "해열", SafetyProfile(age_years=11.9)
    )["candidates"] == []
    assert len(
        search_research_candidates([row], "해열", SafetyProfile(age_years=12))["candidates"]
    ) == 1
    assert len(
        search_research_candidates([row], "해열", SafetyProfile(age_years=18))["candidates"]
    ) == 1


def test_price_never_changes_clinical_ranking() -> None:
    first = fixture_row(source_id="a", official_product_key="H001", official_item_seq="H001", price="9000")
    second = fixture_row(source_id="b", official_product_key="H002", official_item_seq="H002", price="1000")
    baseline = search_research_candidates([first, second], "해열", SafetyProfile())
    swapped = deepcopy([first, second])
    swapped[0]["price"] = "1"
    swapped[0]["displayed_price_krw"] = 1
    swapped[1]["price"] = "999999"
    swapped[1]["displayed_price_krw"] = 999999
    changed = search_research_candidates(swapped, "해열", SafetyProfile())
    assert [row["stableOfficialKey"] for row in baseline["candidates"]] == [
        row["stableOfficialKey"] for row in changed["candidates"]
    ]


def test_same_name_does_not_merge_different_stable_official_products() -> None:
    first = fixture_row(source_id="a", official_product_key="H001", official_item_seq="H001")
    second = fixture_row(source_id="b", official_product_key="H002", official_item_seq="H002")
    second["official_item_name"] = first["official_item_name"]
    result = search_research_candidates([first, second], first["official_item_name"], SafetyProfile())
    assert {row["stableOfficialKey"] for row in result["candidates"]} == {
        "health.kr:H001",
        "health.kr:H002",
    }


def test_import_separates_statuses_and_omits_private_source_fields(tmp_path: Path) -> None:
    rows = [
        fixture_row(source_id="confirmed", official_product_key="H001", official_item_seq="H001"),
        fixture_row(source_id="review", official_match_status="review_required"),
        fixture_row(source_id="missing", official_match_status="not_found"),
        fixture_row(source_id="non-drug", official_match_status="not_applicable"),
    ]
    queue, csv_path, public = write_source_trio(tmp_path, rows)
    result = build_import(queue, csv_path, public)
    assert result["summary"]["source_record_count"] == 4
    assert result["summary"]["status_counts"] == {
        "confirmed": 1,
        "not_applicable": 1,
        "not_found": 1,
        "review_required": 1,
    }
    assert result["summary"]["research_search_usable_count"] == 1
    assert result["summary"]["runtime_promotion_allowed_count"] == 0
    assert result["audit"]["existing_research_invariants"]["valid"] is True
    assert len(result["candidates"]) == 1
    forbidden = {
        "price",
        "displayed_price_krw",
        "official_efficacy",
        "official_dosage",
        "official_precautions",
        "official_additional_data",
    }
    assert forbidden.isdisjoint(result["candidates"][0])

    selection = tmp_path / "selection"
    audit = tmp_path / "audit"
    write_import(result, selection, audit)
    header = (selection / "catalog_health_kr_research_candidates.csv").read_text(
        encoding="utf-8-sig"
    ).splitlines()[0]
    assert all(field not in header.split(",") for field in forbidden)


def test_import_rejects_out_of_sync_public_copy(tmp_path: Path) -> None:
    rows = [fixture_row()]
    queue, csv_path, public = write_source_trio(tmp_path, rows)
    public.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="public_sync_mismatch"):
        build_import(queue, csv_path, public)


def test_csv_reader_accepts_large_health_kr_source_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "large.csv"
    payload = f"id,official_precautions\nretail-1,{'가' * 150_000}\n".encode("utf-8")
    rows = read_csv_bytes(payload, csv_path)
    assert len(rows) == 1
    assert len(rows[0]["official_precautions"]) == 150_000


def test_import_hashes_the_same_source_bytes_it_parses(tmp_path: Path, monkeypatch) -> None:
    queue, csv_path, public = write_source_trio(tmp_path, [fixture_row()])
    source_paths = {queue, csv_path, public}
    read_counts = {path: 0 for path in source_paths}
    original_read_bytes = Path.read_bytes

    def counted_read_bytes(path: Path) -> bytes:
        if path in read_counts:
            read_counts[path] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    result = build_import(queue, csv_path, public)
    assert all(count == 1 for count in read_counts.values())
    assert result["summary"]["provenance"]["queue_sha256"] == hashlib.sha256(
        original_read_bytes(queue)
    ).hexdigest()


def test_conflicts_are_written_to_a_minimal_review_queue(tmp_path: Path) -> None:
    row = fixture_row()
    row["official_section_evidence"]["conflicts"] = ["제형 불일치"]
    queue, csv_path, public = write_source_trio(tmp_path, [row])
    result = build_import(queue, csv_path, public)
    selection = tmp_path / "selection"
    audit = tmp_path / "audit"
    write_import(result, selection, audit)
    conflicts = list(
        csv.DictReader(
            (selection / "catalog_health_kr_conflict_review.csv").open(
                encoding="utf-8-sig", newline=""
            )
        )
    )
    assert conflicts == [
        {
            "catalog_source_id": "retail-1",
            "stable_official_key": "health.kr:H001",
            "official_item_seq": "H001",
            "official_source_url": "https://www.health.kr/searchDrug/result_drug.asp?drug_cd=H001",
            "conflict_count": "1",
            "conflict_reasons": "제형 불일치",
        }
    ]
