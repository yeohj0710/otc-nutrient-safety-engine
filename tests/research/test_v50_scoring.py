from __future__ import annotations

import hashlib
import io
from collections import Counter

from tools.v50_scoring.sample_and_build_cards import (
    CARD_FIELDS,
    EXPECTED_ADJUDICATION_STATUS,
    EXPECTED_FINAL_DISTRIBUTION,
    EXPECTED_POPULATION,
    EXPECTED_SAMPLE,
    SEED,
    build_cards,
    build_sample,
    leak_check,
    load_final_population,
    load_invariant_failure_keys,
    rank_key,
)
from tools.v50_scoring.scoring_harness import configure_output_utf8, validate_judgments
from tools.v50_scoring.compare_and_report import (
    bootstrap_intervals,
    metric_values,
    weighted_kappa,
    wilson_95,
)


def test_rank_is_sha256_of_frozen_seed_question_and_record() -> None:
    expected = hashlib.sha256(f"{SEED}|Q01|PMID-1".encode("utf-8")).hexdigest()
    assert rank_key("Q01", "PMID-1") == expected


def test_population_reconstruction_matches_frozen_v50_margins() -> None:
    population = load_final_population()

    assert len(population) == EXPECTED_POPULATION == 43_207
    assert len({row["key"] for row in population}) == EXPECTED_POPULATION
    assert (
        Counter(row["final_label"] for row in population) == EXPECTED_FINAL_DISTRIBUTION
    )
    assert (
        Counter(row["adjudication_status"] for row in population)
        == EXPECTED_ADJUDICATION_STATUS
    )

    unadjudicated_retain = [
        row
        for row in population
        if row["final_label"] == "retain" and row["adjudication_status"] == "classifier"
    ]
    assert len(unadjudicated_retain) == 6_682
    assert {row["question_id"] for row in unadjudicated_retain} == {
        "OTC-LIT-Q01-ACETAMINOPHEN",
        "OTC-LIT-Q02-NSAID",
        "OTC-LIT-Q03-COLD-ALLERGY",
        "OTC-LIT-Q04-DIGESTIVE",
        "OTC-LIT-Q05-TOPICAL",
    }


def test_sample_is_exhaustive_stratified_design_with_fixed_census_rows() -> None:
    population = load_final_population()
    failures = load_invariant_failure_keys()
    selected, design = build_sample(population, failures)

    assert len(failures) == 15
    assert design["population_total"] == EXPECTED_POPULATION
    assert (
        sum(spec["population_N"] for spec in design["strata"].values())
        == EXPECTED_POPULATION
    )
    assert design["sample_total"] == len(selected) == EXPECTED_SAMPLE == 894
    assert design["partition_is_exhaustive"] is True
    assert design["partition_is_mutually_exclusive"] is True
    assert len({row["key"] for row in selected}) == len(selected)

    chosen = {row["key"]: row for row in selected}
    assert failures <= set(chosen)
    for key in failures:
        spec = design["strata"][chosen[key]["sampling_stratum_id"]]
        assert spec["census"] is True
        assert spec["weight"] == 1.0
        assert chosen[key]["invariant_failure"] is True

    for spec in design["strata"].values():
        if spec["census"]:
            assert spec["weight"] == 1.0
            assert spec["sample_n"] == spec["population_N"]
        else:
            assert spec["weight"] == spec["population_N"] / spec["sample_n"]


def test_generated_cards_have_only_blinded_fields() -> None:
    population = load_final_population()
    failures = load_invariant_failure_keys()
    selected, _ = build_sample(population, failures)
    cards, stats = build_cards(selected)
    check = leak_check(cards)

    assert stats["cards"] == EXPECTED_SAMPLE
    assert check["passed"] is True
    assert all(tuple(card) == CARD_FIELDS for card in cards)


def test_harness_forces_title_only_low_confidence_and_reason_code() -> None:
    cards = [
        {
            "record_id": "PMID-1",
            "question_id": "Q01",
            "title": "Example",
            "abstract": "",
            "publication_types": "Journal Article",
            "mesh_terms": "Humans",
        }
    ]
    invalid = [
        {
            "record_id": "PMID-1",
            "question_id": "Q01",
            "decision": "uncertain",
            "reason_codes": ["exposure"],
            "confidence": "medium",
            "evidence_basis": "title_only",
        }
    ]
    problems = validate_judgments(cards, invalid, require_complete=True)
    assert any("confidence=low" in problem for problem in problems)
    assert any("insufficient_abstract" in problem for problem in problems)


def test_harness_accepts_complete_six_field_contract() -> None:
    cards = [
        {
            "record_id": "PMID-1",
            "question_id": "Q01",
            "title": "Example",
            "abstract": "",
            "publication_types": "Journal Article",
            "mesh_terms": "",
        }
    ]
    valid = [
        {
            "record_id": "PMID-1",
            "question_id": "Q01",
            "decision": "uncertain",
            "reason_codes": ["insufficient_abstract"],
            "confidence": "low",
            "evidence_basis": "title_only",
        }
    ]
    assert validate_judgments(cards, valid, require_complete=True) == []


def test_harness_reconfigures_windows_console_to_utf8() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp949")
    configure_output_utf8(stream)
    stream.write("—")
    stream.flush()
    assert raw.getvalue().decode("utf-8") == "—"


def test_compare_metrics_use_retain_as_the_positive_label() -> None:
    rows = [
        {
            "ai_reference_decision": "retain",
            "scoring_decision": "retain",
            "weight": 2.0,
        },
        {
            "ai_reference_decision": "retain",
            "scoring_decision": "deprioritize",
            "weight": 1.0,
        },
        {
            "ai_reference_decision": "uncertain",
            "scoring_decision": "retain",
            "weight": 1.0,
        },
        {
            "ai_reference_decision": "deprioritize",
            "scoring_decision": "deprioritize",
            "weight": 4.0,
        },
    ]
    metrics = metric_values(rows)

    assert metrics["sensitivity_vs_ai_reference"] == 2 / 3
    assert metrics["specificity_vs_ai_reference"] == 4 / 5
    assert metrics["precision_vs_ai_reference"] == 2 / 3
    assert metrics["agreement_vs_ai_reference"] == 6 / 8
    assert weighted_kappa(rows) is not None


def test_bootstrap_holds_a_census_stratum_fixed() -> None:
    rows = [
        {
            "ai_reference_decision": "retain",
            "scoring_decision": "retain",
            "weight": 1.0,
            "sampling_stratum_id": "census",
            "census": True,
        },
        {
            "ai_reference_decision": "deprioritize",
            "scoring_decision": "deprioritize",
            "weight": 1.0,
            "sampling_stratum_id": "census",
            "census": True,
        },
    ]
    intervals, design = bootstrap_intervals(rows, draws=25, seed_suffix="test")

    assert design["census_strata_fixed"] is True
    assert design["probability_strata_resampled"] == 0
    assert design["interval_collapsed_to_point"] is True
    assert intervals["agreement_vs_ai_reference"] == [1.0, 1.0]


def test_wilson_interval_contains_observed_proportion() -> None:
    interval = wilson_95(8, 10)
    assert interval is not None
    assert interval[0] < 0.8 < interval[1]
