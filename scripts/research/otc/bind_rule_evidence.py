from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"

PREFERENCES = {
    "duplicate_ingredient": ("202106092", "다른 제품과 함께 복용"),
    "duplicate_pharmacologic_class": ("198601920", "비스테로이드성 소염진통제(NSAIDs)와 함께"),
    "max_daily_dose": ("202106092", "1일 최대 4그램"),
    "minimum_interval": ("202106092", "4-6시간 마다"),
    "age_restriction": ("202106092", "만 12세 이상"),
    "pregnancy_lactation": ("198601920", "임신 말기 3개월"),
    "hepatic_disease": ("202106092", "간장애 또는 그 병력이 있는"),
    "renal_disease": ("198601920", "신장장애 또는 그 병력이 있는"),
    "gi_bleeding_ulcer": ("198601920", "위장관계 위험"),
    "sedation_driving": ("196800036", "자동차 운전"),
    "alcohol": ("202106092", "세잔 이상"),
    "anticoagulant_antiplatelet": ("198601920", "쿠마린계 항응혈제"),
    "sedative_medication": ("196800036", "진정제"),
    "decongestant_hypertension": ("196800036", "고혈압"),
    "maximum_duration": ("196800036", "장기간 계속 복용"),
    "urgent_referral": ("202106092", "즉각 중지"),
}

SCOPES = {
    "duplicate_ingredient": "acetaminophen_containing_selected_products",
    "duplicate_pharmacologic_class": "ibuprofen_and_other_NSAIDs",
    "max_daily_dose": "acetaminophen_tylenol500_age_12_plus",
    "minimum_interval": "tylenol500_age_12_plus",
    "age_restriction": "tylenol500_minimum_age_12",
    "pregnancy_lactation": "ibuprofen_pregnancy_lactation",
    "hepatic_disease": "acetaminophen_liver_disease",
    "renal_disease": "ibuprofen_kidney_disease",
    "gi_bleeding_ulcer": "ibuprofen_gi_bleeding_or_ulcer",
    "sedation_driving": "pancol_a_driving",
    "alcohol": "acetaminophen_regular_alcohol_use",
    "anticoagulant_antiplatelet": "ibuprofen_warfarin_or_coumarin_anticoagulant",
    "sedative_medication": "pancol_a_sedative_or_overlapping_cold_medicine",
    "decongestant_hypertension": "pancol_a_phenylephrine_hypertension",
    "maximum_duration": "pancol_a_continuous_use",
    "urgent_referral": "tylenol500_stop_and_consult_symptoms",
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, data: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def bind() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rules = read(OTC / "rules" / "rules.csv")
    evidence = read(OTC / "rules" / "official_evidence_candidates.csv")
    selected = {}
    for rule_type, (item_sequence, phrase) in PREFERENCES.items():
        matches = [row for row in evidence if row["rule_type"] == rule_type and row["item_sequence"] == item_sequence and phrase in row["evidence_text"]]
        if not matches:
            raise ValueError(f"No primary evidence for {rule_type}: {item_sequence} / {phrase}")
        selected[rule_type] = matches[0]
    for rule in rules:
        primary = selected[rule["rule_type"]]
        rule["scope"] = SCOPES[rule["rule_type"]]
        rule["source_id"] = primary["source_id"]
        rule["source_locator"] = f"{primary['product_name']} ({primary['item_sequence']}) · {primary['source_locator']}"

    shortlist = []
    for rule in rules:
        rule_type = rule["rule_type"]
        primary = selected[rule_type]
        candidates = [primary]
        seen_products = {primary["item_sequence"]}
        for row in evidence:
            if row["rule_type"] == rule_type and row["item_sequence"] not in seen_products:
                candidates.append(row)
                seen_products.add(row["item_sequence"])
            if len(candidates) == 3:
                break
        for rank, row in enumerate(candidates, 1):
            shortlist.append({
                "rule_id": rule["rule_id"], "rule_type": rule_type, "rank": str(rank),
                "recommendation": "recommended_primary" if rank == 1 else "alternative_context",
                "scope": rule["scope"], "evidence_candidate_id": row["evidence_candidate_id"],
                "product_name": row["product_name"], "item_sequence": row["item_sequence"],
                "source_id": row["source_id"], "source_url": row["source_url"],
                "source_locator": row["source_locator"], "evidence_text": row["evidence_text"],
                "review_status": "codex_recommended_not_expert_verified",
                "supports_release": "false",
            })
    return rules, shortlist


def main() -> int:
    rules, shortlist = bind()
    write(OTC / "rules" / "rules.csv", rules)
    write(OTC / "rules" / "rule_evidence_shortlist.csv", shortlist)
    print(f"rules_bound={len(rules)} shortlist={len(shortlist)} released={sum(row['status'] == 'released' for row in rules)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
