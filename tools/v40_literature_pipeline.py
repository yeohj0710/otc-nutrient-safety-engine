from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LITERATURE_ROOT = ROOT / "research_v3" / "otc" / "literature"
PICOS_PATH = LITERATURE_ROOT / "picos" / "picos_definition.json"
SEARCH_LOG_PATH = LITERATURE_ROOT / "search_log.csv"
EVIDENCE_MAP_PATH = LITERATURE_ROOT / "evidence_map.csv"
PRODUCTS_PATH = ROOT / "research_v3" / "otc" / "normalized" / "product_master.csv"
INGREDIENTS_PATH = ROOT / "research_v3" / "otc" / "normalized" / "ingredient_master.csv"
BINDINGS_PATH = ROOT / "research_v3" / "otc" / "normalized" / "product_ingredient.csv"
RULES_PATH = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUTILS_TOOL = "otc_safety_v40"
EUTILS_EMAIL = "yeohj0710@yonsei.ac.kr"
MAX_REQUESTS_PER_SECOND = 3
MIN_REQUEST_INTERVAL_SECONDS = 1 / MAX_REQUESTS_PER_SECOND + 0.01
DEFAULT_TOTAL_LIMIT = 10_000
EFETCH_BATCH_SIZE = 500

PICOS_PROMPT = """You are designing the literature layer for a Korean OTC safety engine.
Inputs: the 28 ingredients selected for calculation from MFDS-authorized product records; the rule_type and scope of all 16 active rules; PubMed as the only literature database; the required JSON schema.
Do not read or reuse legacy nutrient-search queries or legacy result counts.
Create 3-6 grouped ingredient-by-harm questions. Every selected ingredient and every rule type must be represented. For each question give P, I, C, O, S, a narrow PubMed query using MeSH and title/abstract terms, and the derivation rationale. The literature can support an evidence claim but cannot override MFDS authorization facts or deterministic engine decisions. Keep factual authorization claims separate from literature evidence claims.
"""


