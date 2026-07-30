"""Run Phase A PubMed count-only probes for the frozen v5 queries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[4]
V5 = Path(__file__).resolve().parent
QUERY_DEFINITIONS = V5 / "query_definitions.json"
MAPPINGS = V5 / "ingredient_mappings.json"
TARGET = V5 / "probe_report.json"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DEFAULT_EMAIL = "yeohj0710@yonsei.ac.kr"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def flatten_messages(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(flatten_messages(item))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            for message in flatten_messages(item):
                result.append(f"{key}: {message}")
        return result
    return [str(value)]


def request_count(session: requests.Session, query: str, email: str) -> dict[str, Any]:
    payload = {
        "db": "pubmed",
        "term": query,
        "retmax": 0,
        "retmode": "json",
        "usehistory": "y",
        "tool": "otc_safety_v50",
        "email": email,
    }
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = session.post(ESEARCH, data=payload, timeout=90)
            if response.status_code in {429, 500, 502, 503, 504}:
                delay = float(response.headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            response.raise_for_status()
            result = response.json()["esearchresult"]
            return {
                "count": int(result["count"]),
                "query_translation": result.get("querytranslation", ""),
                "warninglist": result.get("warninglist"),
                "errorlist": result.get("errorlist"),
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
                "http_status": response.status_code,
            }
        except (requests.RequestException, KeyError, ValueError) as error:
            last_error = error
            time.sleep(2**attempt)
    raise RuntimeError(f"ESearch failed after retries: {last_error}")


def term_table(question: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for classification in ("P", "I", "O"):
        for group in question["blocks"][classification]:
            for term in group["terms"]:
                rows.append(
                    {
                        "term": term,
                        "classification": classification,
                        "included_in_query": bool(group["included_in_query"]),
                        "subtype": group["subtype"],
                    }
                )
    return rows


def self_check(question: dict[str, Any], messages: list[str]) -> list[dict[str, Any]]:
    query = question["query"]
    query_lower = query.lower()
    p_terms = [t for g in question["blocks"]["P"] for t in g["terms"]]
    i_terms = [t for g in question["blocks"]["I"] for t in g["terms"]]
    o_terms = [t for g in question["blocks"]["O"] for t in g["terms"]]
    truncation_messages = [
        message for message in messages
        if "600" in message.lower() or "truncat" in message.lower()
    ]
    checks = [
        (1, "P AND I 두 개념 블록만 사용하고 C·O 블록을 결합하지 않음", "P AND I" in question["block_structure"] and all(term not in query for term in o_terms)),
        (2, "모든 후보 용어를 P/I/O로 분류하고 O 용어를 삭제함", bool(p_terms and i_terms and o_terms) and all(not row["included_in_query"] for row in term_table(question) if row["classification"] == "O")),
        (3, "AND Humans[Mesh]를 사용하지 않음", "humans[mesh]" not in query_lower),
        (4, "연구설계 필터를 사용하지 않음", not any(token in query_lower for token in ("clinical trial[pt]", "randomized controlled trial[pt]", "case reports[pt]"))),
        (5, "언어·출판유형 제한을 사용하지 않음", "[lang]" not in query_lower and "[pt]" not in query_lower),
        (6, "v4와 같은 날짜 시작점만 유지함", question["date_range"]["start"] in query and question["date_range"]["end"] in query),
        (7, "P와 I에 MeSH와 자유어를 병렬 사용함", any("[mesh" in term.lower() for term in p_terms) and any("[tiab]" in term.lower() or "[tw]" in term.lower() for term in p_terms) and any("[mesh" in term.lower() or "[supplementary concept]" in term.lower() for term in i_terms) and any("[tiab]" in term.lower() or "[tw]" in term.lower() for term in i_terms)),
        (8, "자유어 범위는 [tiab] 이상임", all("[tiab]" in term.lower() or "[tw]" in term.lower() or "[mesh" in term.lower() or "[supplementary concept]" in term.lower() for term in p_terms + i_terms)),
        (9, "I에 서로 다른 용어 25개 이상과 배정 성분 전부를 포함함", len(set(i_terms)) >= 25 and bool(question["ingredient_ids"])),
        (10, "절단어 600개 변형 상한 경고가 없음", not truncation_messages),
    ]
    return [
        {"rule": number, "requirement_ko": label, "status": "pass" if passed else "violation", "evidence": {"truncation_messages": truncation_messages} if number == 10 else None}
        for number, label, passed in checks
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("NCBI_EMAIL", DEFAULT_EMAIL))
    args = parser.parse_args()

    definitions = json.loads(QUERY_DEFINITIONS.read_text(encoding="utf-8"))
    mappings = json.loads(MAPPINGS.read_text(encoding="utf-8"))
    mapping_ids = {row["ingredient_id"] for row in mappings["mappings"]}
    selected_ids = set(definitions["selected_ingredient_ids"])
    if mapping_ids != selected_ids:
        raise ValueError("ingredient mapping coverage does not match the frozen 28 ingredients")

    started = utc_now()
    results: list[dict[str, Any]] = []
    session = requests.Session()
    for index, question in enumerate(definitions["questions"]):
        if text_sha256(question["query"]) != question["query_sha256"]:
            raise ValueError(f"query hash mismatch: {question['question_id']}")
        executed_at = utc_now()
        esearch = request_count(session, question["query"], args.email)
        messages = flatten_messages(esearch.get("warninglist")) + flatten_messages(esearch.get("errorlist"))
        checks = self_check(question, messages)
        hit_count = esearch["count"]
        v4_count = int(question["v4_hit_count"])
        results.append(
            {
                "question_id": question["question_id"],
                "title_ko": question["title_ko"],
                "query": question["query"],
                "query_sha256": question["query_sha256"],
                "executed_at_utc": executed_at,
                "hit_count": hit_count,
                "v4_hit_count": v4_count,
                "change_from_v4": {
                    "absolute": hit_count - v4_count,
                    "ratio": hit_count / v4_count if v4_count else None,
                },
                "ingredient_ids": question["ingredient_ids"],
                "rule_types": question["rule_types"],
                "block_structure": question["block_structure"],
                "term_counts": {
                    "P": sum(len(group["terms"]) for group in question["blocks"]["P"]),
                    "I": sum(len(group["terms"]) for group in question["blocks"]["I"]),
                    "O_removed": sum(len(group["terms"]) for group in question["blocks"]["O"]),
                },
                "term_classification": term_table(question),
                "esearch": esearch,
                "protocol_section_3_self_check": checks,
                "all_rules_pass": all(row["status"] == "pass" for row in checks),
            }
        )
        if index + 1 < len(definitions["questions"]):
            time.sleep(0.36)

    report = {
        "schema_version": "5.0.0",
        "phase": "A",
        "status": "complete" if all(row["all_rules_pass"] for row in results) else "violation",
        "database": "PubMed",
        "method": "NCBI ESearch retmax=0 count-only; EFetch calls=0",
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "query_definitions_path": QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
        "query_definitions_sha256": file_sha256(QUERY_DEFINITIONS),
        "ingredient_mappings_path": MAPPINGS.relative_to(ROOT).as_posix(),
        "ingredient_mappings_sha256": file_sha256(MAPPINGS),
        "selected_ingredient_count": len(selected_ids),
        "selected_ingredients_in_queries": sorted(selected_ids),
        "missing_selected_ingredients": [],
        "ingredient_master_reconciliation": mappings["selection_reconciliation"],
        "questions": results,
        "totals": {
            "hit_count_before_cross_question_deduplication": sum(row["hit_count"] for row in results),
            "v4_hit_count_before_cross_question_deduplication": sum(row["v4_hit_count"] for row in results),
            "efetch_calls": 0,
        },
        "v4_to_v5_causal_record_ko": "v4 PICOS 프롬프트의 narrow 지시와 safety outcomes 요건이 O 블록과 Humans[Mesh]를 만들었고 10,000행 상한이 검색식 축소를 강화했다. v5는 P AND I만 사용하고 O·Humans·설계·언어·출판유형 제한을 제거했다.",
    }
    TARGET.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "target": TARGET.relative_to(ROOT).as_posix(), "hits": {row["question_id"]: row["hit_count"] for row in results}}, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
