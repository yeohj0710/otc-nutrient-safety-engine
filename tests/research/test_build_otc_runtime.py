import json

from scripts.research.otc.build_runtime import build


def test_runtime_uses_only_active_calculation_ready_products():
    runtime = build()
    assert runtime["releaseReady"] is False
    assert runtime["rulesReleased"] == 15
    assert len(runtime["releasedRuleTypes"]) == 15
    assert len(runtime["ruleEvidenceByType"]) == 15
    assert runtime["ruleEvidenceByType"]["duplicate_ingredient"] == [
        {
            "ruleId": "OTC-RULE-001",
            "productName": "타이레놀정500밀리그람(아세트아미노펜)",
            "itemSequence": "202106092",
            "sourceId": "MFDS-NEDRUG-DETAIL",
            "locator": "사용상의주의사항 PDF p.1, 문단 12",
            "url": "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/NB",
            "excerptKo": "아세트아미노펜을 포함하는 다른 제품과 함께 복용하여서는 안 된다.",
        }
    ]
    for evidence_rows in runtime["ruleEvidenceByType"].values():
        assert len(evidence_rows) == 1
        rule_evidence = evidence_rows[0]
        assert rule_evidence["ruleId"].startswith("OTC-RULE-")
        assert rule_evidence["productName"]
        assert rule_evidence["itemSequence"].isdigit()
        assert rule_evidence["excerptKo"].strip()
        assert not rule_evidence["excerptKo"].rstrip().endswith(
            ("이 약을", "반드시 의", "중증의 위", "비염(코")
        )
    assert len(runtime["products"]) == 13
    assert all(product["authorizationStatus"] == "active" for product in runtime["products"])
    assert all(product["ingredients"] for product in runtime["products"])
    assert {product["therapeuticClass"] for product in runtime["products"]} == {
        "해열진통제",
        "종합감기약",
        "위장관 일반의약품",
        "외용 소염진통제",
        "항히스타민제",
    }
    assert not {"MFDS-199402278", "MFDS-199303109", "MFDS-200501321"} & {
        product["productId"] for product in runtime["products"]
    }
    for product in runtime["products"]:
        constraints = product["administrationConstraints"]
        daily_frequency = [
            row for row in constraints if row["type"] == "maximum_doses_per_day"
        ]
        assert len(daily_frequency) == 1, product["productName"]
        assert daily_frequency[0]["value"] > 0
        assert daily_frequency[0]["evidence"]["sourceId"] == "MFDS-NEDRUG-DETAIL"
        assert daily_frequency[0]["evidence"]["locator"]
        assert "max_daily_dose" in product["supportedRuleTypes"]


def test_runtime_exposes_catalog_counts_without_private_records_or_prices():
    runtime = build()
    assert runtime["catalogCoverage"] == {
        "sourceSkuCount": 776,
        "healthKrConfirmedCount": 458,
        "healthKrConfirmedUniqueProductCount": 413,
        "runtimePromotionAllowedCount": 0,
        "classificationCounts": {
            "analgesic_antiinflammatory": 57,
            "anthelmintic": 4,
            "antihistamine": 9,
            "cold_respiratory": 18,
            "gastrointestinal": 84,
            "other_otc": 202,
            "topical_or_local": 84,
        },
        "existingProductRematch": {
            "total": 16,
            "success": 4,
            "conflict": 1,
            "unlinked": 11,
        },
    }
    assert len(runtime["catalogExistingMatches"]) == 5
    assert {row["matchStatus"] for row in runtime["catalogExistingMatches"]} == {
        "success",
        "conflict",
    }
    assert all(row["sourceUrl"].startswith("https://") for row in runtime["catalogExistingMatches"])
    assert all(row["mfdsPromotionEvidenceComplete"] is False for row in runtime["catalogExistingMatches"])
    serialized = json.dumps(runtime, ensure_ascii=False).lower()
    assert "retail_price" not in serialized
    assert "price" not in serialized
    assert "catalog_source_id" not in serialized
    assert "document_id" not in serialized
    assert "app_name" not in serialized
    assert "ai_context" not in serialized


def test_runtime_preserves_withdrawn_statuses_but_omits_analysis_exclusions():
    runtime = build()
    statuses = {row["candidateId"]: row["status"] for row in runtime["officialCandidates"]}
    assert statuses == {
        "SAFE-OTC-02": "withdrawn",
        "SAFE-OTC-03": "withdrawn",
    }
    assert "SAFE-OTC-13" not in statuses


def test_runtime_keeps_compound_ingredients_separate():
    runtime = build()
    pancol = next(product for product in runtime["products"] if product["itemSequence"] == "196800036")
    assert len(pancol["ingredients"]) == 6
    assert {row["nameKo"] for row in pancol["ingredients"]} >= {"아세트아미노펜", "클로르페니라민말레산염"}


def test_runtime_converts_100ml_liquid_basis_to_per_ml():
    runtime = build()
    tylenol_liquid = next(product for product in runtime["products"] if product["itemSequence"] == "202200525")
    ibuprofen_liquid = next(product for product in runtime["products"] if product["itemSequence"] == "198601920")
    assert tylenol_liquid["doseUnitLabel"] == "mL"
    assert tylenol_liquid["ingredients"][0]["amountPerUnit"] == 32
    assert tylenol_liquid["ingredients"][0]["unit"] == "mg"
    assert ibuprofen_liquid["ingredients"][0]["amountPerUnit"] == 20
    runtime = build()
    naproxen = next(
        product for product in runtime["products"] if product["itemSequence"] == "197500016"
    )
    by_type = {row["type"]: row for row in naproxen["administrationConstraints"]}
    assert by_type["maximum_doses_per_day"]["value"] == 4
    assert by_type["maximum_daily_ingredient_amount"] == {
        "constraintId": "ADMIN-197500016-MAX-DAILY-ING-naproxen",
        "type": "maximum_daily_ingredient_amount",
        "value": 1250.0,
        "valueUnit": "mg",
        "ingredientId": "ING-naproxen",
        "derivationMethod": "explicit_upper_bound",
        "evidence": {
            "sourceId": "MFDS-NEDRUG-DETAIL",
            "locator": "용법용량 PDF p.1 · 1일 총용량 1,250mg 상한",
            "url": "https://nedrug.mfds.go.kr/dsie/pdf/drb/197500016/UD",
        },
    }