QUESTION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "question_id": "OTC-LIT-Q01-ACETAMINOPHEN",
        "title_ko": "아세트아미노펜 용량·간격·간질환·음주 관련 위해",
        "ingredient_ids": ["ING-acetaminophen"],
        "rule_types": [
            "duplicate_ingredient",
            "max_daily_dose",
            "minimum_interval",
            "age_restriction",
            "hepatic_disease",
            "alcohol",
            "urgent_referral",
        ],
        "picos": {
            "population": "아세트아미노펜을 사용하는 성인 또는 소아",
            "intervention_or_exposure": "중복 복용, 고용량, 짧은 복용 간격, 음주 또는 간질환이 동반된 아세트아미노펜 노출",
            "comparator": "권장 용량·간격 사용 또는 해당 위험 요인이 없는 사용",
            "outcomes": "간손상, 과량복용 독성, 중대한 이상반응과 응급평가 필요성",
            "study_design": "사람 대상 관찰연구, 임상시험, 체계적 문헌고찰과 메타분석",
        },
        "query": '(("Acetaminophen"[Mesh] OR acetaminophen[tiab] OR paracetamol[tiab]) AND ("Drug Overdose"[Mesh] OR overdose[tiab] OR hepatotox*[tiab] OR "liver injury"[tiab] OR alcohol*[tiab] OR "dosing interval"[tiab] OR "daily dose"[tiab]) AND Humans[Mesh] AND ("2010/01/01"[Date - Publication] : "3000"[Date - Publication]))',
        "planning_expected_hit_range": [500, 2500],
        "derivation_rationale_ko": "허가원문에서 산출하는 용량·간격 사실과 별개로 과량, 간질환, 음주가 위해와 연관되는지 설명할 문헌을 찾는다.",
    },
    {
        "question_id": "OTC-LIT-Q02-NSAID",
        "title_ko": "이부프로펜·덱시부프로펜·나프록센의 중복과 주요 위해",
        "ingredient_ids": ["ING-dexibuprofen", "ING-ibuprofen", "ING-naproxen"],
        "rule_types": [
            "duplicate_pharmacologic_class",
            "pregnancy_lactation",
            "renal_disease",
            "gi_bleeding_ulcer",
            "anticoagulant_antiplatelet",
        ],
        "picos": {
            "population": "이부프로펜, 덱시부프로펜 또는 나프록센을 사용하는 사람",
            "intervention_or_exposure": "NSAID 중복, 임신·수유, 신장질환, 위장관 궤양·출혈 또는 항응고·항혈소판제 병용",
            "comparator": "단일 NSAID 사용 또는 해당 위험 요인이 없는 사용",
            "outcomes": "위장관 출혈, 신장 이상, 임신 관련 위해와 출혈성 이상반응",
            "study_design": "사람 대상 관찰연구, 임상시험, 체계적 문헌고찰과 메타분석",
        },
        "query": '((("Ibuprofen"[Mesh] OR ibuprofen[tiab] OR dexibuprofen[tiab] OR "Naproxen"[Mesh] OR naproxen[tiab]) AND ("Gastrointestinal Hemorrhage"[Mesh] OR "Peptic Ulcer"[Mesh] OR "Kidney Diseases"[Mesh] OR renal[tiab] OR pregnancy[tiab] OR anticoag*[tiab] OR antiplatelet*[tiab] OR "drug interaction"[tiab])) AND Humans[Mesh] AND ("2010/01/01"[Date - Publication] : "3000"[Date - Publication]))',
        "planning_expected_hit_range": [800, 3500],
        "derivation_rationale_ko": "세 NSAID를 한 계열로 묶고 규칙이 다루는 위장관·신장·임신·항응고 위험을 동시에 포착한다.",
    },
    {
        "question_id": "OTC-LIT-Q03-COLD-ALLERGY",
        "title_ko": "감기·알레르기 복합성분의 진정·운전·혈압·병용 위해",
        "ingredient_ids": [
            "ING-cetirizine_hydrochloride",
            "ING-chlorpheniramine_maleate",
            "ING-mf-src-41c782105274",
            "ING-mf-src-4b985f9d3bdb",
            "ING-mf-src-cd3363b1ac1f",
            "ING-mf-src-dc293e7de142",
        ],
        "rule_types": [
            "sedation_driving",
            "sedative_medication",
            "decongestant_hypertension",
            "maximum_duration",
        ],
        "picos": {
            "population": "항히스타민제, 비충혈제거제, 진해거담제 또는 카페인이 포함된 일반의약품을 사용하는 사람",
            "intervention_or_exposure": "클로르페니라민·세티리진·페닐레프린·펜톡시베린·구아이페네신·카페인 단독 또는 복합 노출",
            "comparator": "비진정성 대안, 비노출 또는 위험 병용이 없는 사용",
            "outcomes": "졸림과 운전 수행, 진정제 상호작용, 혈압·심혈관 이상과 지속 사용 위해",
            "study_design": "사람 대상 약물역학·운전수행 연구, 임상시험, 체계적 문헌고찰",
        },
        "query": '((("Chlorpheniramine"[Mesh] OR chlorpheniramine[tiab] OR "Cetirizine"[Mesh] OR cetirizine[tiab] OR "Phenylephrine"[Mesh] OR phenylephrine[tiab] OR pentoxyverine[tiab] OR guaifenesin[tiab] OR caffeine[tiab]) AND (sedat*[tiab] OR drows*[tiab] OR driving[tiab] OR psychomotor[tiab] OR hypertension[tiab] OR cardiovascular[tiab] OR "drug interaction"[tiab])) AND Humans[Mesh] AND ("2010/01/01"[Date - Publication] : "3000"[Date - Publication]))',
        "planning_expected_hit_range": [300, 1800],
        "derivation_rationale_ko": "판콜에이와 판피린티, 지르텍의 실제 복합성분에서 운전·진정제·고혈압 규칙을 설명할 문헌을 찾는다.",
    },
    {
        "question_id": "OTC-LIT-Q04-DIGESTIVE",
        "title_ko": "소화효소·담즙산·가스제거 성분 복합 사용의 안전성",
        "ingredient_ids": [
            "ING-mf-src-0546ff64775e",
            "ING-mf-src-06cdde4eaaee",
            "ING-mf-src-484bf5816144",
            "ING-mf-src-5abce34aadf5",
            "ING-mf-src-7ace07a0f45d",
            "ING-mf-src-7ae387262216",
            "ING-mf-src-8f38da8a73d0",
            "ING-mf-src-a5c9920bea02",
            "ING-mf-src-a742c02533bc",
            "ING-mf-src-d33c06bc01c8",
            "ING-mf-src-d75c9c1aefc3",
            "ING-mf-src-db4cde0b063f",
            "ING-mf-src-ea4c014f0616",
        ],
        "rule_types": ["duplicate_ingredient", "maximum_duration"],
        "picos": {
            "population": "소화효소, 시메티콘, 우르소데옥시콜산 또는 브로멜라인 함유 제품을 사용하는 사람",
            "intervention_or_exposure": "판크레아틴·디아스타제·프로테아제·셀룰라제·리파제·브로멜라인·시메티콘·우르소데옥시콜산 단독 또는 복합 노출",
            "comparator": "비노출, 위약 또는 더 짧은 사용",
            "outcomes": "이상반응, 알레르기, 출혈성 상호작용과 장기·중복 사용 안전성",
            "study_design": "사람 대상 임상시험, 관찰연구와 체계적 문헌고찰",
        },
        "query": '((((pancreatin[tiab] OR pancrelipase[tiab] OR "digestive enzyme"[tiab] OR "fungal diastase"[tiab] OR bromelain[tiab] OR "Simethicone"[Mesh] OR simethicone[tiab] OR "Ursodeoxycholic Acid"[Mesh] OR ursodeoxycholic[tiab]) AND (oral[tiab] OR dyspepsia[tiab] OR gastrointestinal[tiab] OR "pancreatic insufficiency"[tiab])) AND ("Drug-Related Side Effects and Adverse Reactions"[Mesh] OR "adverse effect"[tiab] OR "adverse effects"[tiab] OR safety[Title] OR allergy[tiab] OR bleeding[tiab] OR "drug interaction"[tiab] OR "drug interactions"[tiab])) AND Humans[Mesh] AND ("2000/01/01"[Date - Publication] : "3000"[Date - Publication]))',
        "planning_expected_hit_range": [100, 1500],
        "derivation_rationale_ko": "베아제·닥터베아제·훼스탈 제품군의 실제 13개 소화 관련 성분을 일반명 묶음으로 검색한다.",
    },
    {
        "question_id": "OTC-LIT-Q05-TOPICAL",
        "title_ko": "살리실산메틸·멘톨·캄파 등 외용 복합성분의 위해",
        "ingredient_ids": [
            "ING-mf-src-25b653f7fbe2",
            "ING-mf-src-4a3225f1eb5d",
            "ING-mf-src-76b6b5a5a31f",
            "ING-mf-src-8bebf0ac75f4",
            "ING-mf-src-e2b868294a4f",
        ],
        "rule_types": ["age_restriction", "anticoagulant_antiplatelet", "urgent_referral"],
        "picos": {
            "population": "살리실산메틸, 멘톨, 캄파, 박하유 또는 티몰 외용제를 사용하는 사람",
            "intervention_or_exposure": "외용 복합성분의 반복·과량 사용, 소아 노출 또는 항응고제 병용",
            "comparator": "권장 외용 사용 또는 비노출",
            "outcomes": "전신 살리실산 독성, 피부 이상반응, 소아 중독과 출혈 위험",
            "study_design": "사람 대상 독성·약물감시·관찰연구와 체계적 문헌고찰",
        },
        "query": '((("Methyl Salicylate"[Mesh] OR "methyl salicylate"[tiab] OR menthol[tiab] OR camphor[tiab] OR "peppermint oil"[tiab] OR thymol[tiab]) AND (poison*[tiab] OR toxic*[tiab] OR adverse[tiab] OR dermal[tiab] OR child*[tiab] OR anticoag*[tiab] OR bleeding[tiab])) AND Humans[Mesh] AND ("2000/01/01"[Date - Publication] : "3000"[Date - Publication]))',
        "planning_expected_hit_range": [100, 1200],
        "derivation_rationale_ko": "제일쿨파프의 실제 외용 성분에 대해 소아·과량·상호작용 위해를 설명할 문헌을 찾는다.",
    },
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def input_snapshot() -> dict[str, Any]:
    products = [row for row in read_csv(PRODUCTS_PATH) if row["analysis_status"] == "included"]
    selected_bindings = [
        row for row in read_csv(BINDINGS_PATH) if row["selected_for_calculation"] == "true"
    ]
    ingredient_rows = {row["ingredient_id"]: row for row in read_csv(INGREDIENTS_PATH)}
    rules = read_csv(RULES_PATH)
    ingredient_ids = sorted({row["ingredient_id"] for row in selected_bindings})
    snapshot = {
        "products": [
            {"product_id": row["product_id"], "product_name": row["product_name"]}
            for row in products
        ],
        "ingredients": [
            {
                "ingredient_id": ingredient_id,
                "preferred_name_ko": ingredient_rows[ingredient_id]["preferred_name_ko"],
                "preferred_name_en": ingredient_rows[ingredient_id]["preferred_name_en"],
            }
            for ingredient_id in ingredient_ids
        ],
        "rules": [
            {
                "rule_id": row["rule_id"],
                "rule_type": row["rule_type"],
                "scope": row["scope"],
            }
            for row in rules
        ],
        "source_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (PRODUCTS_PATH, INGREDIENTS_PATH, BINDINGS_PATH, RULES_PATH)
        },
    }
    return snapshot


