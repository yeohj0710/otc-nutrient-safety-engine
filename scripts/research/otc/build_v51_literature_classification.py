"""Build the v5.1 rule-literature semantic classification artifacts.

The v5.0 literature layer is immutable input.  This builder joins its ten
emitted links back to the frozen twenty-row v4 candidate table, records a
conservative semantic classification for each emitted link, and preserves all
rejected candidates as excluded lineage rows.

The output has no authority to release or change a safety rule.  The
classification is an AI audit and has not been reviewed by a human expert.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[3]
V50_MANIFEST = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "downstream"
    / "literature_link_manifest.json"
)
V50_LINKS = V50_MANIFEST.with_name("supporting_literature.csv")
V4_CANDIDATES = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
RUNTIME_LITERATURE = ROOT / "src" / "generated" / "otc-supporting-literature.json"

OUTPUT_CSV = ROOT / "research_v51" / "literature" / "link_classification.csv"
OUTPUT_AUDIT = (
    ROOT
    / "research_v51"
    / "audit"
    / "literature_link_classification_audit.json"
)

SCHEMA_VERSION = "1.0.0"
CLASSIFICATION_RECORDED_AT_UTC = "2026-07-31T13:03:34Z"
SEMANTIC_CLASSIFICATIONS = {
    "direct_match",
    "background_context",
    "mixed_scope",
}
ALIGNMENTS = {"match", "limited", "mismatch", "not_assessed"}
UI_POLICIES = {
    "direct",
    "background_only",
    "direct_when_scope_matches_else_background",
    "exclude_from_result_ui",
}

CSV_FIELDS = [
    "classification_id",
    "source_link_id",
    "v50_link_id",
    "rule_id",
    "rule_type",
    "pmid",
    "lineage_status",
    "v50_rejection_reason",
    "semantic_classification",
    "ingredient_alignment",
    "population_alignment",
    "condition_alignment",
    "outcome_alignment",
    "direct_scope_ingredient_ids",
    "direct_scope_product_item_sequences",
    "direct_scope_profile_conditions",
    "direct_scope_medication_terms",
    "ui_policy",
    "ui_direct_label_allowed",
    "legacy_runtime_reachable",
    "supports_rule_release",
    "human_expert_reviewed",
    "locator",
    "locator_quote_sha256",
    "key_finding_ko",
    "classification_reason_ko",
    "ui_boundary_ko",
]


@dataclass(frozen=True)
class ClassificationDecision:
    semantic_classification: str
    ingredient_alignment: str
    population_alignment: str
    condition_alignment: str
    outcome_alignment: str
    direct_scope_ingredient_ids: str
    direct_scope_product_item_sequences: str
    direct_scope_profile_conditions: str
    direct_scope_medication_terms: str
    ui_policy: str
    ui_direct_label_allowed: bool
    classification_reason_ko: str
    ui_boundary_ko: str


# These are sentence-level, abstract-based AI audit decisions.  They are keyed
# by the frozen v4 source link so the v5 lineage can be reconstructed exactly.
CLASSIFICATION_DECISIONS: dict[str, ClassificationDecision] = {
    "OTC-LIT-LINK-001": ClassificationDecision(
        "direct_match",
        "match",
        "limited",
        "match",
        "match",
        "ING-acetaminophen",
        "",
        "ageYears>=12",
        "",
        "direct",
        True,
        "아세트아미노펜 함유 제품을 둘 이상 함께 사용한 조건과 치료적 오용 결과가 성분 중복 규칙에 직접 대응한다. 연구 대상은 미국 중독관리센터에 보고된 12세 이상 사용자로 제한된다.",
        "아세트아미노펜 중복 판정에만 직접 일치로 표시한다. 12세 미만이나 다른 성분 중복으로 일반화하지 않는다.",
    ),
    "OTC-LIT-LINK-003": ClassificationDecision(
        "background_context",
        "limited",
        "limited",
        "limited",
        "match",
        "",
        "",
        "",
        "",
        "background_only",
        False,
        "NSAID와 저용량 아스피린 병용의 위장관 이상반응 신호를 다루지만, 현재 규칙이 만드는 두 비아스피린 NSAID 조합별 직접 비교는 아니다.",
        "NSAID 계열 중복의 배경 연구로만 표시한다. 특정 두 제품 조합의 직접 근거라고 쓰지 않는다.",
    ),
    "OTC-LIT-LINK-006": ClassificationDecision(
        "background_context",
        "match",
        "limited",
        "mismatch",
        "limited",
        "",
        "",
        "",
        "",
        "background_only",
        False,
        "연구는 아세트아미노펜 650 mg 서방형의 8시간 간격 인지와 조기 재복용을 다룬다. 현재 규칙의 타이레놀 500 mg 일반정 4시간 최소 간격과 제형·간격 값이 다르다.",
        "복용 간격 오류의 배경으로만 표시한다. 4시간 기준을 뒷받침하는 직접 문헌으로 표시하지 않는다.",
    ),
    "OTC-LIT-LINK-008": ClassificationDecision(
        "background_context",
        "match",
        "limited",
        "mismatch",
        "limited",
        "",
        "",
        "",
        "",
        "background_only",
        False,
        "영국 소아용 파라세타몰 연령대별 용량 모델 연구이며, 국내 타이레놀 500 mg 정제의 12세 최소 연령 조건을 직접 검증하지 않았다.",
        "소아 연령대별 용량 오류의 배경으로만 표시한다. 국내 500 mg 정제의 12세 제한과 직접 일치한다고 쓰지 않는다.",
    ),
    "OTC-LIT-LINK-007": ClassificationDecision(
        "background_context",
        "match",
        "limited",
        "mismatch",
        "limited",
        "",
        "",
        "",
        "",
        "background_only",
        False,
        "12세 미만 소아의 비의도적 파라세타몰 과량과 액상제 함량·제형 선택 오류를 다룬다. 성인용 500 mg 정제의 최소 연령 조건과 직접 대응하지 않는다.",
        "소아 투약 오류의 배경으로만 표시하고 허가원문과의 conflict를 유지한다.",
    ),
    "OTC-LIT-LINK-009": ClassificationDecision(
        "mixed_scope",
        "limited",
        "match",
        "limited",
        "match",
        "ING-ibuprofen",
        "198601920",
        "pregnant=true;pregnancyTrimester=3",
        "",
        "direct_when_scope_matches_else_background",
        True,
        "임신 3기 이부프로펜 노출과 소아 신장 결과는 현재 규칙 범위에 직접 대응한다. 그러나 수유는 연구하지 않았고, 행에 함께 선언된 덱시부프로펜·나프록센의 직접 결과도 제시하지 않는다.",
        "임신 3기 이부프로펜 조건에서만 직접 일치로 표시한다. 임신 시기 미입력·1기·2기, 수유 단독 또는 다른 NSAID에는 직접 표시하지 않는다.",
    ),
    "OTC-LIT-LINK-010": ClassificationDecision(
        "background_context",
        "match",
        "limited",
        "limited",
        "limited",
        "",
        "",
        "",
        "",
        "background_only",
        False,
        "논문 주제는 간기능 저하 환자의 아세트아미노펜 사용이지만, 연결 문장은 일반 과량과 간효소 상승을 설명한다. 만성 간질환자의 구체적 제한을 직접 확정하지 않는다.",
        "간질환 주의의 불확실성을 설명하는 배경 연구로만 표시하고 conflict를 유지한다.",
    ),
    "OTC-LIT-LINK-011": ClassificationDecision(
        "mixed_scope",
        "limited",
        "limited",
        "match",
        "match",
        "ING-ibuprofen",
        "198601920",
        "kidneyDisease=true;ageYears<=18",
        "",
        "direct_when_scope_matches_else_background",
        True,
        "입원 소아의 이부프로펜 사용, 기존 만성콩팥병, 급성신손상 결과는 직접 대응한다. 성인과 행에 선언된 덱시부프로펜·나프록센으로의 확장은 직접 검증되지 않았다.",
        "18세 이하 신장질환자의 이부프로펜 조건에서만 직접 일치로 표시한다. 연령이 없거나 성인이면 배경으로만 표시한다.",
    ),
    "OTC-LIT-LINK-015": ClassificationDecision(
        "mixed_scope",
        "limited",
        "limited",
        "limited",
        "match",
        "ING-ibuprofen",
        "198601920",
        "medications.class=oral_anticoagulant",
        "warfarin;와파린;apixaban;아픽사반",
        "direct_when_scope_matches_else_background",
        True,
        "이부프로펜을 포함한 NSAID와 경구 항응고제 병용의 출혈 결과는 직접 대응한다. aspirin 항혈소판 분기와 덱시부프로펜은 직접 연구 범위가 아니다.",
        "이부프로펜과 명시된 경구 항응고제 병용에서만 직접 표시한다. aspirin 입력에는 직접 문헌으로 표시하지 않는다.",
    ),
    "OTC-LIT-LINK-017": ClassificationDecision(
        "mixed_scope",
        "limited",
        "limited",
        "match",
        "match",
        "ING-acetaminophen;ING-mf-src-4b985f9d3bdb",
        "196800036",
        "hypertensionOrCardiovascularDisease=true",
        "",
        "direct_when_scope_matches_else_background",
        True,
        "연구는 페닐레프린과 파라세타몰 경구 복합 노출에서 혈압 상승 가능성을 다룬다. 기존 행은 아세트아미노펜만 선언해 결합 노출을 기계적으로 표현하지 못한다.",
        "판콜에이내복액처럼 아세트아미노펜과 페닐레프린을 모두 포함한 제품에서만 직접 일치로 표시한다.",
    ),
}


REJECTED_RUNTIME_REACHABLE = {
    "OTC-LIT-LINK-002",
    "OTC-LIT-LINK-004",
    "OTC-LIT-LINK-005",
    "OTC-LIT-LINK-012",
    "OTC-LIT-LINK-013",
    "OTC-LIT-LINK-014",
    "OTC-LIT-LINK-016",
    "OTC-LIT-LINK-020",
}

REJECTION_EXPLANATIONS = {
    "not_in_v5_corpus": (
        "v5.0 P AND I 검색식이 논문을 인출하지 않아 v5.0 링크로 채택되지 않았다."
    ),
    "no_retain_decision_for_rule_question": (
        "논문이 규칙에 허용된 질문에서 최종 retain 판정을 받지 않아 v5.0 링크로 채택되지 않았다."
    ),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _semantic_json_sha256(path: Path) -> str:
    """Hash the legacy runtime projection without this generator's own metadata.

    `build_supporting_literature.py` embeds `v51Classification` back into the runtime.
    Including that field here would create a source-to-output cycle and require two
    generation passes before the audit hash became current.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    for paper in payload:
        for link in paper.get("ruleLinks", []):
            link.pop("v51Classification", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _numeric_link_id(link_id: str) -> int:
    try:
        return int(link_id.rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid link id: {link_id}") from exc


def _classification_id(source_link_id: str) -> str:
    return f"V51-LIT-CLASS-{_numeric_link_id(source_link_id):03d}"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_fields(
    path: Path,
    rows: list[dict[str, str]],
    required: Iterable[str],
) -> None:
    if not rows:
        raise ValueError(f"{path}: no rows")
    missing = sorted(set(required) - set(rows[0]))
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")


def _load_inputs() -> tuple[
    dict,
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict],
]:
    manifest = json.loads(V50_MANIFEST.read_text(encoding="utf-8"))
    v50_rows = _read_csv(V50_LINKS)
    legacy_rows = _read_csv(V4_CANDIDATES)
    rule_rows = _read_csv(RULES)
    runtime_papers = json.loads(RUNTIME_LITERATURE.read_text(encoding="utf-8"))

    _require_fields(V50_LINKS, v50_rows, {"link_id", "rule_id", "pmid", "locator"})
    _require_fields(
        V4_CANDIDATES,
        legacy_rows,
        {"link_id", "rule_id", "rule_type", "pmid", "locator", "locator_quote_en"},
    )
    _require_fields(RULES, rule_rows, {"rule_id", "rule_type", "status"})

    recorded = manifest["inputs"]
    hash_checks = {
        V50_LINKS: manifest["outputs"]["supporting_literature"]["sha256"],
        V4_CANDIDATES: recorded["v4_candidate_links"]["sha256"],
        RULES: recorded["rules"]["sha256"],
    }
    for path, expected in hash_checks.items():
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(f"{path}: v5.0 recorded SHA-256 mismatch: {actual} != {expected}")

    return manifest, v50_rows, legacy_rows, rule_rows, runtime_papers


def build_rows() -> list[dict[str, str]]:
    manifest, v50_rows, legacy_rows, _, _ = _load_inputs()
    results = manifest["results"]
    accepted = {item["source_link_id"]: item for item in results["links"]}
    rejected = {
        item["source_link_id"]: item for item in results["rejected_candidates"]
    }
    source_ids = {row["link_id"] for row in legacy_rows}

    if set(accepted) & set(rejected):
        raise ValueError("v5.0 accepted and rejected source link sets overlap")
    if set(accepted) | set(rejected) != source_ids:
        raise ValueError("v4 candidate links are not completely partitioned by v5.0")
    if set(accepted) != set(CLASSIFICATION_DECISIONS):
        raise ValueError("classification decisions do not cover the emitted v5.0 links exactly")

    v50_by_id = {row["link_id"]: row for row in v50_rows}
    if len(v50_by_id) != len(v50_rows):
        raise ValueError("duplicate v5.0 link_id")

    output: list[dict[str, str]] = []
    for legacy in sorted(legacy_rows, key=lambda row: _numeric_link_id(row["link_id"])):
        source_link_id = legacy["link_id"]
        common = {
            "classification_id": _classification_id(source_link_id),
            "source_link_id": source_link_id,
            "rule_id": legacy["rule_id"],
            "rule_type": legacy["rule_type"],
            "pmid": legacy["pmid"],
            "supports_rule_release": "false",
            "human_expert_reviewed": "false",
        }

        if source_link_id in accepted:
            metadata = accepted[source_link_id]
            v50_link_id = str(metadata["link_id"])
            v50 = v50_by_id.get(v50_link_id)
            if v50 is None:
                raise ValueError(f"{source_link_id}: missing emitted row {v50_link_id}")
            if (
                v50["rule_id"] != legacy["rule_id"]
                or v50["pmid"] != legacy["pmid"]
                or metadata["rule_id"] != legacy["rule_id"]
                or str(metadata["pmid"]) != legacy["pmid"]
            ):
                raise ValueError(f"{source_link_id}: v4/v5 lineage mismatch")

            decision = CLASSIFICATION_DECISIONS[source_link_id]
            row = {
                **common,
                "v50_link_id": v50_link_id,
                "lineage_status": "v50_emitted",
                "v50_rejection_reason": "",
                "semantic_classification": decision.semantic_classification,
                "ingredient_alignment": decision.ingredient_alignment,
                "population_alignment": decision.population_alignment,
                "condition_alignment": decision.condition_alignment,
                "outcome_alignment": decision.outcome_alignment,
                "direct_scope_ingredient_ids": decision.direct_scope_ingredient_ids,
                "direct_scope_product_item_sequences": decision.direct_scope_product_item_sequences,
                "direct_scope_profile_conditions": decision.direct_scope_profile_conditions,
                "direct_scope_medication_terms": decision.direct_scope_medication_terms,
                "ui_policy": decision.ui_policy,
                "ui_direct_label_allowed": _bool_text(decision.ui_direct_label_allowed),
                "legacy_runtime_reachable": "true",
                "locator": v50["locator"],
                "locator_quote_sha256": _sha256_bytes(
                    v50["locator_quote_en"].encode("utf-8")
                ),
                "key_finding_ko": v50["key_finding_ko"],
                "classification_reason_ko": decision.classification_reason_ko,
                "ui_boundary_ko": decision.ui_boundary_ko,
            }
        else:
            rejection = rejected[source_link_id]
            reason = str(rejection["reason"])
            if reason not in REJECTION_EXPLANATIONS:
                raise ValueError(f"{source_link_id}: unsupported rejection reason {reason}")
            row = {
                **common,
                "v50_link_id": "",
                "lineage_status": f"v50_rejected_{reason}",
                "v50_rejection_reason": reason,
                "semantic_classification": "",
                "ingredient_alignment": "not_assessed",
                "population_alignment": "not_assessed",
                "condition_alignment": "not_assessed",
                "outcome_alignment": "not_assessed",
                "direct_scope_ingredient_ids": "",
                "direct_scope_product_item_sequences": "",
                "direct_scope_profile_conditions": "",
                "direct_scope_medication_terms": "",
                "ui_policy": "exclude_from_result_ui",
                "ui_direct_label_allowed": "false",
                "legacy_runtime_reachable": _bool_text(
                    source_link_id in REJECTED_RUNTIME_REACHABLE
                ),
                "locator": legacy["locator"],
                "locator_quote_sha256": _sha256_bytes(
                    legacy["locator_quote_en"].encode("utf-8")
                ),
                "key_finding_ko": legacy["key_finding_ko"],
                "classification_reason_ko": REJECTION_EXPLANATIONS[reason],
                "ui_boundary_ko": (
                    "v5.0 결과 UI에서 제외하고 v4 후보 계보 감사에서만 보존한다."
                ),
            }
        output.append(row)

    _validate_rows(output, manifest, v50_rows)
    return output


def _validate_rows(
    rows: list[dict[str, str]],
    manifest: dict,
    v50_rows: list[dict[str, str]],
) -> None:
    emitted = [row for row in rows if row["lineage_status"] == "v50_emitted"]
    rejected = [row for row in rows if row["v50_rejection_reason"]]
    classifications = Counter(row["semantic_classification"] for row in emitted)
    rejection_counts = Counter(row["v50_rejection_reason"] for row in rejected)

    expected_classifications = {
        "direct_match": 1,
        "background_context": 5,
        "mixed_scope": 4,
    }
    if len(rows) != 20 or len(emitted) != 10 or len(rejected) != 10:
        raise ValueError("v4/v5 row accounting must be 20 = 10 emitted + 10 rejected")
    if classifications != expected_classifications:
        raise ValueError(f"unexpected semantic classification counts: {classifications}")
    if dict(rejection_counts) != manifest["results"]["rejection_counts"]:
        raise ValueError(f"rejection counts differ from v5.0 manifest: {rejection_counts}")
    if {row["v50_link_id"] for row in emitted} != {row["link_id"] for row in v50_rows}:
        raise ValueError("emitted v5.0 link ids do not match downstream CSV")
    if len({row["rule_id"] for row in emitted}) != 9:
        raise ValueError("emitted rows must cover exactly nine rules")
    if len({row["classification_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate classification_id")
    if any(row["supports_rule_release"] != "false" for row in rows):
        raise ValueError("literature classification cannot support rule release")
    if any(row["human_expert_reviewed"] != "false" for row in rows):
        raise ValueError("no row has completed human expert review")
    if any(row["ui_policy"] not in UI_POLICIES for row in rows):
        raise ValueError("invalid UI policy")
    if any(
        value not in ALIGNMENTS
        for row in rows
        for value in (
            row["ingredient_alignment"],
            row["population_alignment"],
            row["condition_alignment"],
            row["outcome_alignment"],
        )
    ):
        raise ValueError("invalid component alignment")
    for row in emitted:
        if row["semantic_classification"] not in SEMANTIC_CLASSIFICATIONS:
            raise ValueError(f"{row['source_link_id']}: invalid semantic classification")
        if row["semantic_classification"] == "direct_match":
            if row["ui_policy"] != "direct" or row["ui_direct_label_allowed"] != "true":
                raise ValueError("direct_match must permit a direct label")
        elif row["semantic_classification"] == "background_context":
            if (
                row["ui_policy"] != "background_only"
                or row["ui_direct_label_allowed"] != "false"
            ):
                raise ValueError("background_context must remain background only")
        else:
            scope = (
                row["direct_scope_ingredient_ids"],
                row["direct_scope_product_item_sequences"],
                row["direct_scope_profile_conditions"],
                row["direct_scope_medication_terms"],
            )
            if (
                row["ui_policy"] != "direct_when_scope_matches_else_background"
                or row["ui_direct_label_allowed"] != "true"
                or not any(scope)
            ):
                raise ValueError("mixed_scope needs an explicit conditional direct scope")
    if any(
        row["ui_policy"] != "exclude_from_result_ui"
        or row["ui_direct_label_allowed"] != "false"
        or row["semantic_classification"]
        for row in rejected
    ):
        raise ValueError("every rejected legacy link must be excluded from result UI")


def _render_csv(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _runtime_snapshot(runtime_papers: list[dict]) -> dict[str, int]:
    links = [link for paper in runtime_papers for link in paper["ruleLinks"]]
    screened_papers = [paper for paper in runtime_papers if paper["v50Validation"]["screened"]]
    screened_links = [link for paper in screened_papers for link in paper["ruleLinks"]]
    return {
        "served_papers": len(runtime_papers),
        "served_links": len(links),
        "served_rule_count": len({link["ruleId"] for link in links}),
        "v50_screened_papers": len(screened_papers),
        "v50_screened_links": len(screened_links),
        "v50_screened_rule_count": len({link["ruleId"] for link in screened_links}),
    }


def build_audit(rows: list[dict[str, str]], csv_bytes: bytes) -> dict:
    manifest, v50_rows, legacy_rows, rule_rows, runtime_papers = _load_inputs()
    emitted = [row for row in rows if row["lineage_status"] == "v50_emitted"]
    rejected = [row for row in rows if row["v50_rejection_reason"]]
    classification_counts = Counter(row["semantic_classification"] for row in emitted)
    rejection_counts = Counter(row["v50_rejection_reason"] for row in rejected)
    reachable_rejected = [row for row in rejected if row["legacy_runtime_reachable"] == "true"]

    checks = {
        "v4_candidate_rows_partitioned_once": len(rows) == len(legacy_rows) == 20,
        "v50_emitted_rows_classified_once": len(emitted) == len(v50_rows) == 10,
        "v50_emitted_rule_count_is_nine": len({row["rule_id"] for row in emitted}) == 9,
        "semantic_classification_counts_are_1_5_4": dict(classification_counts)
        == {"direct_match": 1, "background_context": 5, "mixed_scope": 4},
        "rejected_rows_match_manifest": dict(rejection_counts)
        == manifest["results"]["rejection_counts"],
        "rejected_rows_excluded_from_result_ui": all(
            row["ui_policy"] == "exclude_from_result_ui"
            and row["ui_direct_label_allowed"] == "false"
            for row in rejected
        ),
        "background_rows_never_allow_direct_label": all(
            row["ui_policy"] == "background_only"
            and row["ui_direct_label_allowed"] == "false"
            for row in emitted
            if row["semantic_classification"] == "background_context"
        ),
        "mixed_rows_have_explicit_direct_scope": all(
            row["ui_policy"] == "direct_when_scope_matches_else_background"
            and any(
                row[field]
                for field in (
                    "direct_scope_ingredient_ids",
                    "direct_scope_product_item_sequences",
                    "direct_scope_profile_conditions",
                    "direct_scope_medication_terms",
                )
            )
            for row in emitted
            if row["semantic_classification"] == "mixed_scope"
        ),
        "human_expert_reviewed_is_false": all(
            row["human_expert_reviewed"] == "false" for row in rows
        ),
        "supports_rule_release_is_false": all(
            row["supports_rule_release"] == "false" for row in rows
        ),
        "v50_inputs_are_read_only": True,
        "outputs_are_outside_research_v3": all(
            "research_v51" in path.parts and "research_v3" not in path.parts
            for path in (OUTPUT_CSV, OUTPUT_AUDIT)
        ),
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ValueError(f"v5.1 literature classification audit failed: {failed}")

    return {
        "schema_version": SCHEMA_VERSION,
        "track": "v5.1-literature-semantic-classification",
        "classification_recorded_at_utc": CLASSIFICATION_RECORDED_AT_UTC,
        "authority": {
            "human_expert_reviewed": False,
            "supports_rule_release": False,
            "changes_authorization_decision": False,
            "evidence_authority": "literature_explanatory_only",
        },
        "inputs": {
            "v50_manifest": {
                "path": V50_MANIFEST.relative_to(ROOT).as_posix(),
                "sha256": _sha256(V50_MANIFEST),
                "read_only": True,
            },
            "v50_supporting_literature": {
                "path": V50_LINKS.relative_to(ROOT).as_posix(),
                "sha256": _sha256(V50_LINKS),
                "rows": len(v50_rows),
                "read_only": True,
            },
            "v4_candidate_links": {
                "path": V4_CANDIDATES.relative_to(ROOT).as_posix(),
                "sha256": _sha256(V4_CANDIDATES),
                "rows": len(legacy_rows),
                "read_only": True,
            },
            "rules": {
                "path": RULES.relative_to(ROOT).as_posix(),
                "sha256": _sha256(RULES),
                "rows": len(rule_rows),
                "read_only": True,
            },
            "runtime_literature_observation": {
                "path": RUNTIME_LITERATURE.relative_to(ROOT).as_posix(),
                "semantic_sha256": _semantic_json_sha256(RUNTIME_LITERATURE),
                "projection": "runtime_without_v51Classification",
                "read_only": True,
            },
        },
        "classification_policy": {
            "direct_match": "성분·조건·결과가 직접 대응하며 명시한 대상 제한 안에서 직접 표시할 수 있다.",
            "background_context": "주제는 관련되지만 제형·용량·대상·조건 또는 결과가 달라 직접 표시할 수 없다.",
            "mixed_scope": "일부 하위 범위만 직접 대응하므로 명시한 조건을 모두 만족할 때만 직접 표시할 수 있다.",
            "legacy_rejected": "v5.0에서 채택되지 않은 후보는 결과 UI에서 제외하고 감사 계보에만 남긴다.",
        },
        "counts": {
            "v4_candidate_rows": len(rows),
            "v50_emitted_rows": len(emitted),
            "v50_rejected_rows": len(rejected),
            "v50_emitted_rule_count": len({row["rule_id"] for row in emitted}),
            "semantic_classifications": dict(sorted(classification_counts.items())),
            "v50_rejection_reasons": dict(sorted(rejection_counts.items())),
        },
        "runtime_risk_snapshot": {
            **_runtime_snapshot(runtime_papers),
            "rejected_legacy_links_reachable": len(reachable_rejected),
            "rejected_legacy_distinct_papers_reachable": len(
                {row["pmid"] for row in reachable_rejected}
            ),
            "rejected_legacy_links_draft_inactive": len(rejected) - len(reachable_rejected),
        },
        "checks": checks,
        "outputs": {
            "classification_csv": {
                "path": OUTPUT_CSV.relative_to(ROOT).as_posix(),
                "rows": len(rows),
                "sha256": _sha256_bytes(csv_bytes),
            },
            "audit_json": {
                "path": OUTPUT_AUDIT.relative_to(ROOT).as_posix(),
            },
        },
        "valid": True,
    }


def build_artifacts() -> tuple[bytes, bytes]:
    rows = build_rows()
    csv_bytes = _render_csv(rows)
    audit = build_audit(rows, csv_bytes)
    audit_bytes = (
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return csv_bytes, audit_bytes


def write(
    classification_path: Path = OUTPUT_CSV,
    audit_path: Path = OUTPUT_AUDIT,
) -> tuple[Path, Path]:
    csv_bytes, audit_bytes = build_artifacts()
    classification_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    classification_path.write_bytes(csv_bytes)
    audit_path.write_bytes(audit_bytes)
    return classification_path, audit_path


def check() -> None:
    csv_bytes, audit_bytes = build_artifacts()
    expected = ((OUTPUT_CSV, csv_bytes), (OUTPUT_AUDIT, audit_bytes))
    for path, content in expected:
        if not path.is_file():
            raise SystemExit(f"missing generated artifact: {path}")
        if path.read_bytes() != content:
            raise SystemExit(f"generated artifact is stale: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed artifacts without writing",
    )
    args = parser.parse_args()
    if args.check:
        check()
        print("v5.1 literature classification artifacts are current")
    else:
        classification_path, audit_path = write()
        print(f"v5.1 literature classification -> {classification_path}")
        print(f"v5.1 literature audit -> {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
