#!/usr/bin/env python3
"""Create non-released informational rules traceable to verified PubMed abstracts."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "research_v2"
FIELDS = [
    "rule_id", "clinical_node_id", "ingredient_id", "population_criteria_json",
    "medication_criteria_json", "dose_json", "duration_json", "outcome_id",
    "action_class", "severity", "message_short", "message_explanation",
    "questions_to_ask_json", "uncertainty_statement", "certainty_grade",
    "jurisdiction_json", "evidence_ids", "source_quote_ids", "reviewer_ids",
    "status", "valid_from", "review_due",
]
SPEC = {
    "K1": ("vitamin_d", "calcium_related_adverse_events", "monitor_or_discuss", "비타민 D 복용량과 칼슘 병용 여부를 확인하세요.", "초록 근거에는 고용량 또는 칼슘 병용 연구에서 고칼슘혈증·고칼슘뇨·결석 결과를 평가한 연구가 있습니다.", ["하루 또는 회당 비타민 D 용량은 얼마인가요?", "칼슘 제품을 함께 복용하나요?", "신장결석 병력이 있나요?"]),
    "K2": ("vitamin_b6", "sensory_neuropathy", "monitor_or_discuss", "비타민 B6 누적 섭취와 감각 이상을 확인하세요.", "초록 근거에는 고용량 또는 장기 피리독신 노출 뒤 감각신경병증을 보고한 연구가 있습니다.", ["여러 제품에서 비타민 B6를 중복 섭취하나요?", "저림·감각저하·보행 이상이 있나요?", "얼마 동안 복용했나요?"]),
    "K3": ("oral_iron", "gastrointestinal_adverse_events", "monitor_or_discuss", "경구 철분 복용 뒤 위장관 증상을 확인하세요.", "초록 근거에는 경구 철분 제제와 복용 일정에 따른 오심·변비·복통 등 위장관 이상반응 연구가 있습니다.", ["철분 제제명과 복용 횟수는 무엇인가요?", "오심·구토·변비·설사·복통이 있나요?"]),
    "K4": ("magnesium", "hypermagnesemia_or_diarrhea", "monitor_or_discuss", "마그네슘 제제와 신장기능·설사·의식저하를 확인하세요.", "초록 근거에는 마그네슘 산화물 복용자의 고마그네슘혈증과 보충제의 설사 결과를 다룬 연구가 있습니다.", ["마그네슘 제제와 하루 용량은 무엇인가요?", "신장기능 저하가 있나요?", "설사·저혈압·서맥·의식 변화가 있나요?"]),
    "K5": ("zinc", "copper_deficiency", "monitor_or_discuss", "아연 장기 복용 시 구리결핍 관련 증상을 확인하세요.", "초록 근거에는 아연 보충 뒤 구리결핍, 빈혈, 호중구감소증, 신경학적 증상을 보고한 사례와 검토가 있습니다.", ["아연 용량과 복용 기간은 얼마인가요?", "빈혈·보행 이상·감각 이상 진단이 있나요?", "구리 수치를 검사했나요?"]),
}


def main() -> None:
    with (ROOT / "extraction" / "seed_abstract_evidence.csv").open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence:
        by_node[row["clinical_node_id"]].append(row)
    quotes = []
    rules = []
    for node, rows in sorted(by_node.items()):
        quote_ids = []
        for row in rows:
            quote_id = f"AQ-{node}-{row['pmid']}"
            quote_ids.append(quote_id)
            quotes.append({"quote_id": quote_id, "evidence_id": row["evidence_id"], "source_url": row["source_url"], "locator": "PubMed abstract", "quote": row["abstract_locator_quote"], "verification_status": "verified_against_pubmed_abstract"})
        ingredient, outcome, action, short, explanation, questions = SPEC[node]
        values = {
            "rule_id": f"DRAFT-{node}-ABSTRACT-001", "clinical_node_id": node,
            "ingredient_id": ingredient, "population_criteria_json": "{}",
            "medication_criteria_json": "{}", "dose_json": "", "duration_json": "",
            "outcome_id": outcome, "action_class": action, "severity": "informational",
            "message_short": short, "message_explanation": explanation,
            "questions_to_ask_json": json.dumps(questions, ensure_ascii=False),
            "uncertainty_statement": "초록만 검토했으며 전문 검토, RoB, GRADE, 전문가 합의, 독립 시나리오 검증을 수행하지 않았습니다.",
            "certainty_grade": "not_graded", "jurisdiction_json": "[]",
            "evidence_ids": ";".join(row["evidence_id"] for row in rows),
            "source_quote_ids": ";".join(quote_ids), "reviewer_ids": "codex_agent",
            "status": "draft_ai", "valid_from": "", "review_due": "",
        }
        rules.append(values)
    for path, rows in [
        (ROOT / "extraction" / "source_quotes.csv", quotes),
        (ROOT / "rules" / "rule_trace.csv", rules),
    ]:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if path.name == "source_quotes.csv" else FIELDS)
            writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"draft_ai_rules": len(rules), "source_quotes": len(quotes)}, indent=2))


if __name__ == "__main__":
    main()
