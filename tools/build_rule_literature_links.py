"""P4 규칙↔문헌 근거 연결 검증·매니페스트 생성.

이 스크립트는 연결을 **만들지 않는다.** `supporting_literature.csv` 에 에이전트가 직접 적은
연결을 읽어 다음을 기계적으로 검증하고, 통과한 경우에만 매니페스트를 쓴다.

1. 모든 링크가 v4.0 검색 코퍼스에 있고 P2 선별에서 `retain` 판정을 받았는가
2. `locator` 가 가리키는 초록 문장이 실제로 존재하고 기록된 인용문과 정확히 같은가
3. 규칙 16개가 전부 최소 1건의 문헌 연결을 가지는가
4. 문헌이 규칙을 배포시키지 않는가(`supports_rule_release` 는 전부 false)
5. 허가 근거(rules.csv 의 source/locator)와 문헌 근거가 서로 다른 컬럼·권한으로 남는가
6. 개인화 축(성분·프로파일 조건)이 실제 데이터에 존재하는 값만 쓰는가
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.literature_locator import parse_locator, sentence_at

ROOT = Path(__file__).resolve().parents[1]
OTC = ROOT / "research_v3" / "otc"
LINKS = OTC / "rules" / "supporting_literature.csv"
RULES = OTC / "rules" / "rules.csv"
EVIDENCE_MAP = OTC / "literature" / "evidence_map.csv"
DECISION_DIR = OTC / "literature" / "screening" / "agent_decisions"
INGREDIENTS = OTC / "normalized" / "ingredient_master.csv"
PRODUCT_INGREDIENT = OTC / "normalized" / "product_ingredient.csv"
MANIFEST = OTC / "rules" / "literature_link_manifest.json"

EVIDENCE_RELATIONS = {"supports_caution", "contextualizes_uncertainty", "supports_mechanism"}
AUTHORIZATION_ALIGNMENTS = {"consistent", "conflict"}
EVIDENCE_AUTHORITY = "literature_explanatory_only"
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
    "hoursSincePreviousDose",
    "continuousDays",
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_screening() -> dict[str, str]:
    decisions: dict[str, str] = {}
    for path in sorted(DECISION_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            decisions[row["record_id"]] = row["decision"]
    return decisions


def validate() -> dict[str, Any]:
    rules = _rows(RULES)
    rule_by_id = {row["rule_id"]: row for row in rules}
    records = {row["pmid"]: row for row in _rows(EVIDENCE_MAP)}
    decisions = load_screening()
    known_ingredients = {row["ingredient_id"] for row in _rows(INGREDIENTS)}
    ingredient_products = defaultdict(set)
    for row in _rows(PRODUCT_INGREDIENT):
        ingredient_products[row["ingredient_id"]].add(row["product_id"])

    errors: list[str] = []
    links: list[dict[str, Any]] = []
    for row in _rows(LINKS):
        link_id = row["link_id"]
        rule = rule_by_id.get(row["rule_id"])
        if rule is None:
            errors.append(f"{link_id}: unknown rule_id {row['rule_id']}")
            continue
        if rule["rule_type"] != row["rule_type"]:
            errors.append(f"{link_id}: rule_type mismatch with rules.csv")

        record = records.get(row["pmid"])
        if record is None:
            errors.append(f"{link_id}: PMID {row['pmid']} is outside the v4.0 search corpus")
            continue
        if row["record_id"] != record["record_id"]:
            errors.append(f"{link_id}: record_id mismatch for PMID {row['pmid']}")
        decision = decisions.get(record["record_id"])
        if decision != "retain":
            errors.append(f"{link_id}: screening decision is {decision!r}, expected 'retain'")
        if row["screening_decision"] != "retain":
            errors.append(f"{link_id}: screening_decision column must record 'retain'")

        # locator 검증 — 여기서 걸리면 인용문이 초록과 다르다는 뜻이다.
        try:
            index = parse_locator(row["locator"])
            actual = sentence_at(record["abstract"], index)
        except (ValueError, IndexError) as exc:
            errors.append(f"{link_id}: {exc}")
            continue
        if actual != row["locator_quote_en"]:
            errors.append(
                f"{link_id}: quote does not match abstract sentence {index}\n"
                f"      csv={row['locator_quote_en'][:120]!r}\n"
                f"      abs={actual[:120]!r}"
            )

        if row["evidence_relation"] not in EVIDENCE_RELATIONS:
            errors.append(f"{link_id}: invalid evidence_relation {row['evidence_relation']!r}")
        if row["evidence_authority"] != EVIDENCE_AUTHORITY:
            errors.append(f"{link_id}: evidence_authority must be {EVIDENCE_AUTHORITY}")
        if row["authorization_alignment"] not in AUTHORIZATION_ALIGNMENTS:
            errors.append(f"{link_id}: invalid authorization_alignment")
        if row["authorization_alignment"] == "conflict" and not row["authorization_note_ko"].strip():
            errors.append(f"{link_id}: conflict must carry authorization_note_ko")
        if row["supports_rule_release"].lower() != "false":
            errors.append(f"{link_id}: literature must never release a rule")
        if row["url"] != f"https://pubmed.ncbi.nlm.nih.gov/{row['pmid']}/":
            errors.append(f"{link_id}: non-PubMed url")

        ingredient_ids = [v for v in row["ingredient_ids"].split(";") if v]
        unknown = sorted(set(ingredient_ids) - known_ingredients)
        if unknown:
            errors.append(f"{link_id}: unknown ingredient ids {unknown}")
        for ingredient_id in ingredient_ids:
            if not ingredient_products[ingredient_id]:
                errors.append(f"{link_id}: ingredient {ingredient_id} is bound to no product")
        profile_conditions = [v for v in row["profile_conditions"].split(";") if v]
        unknown_profile = sorted(set(profile_conditions) - PROFILE_CONDITIONS)
        if unknown_profile:
            errors.append(f"{link_id}: unobserved personalization axis {unknown_profile}")

        for field in ("key_finding_ko", "selection_reason_ko", "limitation_ko", "study_design"):
            if not row[field].strip():
                errors.append(f"{link_id}: missing {field}")

        links.append(
            {
                "link_id": link_id,
                "rule_id": row["rule_id"],
                "rule_type": row["rule_type"],
                "rule_status": rule["status"],
                "pmid": row["pmid"],
                "record_id": row["record_id"],
                "locator": row["locator"],
                "evidence_relation": row["evidence_relation"],
                "authorization_alignment": row["authorization_alignment"],
                "ingredient_ids": ingredient_ids,
                "profile_conditions": profile_conditions,
            }
        )

    link_ids = [item["link_id"] for item in links]
    duplicates = [k for k, v in Counter(link_ids).items() if v > 1]
    if duplicates:
        errors.append(f"duplicate link_id: {duplicates}")
    pairs = [(item["rule_id"], item["pmid"]) for item in links]
    duplicate_pairs = [k for k, v in Counter(pairs).items() if v > 1]
    if duplicate_pairs:
        errors.append(f"duplicate (rule_id, pmid): {duplicate_pairs}")

    covered = {item["rule_id"] for item in links}
    missing_rules = sorted({row["rule_id"] for row in rules} - covered)
    if missing_rules:
        errors.append(f"rules without literature link: {missing_rules}")

    return {"errors": errors, "links": links, "rules": rules}


def build_manifest() -> dict[str, Any]:
    result = validate()
    if result["errors"]:
        raise SystemExit("literature link validation failed:\n  " + "\n  ".join(result["errors"]))

    links = result["links"]
    rules = result["rules"]
    per_rule = defaultdict(list)
    for item in links:
        per_rule[item["rule_id"]].append(item)

    # 개인화 축: 제품명 -> 성분 -> 문헌. 실제 데이터에 있는 연결만 센다.
    analysis_products = {
        row["product_id"]: row["product_name"]
        for row in _rows(OTC / "normalized" / "product_master.csv")
        if row["analysis_status"] == "included"
    }
    ingredients_by_product = defaultdict(set)
    for row in _rows(PRODUCT_INGREDIENT):
        if row["product_id"] in analysis_products:
            ingredients_by_product[row["product_id"]].add(row["ingredient_id"])

    ingredient_axis = defaultdict(set)
    for item in links:
        for ingredient_id in item["ingredient_ids"]:
            ingredient_axis[ingredient_id].add(item["pmid"])
    profile_axis = defaultdict(set)
    for item in links:
        for condition in item["profile_conditions"]:
            profile_axis[condition].add(item["pmid"])

    product_axis: dict[str, dict[str, Any]] = {}
    for product_id, product_name in sorted(analysis_products.items(), key=lambda kv: kv[1]):
        matched_ingredients = sorted(ingredients_by_product[product_id] & set(ingredient_axis))
        pmids: set[str] = set()
        for ingredient_id in matched_ingredients:
            pmids |= ingredient_axis[ingredient_id]
        product_axis[product_name] = {
            "product_id": product_id,
            "ingredient_ids": matched_ingredients,
            "pmids": sorted(pmids),
        }

    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "phase": "P4",
        "purpose_ko": "규칙별 문헌 근거 연결 현황과 검증 결과",
        "authority_separation_ko": (
            "규칙 판정 권한은 허가원문(rules.csv 의 source_id·source_locator)에만 있다. "
            "문헌은 설명용이며 supports_rule_release 는 전부 false 다. 두 근거는 서로 다른 "
            "파일·컬럼에 남기고 합치지 않는다."
        ),
        "rules_total": len(rules),
        "rules_with_literature": len(per_rule),
        "rules_without_literature": sorted({row["rule_id"] for row in rules} - set(per_rule)),
        "links_total": len(links),
        "links_by_rule": {rule_id: len(items) for rule_id, items in sorted(per_rule.items())},
        "unique_pmids": len({item["pmid"] for item in links}),
        "evidence_relation_counts": dict(
            sorted(Counter(item["evidence_relation"] for item in links).items())
        ),
        "authorization_alignment_counts": dict(
            sorted(Counter(item["authorization_alignment"] for item in links).items())
        ),
        "conflicts": [
            {"link_id": item["link_id"], "rule_id": item["rule_id"], "pmid": item["pmid"]}
            for item in links
            if item["authorization_alignment"] == "conflict"
        ],
        "personalization_axis": {
            "note_ko": (
                "제품명 → 성분 → 문헌 축. 분석 대상 13개 제품의 실제 성분 결합에서만 뻗어 "
                "나가며 관찰되지 않은 축은 만들지 않는다."
            ),
            "by_product": product_axis,
            "products_with_literature": sum(1 for v in product_axis.values() if v["pmids"]),
            "products_total": len(product_axis),
            "products_without_literature": sorted(
                name for name, v in product_axis.items() if not v["pmids"]
            ),
            "coverage_gap_note_ko": (
                "문헌이 붙지 않은 제품은 소화효소제 4종과 외용 첩부제 1종이다. v4.0 검색 "
                "코퍼스에서 소화기 질문(OTC-LIT-Q04)의 retain 이 27건뿐이고 그중 국내 "
                "일반의약품 소화효소제 조합을 다룬 문헌이 없었기 때문이다. 억지로 맞지 않는 "
                "문헌을 붙이지 않고 공백으로 남긴다. 이 제품들의 판정은 허가원문만으로 이뤄진다."
            ),
            "by_ingredient": {k: sorted(v) for k, v in sorted(ingredient_axis.items())},
            "by_profile_condition": {k: sorted(v) for k, v in sorted(profile_axis.items())},
        },
        "corpus": {
            "evidence_map_rows": len(_rows(EVIDENCE_MAP)),
            "screening_retained": sum(1 for v in load_screening().values() if v == "retain"),
        },
        "input_sha256": {
            "supporting_literature.csv": _sha256(LINKS),
            "rules.csv": _sha256(RULES),
            "evidence_map.csv": _sha256(EVIDENCE_MAP),
        },
        "validation": {"errors": [], "locator_check": "every quote matched its abstract sentence"},
    }


def main() -> int:
    manifest = build_manifest()
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest["output_sha256"] = _sha256(MANIFEST)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "rules_with_literature": manifest["rules_with_literature"],
                "rules_total": manifest["rules_total"],
                "links": manifest["links_total"],
                "conflicts": len(manifest["conflicts"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
