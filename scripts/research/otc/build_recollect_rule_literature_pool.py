"""규칙별 '선별 통과 문헌' 풀을 재수집 트랙 자료로 다시 굽는다.

`build_rule_literature_pool.py` 와 같은 도출식을 쓴다. 위해 표현·맥락 조건·상태
표지·성분 표기·인용 문장 점수식을 그 파일에서 그대로 가져와 쓴다. 베껴 두면 두
벌이 갈라지므로 import 한다. 바뀌는 것은 입력 둘뿐이다.

    코퍼스   research_v3/.../evidence_map.csv       -> data/kwon/corpus/evidence_map.csv
    판정     research_v3/.../decisions.csv          -> data/kwon/screen/redo-20260820/effective.decisions.jsonl

좁히는 방식은 그대로 두 단계이고 둘 다 결정적이다.
  1. 규칙이 허용한 질문(`allowed_question_ids`)에서 선별이 유지로 판정한 레코드
  2. 그 안에서 규칙 유형의 위해 표현이 제목·초록에 나타나는 레코드

규칙이 무엇을 허용하는지는 봉인한 v5.0 링크 원장에서 읽는다. 그 원장은 고치지 않는다.

**층을 섞지 않는다.** 검증 근거(규칙 9개·링크 10건)는 문장 locator 와 원문 인용
대조를 통과한 것이고 봉인 상태 그대로다. 이 도구가 만드는 것은 그 아래 층이며
인용 대조를 거치지 않았고 규칙을 배포시키지 못한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TRACK_ROOT = Path(r"C:\dev\evidence-recollect\data\kwon")

CORPUS = TRACK_ROOT / "corpus" / "evidence_map.csv"
DECISIONS = TRACK_ROOT / "screen" / "redo-20260820" / "effective.decisions.jsonl"
MANIFEST = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "downstream"
    / "literature_link_manifest.json"
)
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
TARGET = ROOT / "src" / "generated" / "recollect" / "rule-literature-pool.json"

# 확정된 도출 결과. 어긋나면 입력이나 도출식이 달라졌다는 뜻이므로 멈춘다.
EXPECTED_UNIQUE_PAPERS = 14676

csv.field_size_limit(1 << 30)


def _load_original() -> Any:
    """옛 빌더에서 도출식을 그대로 가져온다."""
    path = Path(__file__).with_name("build_rule_literature_pool.py")
    spec = importlib.util.spec_from_file_location("otc_rule_pool_original", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"도출식을 읽지 못했습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_original()
RULE_TYPE_PATTERNS = base.RULE_TYPE_PATTERNS
RULE_TYPE_CONTEXT = base.RULE_TYPE_CONTEXT
PROFILE_FACETS = base.PROFILE_FACETS
INGREDIENT_TERMS = base.INGREDIENT_TERMS
MAX_PER_RULE = base.MAX_PER_RULE
choose_key_sentence = base.choose_key_sentence


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

    for path in (CORPUS, DECISIONS, MANIFEST, RULES):
        if not path.is_file():
            raise SystemExit(f"입력이 없습니다: {path}")

    # 1. 질문별 유지 집합
    retain: dict[str, set[str]] = {}
    decision_rows = 0
    with DECISIONS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            decision_rows += 1
            row = json.loads(line)
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

    # 3. 필요한 레코드만 코퍼스에서 읽는다(152 MB 전체를 메모리에 올리지 않는다).
    papers: dict[str, dict[str, object]] = {}
    haystack: dict[str, str] = {}
    abstracts: dict[str, str] = {}
    with CORPUS.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_header = [
            "record_id", "question_id", "pmid", "title", "abstract", "year", "venue",
            "doi", "publication_types", "mesh", "dedup_identity", "has_abstract", "slice_id",
        ]
        if reader.fieldnames != expected_header:
            raise SystemExit(f"코퍼스 헤더가 다릅니다: {reader.fieldnames}")
        for row in reader:
            record = row["record_id"]
            if record not in wanted or record in papers:
                continue
            pmid = (row.get("pmid") or "").strip()
            papers[record] = {
                "record_id": record,
                "pmid": pmid,
                "title": (row.get("title") or "").strip(),
                # 새 코퍼스는 학술지를 venue, 출판연도를 year 로 적는다.
                "journal": (row.get("venue") or "").strip(),
                "year": (row.get("year") or "").strip(),
                "doi": (row.get("doi") or "").strip(),
                "publication_types": (row.get("publication_types") or "").strip(),
                "has_abstract": (row.get("has_abstract") or "").strip().lower()
                in ("true", "1", "yes"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            }
            haystack[record] = f"{row.get('title', '')} {row.get('abstract', '')}".lower()
            abstracts[record] = row.get("abstract") or ""
            text = haystack[record]
            papers[record]["f"] = sum(
                1 << i for i, (_, pat) in enumerate(PROFILE_FACETS)
                if re.search(pat, text, re.IGNORECASE)
            )
            papers[record]["g"] = sum(
                1 << i for i, (_, pat) in enumerate(INGREDIENT_TERMS)
                if re.search(pat, text, re.IGNORECASE)
            )

    missing = wanted - papers.keys()
    if missing:
        raise SystemExit(
            f"유지 판정을 받았으나 코퍼스에 없는 레코드 {len(missing)}건: {sorted(missing)[:3]}"
        )

    # 4. 규칙별 두 단계 좁히기
    out_rules: dict[str, object] = {}
    matched_papers: set[str] = set()
    listed_papers: set[str] = set()
    rule_paper_pairs = 0
    rule_question_rows = 0
    report: list[tuple[str, str, int, int, int]] = []

    for rule in rules_meta:
        rule_id = rule["rule_id"]
        rule_type = rule["rule_type"]
        pattern = RULE_TYPE_PATTERNS.get(rule_type)
        if pattern is None:
            raise SystemExit(f"규칙 유형에 표현 정의가 없습니다: {rule_type}")
        regex = re.compile(pattern, re.IGNORECASE)
        context_pattern = RULE_TYPE_CONTEXT.get(rule_type)
        context_regex = (
            re.compile(context_pattern, re.IGNORECASE) if context_pattern else None
        )

        def hit(record: str) -> bool:
            text = haystack.get(record, "")
            return bool(regex.search(text)) and (
                context_regex is None or bool(context_regex.search(text))
            )

        question_pool: set[str] = set()
        for question in rule["allowed_question_ids"]:
            question_pool |= retain.get(question, set())

        matched = [r for r in sorted(question_pool) if hit(r)]
        matched_papers.update(matched)
        rule_paper_pairs += len(matched)
        # 한 논문이 이 규칙의 질문 두 곳에서 유지를 받으면 원장 행으로는 두 건이다.
        rule_question_rows += sum(
            1 for q in rule["allowed_question_ids"] for r in retain.get(q, set()) if hit(r)
        )

        def relevance(record: str) -> tuple[int, int, int, int, str]:
            """관련도. 제목에서 맞으면 가장 크게 치고, 초록 히트 수로 다음을 가른다."""
            title = str(papers[record]["title"]).lower()
            abstract = abstracts.get(record, "").lower()
            title_hit = 1 if regex.search(title) else 0
            hits = len(regex.findall(abstract)) + len(regex.findall(title))
            has_abstract = 1 if papers[record]["has_abstract"] else 0
            return (-title_hit, -has_abstract, -min(hits, 20),
                    -int(papers[record]["year"] or 0), record)

        matched.sort(key=relevance)
        kept = matched[:MAX_PER_RULE]
        listed_papers.update(kept)
        quotes: dict[str, dict[str, str]] = {}
        for record in kept:
            locator, sentence = choose_key_sentence(
                str(papers[record]["title"]), abstracts.get(record, ""), regex
            )
            quotes[record] = {"locator": locator, "quote": sentence}
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
            "quotes": quotes,
        }
        report.append((rule_id, rule_type, len(question_pool), len(matched), len(kept)))

    print(f"{'규칙':16s} {'유형':30s} {'질문풀':>7} {'유형일치':>8} {'수록':>6}")
    for rule_id, rule_type, pool, matched_count, kept_count in report:
        print(f"{rule_id:16s} {rule_type:30s} {pool:>7,} {matched_count:>8,} {kept_count:>6,}")
    print(
        f"\n유형일치 고유 논문 {len(matched_papers):,}편 · "
        f"규칙×논문 {rule_paper_pairs:,}쌍 · 규칙×질문×논문 {rule_question_rows:,}행"
    )
    print(f"화면 수록 고유 논문 {len(listed_papers):,}편 (규칙당 상한 {MAX_PER_RULE})")

    if len(matched_papers) != EXPECTED_UNIQUE_PAPERS:
        raise SystemExit(
            f"유형일치 고유 논문이 {len(matched_papers):,}편입니다. "
            f"확정값 {EXPECTED_UNIQUE_PAPERS:,}편과 다릅니다. 입력이나 도출식을 확인하십시오."
        )

    payload = {
        "schema_version": "1.0.0",
        "track": "recollect-v2",
        "study": "kwon",
        "tier": "screening_passed_literature",
        "authority": {
            "supports_rule_release": False,
            "evidence_authority": "literature_explanatory_only",
            "quote_verified": False,
            "human_expert_reviewed": 0,
        },
        "purpose": (
            "검증 근거(규칙 9개·링크 10건) 아래 층. 규칙이 허용한 질문에서 재수집 트랙 선별이 "
            "유지로 판정하고, 규칙 유형의 위해 표현이 제목·초록에 나타나는 문헌이다. "
            "문장 locator 와 원문 인용 대조를 거치지 않았으므로 검증 근거와 지위가 다르다."
        ),
        "derivation": {
            "step_1": "규칙의 allowed_question_ids 에서 decision=retain 인 레코드",
            "step_2": "규칙 유형의 위해 표현이 title+abstract 에 나타나는 레코드",
            "ordering": "제목 일치 우선, 초록 있음, 표현 히트 수, 그다음 최신 출판연도",
            "step_3": (
                "규칙 관점에서 초록의 인용 문장을 고른다. v3.0 build_site_v3 의 "
                "split_sentences·choose_key_finding 과 같은 점수식이며, 질문별 결과 용어 "
                "자리에 규칙 유형의 위해 표현을 넣는다"
            ),
            "per_rule_cap": MAX_PER_RULE,
            "cap_note": (
                "상한은 화면 페이징과 전송량 때문이다. 도출 자체는 자르지 않으며 "
                "자른 수는 규칙마다 truncated 에 남는다"
            ),
            "deterministic": True,
            "language_model_calls": 0,
            "same_as": "scripts/research/otc/build_rule_literature_pool.py (표현·점수식을 import)",
        },
        "inputs": {
            "decisions": {
                "path": str(DECISIONS),
                "sha256": sha256_file(DECISIONS),
                "rows": decision_rows,
            },
            "evidence_map": {"path": str(CORPUS), "sha256": sha256_file(CORPUS)},
            "link_manifest": {
                "path": "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
                "sha256": sha256_file(MANIFEST),
                "note": "봉인한 v5.0 산출물. 규칙이 허용한 질문만 읽는다",
            },
        },
        "rule_type_patterns": RULE_TYPE_PATTERNS,
        "rule_type_context_patterns": RULE_TYPE_CONTEXT,
        "profile_facets": [name for name, _ in PROFILE_FACETS],
        "ingredient_terms": [name for name, _ in INGREDIENT_TERMS],
        "totals": {
            "rules": len(out_rules),
            "unique_papers_matched": len(matched_papers),
            "rule_paper_pairs": rule_paper_pairs,
            "rule_question_paper_rows": rule_question_rows,
            "unique_papers_listed": len(listed_papers),
            "quotable_sentences": sum(
                len(r["quotes"]) for r in out_rules.values()  # type: ignore[index]
            ),
            "title_only_quotes": sum(
                1
                for r in out_rules.values()
                for q in r["quotes"].values()  # type: ignore[index,union-attr]
                if q["locator"] == "TITLE"
            ),
            "retain_rows_in_corpus": sum(len(v) for v in retain.values()),
            "retain_papers_in_corpus": len(set().union(*retain.values())) if retain else 0,
        },
        "rules": out_rules,
        "papers": {r: papers[r] for r in sorted(listed_papers)},
    }

    if args.check:
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"-> {TARGET.relative_to(ROOT)}  ({TARGET.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
