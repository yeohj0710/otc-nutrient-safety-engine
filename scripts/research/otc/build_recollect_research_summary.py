"""재수집 트랙(recollect-v2 · kwon)의 수치를 연구 정보 화면용 JSON 으로 굽는다.

옛 트랙 원장(`research_v3/logs/v50_run_report.json`,
`v50_scoring_report.json`)은 제출한 논문의 근거다. 여기서 읽지도 쓰지도 않는다.
단 하나, 옛 코퍼스의 질문별 행 수만 비교 열에 쓰려고 읽는다.

새 트랙 원장은 다른 저장소에 있다.

    C:\\dev\\evidence-recollect\\data\\kwon\\
      corpus/evidence_map.csv                        코퍼스
      screen/redo-20260820/effective.decisions.jsonl 선별 판정 (지금 원장)
      score-20260820/                                2차 맹검 채점
      fulltext/fulltext.jsonl                        원문 색인
      report.json                                    위 넷을 집계한 것

수치는 report.json 에서 그대로 옮긴다. 다만 카파는 원장에 없어 여기서 계산한다.
계산이 제멋대로가 아니라는 것을 보이려고, 같은 가중치로 일치도를 다시 구해
report.json 의 값과 어긋나면 멈춘다.

사이트는 `.vercelignore` 와 무관하게 이 저장소 밖을 읽을 수 없으므로, 화면이 쓸
값만 `src/generated/recollect/research-summary.json` 에 옮겨 두고 커밋한다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TRACK_ROOT = Path(r"C:\dev\evidence-recollect\data\kwon")

REPORT = TRACK_ROOT / "report.json"
CORPUS = TRACK_ROOT / "corpus" / "evidence_map.csv"
CORPUS_MANIFEST = TRACK_ROOT / "corpus" / "corpus_manifest.json"
DECISIONS = TRACK_ROOT / "screen" / "redo-20260820" / "effective.decisions.jsonl"
SCORING = TRACK_ROOT / "score-20260820" / "scoring_report.json"
SCORES = TRACK_ROOT / "score-20260820" / "scores.jsonl"
SAMPLE = TRACK_ROOT / "score-20260820" / "sample.json"
FULLTEXT = TRACK_ROOT / "fulltext" / "fulltext.jsonl"
QUERIES = TRACK_ROOT / "queries" / "query_definitions_nodate.json"
RAW_DIR = TRACK_ROOT / "raw"

# 옛 트랙에서 가져오는 것은 비교용 두 가지뿐이다. 읽기만 한다.
OLD_LEDGER = ROOT / "research_v3" / "logs" / "v50_run_report.json"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
LINKS = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "downstream"
    / "literature_link_manifest.json"
)
POOL = ROOT / "src" / "generated" / "recollect" / "rule-literature-pool.json"

TARGET = ROOT / "src" / "generated" / "recollect" / "research-summary.json"

QUESTION_TITLES = {
    "OTC-LIT-Q01-ACETAMINOPHEN": "아세트아미노펜 용량·간격·간질환·음주 관련 위해",
    "OTC-LIT-Q02-NSAID": "이부프로펜·덱시부프로펜·나프록센의 중복과 주요 위해",
    "OTC-LIT-Q03-COLD-ALLERGY": "감기·알레르기 복합성분의 진정·운전·혈압·병용 위해",
    "OTC-LIT-Q04-DIGESTIVE": "소화효소·담즙산·가스제거 성분 복합 사용의 안전성",
    "OTC-LIT-Q05-TOPICAL": "살리실산메틸·멘톨·캄파 등 외용 복합성분의 위해",
}

LABELS = ("retain", "deprioritize", "uncertain")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_labels(text: str) -> dict[str, int]:
    """원장이 한 줄로 적은 라벨 분포를 숫자로 되돌린다. 값은 그대로 옮긴다."""
    counts: dict[str, int] = {}
    for part in re.split(r"[·,]", text):
        match = re.match(r"\s*(유지|후순위|판정 보류)\s+([\d,]+)\s*$", part)
        if not match:
            raise SystemExit(f"라벨 분포를 읽지 못했습니다: {text!r}")
        counts[{"유지": "retain", "후순위": "deprioritize", "판정 보류": "uncertain"}[match.group(1)]] = int(
            match.group(2).replace(",", "")
        )
    if set(counts) != {"retain", "deprioritize", "uncertain"}:
        raise SystemExit(f"라벨 세 가지가 다 있어야 합니다: {text!r}")
    return counts


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def weighted_scoring(report_scoring: dict[str, Any]) -> dict[str, Any]:
    """채점 arm 의 카파를 설계 가중치로 구한다.

    층은 파이프라인 판정으로 나뉘므로 가중치도 파이프라인 판정에서 나온다.
    같은 가중치로 일치도를 다시 구해 원장 값과 맞는지 먼저 확인한다. 어긋나면
    가중 방식이 다르다는 뜻이므로 카파도 믿을 수 없어 여기서 멈춘다.
    """
    pipeline = {
        (row["question_id"], row["record_id"]): row["decision"]
        for row in read_jsonl(DECISIONS)
    }
    scorer = {
        (row["question_id"], row["record_id"]): row["decision"]
        for row in read_jsonl(SCORES)
    }
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    weight = {s["stratum"]: s["N"] / s["n"] for s in sample["strata"]}

    missing = [key for key in scorer if key not in pipeline]
    if missing:
        raise SystemExit(f"채점 행 {len(missing)}개가 선별 원장에 없습니다: {missing[:3]}")

    pairs = [(pipeline[key], scorer[key], weight[pipeline[key]]) for key in scorer]
    total = sum(w for _, _, w in pairs)
    agreement = sum(w for a, b, w in pairs if a == b) / total

    marginal_a: dict[str, float] = defaultdict(float)
    marginal_b: dict[str, float] = defaultdict(float)
    for a, b, w in pairs:
        marginal_a[a] += w
        marginal_b[b] += w
    expected = sum((marginal_a[l] / total) * (marginal_b[l] / total) for l in LABELS)
    kappa = (agreement - expected) / (1 - expected)

    recomputed = round(agreement * 100, 2)
    if abs(recomputed - report_scoring["agreement_vs_ai_reference"]) > 0.01:
        raise SystemExit(
            "가중 일치도가 원장과 다릅니다: "
            f"계산 {recomputed} · 원장 {report_scoring['agreement_vs_ai_reference']}"
        )

    return {
        "kappa": round(kappa, 3),
        "kappaMethod": "설계 가중 3분류 비가중 카파. 층 가중치는 N/n",
        "agreementRecomputed": recomputed,
        "seed": sample["seed"],
        "strata": len(sample["strata"]),
        "stratumRows": {s["stratum"]: {"N": s["N"], "n": s["n"]} for s in sample["strata"]},
        "excludedFromEarlierArm": sample["excluded_rows"],
        "eligiblePopulation": sample["population"],
    }


def main() -> None:
    for path in (
        REPORT, CORPUS, CORPUS_MANIFEST, DECISIONS, SCORING, SCORES, SAMPLE,
        FULLTEXT, QUERIES, OLD_LEDGER, RULES, LINKS,
    ):
        if not path.is_file():
            raise SystemExit(f"입력이 없습니다: {path}")

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    scoring = json.loads(SCORING.read_text(encoding="utf-8"))
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    old_ledger = json.loads(OLD_LEDGER.read_text(encoding="utf-8"))
    links = json.loads(LINKS.read_text(encoding="utf-8"))["results"]

    old_rows = old_ledger["phases"]["B"]["full_record"]["per_question_membership_rows"]
    rows_now = report["corpus"]["per_question"]
    hits = {q["question_id"]: q for q in queries["questions"]}

    questions = [
        {
            "id": qid,
            "titleKo": QUESTION_TITLES[qid],
            "rows": rows_now[qid],
            "previousRows": old_rows[qid],
            "hitsOld": hits[qid]["old_hit_count"],
            "hitsAfterDateRemoval": hits[qid]["hits_before_amendment"],
            "hitsAfterAmendment": hits[qid]["hits_after_amendment"],
        }
        for qid in QUESTION_TITLES
    ]

    rule_rows = RULES.read_text(encoding="utf-8-sig").splitlines()
    released = sum(1 for line in rule_rows[1:] if ",released," in line)

    pool_totals: dict[str, Any] | None = None
    if POOL.is_file():
        pool_totals = json.loads(POOL.read_text(encoding="utf-8"))["totals"]

    weighted = weighted_scoring(scoring)
    xml_files = sorted(p.name for p in RAW_DIR.glob("*.xml")) if RAW_DIR.is_dir() else []

    summary = {
        "schemaVersion": "1.0.0",
        "track": report["track"],
        "study": report["study"],
        "label": report["label"],
        "builtAt": report["built_at"],
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generatedFrom": {
            "report": {"path": str(REPORT), "sha256": sha256_file(REPORT)},
            "corpus": {"path": str(CORPUS), "sha256": report["corpus"]["csv_sha256"]},
            "decisions": {"path": str(DECISIONS), "sha256": sha256_file(DECISIONS)},
            "scoring": {"path": str(SCORING), "sha256": sha256_file(SCORING)},
            "fulltext": {"path": str(FULLTEXT), "sha256": sha256_file(FULLTEXT)},
            "supersededLedger": "research_v3/logs/v50_run_report.json (봉인 · 비교 열에만 사용)",
        },
        # 판정을 내리는 층은 허가원문이고 재수집이 건드리지 않는다. 값의 출처도 그대로다.
        "authorization": {
            "analysedProducts": 13,
            "collectedProducts": 16,
            "uniqueIngredients": old_ledger["ingredient_coverage"]["included_count"],
            "productIngredientLinks": 47,
            "administrationConstraints": 32,
            "ruleCount": links["rule_count"],
            "releasedRuleCount": released,
        },
        "search": {
            "dateLimitRemoved": True,
            "amendment": queries["amendment"]["id"],
            "amendmentWhat": "대상(P) 블록을 필수에서 선택으로 내렸다. 검색어 자체는 그대로다",
            "questions": questions,
            "hitsOldTotal": sum(q["hitsOld"] for q in questions),
            "hitsAfterDateRemovalTotal": sum(q["hitsAfterDateRemoval"] for q in questions),
            "hitsAfterAmendmentTotal": sum(q["hitsAfterAmendment"] for q in questions),
        },
        "corpus": {
            "rows": report["corpus"]["rows"],
            "uniquePapers": report["corpus"]["unique_papers"],
            "rowsWithAbstract": report["corpus"]["rows_with_abstract"],
            "rowsTitleOnly": report["corpus"]["rows_title_only"],
            "duplicatesRemoved": manifest["duplicates_removed"],
            "previousRows": report["corpus"]["old_rows"],
            "growthVsPrevious": report["corpus"]["growth_vs_old"],
            "xmlFiles": len(xml_files),
        },
        "screening": {
            "screened": report["screening"]["screened"],
            "final": {
                "retain": report["screening"]["final"]["유지"],
                "deprioritize": report["screening"]["final"]["후순위"],
                "uncertain": report["screening"]["final"]["판정 보류"],
            },
            "retainedPapers": report["screening"]["retained_papers"],
            "coverage": report["screening"]["coverage"],
            "humanDecisions": report["screening"]["human_decisions"],
            "amendments": [
                {
                    "id": "AM-REC-010",
                    "what": "초록 없이 제목만 있는 행을 다시 판정했습니다",
                    "rows": report["amendments"]["AM-REC-010"]["rows"],
                    "newLabels": parse_labels(report["amendments"]["AM-REC-010"]["new_labels"]),
                },
                {
                    "id": "AM-REC-011",
                    "what": "사유 칸이 빈 채로 기록된 행을 다시 판정했습니다",
                    "rows": report["amendments"]["AM-REC-011"]["rows"],
                    "newLabels": parse_labels(report["amendments"]["AM-REC-011"]["new_labels"]),
                },
            ],
            "amendmentOverlapRows": report["amendments"]["overlap"]["rows"],
            "changedFromEarlierPass": report["amendments"]["disagreements_with_old"]["union"],
        },
        "fulltext": {
            "checkedPapers": report["fulltext"]["checked"],
            "withPmcid": report["fulltext"]["with_pmcid"],
            "withFulltext": report["fulltext"]["with_fulltext"],
            "shareOfRetainedPct": report["fulltext"]["share_of_retained_pct"],
            "shareOfPmcLinkedPct": report["fulltext"]["share_of_pmc_linked_pct"],
            "medianChars": report["fulltext"]["median_chars"],
        },
        "scoring": {
            "sampleRows": scoring["scored"],
            "populationRows": scoring["population"],
            "eligiblePopulation": weighted["eligiblePopulation"],
            "excludedFromEarlierArm": weighted["excludedFromEarlierArm"],
            "strata": weighted["strata"],
            "stratumRows": weighted["stratumRows"],
            "seed": weighted["seed"],
            "agreement": scoring["agreement_vs_ai_reference"],
            "agreementCi": scoring["agreement_ci"],
            "sensitivity": scoring["sensitivity_vs_ai_reference"],
            "specificity": scoring["specificity_vs_ai_reference"],
            "kappa": weighted["kappa"],
            "kappaMethod": weighted["kappaMethod"],
            "pipelineRetainShare": scoring["pipeline_retain_share"],
            "scorerRetainShare": scoring["scorer_retain_share_weighted"],
            "retainShareRatio": scoring["retain_share_ratio"],
            "disagreementByDirection": {
                "retain->deprioritize": scoring["disagreement_by_direction"]["retain→deprioritize"],
                "deprioritize->retain": scoring["disagreement_by_direction"]["deprioritize→retain"],
                "uncertain->retain": scoring["disagreement_by_direction"]["uncertain→retain"],
                "uncertain->deprioritize": scoring["disagreement_by_direction"]["uncertain→deprioritize"],
            },
            "lockedAt": scoring["locked_at"],
            "openedAt": scoring["opened_at"],
            "truthOpenedBeforeLock": scoring["truth_opened_before_lock"],
        },
        # 검증 근거 층은 봉인한 downstream 산출물 그대로다. 재수집이 바꾸지 않는다.
        "ruleLiterature": {
            "ruleCount": links["rule_count"],
            "resolvedRuleCount": links["resolved_rule_count"],
            "unresolvedRuleCount": links["unresolved_rule_count"],
            "unresolvedRuleIds": links["unresolved_rule_ids"],
            "linkCount": links["emitted_link_count"],
            "verifiedTrack": "v5.0 (봉인)",
        },
        "rulePool": pool_totals,
        "comparator": {
            "required": report["comparator"]["required"],
            "classified": report["comparator"]["classified"],
            "note": report["comparator"]["note"],
        },
        "flags": {
            "independentBlinding": False,
            "releaseReady": False,
            "humanReferenceRows": report["screening"]["human_decisions"],
            "invariantsChecked": report["invariants"]["checked"],
            "invariantsFailed": report["invariants"]["failed"],
        },
        "limitations": [
            "사람이 판정한 참조표준이 0건입니다. 어떤 값도 임상적 정확도나 검증 완료를 뜻하지 않습니다.",
            "자료원은 PubMed 하나입니다. 제2 데이터베이스, 회색문헌, 인용 검색을 하지 않았습니다.",
            (
                f"유지 {report['screening']['retained_papers']:,}편 가운데 "
                f"원문을 확보한 것은 {report['fulltext']['with_fulltext']:,}편"
                f"({report['fulltext']['share_of_retained_pct']}%)입니다. 나머지는 제목과 초록만 읽었습니다."
            ),
            (
                f"선별 사유가 빈 채로 기록된 행이 "
                f"{report['previous_report_known_defects'][0]['rows']:,}건 있었습니다. "
                "2026-08-20 재판정으로 판정은 다시 받았지만, 그때 적은 사유는 원래 판정의 "
                "사유가 아니라 재판정의 사유입니다."
            ),
            "대조군 분류기를 돌리지 않았습니다. 대조군도 언어모델이라 규칙 대 AI 대조가 성립하지 않습니다.",
            "판매량 자료가 없습니다. 분석 제품 13개는 대표 일반의약품 후보이며 판매 순위 집합이 아닙니다.",
        ],
        "reminder": report["reminder"],
    }

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    corpus = summary["corpus"]
    screening = summary["screening"]
    print(f"재수집 트랙 요약 -> {TARGET}")
    print(
        f"  코퍼스 {corpus['rows']:,}행({corpus['growthVsPrevious']}배) · "
        f"유지 {screening['final']['retain']:,} · "
        f"일치도 {summary['scoring']['agreement']}% · κ {summary['scoring']['kappa']}"
    )


if __name__ == "__main__":
    main()
