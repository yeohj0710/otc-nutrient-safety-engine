import csv
import json
import sys
from pathlib import Path

from scripts.research import import_review_wizard_result


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_complete_wizard_imports_all_human_sections(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "research_v3"
    press_fields = ["review_id", "reviewer_id", "review_date_utc", "rating", "comment", "resolution", "status"]
    write_csv(root / "search/provisional_pubmed_20260710/peer_review.csv", press_fields, [{"review_id": f"P-{i}"} for i in range(35)])
    literature_fields = ["evidence_candidate_id", "source_locator"]
    write_csv(root / "human_review_minimal/03_우선문헌_118건_검토.csv", literature_fields, [{"evidence_candidate_id": f"E-{i}", "source_locator": "PubMed abstract"} for i in range(118)])
    rule_fields = ["review_item_id", "evidence_quote", *import_review_wizard_result.RULE_BOOLEAN_FIELDS, "overall_decision", "required_revision", "reviewer_id", "reviewer_role", "reviewed_at", "adjudication_status", "notes"]
    write_csv(root / "rules/expert_rule_review_packet.csv", rule_fields, [{"review_item_id": f"R-{i}", "evidence_quote": "official quote"} for i in range(6)])
    scenario_fields = ["scenario_id", "scenario_type", "input_json", "gold_hazards_json", "critical", "adjudicator_id", "adjudicated_at", "locked_before_test", "notes"]
    write_csv(root / "human_review_minimal/05_독립시나리오_12건_확정.csv", scenario_fields, [{"scenario_id": f"S-{i}", "input_json": json.dumps({"ingredient": "zinc"}), "critical": "false"} for i in range(12)])
    candidate_fields = ["evidence_candidate_id", "parent_candidate_id", "pmcid", "source_path", "locator", "clinical_node_id", "evidence_text", "signal_types", "dose_mentions", "duration_mentions", "population_mentions"]
    write_csv(root / "extraction/ai_full_text_evidence_candidates.csv", candidate_fields, [{"evidence_candidate_id": f"FT-E-{i}", "parent_candidate_id": f"E-{i}", "pmcid": f"PMC{i}", "source_path": f"research_v3/full_text/oa_xml/PMC{i}.xml", "locator": "Results > paragraph 1", "clinical_node_id": "K5", "evidence_text": "Safety outcome paragraph", "signal_types": "adverse event"} for i in range(63)])
    decisions = {}
    for i in range(4):
        decisions[f"approval:A-{i}"] = {"decision": "approve", "reviewer_id": "교수", "reviewer_role": "지도교수", "reviewed_at": "2026-07-13T00:00:00Z"}
    for i in range(35):
        decisions[f"press:P-{i}"] = {"rating": "yes", "reviewer_id": "검색자", "reviewer_role": "검색전략 검토자", "reviewed_at": "2026-07-13T00:00:00Z", "review_kind": "human_review"}
    for i in range(118):
        decisions[f"literature:E-{i}"] = {"decision": "include_candidate", "reviewer_id": "문헌자", "reviewer_role": "문헌 검토자", "reviewed_at": "2026-07-13T00:00:00Z", "review_kind": "human_review"}
    for i in range(6):
        decisions[f"rules:R-{i}"] = {"decision": "approve", "reviewer_id": "전문가", "reviewer_role": "약사·전문가", "reviewed_at": "2026-07-13T00:00:00Z", "review_kind": "human_review"}
    for i in range(12):
        decisions[f"scenarios:S-{i}"] = {"label": "warning", "reviewer_id": "평가자", "reviewer_role": "독립 평가자", "reviewed_at": "2026-07-13T00:00:00Z", "review_kind": "human_review", "locked_before_test": True}
    for i in range(63):
        decisions[f"fulltext:PMC{i}"] = {"decision": "include", "locator": "Results > paragraph 1", "reviewer_id": "전문검토자", "reviewer_role": "전문 검토자", "reviewed_at": "2026-07-13T00:00:00Z", "review_kind": "human_review"}
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"overall_status": "completed", "decisions": decisions}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["import", "--input", str(result), "--root", str(root)])
    import_review_wizard_result.main()
    screening = list(csv.DictReader((root / "screening/title_abstract.csv").open(encoding="utf-8-sig")))
    rules = list(csv.DictReader((root / "rules/expert_rule_review_packet.csv").open(encoding="utf-8-sig")))
    scenarios = list(csv.DictReader((root / "validation/independent_scenarios.csv").open(encoding="utf-8-sig")))
    full_text = list(csv.DictReader((root / "screening/full_text.csv").open(encoding="utf-8-sig")))
    evidence = list(csv.DictReader((root / "extraction/evidence.csv").open(encoding="utf-8-sig")))
    assert len(screening) == 118 and all(row["decision"] == "include" for row in screening)
    assert len(rules) == 6 and all(row["overall_decision"] == "approve" and row["source_locator_verified"] == "true" for row in rules)
    assert len(scenarios) == 12 and all(row["gold_hazards_json"] == '["V3-DRAFT-KDRI-ZN-UL"]' for row in scenarios)
    assert len(full_text) == 63 and all(row["decision"] == "include" and row["locator"] for row in full_text)
    assert len(evidence) == 63 and all(row["review_status"] == "verified" and row["verbatim_quote"] for row in evidence)
