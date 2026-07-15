from scripts.research.otc.bind_rule_evidence import bind


def test_all_rule_families_keep_specific_primary_official_evidence_after_review():
    rules, shortlist = bind()
    assert len(rules) == 16
    assert sum(rule["status"] == "released" for rule in rules) == 15
    assert sum(rule["status"] == "draft" for rule in rules) == 1
    assert next(rule for rule in rules if rule["rule_id"] == "OTC-RULE-015")["status"] == "draft"
    assert all(rule["source_id"] == "MFDS-NEDRUG-DETAIL" for rule in rules)
    assert all("PDF p." in rule["source_locator"] and "문단" in rule["source_locator"] for rule in rules)
    assert all(rule["scope"] not in {"selected_products", "product_or_ingredient", "concomitant_medication"} for rule in rules)
    primary = [row for row in shortlist if row["recommendation"] == "recommended_primary"]
    assert len(primary) == 16
    assert all(row["supports_release"] == "false" for row in primary)
    assert all(row["review_status"] == "codex_recommended_not_expert_verified" for row in primary)
