from scripts.research.otc.build_rule_evidence_candidates import build


def test_candidates_are_official_located_and_not_released():
    rows = build()
    assert rows
    assert all(row["source_id"] == "MFDS-NEDRUG-DETAIL" for row in rows)
    assert all("PDF p." in row["source_locator"] and "문단" in row["source_locator"] for row in rows)
    assert all(row["review_status"] == "codex_candidate_not_expert_verified" for row in rows)
    assert all(row["supports_release"] == "false" for row in rows)


def test_core_tylenol_evidence_candidates_exist():
    rows = [row for row in build() if row["item_sequence"] == "202106092"]
    assert {row["rule_type"] for row in rows} >= {
        "duplicate_ingredient", "max_daily_dose", "minimum_interval", "age_restriction",
        "pregnancy_lactation", "hepatic_disease", "renal_disease", "gi_bleeding_ulcer", "alcohol",
        "anticoagulant_antiplatelet", "sedative_medication", "urgent_referral",
    }
