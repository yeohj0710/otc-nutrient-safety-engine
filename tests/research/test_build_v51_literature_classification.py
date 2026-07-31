from __future__ import annotations

import csv
import io
import json

from scripts.research.otc.build_v51_literature_classification import (
    OUTPUT_AUDIT,
    OUTPUT_CSV,
    _semantic_json_sha256,
    build_artifacts,
    build_rows,
    write,
)


def test_runtime_observation_hash_ignores_embedded_v51_classification(tmp_path) -> None:
    target = tmp_path / "runtime.json"
    payload = [{"pmid": "1", "ruleLinks": [{"linkId": "L1", "ruleId": "R1"}]}]
    target.write_text(json.dumps(payload), encoding="utf-8")
    legacy_hash = _semantic_json_sha256(target)

    payload[0]["ruleLinks"][0]["v51Classification"] = {
        "classificationId": "C1",
        "uiPolicy": "direct",
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert _semantic_json_sha256(target) == legacy_hash

    payload[0]["ruleLinks"][0]["ruleId"] = "R2"
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert _semantic_json_sha256(target) != legacy_hash


def test_v4_candidates_are_partitioned_and_v50_links_have_1_5_4_classification() -> None:
    rows = build_rows()
    emitted = [row for row in rows if row["lineage_status"] == "v50_emitted"]
    rejected = [row for row in rows if row["v50_rejection_reason"]]

    assert len(rows) == 20
    assert len({row["source_link_id"] for row in rows}) == 20
    assert len(emitted) == 10
    assert len(rejected) == 10
    assert len({row["rule_id"] for row in emitted}) == 9
    assert {
        classification: sum(
            row["semantic_classification"] == classification for row in emitted
        )
        for classification in ("direct_match", "background_context", "mixed_scope")
    } == {"direct_match": 1, "background_context": 5, "mixed_scope": 4}


def test_rejected_legacy_links_are_never_allowed_in_result_ui() -> None:
    rejected = [row for row in build_rows() if row["v50_rejection_reason"]]
    assert {
        row["v50_rejection_reason"] for row in rejected
    } == {"not_in_v5_corpus", "no_retain_decision_for_rule_question"}
    assert all(row["semantic_classification"] == "" for row in rejected)
    assert all(row["ui_policy"] == "exclude_from_result_ui" for row in rejected)
    assert all(row["ui_direct_label_allowed"] == "false" for row in rejected)
    assert all(row["human_expert_reviewed"] == "false" for row in rejected)
    assert all(row["supports_rule_release"] == "false" for row in rejected)


def test_regression_boundaries_for_background_and_mixed_links() -> None:
    rows = {row["v50_link_id"]: row for row in build_rows() if row["v50_link_id"]}

    interval = rows["OTC-LIT-V50-LINK-003"]
    assert interval["semantic_classification"] == "background_context"
    assert "650 mg 서방형" in interval["classification_reason_ko"]
    assert "4시간" in interval["classification_reason_ko"]

    pregnancy = rows["OTC-LIT-V50-LINK-006"]
    assert pregnancy["semantic_classification"] == "mixed_scope"
    assert pregnancy["direct_scope_ingredient_ids"] == "ING-ibuprofen"
    assert (
        pregnancy["direct_scope_profile_conditions"]
        == "pregnant=true;pregnancyTrimester=3"
    )
    assert "수유 단독" in pregnancy["ui_boundary_ko"]

    renal = rows["OTC-LIT-V50-LINK-008"]
    assert renal["direct_scope_profile_conditions"] == "kidneyDisease=true;ageYears<=18"
    assert "성인" in renal["ui_boundary_ko"]

    anticoagulant = rows["OTC-LIT-V50-LINK-009"]
    assert anticoagulant["semantic_classification"] == "mixed_scope"
    assert "aspirin" not in anticoagulant["direct_scope_medication_terms"].lower()
    assert "aspirin" in anticoagulant["ui_boundary_ko"].lower()

    decongestant = rows["OTC-LIT-V50-LINK-010"]
    assert decongestant["direct_scope_ingredient_ids"].split(";") == [
        "ING-acetaminophen",
        "ING-mf-src-4b985f9d3bdb",
    ]
    assert decongestant["direct_scope_product_item_sequences"] == "196800036"


def test_audit_records_authority_boundary_and_runtime_risk_counts() -> None:
    csv_bytes, audit_bytes = build_artifacts()
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    audit = json.loads(audit_bytes)

    assert len(rows) == 20
    assert audit["authority"]["human_expert_reviewed"] is False
    assert audit["authority"]["supports_rule_release"] is False
    assert audit["authority"]["changes_authorization_decision"] is False
    assert audit["counts"]["semantic_classifications"] == {
        "background_context": 5,
        "direct_match": 1,
        "mixed_scope": 4,
    }
    assert audit["runtime_risk_snapshot"]["served_papers"] == 19
    assert audit["runtime_risk_snapshot"]["served_links"] == 20
    assert audit["runtime_risk_snapshot"]["rejected_legacy_links_reachable"] == 8
    assert audit["runtime_risk_snapshot"]["rejected_legacy_distinct_papers_reachable"] == 7
    assert audit["runtime_risk_snapshot"]["rejected_legacy_links_draft_inactive"] == 2
    assert all(audit["checks"].values())
    assert audit["valid"] is True


def test_written_artifacts_match_builder_and_custom_targets(tmp_path) -> None:
    csv_bytes, audit_bytes = build_artifacts()
    assert OUTPUT_CSV.read_bytes() == csv_bytes
    assert OUTPUT_AUDIT.read_bytes() == audit_bytes

    csv_target = tmp_path / "literature" / "link_classification.csv"
    audit_target = tmp_path / "audit" / "literature_link_classification_audit.json"
    write(csv_target, audit_target)
    assert csv_target.read_bytes() == csv_bytes
    assert audit_target.read_bytes() == audit_bytes