def validate_question_coverage(snapshot: dict[str, Any], questions: Iterable[dict[str, Any]]) -> None:
    questions = list(questions)
    if not 3 <= len(questions) <= 6:
        raise ValueError("PICOS 질문 수는 3~6개여야 합니다.")
    expected_ingredients = {row["ingredient_id"] for row in snapshot["ingredients"]}
    actual_ingredients = {
        ingredient_id for question in questions for ingredient_id in question["ingredient_ids"]
    }
    expected_rule_types = {row["rule_type"] for row in snapshot["rules"]}
    actual_rule_types = {rule_type for question in questions for rule_type in question["rule_types"]}
    if expected_ingredients != actual_ingredients:
        raise ValueError(
            f"성분 범위 불일치: missing={sorted(expected_ingredients - actual_ingredients)}, "
            f"extra={sorted(actual_ingredients - expected_ingredients)}"
        )
    if expected_rule_types - actual_rule_types:
        raise ValueError(f"규칙 유형 누락: {sorted(expected_rule_types - actual_rule_types)}")
    for question in questions:
        query = question["query"]
        if "[Mesh]" not in query or "[tiab]" not in query:
            raise ValueError(f"MeSH와 tiab가 모두 필요합니다: {question['question_id']}")


def build_picos() -> dict[str, Any]:
    snapshot = input_snapshot()
    questions = [dict(question) for question in QUESTION_SPECS]
    validate_question_coverage(snapshot, questions)
    prompt_hash = sha256_bytes(PICOS_PROMPT.encode("utf-8"))
    manifest = {
        "schema_version": "1.0.0",
        "generated_at_utc": utc_now(),
        "execution_mode": "agent_local",
        "database": "PubMed",
        "human_decisions": 0,
        "legacy_query_inputs_used": False,
        "prompt": PICOS_PROMPT,
        "prompt_sha256": prompt_hash,
        "input_snapshot": snapshot,
        "input_sha256": canonical_sha256(snapshot),
        "questions": questions,
    }
    PICOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PICOS_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


