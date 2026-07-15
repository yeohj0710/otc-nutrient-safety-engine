from scripts.research.otc.build_nedrug_masters import basis_variant, build, canonical_raw_name


def test_source_qualifier_is_not_a_distinct_ingredient():
    assert canonical_raw_name("아세트아미노펜(미분화)") == "아세트아미노펜"


def test_variant_parser_preserves_package_ambiguity():
    assert basis_variant(" - (7) 1매 (원지름 25mm) 중") == "규격-7"
    assert basis_variant("1매 중 - 내수용") == "내수용"


def test_real_master_excludes_withdrawn_and_blocks_ambiguous_package():
    products, ingredients, joins, exclusions = build()
    assert len(products) == 16
    assert sum(row["record_status"] == "verified_from_source" for row in products) == 14
    assert sum(row["analysis_status"] == "included" for row in products) == 13
    assert not any(row["product_id"] in {"MFDS-199402278", "MFDS-199303109"} for row in joins)
    arex = next(row for row in products if row["candidate_id"] == "SAFE-OTC-13")
    assert arex["calculation_ready"] == "false"
    assert arex["calculation_blocker"] == "package-size variant unresolved"
    assert arex["analysis_status"] == "excluded"
    assert arex["analysis_exclusion_reason"] == "ambiguous_authorized_package_size"
    assert exclusions == [
        {
            "candidate_id": "SAFE-OTC-13",
            "product_id": "MFDS-200501321",
            "item_sequence": "200501321",
            "product_name": "신신파스아렉스",
            "exclusion_stage": "analysis_and_runtime",
            "exclusion_reason": "ambiguous_authorized_package_size",
            "source_id": "MFDS-NEDRUG-DETAIL",
            "source_locator": arex["source_locator"],
            "source_sha256": arex["source_sha256"],
            "source_records_preserved": "true",
        }
    ]
    assert any(row["ingredient_id"] == "ING-acetaminophen" for row in ingredients)
    assert {"ING-dexibuprofen", "ING-naproxen", "ING-cetirizine_hydrochloride"} <= {row["ingredient_id"] for row in ingredients}
