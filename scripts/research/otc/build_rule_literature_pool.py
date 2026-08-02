"""규칙별 '선별 통과 문헌' 풀을 사이트 런타임 JSON 으로 굽는다.

배경. v5.0 이 검증한 규칙-문헌 연결은 10건이고 사이트가 서빙하던 것은 20건(고유 19편)이
전부였다. 그 20건은 문장 locator 와 원문 인용 대조를 통과한 **검증 근거**이며 그 지위는
그대로 둔다. 이 도구는 그 아래에 한 층을 더 만든다 — 규칙이 허용한 질문에서 v5.0 선별이
retain 으로 판정한 문헌이다.

두 층은 지위가 다르다. 섞어 쓰면 안 된다.

    검증 근거      규칙 9개 · 링크 10건. 문장 locator + 원문 인용 대조 통과
    선별 통과 문헌  이 도구가 만든다. 인용 대조를 하지 않았고 규칙을 배포시키지 못한다

논문 수치(9규칙·10건)는 검증 근거를 가리키므로 이 도구가 바꾸지 않는다.

좁히는 방식은 두 단계이고 둘 다 결정적이다.
  1. 규칙이 허용한 질문(`allowed_question_ids`)의 retain 집합
  2. 그 안에서 규칙 유형의 위해 표현이 제목·초록에 나타나는 문헌

**봉인 산출물을 고치지 않는다.** 읽기만 하고 `src/generated/` 에 파일 하나를 쓴다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
DECISIONS = V5 / "screening" / "decisions.csv"
EVIDENCE_MAP = V5 / "evidence_map.csv"
MANIFEST = V5 / "downstream" / "literature_link_manifest.json"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
TARGET = ROOT / "src" / "generated" / "otc-rule-literature-pool.json"

csv.field_size_limit(1 << 30)

# 규칙 유형이 뜻하는 위해 표현. 허가원문이 정한 규칙 유형에서 그대로 따온다.
# 새 판단을 넣지 않으려고 유형 이름이 가리키는 임상 개념만 적는다.
RULE_TYPE_PATTERNS: dict[str, str] = {
    "duplicate_ingredient":
        r"duplicat|co-?ingest|concomitant|multiple product|combination product|"
        r"-containing|overlap|simultaneous",
    "duplicate_pharmacologic_class":
        r"nsaid|non-?steroidal|duplicat|same class|concomitant|combination",
    "max_daily_dose":
        r"maximum daily|daily dose|overdose|over-?dose|supratherapeutic|exceed|"
        r"excessive dose|dose limit|4 ?g|4000 ?mg",
    "minimum_interval":
        r"dosing interval|dose interval|every \d+ ?h|frequency of (?:dos|administ)|"
        r"repeated dos|inter-?dose",
    "age_restriction":
        r"child|paediatric|pediatric|infant|adolescent|age (?:limit|restrict)|"
        r"under \d+ years|younger than",
    "pregnancy_lactation":
        r"pregnan|gestation|lactat|breast-?feed|nursing mother|fetal|foetal",
    "hepatic_disease":
        r"hepatotox|hepatic|liver injury|liver disease|cirrhosis|transaminase|alt |ast ",
    "renal_disease":
        r"renal|kidney|nephrotox|nephropathy|dialysis|creatinine|glomerular",
    "gi_bleeding_ulcer":
        r"gastrointestinal bleed|gi bleed|peptic ulcer|gastric ulcer|"
        r"upper gastrointestinal|haemorrhage|hemorrhage|erosion|gastropathy",
    "sedation_driving":
        r"sedat|drowsi|somnolen|psychomotor|driving|vigilance|impair(?:ed|ment) "
        r"(?:alert|perform)|reaction time",
    "alcohol":
        r"alcohol|ethanol|drinking|alcoholic",
    "anticoagulant_antiplatelet":
        r"warfarin|anticoagul|antiplatelet|clopidogrel|coumarin|inr\b|"
        r"bleeding risk|aspirin",
    "sedative_medication":
        r"sedative|hypnotic|benzodiazep|cns depress|anxiolytic|sleep(?:ing)? (?:aid|medicat)|"
        r"barbiturate",
    "decongestant_hypertension":
        r"decongestant|pseudoephedrine|phenylephrine|blood pressure|hypertens|"
        r"cardiovascular|vasoconstrict",
    "maximum_duration":
        r"duration of (?:use|treatment|therapy)|prolonged use|long-?term use|"
        r"chronic use|consecutive days|beyond \d+ days",
    "urgent_referral":
        r"emergency|urgent|refer(?:ral)? to|seek medical|hospital|warning sign|"
        r"immediate(?:ly)? (?:stop|discontinu|consult)",
}

MAX_PER_RULE = 400  # 화면 페이징 상한. 초과분은 잘린 수를 함께 기록한다.


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="파일을 쓰지 않고 집계만 보고한다")
    args = parser.parse_args()

    for path in (DECISIONS, EVIDENCE_MAP, MANIFEST, RULES):
        if not path.is_file():
            raise SystemExit(f"입력이 없습니다: {path}")

    # 1. 질문별 retain 집합
    retain: dict[str, set[str]] = {}
    with DECISIONS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["decision"] == "retain":
                retain.setdefault(row["question_id"], set()).add(row["record_id"])

    # 2. 규칙 메타
    with RULES.open(encoding="utf-8-sig", newline="") as handle:
        rule_rows = {r["rule_id"]: r for r in csv.DictReader(handle)}

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rules_meta = manifest["results"]["rules"]

    wanted: set[str] = set()
    for rule in rules_meta:
        for question in rule["allowed_question_ids"]:
            wanted |= retain.get(question, set())

    # 3. 필요한 레코드만 코퍼스에서 읽는다(94 MB 전체를 메모리에 올리지 않는다).
    papers: dict[str, dict[str, object]] = {}
    haystack: dict[str, str] = {}
    with EVIDENCE_MAP.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            record = row["record_id"]
            if record not in wanted or record in papers:
                continue
            pmid = (row.get("pmid") or "").strip()
            papers[record] = {
                "record_id": record,
                "pmid": pmid,
                "title": (row.get("title") or "").strip(),
                "journal": (row.get("journal") or "").strip(),
                "year": (row.get("publication_year") or "").strip(),
                "doi": (row.get("doi") or "").strip(),
                "publication_types": (row.get("publication_types") or "").strip(),
                "has_abstract": (row.get("has_abstract") or "").strip().lower()
                in ("true", "1", "yes"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            }
            haystack[record] = f"{row.get('title', '')} {row.get('abstract', '')}".lower()

    # 4. 규칙별 두 단계 좁히기
    out_rules: dict[str, object] = {}
    used: set[str] = set()
    report: list[tuple[str, str, int, int, int]] = []
    for rule in rules_meta:
        rule_id = rule["rule_id"]
        rule_type = rule["rule_type"]
        pattern = RULE_TYPE_PATTERNS.get(rule_type)
        if pattern is None:
            raise SystemExit(f"규칙 유형에 표현 정의가 없습니다: {rule_type}")
        regex = re.compile(pattern, re.IGNORECASE)

        question_pool: set[str] = set()
        for question in rule["allowed_question_ids"]:
            question_pool |= retain.get(question, set())

        matched = [r for r in sorted(question_pool) if regex.search(haystack.get(r, ""))]
        # 초록이 있는 문헌을 앞에, 그 다음 최신순으로 둔다.
        matched.sort(
            key=lambda r: (
                0 if papers[r]["has_abstract"] else 1,
                -int(papers[r]["year"] or 0),
                r,
            )
        )
        kept = matched[:MAX_PER_RULE]
        used.update(kept)
        out_rules[rule_id] = {
            "rule_type": rule_type,
            "status": rule_rows.get(rule_id, {}).get("status", ""),
            "allowed_question_ids": rule["allowed_question_ids"],
            "question_pool_total": len(question_pool),
            "rule_type_matched_total": len(matched),
            "listed": len(kept),
            "truncated": max(0, len(matched) - len(kept)),
            "verified_link_count": rule["link_count"],
            "record_ids": kept,
        }
        report.append((rule_id, rule_type, len(question_pool), len(matched), len(kept)))

    payload = {
        "schema_version": "1.0.0",
        "track": "v5.0",
        "tier": "screening_passed_literature",
        "authority": {
            "supports_rule_release": False,
            "evidence_authority": "literature_explanatory_only",
            "quote_verified": False,
            "human_expert_reviewed": 0,
        },
        "purpose": (
            "검증 근거(규칙 9개·링크 10건) 아래 층. 규칙이 허용한 질문에서 v5.0 선별이 "
            "retain 으로 판정하고, 규칙 유형의 위해 표현이 제목·초록에 나타나는 문헌이다. "
            "문장 locator 와 원문 인용 대조를 거치지 않았으므로 검증 근거와 지위가 다르다."
        ),
        "derivation": {
            "step_1": "규칙의 allowed_question_ids 에서 decision=retain 인 레코드",
            "step_2": "규칙 유형의 위해 표현이 title+abstract 에 나타나는 레코드",
            "ordering": "초록 있음 우선, 그다음 최신 출판연도",
            "per_rule_cap": MAX_PER_RULE,
            "deterministic": True,
            "language_model_calls": 0,
        },
        "inputs": {
            "decisions": {
                "path": "research_v3/otc/literature/v5/screening/decisions.csv",
                "sha256": sha256_file(DECISIONS),
            },
            "evidence_map": {
                "path": "research_v3/otc/literature/v5/evidence_map.csv",
                "sha256": sha256_file(EVIDENCE_MAP),
            },
            "link_manifest": {
                "path": "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
                "sha256": sha256_file(MANIFEST),
            },
        },
        "rule_type_patterns": RULE_TYPE_PATTERNS,
        "totals": {
            "rules": len(out_rules),
            "unique_papers_listed": len(used),
            "retain_rows_in_corpus": sum(len(v) for v in retain.values()),
        },
        "rules": out_rules,
        "papers": {r: papers[r] for r in sorted(used)},
    }

    print(f"{'규칙':16s} {'유형':30s} {'질문풀':>7} {'유형일치':>8} {'수록':>6}")
    for rule_id, rule_type, pool, matched, kept in report:
        print(f"{rule_id:16s} {rule_type:30s} {pool:>7,} {matched:>8,} {kept:>6,}")
    print(f"\n고유 논문 수록 {len(used):,}편")

    if args.check:
        return 0

    TARGET.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"-> {TARGET.relative_to(ROOT)}  ({TARGET.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