class RateLimitedEutils:
    def __init__(self) -> None:
        self._last_request = 0.0

    def get(self, endpoint: str, params: dict[str, str | int]) -> tuple[bytes, str, str]:
        params = {**params, "tool": EUTILS_TOOL, "email": EUTILS_EMAIL}
        url = f"{EUTILS_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(1, 4):
            wait_seconds = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - self._last_request)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            requested_at = utc_now()
            try:
                request = urllib.request.Request(url, headers={"User-Agent": f"{EUTILS_TOOL}/1.0 ({EUTILS_EMAIL})"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read()
                self._last_request = time.monotonic()
                return content, url, requested_at
            except Exception as error:  # pragma: no cover - network failure path
                self._last_request = time.monotonic()
                last_error = error
                if attempt < 3:
                    time.sleep(attempt)
        raise RuntimeError(f"E-utilities 요청 3회 실패: {url}") from last_error


def xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def parse_esearch(content: bytes) -> dict[str, Any]:
    root = ET.fromstring(content)
    error = root.findtext("ERROR")
    if error:
        raise ValueError(f"ESearch 오류: {error}")
    return {
        "count": int(root.findtext("Count", "0")),
        "query_key": root.findtext("QueryKey", ""),
        "webenv": root.findtext("WebEnv", ""),
        "translated_query": root.findtext("QueryTranslation", ""),
    }


def parse_pubmed_xml(content: bytes, question_id: str) -> list[dict[str, Any]]:
    root = ET.fromstring(content)
    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        citation = article.find("MedlineCitation")
        if citation is None:
            continue
        pmid = xml_text(citation.find("PMID"))
        article_node = citation.find("Article")
        if not pmid or article_node is None:
            continue
        abstract_parts = []
        for part in article_node.findall("Abstract/AbstractText"):
            label = part.attrib.get("Label", "").strip()
            value = xml_text(part)
            abstract_parts.append(f"{label}: {value}" if label and value else value)
        journal = xml_text(article_node.find("Journal/Title"))
        year = (
            xml_text(article_node.find("Journal/JournalIssue/PubDate/Year"))
            or xml_text(article_node.find("Journal/JournalIssue/PubDate/MedlineDate"))[:4]
        )
        doi = ""
        for article_id in article.findall("PubmedData/ArticleIdList/ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                doi = xml_text(article_id)
                break
        records.append(
            {
                "pmid": pmid,
                "title": xml_text(article_node.find("ArticleTitle")),
                "abstract": " ".join(part for part in abstract_parts if part),
                "journal": journal,
                "publication_year": year,
                "doi": doi,
                "publication_types": sorted(
                    {xml_text(node) for node in article_node.findall("PublicationTypeList/PublicationType") if xml_text(node)}
                ),
                "mesh_terms": sorted(
                    {xml_text(node.find("DescriptorName")) for node in citation.findall("MeshHeadingList/MeshHeading") if xml_text(node.find("DescriptorName"))}
                ),
                "question_ids": [question_id],
            }
        )
    return records


def normalize_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        pmid = record["pmid"]
        if pmid not in merged:
            merged[pmid] = dict(record)
            continue
        existing = merged[pmid]
        existing["question_ids"] = sorted(set(existing["question_ids"]) | set(record["question_ids"]))
        existing["publication_types"] = sorted(
            set(existing["publication_types"]) | set(record["publication_types"])
        )
        existing["mesh_terms"] = sorted(set(existing["mesh_terms"]) | set(record["mesh_terms"]))
        if not existing["abstract"] and record["abstract"]:
            existing["abstract"] = record["abstract"]
    return sorted(merged.values(), key=lambda row: int(row["pmid"]))


def write_checksum(directory: Path, files: Iterable[Path]) -> None:
    lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(files, key=lambda item: item.name)]
    (directory / "checksum.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_search_log(rows: Iterable[dict[str, Any]]) -> None:
    fieldnames = [
        "question_id",
        "run_id",
        "executed_at_utc",
        "query_sha256",
        "hit_count",
        "fetched_count",
        "status",
        "total_hit_limit",
        "notes",
    ]
    existing: list[dict[str, str]] = read_csv(SEARCH_LOG_PATH) if SEARCH_LOG_PATH.exists() else []
    combined = [*existing, *rows]
    SEARCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SEARCH_LOG_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined)


def write_evidence_map(records: list[dict[str, Any]], input_hash: str) -> None:
    fieldnames = [
        "record_id",
        "pmid",
        "title",
        "abstract",
        "has_abstract",
        "journal",
        "publication_year",
        "doi",
        "publication_types",
        "mesh_terms",
        "question_ids",
        "source_database",
        "input_sha256",
    ]
    EVIDENCE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MAP_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "record_id": f"PMID-{record['pmid']}",
                    "pmid": record["pmid"],
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "has_abstract": str(bool(record["abstract"])).lower(),
                    "journal": record["journal"],
                    "publication_year": record["publication_year"],
                    "doi": record["doi"],
                    "publication_types": ";".join(record["publication_types"]),
                    "mesh_terms": ";".join(record["mesh_terms"]),
                    "question_ids": ";".join(record["question_ids"]),
                    "source_database": "PubMed",
                    "input_sha256": input_hash,
                }
            )


