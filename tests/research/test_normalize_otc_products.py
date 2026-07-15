import csv
import json
from pathlib import Path

from scripts.research.otc.normalize_products import load_aliases, normalize_item, normalize_snapshots, parse_material


ROOT = Path(__file__).resolve().parents[2]
ALIASES = ROOT / "research_v3" / "otc" / "normalization" / "ingredient_aliases.csv"


def compound_item(**overrides):
    item = {
        "ITEM_SEQ": "200000002",
        "ITEM_NAME": "검증용복합정",
        "ENTP_NAME": "검증제약",
        "ETC_OTC_CODE": "일반의약품",
        "CHART": "흰색 정제",
        "ROUTE_NAME": "경구",
        "MATERIAL_NAME": "총량 : 1정(500mg) 중 | 성분명 : 아세트아미노펜 | 분량 : 325 | 단위 : 밀리그램 | 규격 : KP | 성분명 : 클로르페니라민말레산염 | 분량 : 2 | 단위 : 밀리그램 | 규격 : KP",
        "EE_DOC_DATA": "감기의 제증상 완화",
        "UD_DOC_DATA": "허가 용법용량",
        "NB_DOC_DATA": "허가 사용상의 주의사항",
    }
    item.update(overrides)
    return item


def test_parse_material_splits_compound_ingredients_and_units() -> None:
    basis, rows = parse_material(compound_item()["MATERIAL_NAME"])
    assert basis == "1정(500mg) 중"
    assert [(row["ingredient_name_raw"], row["amount_per_unit"], row["amount_unit"]) for row in rows] == [
        ("아세트아미노펜", 325.0, "mg"),
        ("클로르페니라민말레산염", 2.0, "mg"),
    ]


def test_normalize_item_keeps_one_product_and_multiple_ingredient_rows() -> None:
    result = normalize_item(compound_item(), load_aliases(ALIASES), "a" * 64, "2026-07-14")
    assert result["eligible"] is True
    assert result["product"]["classification"] == "일반의약품"
    assert len(result["ingredients"]) == 2
    assert {row["ingredient_id"] for row in result["ingredients"]} == {
        "ING-acetaminophen",
        "ING-chlorpheniramine_maleate",
    }


def test_non_otc_cancelled_and_unknown_ingredients_are_rejected() -> None:
    aliases = load_aliases(ALIASES)
    prescription = normalize_item(compound_item(ETC_OTC_CODE="전문의약품"), aliases, "a" * 64, "2026-07-14")
    cancelled = normalize_item(compound_item(CANCEL_DATE="20260101"), aliases, "a" * 64, "2026-07-14")
    unknown = normalize_item(compound_item(MATERIAL_NAME="총량 : 1정 중 | 성분명 : 미확인성분 | 분량 : 1 | 단위 : 밀리그램"), aliases, "a" * 64, "2026-07-14")
    assert "not_otc" in prescription["rejection_reasons"]
    assert "cancelled_or_withdrawn" in cancelled["rejection_reasons"]
    assert any(reason.startswith("unverified_ingredient:") for reason in unknown["rejection_reasons"])
    assert not prescription["eligible"] and not cancelled["eligible"] and not unknown["eligible"]


def test_normalize_snapshots_writes_traceable_tables_and_rejections(tmp_path: Path) -> None:
    payload = {
        "body": {
            "totalCount": 2,
            "items": [compound_item(), compound_item(ITEM_SEQ="200000003", ITEM_NAME="전문정", ETC_OTC_CODE="전문의약품")],
        }
    }
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "normalized"
    report = normalize_snapshots([snapshot], ALIASES, output, "2026-07-14")
    assert report == {"products": 1, "ingredients": 2, "product_ingredients": 2, "rejected": 1}
    with (output / "product_ingredients.csv").open(encoding="utf-8-sig", newline="") as handle:
        joins = list(csv.DictReader(handle))
    assert len(joins) == 2
    assert all(row["source_locator"].startswith("원료약품 및 분량") for row in joins)
    assert (output / "normalization_report.json").exists()
