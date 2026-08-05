"""규칙↔문헌 연결표를 사이트 런타임 JSON 으로 굽는다.

입력은 `research_v3/otc/rules/supporting_literature.csv` (규칙 1건 × 논문 1편 = 1행)와
`research_v51/literature/link_classification.csv`이고, 출력은 논문 단위로 묶은
`src/generated/otc-supporting-literature.json` 이다. 기존 20개 연결은 감사 계보로 모두
보존하되 v5.1 분류가 결과 화면에서 제외·배경·조건부 직접 일치를 결정하게 한다.

문헌은 판정 권한이 없다. 모든 행의 `supports_rule_release` 는 false 여야 하며, 규칙 배포
근거는 `rules.csv` 의 `source_id`·`source_locator`(허가원문)만이다. 이 스크립트는 그 경계를
검증하고, locator 가 가리키는 초록 문장이 실제 초록과 같은지도 다시 확인한다.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.literature_locator import parse_locator, sentence_at  # noqa: E402

SOURCE = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
TARGET = ROOT / "src" / "generated" / "otc-supporting-literature.json"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
EVIDENCE_MAP = ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"

V50_LINKS = (
    ROOT / "research_v3" / "otc" / "literature" / "v5" / "downstream" / "supporting_literature.csv"
)
# 미검증 사유는 추정하지 않고 v5.0 하류 매니페스트가 기록한 값을 그대로 쓴다.
# 출판연도로 사유를 유추하던 이전 방식은 AM-OTC-004 로 폐기했다. v5.0 검색 기간은
# 질문별로 2010-01-01(Q01~Q03) 또는 2000-01-01(Q04~Q05)이고 코퍼스 출판연도 범위는
# 2000~2026 이라, 기간 때문에 빠진 후보는 한 편도 없다.
V50_MANIFEST = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "downstream"
    / "literature_link_manifest.json"
)
V51_CLASSIFICATIONS = (
    ROOT / "research_v51" / "literature" / "link_classification.csv"
)
V50_REASON_LABELS = {
    "not_in_v5_corpus": "v5.0 코퍼스에 없음(검색식 미인출)",
    "no_retain_decision_for_rule_question": "v5.0 코퍼스에 있으나 해당 질문에서 retain 아님",
}

REVIEW_STATUS = "agent_curated_from_v40_retained_corpus"
EVIDENCE_AUTHORITY = "literature_explanatory_only"
DISCLAIMER_KO = "참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지 않습니다."
EVIDENCE_RELATIONS = {"supports_caution", "contextualizes_uncertainty", "supports_mechanism"}
AUTHORIZATION_ALIGNMENTS = {"consistent", "conflict"}
V51_SEMANTIC_CLASSIFICATIONS = {
    "direct_match",
    "background_context",
    "mixed_scope",
}
V51_UI_POLICIES = {
    "direct",
    "background_only",
    "direct_when_scope_matches_else_background",
    "exclude_from_result_ui",
}
# 사용자 프로파일 축. 판정 카드에서 문헌을 걸러내는 데 쓴다.
PROFILE_CONDITIONS = {
    "pregnant",
    "lactating",
    "liverDisease",
    "kidneyDisease",
    "giBleedingOrUlcer",
    "hypertensionOrCardiovascularDisease",
    "willDrive",
    "alcohol",
    "medications",
    "ageYears",
    "redFlagSymptoms",
}
# 복용 입력 축. 프로파일이 아니라 제품 입력이라 필터에 쓰지 않고 표시만 한다.
DOSE_INPUT_CONDITIONS = {"hoursSincePreviousDose", "continuousDays"}


def _v50_verified_pmids() -> set[str]:
    """v5.0 선별 판정으로 실제 검증된 링크의 PMID 집합.

    파일이 없으면 빈 집합을 돌려주고, 그 경우 모든 문헌이 unverified 로 표시된다.
    조용히 verified 로 넘기지 않는다.
    """
    if not V50_LINKS.exists():
        return set()
    out: set[str] = set()
    for row in _rows(V50_LINKS):
        pmid = (row.get("pmid") or row.get("﻿pmid") or "").strip()
        if pmid:
            out.add(pmid)
    return out


def _v50_rejection_reasons() -> dict[str, str]:
    """v5.0 검증을 통과하지 못한 후보의 PMID → 사유.

    매니페스트가 없으면 빈 사전을 돌려주고, 그 경우 미검증 문헌의 사유는 unknown 이 된다.
    사유를 출판연도로 추정하지 않는다.
    """
    if not V50_MANIFEST.exists():
        return {}
    data = json.loads(V50_MANIFEST.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for entry in data.get("results", {}).get("rejected_candidates", []):
        pmid = str(entry.get("candidate_pmid") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        if not pmid or not reason:
            continue
        if pmid in out and out[pmid] != reason:
            raise SystemExit(f"PMID {pmid} 의 미검증 사유가 서로 다르다: {out[pmid]} vs {reason}")
        out[pmid] = reason
    return out


_V50_VERIFIED: set[str] | None = None
_V50_REJECTED: dict[str, str] | None = None


def _v50_validation(pmid: str) -> dict[str, object]:
    """이 문헌이 v5.0 선별로 검증됐는지, 아니면 왜 검증되지 못했는지.

    규칙 16개 중 9개만 문헌이 연결됐고 연결은 10건이다. 나머지가 왜 빠졌는지를
    화면에서 감추지 않는다. 사유는 v5.0 하류 매니페스트가 기록한 값 그대로다.
    """
    global _V50_VERIFIED, _V50_REJECTED
    if _V50_VERIFIED is None:
        _V50_VERIFIED = _v50_verified_pmids()
    if _V50_REJECTED is None:
        _V50_REJECTED = _v50_rejection_reasons()
    if pmid in _V50_VERIFIED:
        return {"screened": True, "reason": None, "labelKo": "v5.0 선별 검증"}
    reason = _V50_REJECTED.get(pmid)
    if reason is None:
        return {"screened": False, "reason": "unknown", "labelKo": "v5.0 검증 기록 없음"}
    return {
        "screened": False,
        "reason": reason,
        "labelKo": V50_REASON_LABELS.get(reason, f"v5.0 미검증({reason})"),
    }


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_bool(value: str, *, field: str, row_id: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{row_id}: {field} must be true or false")


def _v51_classifications() -> dict[str, dict[str, object]]:
    """v5.1 의미 분류를 원래 문헌 연결 ID별 런타임 메타데이터로 읽는다."""
    classifications: dict[str, dict[str, object]] = {}
    for row in _rows(V51_CLASSIFICATIONS):
        classification_id = row["classification_id"].strip()
        source_link_id = row["source_link_id"].strip()
        if not classification_id or not source_link_id:
            raise ValueError("v5.1 literature classification is missing an id")
        if source_link_id in classifications:
            raise ValueError(f"duplicate v5.1 classification for {source_link_id}")

        semantic = row["semantic_classification"].strip() or None
        if semantic is not None and semantic not in V51_SEMANTIC_CLASSIFICATIONS:
            raise ValueError(
                f"{classification_id}: invalid semantic classification {semantic}"
            )
        ui_policy = row["ui_policy"].strip()
        if ui_policy not in V51_UI_POLICIES:
            raise ValueError(f"{classification_id}: invalid UI policy {ui_policy}")

        human_reviewed = _parse_bool(
            row["human_expert_reviewed"],
            field="human_expert_reviewed",
            row_id=classification_id,
        )
        supports_release = _parse_bool(
            row["supports_rule_release"],
            field="supports_rule_release",
            row_id=classification_id,
        )
        direct_label_allowed = _parse_bool(
            row["ui_direct_label_allowed"],
            field="ui_direct_label_allowed",
            row_id=classification_id,
        )
        if human_reviewed or supports_release:
            raise ValueError(
                f"{classification_id}: v5.1 literature cannot claim expert review or rule-release authority"
            )
        if ui_policy == "exclude_from_result_ui" and direct_label_allowed:
            raise ValueError(
                f"{classification_id}: excluded literature cannot allow a direct label"
            )

        def split(field: str) -> list[str]:
            return [item.strip() for item in row[field].split(";") if item.strip()]

        classifications[source_link_id] = {
            "classificationId": classification_id,
            "lineageStatus": row["lineage_status"].strip(),
            "semanticClassification": semantic,
            "uiPolicy": ui_policy,
            "uiDirectLabelAllowed": direct_label_allowed,
            "directScope": {
                "ingredientIds": split("direct_scope_ingredient_ids"),
                "productItemSequences": split(
                    "direct_scope_product_item_sequences"
                ),
                "profileConditions": split("direct_scope_profile_conditions"),
                "medicationTerms": split("direct_scope_medication_terms"),
            },
            "classificationReasonKo": row["classification_reason_ko"].strip(),
            "uiBoundaryKo": row["ui_boundary_ko"].strip(),
            "humanExpertReviewed": human_reviewed,
            "supportsRuleRelease": supports_release,
        }
    return classifications


def build() -> list[dict]:
    rule_rows = _rows(RULES)
    rule_types_by_id = {row["rule_id"]: row["rule_type"] for row in rule_rows}
    released_rule_types = {row["rule_type"] for row in rule_rows if row["status"] == "released"}
    abstracts = {row["pmid"]: row["abstract"] for row in _rows(EVIDENCE_MAP)}
    v51_classifications = _v51_classifications()

    papers: dict[str, dict] = {}
    seen_links: set[str] = set()
    for row in _rows(SOURCE):
        link_id = row["link_id"]
        if link_id in seen_links:
            raise ValueError(f"duplicate link_id: {link_id}")
        seen_links.add(link_id)

        v51_classification = v51_classifications.get(link_id)
        if v51_classification is None:
            raise ValueError(f"{link_id}: missing v5.1 semantic classification")

        pmid = row["pmid"].strip()
        if not re.fullmatch(r"\d{7,8}", pmid):
            raise ValueError(f"invalid PMID: {pmid}")
        if rule_types_by_id.get(row["rule_id"]) != row["rule_type"]:
            raise ValueError(f"{link_id}: rule_id/rule_type mismatch with rules.csv")
        if row["review_status"] != REVIEW_STATUS:
            raise ValueError(f"{link_id}: invalid review status")
        if row["supports_rule_release"].lower() != "false":
            raise ValueError(f"{link_id}: supporting literature cannot release a rule")
        if row["evidence_authority"] != EVIDENCE_AUTHORITY:
            raise ValueError(f"{link_id}: literature must stay explanatory only")
        if row["evidence_relation"] not in EVIDENCE_RELATIONS:
            raise ValueError(f"{link_id}: invalid evidence relation {row['evidence_relation']}")
        if row["authorization_alignment"] not in AUTHORIZATION_ALIGNMENTS:
            raise ValueError(f"{link_id}: invalid authorization alignment")
        if row["url"] != f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/":
            raise ValueError(f"{link_id}: non-PubMed URL")

        abstract = abstracts.get(pmid)
        if abstract is None:
            raise ValueError(f"{link_id}: PMID {pmid} is outside the v4.0 search corpus")
        quote = sentence_at(abstract, parse_locator(row["locator"]))
        if quote != row["locator_quote_en"]:
            raise ValueError(f"{link_id}: locator quote does not match the abstract sentence")

        declared = [v for v in row["profile_conditions"].split(";") if v]
        unknown = set(declared) - PROFILE_CONDITIONS - DOSE_INPUT_CONDITIONS
        if unknown:
            raise ValueError(f"{link_id}: unobserved personalization axis {sorted(unknown)}")
        profile_conditions = [v for v in declared if v in PROFILE_CONDITIONS]
        dose_input_conditions = [v for v in declared if v in DOSE_INPUT_CONDITIONS]

        required = ["doi", "title", "study_design", "key_finding_ko", "selection_reason_ko", "limitation_ko"]
        missing = [field for field in required if not row[field].strip()]
        if missing:
            raise ValueError(f"{link_id}: missing fields {missing}")

        paper = papers.setdefault(
            pmid,
            {
                "pmid": pmid,
                "doi": row["doi"],
                "title": row["title"],
                "journal": row["journal"],
                "publicationYear": int(row["publication_year"]),
                "studyDesign": row["study_design"],
                "evidenceAuthority": EVIDENCE_AUTHORITY,
                "supportsRuleRelease": False,
                "v50Validation": _v50_validation(pmid),
                "reviewStatus": REVIEW_STATUS,
                "disclaimerKo": DISCLAIMER_KO,
                "url": row["url"],
                "ruleTypes": [],
                "ruleLinks": [],
                "ingredientIds": [],
                "profileConditions": [],
                "doseInputConditions": [],
            },
        )
        if row["rule_type"] not in paper["ruleTypes"]:
            paper["ruleTypes"].append(row["rule_type"])
        paper["ruleLinks"].append(
            {
                "linkId": link_id,
                "ruleId": row["rule_id"],
                "ruleType": row["rule_type"],
                "ruleReleased": row["rule_type"] in released_rule_types,
                "evidenceRelation": row["evidence_relation"],
                "locator": row["locator"],
                "locatorQuoteEn": row["locator_quote_en"],
                "keyFindingKo": row["key_finding_ko"],
                "selectionReasonKo": row["selection_reason_ko"],
                "limitationKo": row["limitation_ko"],
                "authorizationAlignment": row["authorization_alignment"],
                "authorizationNoteKo": row["authorization_note_ko"],
                "v51Classification": v51_classification,
            }
        )
        for ingredient_id in (v for v in row["ingredient_ids"].split(";") if v):
            if ingredient_id not in paper["ingredientIds"]:
                paper["ingredientIds"].append(ingredient_id)
        for condition in profile_conditions:
            if condition not in paper["profileConditions"]:
                paper["profileConditions"].append(condition)
        for condition in dose_input_conditions:
            if condition not in paper["doseInputConditions"]:
                paper["doseInputConditions"].append(condition)

    extra_classifications = set(v51_classifications) - seen_links
    if extra_classifications:
        raise ValueError(
            "v5.1 classifications without a source literature link: "
            f"{sorted(extra_classifications)}"
        )

    linked_rule_ids = {
        link["ruleId"] for paper in papers.values() for link in paper["ruleLinks"]
    }
    missing_rules = sorted({row["rule_id"] for row in rule_rows} - linked_rule_ids)
    if missing_rules:
        raise ValueError(f"rules without literature link: {missing_rules}")

    # 판정 카드가 첫 문헌을 고를 때 쓰는 대표 필드. 링크 중 첫 번째를 승격한다.
    for paper in papers.values():
        primary = paper["ruleLinks"][0]
        paper["evidenceRelation"] = primary["evidenceRelation"]
        paper["keyFindingKo"] = primary["keyFindingKo"]
        paper["selectionReasonKo"] = primary["selectionReasonKo"]
        paper["limitationKo"] = primary["limitationKo"]

    return sorted(papers.values(), key=lambda item: item["pmid"])


def write(target: Path = TARGET) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    papers = build()
    write()
    links = sum(len(paper["ruleLinks"]) for paper in papers)
    print(f"supporting_literature papers={len(papers)} links={links} target={TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