def run_search(total_limit: int = DEFAULT_TOTAL_LIMIT) -> dict[str, Any]:
    if not PICOS_PATH.exists():
        build_picos()
    picos = json.loads(PICOS_PATH.read_text(encoding="utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client = RateLimitedEutils()
    searches: list[dict[str, Any]] = []

    for question in picos["questions"]:
        directory = LITERATURE_ROOT / "searches" / question["question_id"] / run_id
        directory.mkdir(parents=True, exist_ok=False)
        query = question["query"]
        (directory / "query.txt").write_text(query + "\n", encoding="utf-8")
        content, url, requested_at = client.get(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmax": 0, "usehistory": "y", "retmode": "xml"},
        )
        esearch_path = directory / "esearch.xml"
        esearch_path.write_bytes(content)
        parsed = parse_esearch(content)
        searches.append(
            {
                "question": question,
                "directory": directory,
                "esearch_path": esearch_path,
                "esearch_url": url,
                "esearch_requested_at_utc": requested_at,
                **parsed,
            }
        )

    total_hits = sum(search["count"] for search in searches)
    if total_hits > total_limit:
        log_rows = []
        for search in searches:
            metadata = {
                "question_id": search["question"]["question_id"],
                "run_id": run_id,
                "status": "counted_not_fetched_total_limit_exceeded",
                "query": search["question"]["query"],
                "query_sha256": sha256_bytes(search["question"]["query"].encode("utf-8")),
                "hit_count": search["count"],
                "translated_query": search["translated_query"],
                "esearch_url": search["esearch_url"],
                "esearch_requested_at_utc": search["esearch_requested_at_utc"],
                "total_hits_all_questions": total_hits,
                "total_hit_limit": total_limit,
            }
            (search["directory"] / "response_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            write_checksum(search["directory"], [search["esearch_path"]])
            log_rows.append(
                {
                    "question_id": search["question"]["question_id"],
                    "run_id": run_id,
                    "executed_at_utc": search["esearch_requested_at_utc"],
                    "query_sha256": metadata["query_sha256"],
                    "hit_count": search["count"],
                    "fetched_count": 0,
                    "status": metadata["status"],
                    "total_hit_limit": total_limit,
                    "notes": f"all_questions_total={total_hits}",
                }
            )
        append_search_log(log_rows)
        raise RuntimeError(f"총 PubMed hit {total_hits}건이 상한 {total_limit}건을 초과했습니다.")

    all_records: list[dict[str, Any]] = []
    log_rows = []
    for search in searches:
        response_files = [search["esearch_path"]]
        request_metadata = []
        fetched = 0
        for start in range(0, search["count"], EFETCH_BATCH_SIZE):
            content, url, requested_at = client.get(
                "efetch.fcgi",
                {
                    "db": "pubmed",
                    "query_key": search["query_key"],
                    "WebEnv": search["webenv"],
                    "retstart": start,
                    "retmax": EFETCH_BATCH_SIZE,
                    "rettype": "abstract",
                    "retmode": "xml",
                },
            )
            path = search["directory"] / f"efetch_{start // EFETCH_BATCH_SIZE + 1:04d}.xml"
            path.write_bytes(content)
            parsed_records = parse_pubmed_xml(content, search["question"]["question_id"])
            all_records.extend(parsed_records)
            fetched += len(parsed_records)
            response_files.append(path)
            request_metadata.append(
                {
                    "file": path.name,
                    "requested_at_utc": requested_at,
                    "url": url,
                    "bytes": len(content),
                    "sha256": sha256_bytes(content),
                    "parsed_records": len(parsed_records),
                }
            )
        status = "complete" if fetched == search["count"] else "incomplete_count_mismatch"
        metadata = {
            "question_id": search["question"]["question_id"],
            "run_id": run_id,
            "status": status,
            "query": search["question"]["query"],
            "query_sha256": sha256_bytes(search["question"]["query"].encode("utf-8")),
            "hit_count": search["count"],
            "fetched_count": fetched,
            "translated_query": search["translated_query"],
            "esearch_url": search["esearch_url"],
            "esearch_requested_at_utc": search["esearch_requested_at_utc"],
            "efetch_batch_size": EFETCH_BATCH_SIZE,
            "requests": request_metadata,
            "total_hits_all_questions": total_hits,
            "total_hit_limit": total_limit,
            "rate_limit_requests_per_second": MAX_REQUESTS_PER_SECOND,
            "tool": EUTILS_TOOL,
            "email": EUTILS_EMAIL,
        }
        (search["directory"] / "response_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_checksum(search["directory"], response_files)
        log_rows.append(
            {
                "question_id": search["question"]["question_id"],
                "run_id": run_id,
                "executed_at_utc": search["esearch_requested_at_utc"],
                "query_sha256": metadata["query_sha256"],
                "hit_count": search["count"],
                "fetched_count": fetched,
                "status": status,
                "total_hit_limit": total_limit,
                "notes": "",
            }
        )

    if any(row["status"] != "complete" for row in log_rows):
        append_search_log(log_rows)
        raise RuntimeError("한 개 이상의 PubMed 검색에서 ESearch와 EFetch 건수가 다릅니다.")

    normalized = normalize_records(all_records)
    corpus_input = {
        "picos_sha256": sha256_file(PICOS_PATH),
        "search_run_id": run_id,
        "raw_response_sha256": sorted(
            sha256_file(path)
            for search in searches
            for path in search["directory"].glob("*.xml")
        ),
    }
    corpus_input_hash = canonical_sha256(corpus_input)
    write_evidence_map(normalized, corpus_input_hash)
    append_search_log(log_rows)

    for question in picos["questions"]:
        matching = next(row for row in log_rows if row["question_id"] == question["question_id"])
        question["observed_hit_count"] = int(matching["hit_count"])
        question["observed_run_id"] = run_id
    picos["last_search"] = {
        "run_id": run_id,
        "total_hits_before_deduplication": total_hits,
        "unique_pmids": len(normalized),
        "evidence_map_sha256": sha256_file(EVIDENCE_MAP_PATH),
        "corpus_input_sha256": corpus_input_hash,
    }
    PICOS_PATH.write_text(json.dumps(picos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return picos["last_search"]


def main() -> None:
    parser = argparse.ArgumentParser(description="v4.0 OTC PubMed 문헌 근거층 파이프라인")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("design", help="AI PICOS 정의와 입력 해시를 생성합니다.")
    search_parser = subparsers.add_parser("search", help="ESearch 후 상한을 확인하고 EFetch를 실행합니다.")
    search_parser.add_argument("--total-limit", type=int, default=DEFAULT_TOTAL_LIMIT)
    args = parser.parse_args()
    if args.command == "design":
        result = build_picos()
        print(json.dumps({"questions": len(result["questions"]), "prompt_sha256": result["prompt_sha256"]}))
    else:
        print(json.dumps(run_search(args.total_limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
