"""P4 문헌 근거 연결 후보 검색 보조 도구.

이 스크립트는 **연결을 결정하지 않는다.** retain 판정된 문헌 중 규칙 유형별 키워드가 걸리는
후보를 점수 순으로 보여줄 뿐이며, 어떤 논문을 어떤 규칙에 붙일지와 초록의 어느 문장을
locator 로 쓸지는 에이전트가 초록을 직접 읽고 결정한다.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITERATURE = ROOT / "research_v3" / "otc" / "literature"
EVIDENCE_MAP = LITERATURE / "evidence_map.csv"
DECISIONS = LITERATURE / "screening" / "agent_decisions"

# 규칙 유형별 검색어. 판정 기준이 아니라 후보를 좁히는 필터일 뿐이다.
RULE_TYPE_QUERIES: dict[str, tuple[str, ...]] = {
    "duplicate_ingredient": (
        "multiple acetaminophen", "more than one product", "combination product",
        "duplicate", "concomitant acetaminophen", "unintentional overdose",
    ),
    "duplicate_pharmacologic_class": (
        "concurrent nsaid", "two nsaid", "concomitant nsaid", "nsaid combination",
        "duplicate therapy", "multiple nsaid",
    ),
    "max_daily_dose": (
        "maximum daily dose", "4 g", "exceed", "supratherapeutic", "recommended daily",
        "above the recommended",
    ),
    "minimum_interval": (
        "dosing interval", "every 4 h", "too soon", "shorter interval", "frequency of dosing",
        "repeated dose",
    ),
    "age_restriction": (
        "dosing error", "weight-based", "age-based dos", "children under", "paediatric dos",
        "pediatric dos", "caregiver",
    ),
    "pregnancy_lactation": (
        "pregnan", "in utero", "breastfeed", "lactation", "fetal", "third trimester",
    ),
    "hepatic_disease": (
        "hepatotoxicity", "liver injury", "hepatic failure", "chronic liver disease",
        "cirrhosis", "transaminase",
    ),
    "renal_disease": (
        "renal", "kidney", "nephrotoxic", "acute kidney injury", "creatinine clearance",
        "chronic kidney disease",
    ),
    "gi_bleeding_ulcer": (
        "gastrointestinal bleeding", "peptic ulcer", "upper gastrointestinal",
        "gi bleeding", "perforation", "gastroduodenal",
    ),
    "sedation_driving": (
        "driving", "psychomotor", "sedation", "impair", "drowsiness", "vigilance",
    ),
    "alcohol": (
        "alcohol", "ethanol", "chronic alcohol", "drinker", "alcoholic",
    ),
    "anticoagulant_antiplatelet": (
        "warfarin", "anticoagulant", "inr", "antiplatelet", "bleeding risk", "vitamin k antagonist",
    ),
    "sedative_medication": (
        "benzodiazepine", "sedative", "hypnotic", "zolpidem", "cns depressant",
        "additive sedation",
    ),
    "decongestant_hypertension": (
        "phenylephrine", "pseudoephedrine", "decongestant", "blood pressure",
        "hypertens", "sympathomimetic",
    ),
    "maximum_duration": (
        "repeated supratherapeutic", "staggered overdose", "prolonged use", "long-term use",
        "chronic use", "medication overuse headache", "medication-overuse headache",
    ),
    "urgent_referral": (
        "stevens-johnson", "toxic epidermal", "anaphyla", "angioedema", "serious cutaneous",
        "emergency department referral", "life-threatening",
    ),
}


def load_decisions() -> dict[str, str]:
    decisions: dict[str, str] = {}
    for path in glob.glob(str(DECISIONS / "*.jsonl")):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            decisions[row["record_id"]] = row["decision"]
    return decisions


def load_records() -> dict[str, dict[str, str]]:
    with EVIDENCE_MAP.open(encoding="utf-8-sig", newline="") as handle:
        return {row["record_id"]: row for row in csv.DictReader(handle)}


def sentences(abstract: str) -> list[str]:
    """초록을 문장 단위로 자른다. locator 는 이 인덱스를 쓴다."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", abstract.strip())
    return [part.strip() for part in parts if part.strip()]


def search(rule_type: str, limit: int, decisions: dict[str, str], records: dict[str, dict[str, str]]):
    queries = RULE_TYPE_QUERIES[rule_type]
    scored = []
    for record_id, decision in decisions.items():
        if decision != "retain":
            continue
        record = records[record_id]
        haystack = f"{record['title']} {record['abstract']}".lower()
        hits = [q for q in queries if q in haystack]
        if not hits:
            continue
        scored.append((len(hits), int(record["publication_year"] or 0), record, hits))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return scored[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rule_type", choices=sorted(RULE_TYPE_QUERIES))
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--sentences", action="store_true", help="후보의 문장 인덱스를 함께 출력")
    args = parser.parse_args()

    decisions = load_decisions()
    records = load_records()
    for score, year, record, hits in search(args.rule_type, args.limit, decisions, records):
        print(f"[{record['pmid']}] {year} score={score} hits={hits}")
        print(f"    {record['title']}")
        print(f"    journal={record['journal']} doi={record['doi']}")
        print(f"    types={record['publication_types']}")
        if args.sentences:
            for index, sentence in enumerate(sentences(record["abstract"]), start=1):
                print(f"      S{index:02d}: {sentence}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
