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


def test_pdf_line_wrapped_primary_evidence_is_reconstructed():
    by_id = {row["evidence_candidate_id"]: row for row in build()}
    expected_endings = {
        "SAFE-OTC-01-NB-P1-B12-duplicate_ingredient": "함께 복용하여서는 안 된다.",
        "SAFE-OTC-01-NB-P1-B3-alcohol": "간손상이 유발될 수 있다.",
        "SAFE-OTC-05-NB-P1-B17-gi_bleeding_ulcer": "이상반응이 나타날 수 있다.",
        "SAFE-OTC-05-NB-P2-B9-pregnancy_lactation": "조기 폐쇄시킬 수 있다)",
        "SAFE-OTC-05-NB-P4-B10-anticoagulant_antiplatelet": "위험이 높아질 수 있다.)",
        "SAFE-OTC-10-NB-P1-B20-sedative_medication": "멀미약, 알레르기용약)",
        "SAFE-OTC-10-NB-P2-B4-decongestant_hypertension": "고열이 있는 사람",
    }
    for candidate_id, ending in expected_endings.items():
        assert by_id[candidate_id]["evidence_text"].endswith(ending)
    assert by_id["SAFE-OTC-10-NB-P1-B20-sedative_medication"]["evidence_text"].startswith(
        "3. 이 약을 복용하는 동안 다음의 약을 복용하지 말 것."
    )
    assert by_id["SAFE-OTC-10-NB-P2-B4-decongestant_hypertension"]["evidence_text"].startswith(
        "4. 다음과 같은 사람은 이 약을 복용하기 전에"
    )
