from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "extract_quantitative_effects.py"
SPEC = importlib.util.spec_from_file_location("extract_quantitative_effects", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base_row(quote: str) -> dict[str, str]:
    return {
        "evidence_id": "EV-1", "record_id": "REC-1", "ingredient_id": "K1",
        "source_id": "PMC1", "locator": "Results, p1", "verbatim_quote": quote,
    }


def test_extracts_ratio_ci_percentage_and_fraction_without_interpretation() -> None:
    rows = MODULE.extract_row(base_row("RR 0.56; 95% CI 0.37–0.84; events 2/117 (1.7%)."))
    assert [row["statistic_type"] for row in rows] == [
        "relative_effect_measure", "reported_percentage", "reported_fraction"
    ]
    assert rows[0]["measure_label"] == "RR"
    assert rows[0]["estimate"] == "0.56"
    assert rows[0]["ci_lower"] == "0.37"
    assert rows[0]["ci_upper"] == "0.84"
    assert rows[1]["estimate"] == "1.7"
    assert rows[2]["numerator"] == "2"
    assert rows[2]["denominator"] == "117"
    assert all(row["synthesis_eligible"] == "false" for row in rows)


def test_extracts_percentage_range_as_range_not_point_estimate() -> None:
    rows = MODULE.extract_row(base_row("Idiopathic hypercalciuria occurs in 5–8%."))
    assert len(rows) == 1
    assert rows[0]["estimate"] == ""
    assert rows[0]["range_lower"] == "5"
    assert rows[0]["range_upper"] == "8"
