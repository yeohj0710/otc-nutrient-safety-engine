from scripts.research.otc.build_runtime import build


def test_runtime_uses_only_active_calculation_ready_products():
    runtime = build()
    assert runtime["releaseReady"] is False
    assert runtime["rulesReleased"] == 15
    assert len(runtime["releasedRuleTypes"]) == 15
    assert len(runtime["products"]) == 13
    assert all(product["authorizationStatus"] == "active" for product in runtime["products"])
    assert all(product["ingredients"] for product in runtime["products"])
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


def test_runtime_preserves_withdrawn_and_ambiguous_statuses():
    runtime = build()
    statuses = {row["candidateId"]: row["status"] for row in runtime["officialCandidates"]}
    assert statuses == {
        "SAFE-OTC-02": "withdrawn",
        "SAFE-OTC-03": "withdrawn",
        "SAFE-OTC-13": "package_variant_unresolved",
    }


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
