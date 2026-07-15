from scripts.research.otc.build_review_wizard import build_html, build_payload


def test_review_wizard_embeds_official_evidence_without_prefilled_human_decisions():
    payload = build_payload()
    page = build_html(payload)
    assert len(payload["sections"]["official_evidence_candidates"]) > 0
    assert payload["human_decisions"] == {}
    assert "공식 근거 후보" in page
    assert "Codex 후보 · 전문가 미확인" in page
    assert "supports_release" in page


def test_review_wizard_limits_exported_decisions_to_selected_reviewer_role():
    page = build_html(build_payload())
    assert 'data-allowed-role="pharmacist_expert"' in page
    assert 'data-allowed-role="independent_scenario_reviewer"' in page
    assert 'data-allowed-role="normalization_reviewer"' in page
    assert 'data-allowed-role="research_advisor"' in page
    assert 'section[data-allowed-role="${reviewerRole}"] .review-card' in page
    assert "section.classList.toggle('role-hidden'" in page
    assert 'otc_review_${data.reviewer.reviewer_role}_${safeId}.json' in page
    assert 'id="reviewerId" value=""' in page
    assert '<option value="" selected>선택</option>' in page


def test_role_specific_review_wizards_prefill_only_the_role():
    payload = build_payload()
    pharmacist = build_html(payload, "pharmacist_expert", "EXT-PHARM-001")
    independent = build_html(payload, "independent_scenario_reviewer", "EXT-INDEP-001")
    assert '<option value="pharmacist_expert" selected>약사·약학 전문가</option>' in pharmacist
    assert '<option value="independent_scenario_reviewer" selected>독립 시나리오 검토자</option>' in independent
    assert 'id="reviewerId" value="EXT-PHARM-001" autocomplete="off" readonly' in pharmacist
    assert 'id="reviewerId" value="EXT-INDEP-001" autocomplete="off" readonly' in independent
    assert 'id="reviewerRole" disabled' in pharmacist
    assert 'id="reviewerRole" disabled' in independent


def test_assisted_independent_review_prechecks_codex_recommendations_and_discloses_method():
    page = build_html(
        build_payload(),
        "independent_scenario_reviewer",
        "EXT-INDEP-001",
        prefill_independent=True,
    )
    assert page.count(' checked>') == 13
    assert page.count('data-recommended-value="1"') == 11
    assert page.count('data-recommended-value="0"') == 2
    assert '"review_method": "codex_prefilled_external_human_confirmation"' in page
    assert '"predictions_exposed": 13' in page
    assert '"independent_blinding": false' in page


def test_independent_review_embeds_case_inputs_without_answer_leakage():
    payload = build_payload()
    cases = {row["scenario_id"]: row["case_payload"] for row in payload["sections"]["independent_scenarios"]}
    assert cases["IND-OTC-011"]["productInputs"][0]["hoursSincePreviousDose"] == 2
    assert cases["IND-OTC-013"]["productInputs"][0]["productNameQuery"] == "지원 목록에 없는 임의 일반의약품"
    assert all("referenceLabel" not in case and "prediction" not in case for case in cases.values())
    page = build_html(payload, "independent_scenario_reviewer")
    assert "이전 복용 후 2시간" in page
    assert "지원 목록에 없는 임의 일반의약품" in page
