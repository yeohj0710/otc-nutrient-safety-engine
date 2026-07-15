import json

from scripts.research.otc.audit_runtime_alignment import audit, write


def test_runtime_matches_the_analysis_dataset_and_sources() -> None:
    result = audit()
    assert result["valid"] is True
    assert result["counts"] == {
        "analysis_products": 13,
        "runtime_products": 13,
        "analysis_product_ingredient_variant_rows": 57,
        "selected_product_ingredient_bindings": 47,
        "runtime_product_ingredient_bindings": 47,
        "analysis_unique_ingredients": 28,
        "runtime_unique_ingredients": 28,
        "verified_administration_constraints": 32,
        "runtime_administration_constraints": 32,
    }
    assert result["declared_unit_conversions"] == [
        {
            "item_sequence": "198601920",
            "product_name": "어린이부루펜시럽",
            "source": "2 g/100 mL",
            "runtime": "20 mg/mL",
        },
        {
            "item_sequence": "202200525",
            "product_name": "어린이타이레놀현탁액",
            "source": "3.2 g/100 mL",
            "runtime": "32 mg/mL",
        },
    ]
    assert result["excluded_product_leaks"] == []
    assert result["errors"] == []


def test_written_alignment_audit_matches_current_data() -> None:
    result = audit()
    target = write(result)
    assert json.loads(target.read_text(encoding="utf-8")) == result
