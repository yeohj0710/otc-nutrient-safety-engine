"""Audit the immutable v5 classifier layer against AI-authored invariants.

The historical pipeline preserved no callable semantic classifier.  This audit
therefore validates the exact evidence-membership, batch-output, checkpoint, and
CSV projection contract before checking manually specified expectations for real
corpus records.  Failed semantic cases are recorded and become mandatory
adjudication targets; classifier labels are never rewritten here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from light_screening_pipeline import (
    BATCHES,
    CHECKPOINTS as CLASSIFIER_CHECKPOINTS,
    DECISION_FIELDS,
    ORDER,
    validate_output,
)


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREEN = V5 / "screening"
EVIDENCE = V5 / "evidence_map.csv"
PROMPT = V5 / "prompts" / "frozen_light_screening_prompt.md"
CLASSIFIER = SCREEN / "classifier_decisions.csv"
FROZEN_VALIDATION = SCREEN / "classifier_validation.json"
SUPPLEMENTAL_VALIDATION = SCREEN / "classifier_validation_cross_layer.json"
V4_MANIFEST = ROOT / "research_v3" / "otc" / "literature" / "screening" / "screening_manifest.json"
V4_EVIDENCE = ROOT / "research_v3" / "otc" / "literature" / "evidence_map.csv"
V4_CHECKPOINTS = ROOT / "research_v3" / "otc" / "literature" / "screening" / "checkpoints.jsonl"
VALIDATOR = Path(__file__).resolve()

EXPECTED_CLASSIFIER_ROWS = 43_207
EXPECTED_BATCH_COUNT = 182
BATCH_INPUT_FIELDS = (
    "record_id",
    "question_id",
    "title",
    "abstract",
    "publication_types",
    "mesh_terms",
)

Q01 = "OTC-LIT-Q01-ACETAMINOPHEN"
Q02 = "OTC-LIT-Q02-NSAID"
Q03 = "OTC-LIT-Q03-COLD-ALLERGY"
Q04 = "OTC-LIT-Q04-DIGESTIVE"
Q05 = "OTC-LIT-Q05-TOPICAL"


CASES: list[dict[str, Any]] = [
    {"record_id": "PMID-22752270", "question_id": Q01, "expected": "deprioritize", "categories": ["preclinical_only", "assigned_ingredient_match"], "rationale_ko": "acetaminophen 간독성과 enalapril 효과를 생쥐에서만 평가해 사람 안전성 근거가 아니다."},
    {"record_id": "PMID-21787682", "question_id": Q01, "expected": "deprioritize", "categories": ["preclinical_only", "assigned_ingredient_match"], "rationale_ko": "acetaminophen은 Wistar rat에만 투여됐고 사람 결과가 없다."},
    {"record_id": "PMID-22005020", "question_id": Q02, "expected": "deprioritize", "categories": ["preclinical_only", "assigned_ingredient_match"], "rationale_ko": "ibuprofen 등 노출과 발달 결과를 임신 rat과 새끼에서만 평가했다."},
    {"record_id": "PMID-22449385", "question_id": Q03, "expected": "deprioritize", "categories": ["preclinical_only", "class_exposure"], "rationale_ko": "H1 항히스타민 계열의 수면 유발 결과를 rat에서만 평가했다."},
    {"record_id": "PMID-16436655", "question_id": Q04, "expected": "deprioritize", "categories": ["preclinical_only", "assigned_ingredient_match"], "rationale_ko": "UDCA의 담도 상피 보호 효과를 rat model에서만 평가했다."},
    {"record_id": "PMID-19815612", "question_id": Q01, "expected": "retain", "categories": ["human_exposure", "assigned_ingredient_match"], "rationale_ko": "사람 paracetamol 과량복용과 귀속 가능한 급성 신부전 증례군이다."},
    {"record_id": "PMID-24445686", "question_id": Q02, "expected": "retain", "categories": ["human_exposure", "assigned_ingredient_match"], "rationale_ko": "소아 ibuprofen 병용 노출과 급성 신손상 신호를 분석했다."},
    {"record_id": "PMID-24395298", "question_id": Q03, "expected": "retain", "categories": ["human_exposure", "assigned_ingredient_match"], "rationale_ko": "사람 cetirizine과 alcohol 병용의 정신운동 결과를 무작위 교차시험에서 측정했다."},
    {"record_id": "PMID-19779704", "question_id": Q01, "expected": "retain", "categories": ["human_exposure", "assigned_ingredient_match"], "rationale_ko": "사람 사후자료에서 warfarin과 paracetamol 병용의 유해 상호작용을 평가했다."},
    {"record_id": "PMID-19779704", "question_id": Q02, "expected": "deprioritize", "categories": ["assigned_ingredient_mismatch", "outcome_without_exposure"], "rationale_ko": "실제 귀속 노출은 paracetamol이며 NSAID는 연구 배경으로만 언급된다."},
    {"record_id": "PMID-20227026", "question_id": Q02, "expected": "retain", "categories": ["class_exposure", "human_exposure"], "rationale_ko": "사람 NSAID 계열 노출과 상부 위장관 이상반응을 직접 다룬다."},
    {"record_id": "PMID-20227026", "question_id": Q05, "expected": "deprioritize", "categories": ["assigned_ingredient_mismatch", "route_mismatch"], "rationale_ko": "전신 NSAID 연구이며 Q05의 외용 counterirritant 노출이 아니다."},
    {"record_id": "PMID-10601046", "question_id": Q04, "expected": "uncertain", "categories": ["no_abstract", "assigned_ingredient_match"], "rationale_ko": "UDCA 노출 가능성은 보이지만 제목만으로 사람 안전성 결과를 확정할 수 없다."},
    {"record_id": "PMID-19959976", "question_id": Q01, "expected": "retain", "categories": ["no_abstract", "human_exposure", "assigned_ingredient_match"], "rationale_ko": "제목만으로 acetaminophen 과량복용이라는 사람 안전성 문제가 명확하다."},
    {"record_id": "PMID-26631399", "question_id": Q02, "expected": "retain", "categories": ["no_abstract", "human_exposure", "assigned_ingredient_match"], "rationale_ko": "제목에 ibuprofen-aspirin 상호작용과 치명적 혈전 결과가 명시됐다."},
    {"record_id": "PMID-37248974", "question_id": Q01, "expected": "deprioritize", "categories": ["assigned_ingredient_mismatch", "outcome_without_exposure"], "rationale_ko": "drug-induced liver injury 결과를 다루지만 acetaminophen 노출이 없다."},
    {"record_id": "PMID-23187061", "question_id": Q02, "expected": "deprioritize", "categories": ["assigned_ingredient_mismatch", "outcome_without_exposure"], "rationale_ko": "실제 원인 노출은 acetaminophen 과량복용이고 NSAID 노출은 없다."},
    {"record_id": "PMID-22406651", "question_id": Q03, "expected": "deprioritize", "categories": ["assigned_ingredient_mismatch", "outcome_without_exposure"], "rationale_ko": "opioid 중독 증례이며 Q03 배정 성분 또는 계열 노출이 없다."},
    {"record_id": "PMID-19781895", "question_id": Q01, "expected": "deprioritize", "categories": ["exposure_without_outcome", "assigned_ingredient_match"], "rationale_ko": "acetaminophen 해열 효능을 측정했으며 귀속 가능한 안전성 결과가 없다."},
    {"record_id": "PMID-23397664", "question_id": Q02, "expected": "deprioritize", "categories": ["exposure_without_outcome", "route_mismatch"], "rationale_ko": "정맥 ketorolac 약동학 연구로 경구 안전성 결과가 없다."},
    {"record_id": "PMID-23973502", "question_id": Q03, "expected": "deprioritize", "categories": ["exposure_without_outcome", "assigned_ingredient_mismatch"], "rationale_ko": "caffeine은 영양 섭취 측정치일 뿐 caffeine 귀속 안전성 결과가 없다."},
    {"record_id": "PMID-33560089", "question_id": Q04, "expected": "deprioritize", "categories": ["exposure_without_outcome", "q04_oral_digestive_enzyme_safety"], "rationale_ko": "사람 경구 pancrelipase 노출은 있으나 효능·증상 결과만 있고 안전성 결과가 없다."},
    {"record_id": "PMID-37694700", "question_id": Q05, "expected": "deprioritize", "categories": ["exposure_without_outcome", "q05_topical_pediatric_exposure"], "rationale_ko": "신생아에게 menthol ointment를 쓴 관행은 보고하지만 귀속 안전성 결과는 분석하지 않는다."},
    {"record_id": "PMID-18823646", "question_id": Q02, "expected": "retain", "categories": ["class_exposure", "human_exposure"], "rationale_ko": "사람 NSAID 계열의 궤양·심혈관·고혈압·신부전 이상반응을 다룬다."},
    {"record_id": "PMID-20565458", "question_id": Q03, "expected": "retain", "categories": ["class_exposure", "human_exposure"], "rationale_ko": "경구 H1 항히스타민 계열과 lorazepam 병용의 중추신경 결과를 사람에게서 측정했다."},
    {"record_id": "PMID-24098516", "question_id": Q03, "expected": "retain", "categories": ["class_exposure", "human_exposure"], "rationale_ko": "성인의 진정성 H1 항히스타민 오남용과 의존을 직접 조사했다."},
    {"record_id": "PMID-10950038", "question_id": Q04, "expected": "retain", "categories": ["q04_oral_digestive_enzyme_safety", "human_exposure"], "rationale_ko": "소아·성인 cystic fibrosis 환자에게 pancrelipase를 투여하고 safety와 tolerance를 평가했다."},
    {"record_id": "PMID-10644326", "question_id": Q04, "expected": "retain", "categories": ["q04_oral_digestive_enzyme_safety", "human_exposure"], "rationale_ko": "사람의 경구 pancreatic enzyme 과다 사용과 fibrosing colonopathy가 직접 연결된다."},
    {"record_id": "PMID-21197074", "question_id": Q04, "expected": "retain", "categories": ["q04_oral_digestive_enzyme_safety", "human_exposure"], "rationale_ko": "사람 pancrelipase 무작위시험이 이상반응을 명시적으로 관찰했다."},
    {"record_id": "PMID-23383603", "question_id": Q04, "expected": "retain", "categories": ["q04_oral_digestive_enzyme_safety", "human_exposure"], "rationale_ko": "경구 pancreatin 시험과 1년 연장 연구가 치료 후 이상반응과 중단을 보고했다."},
    {"record_id": "PMID-18787288", "question_id": Q04, "expected": "deprioritize", "categories": ["no_abstract", "assigned_ingredient_mismatch", "outcome_without_exposure"], "rationale_ko": "제목이 pancreatic enzyme 보충 노출이 없었다고 명시한다."},
    {"record_id": "PMID-21418260", "question_id": Q04, "expected": "retain", "categories": ["q04_oral_digestive_enzyme_safety", "human_exposure"], "rationale_ko": "6개월 경구 pancrelipase 연구가 치료 관련 이상반응을 보고했다."},
    {"record_id": "PMID-15219304", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "비처방 외용 camphor 제품에 대한 toddler 노출과 중독 위험을 다룬다."},
    {"record_id": "PMID-10881777", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "2개월 영아에게 camphor 피부 제품을 사용한 뒤 간독성이 나타나고 중단 후 호전됐다."},
    {"record_id": "PMID-33245023", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "소아 599명의 topical salicylate 제품 노출과 독성 징후·입원 결과를 보고했다."},
    {"record_id": "PMID-19403490", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "반복 피부 도포를 포함한 소아 camphor 중독·경련 군집이다."},
    {"record_id": "PMID-18029526", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "보호자가 camphor를 복부에 마사지한 뒤 소아에게 status epilepticus가 발생했다."},
    {"record_id": "PMID-28491925", "question_id": Q05, "expected": "retain", "categories": ["q05_topical_pediatric_exposure", "human_exposure"], "rationale_ko": "영아 국소 camphor 노출에서 관찰된 무위해 결과를 해석할 수 있다."},
    {"record_id": "PMID-30741813", "question_id": Q01, "expected": "deprioritize", "categories": ["route_mismatch", "exposure_without_outcome"], "rationale_ko": "수술 전 정맥 acetaminophen 효능 시험으로 Q01의 IV-only 제외 조건에 해당한다."},
    {"record_id": "PMID-30660018", "question_id": Q02, "expected": "deprioritize", "categories": ["route_mismatch", "human_exposure"], "rationale_ko": "NSAID를 점안제로만 투여해 Q02의 경구 또는 경로 미상 범위 밖이다."},
    {"record_id": "PMID-28986120", "question_id": Q05, "expected": "deprioritize", "categories": ["route_mismatch", "assigned_ingredient_mismatch"], "rationale_ko": "소아 경구 aspirin 유발시험이며 외용 counterirritant 노출이 아니다."},
    {"record_id": "PMID-35168221", "question_id": Q05, "expected": "deprioritize", "categories": ["formulation_only", "exposure_without_outcome"], "rationale_ko": "menthol은 전달체 성분이고 실제 연구 노출·결과는 folate와 iron이다."},
]

REQUIRED_CATEGORIES = {
    "preclinical_only",
    "human_exposure",
    "assigned_ingredient_match",
    "assigned_ingredient_mismatch",
    "no_abstract",
    "outcome_without_exposure",
    "exposure_without_outcome",
    "class_exposure",
    "q04_oral_digestive_enzyme_safety",
    "q05_topical_pediatric_exposure",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise RuntimeError(f"{path.name}:{line_number} is not a JSON object")
        rows.append(row)
    return rows


def evidence_memberships(
    rows: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], set[tuple[str, str]]]:
    evidence: dict[str, dict[str, str]] = {}
    memberships: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, 2):
        record_id = row.get("record_id", "")
        if not record_id:
            raise RuntimeError(f"evidence_map.csv:{row_number} has no record_id")
        if record_id != record_id.strip():
            raise RuntimeError(f"evidence_map.csv:{row_number} has padded record_id: {record_id!r}")
        if record_id in evidence:
            raise RuntimeError(f"evidence_map.csv has duplicate record_id: {record_id}")
        evidence[record_id] = row

        question_ids = row.get("question_ids", "").split(";")
        if any(value != value.strip() for value in question_ids):
            raise RuntimeError(f"evidence_map.csv:{row_number} has padded question_ids: {record_id}")
        if not question_ids:
            raise RuntimeError(f"evidence_map.csv:{row_number} has no question membership: {record_id}")
        if any(not value for value in question_ids):
            raise RuntimeError(f"evidence_map.csv:{row_number} has an empty question membership: {record_id}")
        if len(question_ids) != len(set(question_ids)):
            raise RuntimeError(f"evidence_map.csv:{row_number} repeats a question membership: {record_id}")
        unknown = sorted(set(question_ids) - set(ORDER))
        if unknown:
            raise RuntimeError(f"evidence_map.csv:{row_number} has unknown questions: {unknown}")
        for question_id in question_ids:
            key = (record_id, question_id)
            if key in memberships:
                raise RuntimeError(f"evidence_map.csv has duplicate membership: {key}")
            memberships.add(key)
    return evidence, memberships


def expected_question_inputs(
    evidence_rows: list[dict[str, str]],
    question_id: str,
) -> list[dict[str, str]]:
    return [
        {
            "record_id": row["record_id"],
            "question_id": question_id,
            "title": row["title"],
            "abstract": row["abstract"],
            "publication_types": row["publication_types"],
            "mesh_terms": row["mesh_terms"],
        }
        for row in evidence_rows
        if question_id in row["question_ids"].split(";")
    ]


def require_same_batch_inputs(
    expected: list[dict[str, str]],
    actual: list[dict[str, Any]],
    *,
    batch_id: str,
) -> None:
    if actual == expected:
        return
    if len(actual) != len(expected):
        raise RuntimeError(
            f"{batch_id}: input row count differs from reconstructed evidence-map slice: "
            f"{len(actual)} != {len(expected)}"
        )
    for row_number, (expected_row, actual_row) in enumerate(zip(expected, actual), 1):
        if actual_row == expected_row:
            continue
        differing_fields = sorted(
            field
            for field in set(expected_row) | set(actual_row)
            if expected_row.get(field) != actual_row.get(field)
        )
        raise RuntimeError(
            f"{batch_id}:{row_number} differs from reconstructed evidence-map input: "
            f"fields={differing_fields}"
        )
    raise RuntimeError(f"{batch_id}: input differs from reconstructed evidence-map slice")


def normalize_decision(
    row: dict[str, Any],
    *,
    layer: str,
    row_number: int,
) -> tuple[str, str, str, tuple[str, ...], str, str]:
    missing = [field for field in DECISION_FIELDS if field not in row]
    if missing:
        raise RuntimeError(f"{layer}:{row_number} is missing decision fields: {missing}")
    scalar_fields = [field for field in DECISION_FIELDS if field != "reason_codes"]
    invalid_scalar_fields = [field for field in scalar_fields if not isinstance(row[field], str)]
    if invalid_scalar_fields:
        raise RuntimeError(f"{layer}:{row_number} has non-string fields: {invalid_scalar_fields}")
    raw_reason_codes = row["reason_codes"]
    if isinstance(raw_reason_codes, str):
        reason_codes = tuple(raw_reason_codes.split(";"))
    elif (
        isinstance(raw_reason_codes, list)
        and raw_reason_codes
        and all(isinstance(code, str) and code for code in raw_reason_codes)
    ):
        reason_codes = tuple(raw_reason_codes)
    else:
        raise RuntimeError(f"{layer}:{row_number} has invalid reason_codes")
    if not reason_codes or any(not code for code in reason_codes):
        raise RuntimeError(f"{layer}:{row_number} has empty reason_codes")
    return (
        row["record_id"],
        row["question_id"],
        row["decision"],
        reason_codes,
        row["confidence"],
        row["evidence_basis"],
    )


def index_decisions(
    rows: list[dict[str, Any]],
    *,
    layer: str,
) -> dict[tuple[str, str], tuple[str, str, str, tuple[str, ...], str, str]]:
    indexed: dict[tuple[str, str], tuple[str, str, str, tuple[str, ...], str, str]] = {}
    for row_number, row in enumerate(rows, 1):
        normalized = normalize_decision(row, layer=layer, row_number=row_number)
        key = (normalized[0], normalized[1])
        if key in indexed:
            raise RuntimeError(f"{layer} has duplicate screening unit: {key}")
        indexed[key] = normalized
    return indexed


def require_same_key_universe(
    expected: set[tuple[str, str]],
    actual: set[tuple[str, str]],
    *,
    layer: str,
) -> None:
    if actual == expected:
        return
    missing = sorted(expected - actual)[:5]
    extra = sorted(actual - expected)[:5]
    raise RuntimeError(
        f"{layer} key universe differs from evidence-map memberships: "
        f"missing={len(expected - actual)} {missing}; extra={len(actual - expected)} {extra}"
    )


def require_same_decisions(
    reference: dict[tuple[str, str], tuple[str, str, str, tuple[str, ...], str, str]],
    candidate: dict[tuple[str, str], tuple[str, str, str, tuple[str, ...], str, str]],
    *,
    reference_layer: str,
    candidate_layer: str,
) -> None:
    mismatches = [key for key in reference if reference[key] != candidate[key]]
    if not mismatches:
        return
    examples = []
    for key in sorted(mismatches)[:3]:
        differing_fields = [
            field
            for field, expected, actual in zip(DECISION_FIELDS, reference[key], candidate[key])
            if expected != actual
        ]
        examples.append({"key": key, "fields": differing_fields})
    raise RuntimeError(
        f"{candidate_layer} differs from {reference_layer} on normalized decisions: "
        f"mismatches={len(mismatches)} examples={examples}"
    )


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def validate_frozen_primary(
    path: Path,
    *,
    classifier_decisions: dict[
        tuple[str, str],
        tuple[str, str, str, tuple[str, ...], str, str],
    ],
    classifier_rows: list[dict[str, str]],
    evidence: dict[str, dict[str, str]],
) -> dict[str, Any]:
    source_name = display_path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"frozen primary validation is missing: {source_name}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"frozen primary validation is malformed JSON: {source_name}: {exc}") from exc
    if not isinstance(document, dict):
        raise RuntimeError(f"{source_name}: primary document must be a JSON object")

    if document.get("schema_version") != "1.0.0":
        raise RuntimeError(f"{source_name}: unsupported primary schema_version")
    if document.get("validation_scope") != (
        "classifier_output_contract_and_ai_authored_real_record_invariants"
    ):
        raise RuntimeError(f"{source_name}: primary validation_scope differs")

    cases = document.get("cases")
    case_count = document.get("case_count")
    if not isinstance(cases, list):
        raise RuntimeError(f"{source_name}: cases must be an array")
    if (
        type(case_count) is not int
        or case_count != len(cases)
        or case_count < 20
        or case_count != len(CASES)
    ):
        raise RuntimeError(
            f"{source_name}: case_count must exactly describe the canonical cases and be at least 20"
        )

    seen_keys: set[tuple[str, str]] = set()
    seen_case_ids: set[str] = set()
    covered_from_cases: set[str] = set()
    recomputed_pass_count = 0
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            raise RuntimeError(f"{source_name}: case {index} must be an object")
        canonical_definition = CASES[index - 1]
        canonical_projection = {
            "case_id": f"INV-{index:03d}",
            **canonical_definition,
        }
        if any(case.get(field) != value for field, value in canonical_projection.items()):
            raise RuntimeError(
                f"{source_name}: case {index} differs from the canonical CASES projection"
            )
        case_id = case.get("case_id")
        record_id = case.get("record_id")
        question_id = case.get("question_id")
        expected = case.get("expected")
        categories = case.get("categories")
        passed = case.get("passed")
        if not isinstance(case_id, str) or not case_id or case_id in seen_case_ids:
            raise RuntimeError(f"{source_name}: case {index} has a missing or duplicate case_id")
        seen_case_ids.add(case_id)
        if not isinstance(record_id, str) or not isinstance(question_id, str):
            raise RuntimeError(f"{source_name}: {case_id} has invalid screening identifiers")
        key = (record_id, question_id)
        if key in seen_keys:
            raise RuntimeError(f"{source_name}: duplicate primary case key: {key}")
        seen_keys.add(key)
        if key not in classifier_decisions:
            raise RuntimeError(f"{source_name}: primary case is absent from current classifier: {key}")
        if expected not in {"retain", "deprioritize", "uncertain"}:
            raise RuntimeError(f"{source_name}: {case_id} has invalid expected decision")
        if (
            not isinstance(categories, list)
            or not categories
            or not all(isinstance(category, str) and category for category in categories)
            or len(categories) != len(set(categories))
        ):
            raise RuntimeError(f"{source_name}: {case_id} has invalid categories")
        covered_from_cases.update(categories)
        if type(passed) is not bool:
            raise RuntimeError(f"{source_name}: {case_id}.passed must be boolean")

        current = classifier_decisions[key]
        observed_reason_codes = case.get("observed_reason_codes")
        observed_fields_match = all(
            (
                case.get("observed_decision") == current[2],
                isinstance(observed_reason_codes, list),
                tuple(observed_reason_codes) == current[3]
                if isinstance(observed_reason_codes, list)
                else False,
                case.get("observed_confidence") == current[4],
                case.get("observed_evidence_basis") == current[5],
            )
        )
        if not observed_fields_match:
            raise RuntimeError(
                f"{source_name}: {case_id} observed fields differ from current classifier"
            )
        recomputed_passed = current[2] == expected
        if passed is not recomputed_passed:
            raise RuntimeError(f"{source_name}: {case_id}.passed differs from recomputation")
        recomputed_pass_count += int(recomputed_passed)

        evidence_row = evidence.get(record_id)
        if evidence_row is None:
            raise RuntimeError(f"{source_name}: {case_id} is absent from current evidence map")
        if case.get("title") != evidence_row["title"]:
            raise RuntimeError(f"{source_name}: {case_id}.title differs from current evidence map")
        if case.get("has_abstract") is not bool(evidence_row["abstract"].strip()):
            raise RuntimeError(f"{source_name}: {case_id}.has_abstract differs from current evidence map")

    pass_count = document.get("pass_count")
    fail_count = document.get("fail_count")
    if type(pass_count) is not int or type(fail_count) is not int:
        raise RuntimeError(f"{source_name}: pass_count and fail_count must be integers")
    if pass_count != recomputed_pass_count or fail_count != case_count - recomputed_pass_count:
        raise RuntimeError(f"{source_name}: pass_count/fail_count differ from case results")
    if pass_count + fail_count != case_count:
        raise RuntimeError(f"{source_name}: pass_count + fail_count differs from case_count")

    required_categories = document.get("required_categories")
    covered_categories = document.get("covered_categories")
    if required_categories != sorted(REQUIRED_CATEGORIES):
        raise RuntimeError(f"{source_name}: required_categories differ from the primary contract")
    if covered_categories != sorted(covered_from_cases):
        raise RuntimeError(f"{source_name}: covered_categories differ from case categories")
    if not REQUIRED_CATEGORIES <= covered_from_cases:
        raise RuntimeError(f"{source_name}: required category coverage is incomplete")

    format_contract = document.get("format_contract")
    if not isinstance(format_contract, dict) or any(
        (
            format_contract.get("passed") is not True,
            format_contract.get("batch_count") != EXPECTED_BATCH_COUNT,
            format_contract.get("expected_batch_count") != EXPECTED_BATCH_COUNT,
            format_contract.get("row_count") != EXPECTED_CLASSIFIER_ROWS,
            format_contract.get("expected_row_count") != EXPECTED_CLASSIFIER_ROWS,
        )
    ):
        raise RuntimeError(f"{source_name}: primary format contract is not 182/43,207 and passed")

    expected_distribution = dict(
        sorted(Counter(row["decision"] for row in classifier_rows).items())
    )
    classifier_layer = document.get("classifier_layer")
    if not isinstance(classifier_layer, dict) or any(
        (
            classifier_layer.get("path") != CLASSIFIER.relative_to(ROOT).as_posix(),
            classifier_layer.get("sha256") != sha256(CLASSIFIER),
            classifier_layer.get("rows") != EXPECTED_CLASSIFIER_ROWS,
            classifier_layer.get("decision_distribution") != expected_distribution,
        )
    ):
        raise RuntimeError(f"{source_name}: classifier_layer is stale or malformed")

    source_hashes = document.get("source_hashes")
    expected_source_hashes = {
        "evidence_map.csv": sha256(EVIDENCE),
        "classifier_decisions.csv": sha256(CLASSIFIER),
        "light_screening_pipeline.py": sha256(V5 / "light_screening_pipeline.py"),
        "v4_screening_manifest.json": sha256(V4_MANIFEST),
        "v4_evidence_map.csv": sha256(V4_EVIDENCE),
        "v4_checkpoints.jsonl": sha256(V4_CHECKPOINTS),
    }
    if not isinstance(source_hashes, dict) or any(
        source_hashes.get(name) != expected_hash
        for name, expected_hash in expected_source_hashes.items()
    ):
        raise RuntimeError(f"{source_name}: primary source hashes are stale or malformed")

    v4_manifest = json.loads(V4_MANIFEST.read_text(encoding="utf-8-sig"))
    v4_classifier_rows = int(v4_manifest["classified_rows"])
    v4_uncertain = int(v4_manifest["decision_distribution"]["uncertain"])
    v4_by_basis = v4_manifest["decision_by_evidence_basis"]
    expected_v4_comparison = {
        "classifier_output_rows": v4_classifier_rows,
        "uncertain": v4_uncertain,
        "uncertain_rate": rate(v4_uncertain, v4_classifier_rows),
        "abstract_rows": int(v4_manifest["evidence_basis_distribution"]["title_abstract"]),
        "abstract_uncertain": int(v4_by_basis["title_abstract|uncertain"]),
        "abstract_uncertain_rate": rate(
            int(v4_by_basis["title_abstract|uncertain"]),
            int(v4_manifest["evidence_basis_distribution"]["title_abstract"]),
        ),
        "title_only_rows": int(v4_manifest["evidence_basis_distribution"]["title_only"]),
        "title_only_uncertain": int(v4_by_basis["title_only|uncertain"]),
        "title_only_uncertain_rate": rate(
            int(v4_by_basis["title_only|uncertain"]),
            int(v4_manifest["evidence_basis_distribution"]["title_only"]),
        ),
    }

    v5_by_basis = Counter(
        (row["evidence_basis"], row["decision"]) for row in classifier_rows
    )
    v5_abstract_rows = sum(row["evidence_basis"] == "abstract" for row in classifier_rows)
    v5_title_only_rows = len(classifier_rows) - v5_abstract_rows
    v5_uncertain = sum(row["decision"] == "uncertain" for row in classifier_rows)
    v5_uncertain_abstract = v5_by_basis[("abstract", "uncertain")]
    v5_uncertain_title = v5_by_basis[("title_only", "uncertain")]
    uncertain_abstract_lengths = sorted(
        len(evidence[row["record_id"]]["abstract"].strip())
        for row in classifier_rows
        if row["decision"] == "uncertain" and row["evidence_basis"] == "abstract"
    )
    if uncertain_abstract_lengths:
        midpoint = len(uncertain_abstract_lengths) // 2
        uncertain_abstract_length_median: float | int | None = (
            uncertain_abstract_lengths[midpoint]
            if len(uncertain_abstract_lengths) % 2
            else (
                uncertain_abstract_lengths[midpoint - 1]
                + uncertain_abstract_lengths[midpoint]
            )
            / 2
        )
    else:
        uncertain_abstract_length_median = None
    question_stats: dict[str, dict[str, float | int]] = {}
    for question_id in ORDER:
        subset = [row for row in classifier_rows if row["question_id"] == question_id]
        uncertain = sum(row["decision"] == "uncertain" for row in subset)
        question_stats[question_id] = {
            "rows": len(subset),
            "uncertain": uncertain,
            "uncertain_rate": rate(uncertain, len(subset)),
        }
    expected_v5_comparison = {
        "classifier_output_rows": len(classifier_rows),
        "uncertain": v5_uncertain,
        "uncertain_rate": rate(v5_uncertain, len(classifier_rows)),
        "abstract_rows": v5_abstract_rows,
        "abstract_uncertain": v5_uncertain_abstract,
        "abstract_uncertain_rate": rate(v5_uncertain_abstract, v5_abstract_rows),
        "title_only_rows": v5_title_only_rows,
        "title_only_uncertain": v5_uncertain_title,
        "title_only_uncertain_rate": rate(v5_uncertain_title, v5_title_only_rows),
        "uncertain_with_abstract_share": rate(v5_uncertain_abstract, v5_uncertain),
        "uncertain_abstract_length_median": uncertain_abstract_length_median,
        "uncertain_abstract_at_least_180_chars": sum(
            length >= 180 for length in uncertain_abstract_lengths
        ),
        "uncertain_abstract_at_least_600_chars": sum(
            length >= 600 for length in uncertain_abstract_lengths
        ),
        "questions": question_stats,
    }
    v4_uncertain_rate = rate(v4_uncertain, v4_classifier_rows)
    expected_difference = {
        "uncertain_rate_percentage_point_change": 100
        * (rate(v5_uncertain, len(classifier_rows)) - v4_uncertain_rate),
        "uncertain_rate_ratio": (
            rate(v5_uncertain, len(classifier_rows)) / v4_uncertain_rate
            if v4_uncertain_rate
            else None
        ),
    }
    uncertain_comparison = document.get("uncertain_comparison")
    if not isinstance(uncertain_comparison, dict) or any(
        (
            uncertain_comparison.get("comparison_unit") != "classifier_output_row",
            uncertain_comparison.get("v4_0") != expected_v4_comparison,
            uncertain_comparison.get("v5_0_classifier_layer") != expected_v5_comparison,
            uncertain_comparison.get("difference") != expected_difference,
        )
    ):
        raise RuntimeError(
            f"{source_name}: uncertain_comparison counts or rates differ from current sources"
        )

    if type(document.get("human_reference_rows")) is not int or document.get(
        "human_reference_rows"
    ) != 0:
        raise RuntimeError(f"{source_name}: human_reference_rows must be integer 0")
    if document.get("independent_blinding") is not False:
        raise RuntimeError(f"{source_name}: independent_blinding must be false")
    if document.get("release_ready") is not False:
        raise RuntimeError(f"{source_name}: release_ready must be false")
    return document


def atomic_json(path: Path, payload: object) -> None:
    rendered = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(rendered)
    os.replace(temporary, path)


def resolve_supplemental_output(path: Path) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    candidate = candidate.resolve()
    allowed = SUPPLEMENTAL_VALIDATION.resolve()
    if candidate != allowed:
        raise RuntimeError(
            "supplemental output must be exactly "
            f"{SUPPLEMENTAL_VALIDATION.relative_to(ROOT).as_posix()}"
        )
    return candidate


def rate(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def main(*, output_path: Path | None = None) -> int:
    supplemental_output = (
        resolve_supplemental_output(output_path) if output_path is not None else None
    )
    evidence_rows = read_csv(EVIDENCE)
    evidence, membership_keys = evidence_memberships(evidence_rows)
    if len(membership_keys) != EXPECTED_CLASSIFIER_ROWS:
        raise RuntimeError(
            "evidence_map.csv does not define the immutable "
            f"{EXPECTED_CLASSIFIER_ROWS:,}-membership universe: {len(membership_keys):,}"
        )

    with CLASSIFIER.open(encoding="utf-8-sig", newline="") as handle:
        classifier_reader = csv.DictReader(handle)
        if classifier_reader.fieldnames != DECISION_FIELDS:
            raise RuntimeError(
                f"classifier_decisions.csv fields differ: {classifier_reader.fieldnames} != {DECISION_FIELDS}"
            )
        classifier_rows = list(classifier_reader)
    classifier_decisions = index_decisions(classifier_rows, layer="classifier_decisions.csv")
    if len(classifier_rows) != EXPECTED_CLASSIFIER_ROWS:
        raise RuntimeError(
            "classifier_decisions.csv is not the immutable "
            f"{EXPECTED_CLASSIFIER_ROWS:,}-row layer: {len(classifier_rows):,}"
        )
    require_same_key_universe(
        membership_keys,
        set(classifier_decisions),
        layer="classifier_decisions.csv",
    )

    frozen_primary = validate_frozen_primary(
        FROZEN_VALIDATION,
        classifier_decisions=classifier_decisions,
        classifier_rows=classifier_rows,
        evidence=evidence,
    )

    checkpoint_rows = read_jsonl(CLASSIFIER_CHECKPOINTS)
    checkpoint_decisions = index_decisions(checkpoint_rows, layer="screening/checkpoints.jsonl")
    if len(checkpoint_rows) != EXPECTED_CLASSIFIER_ROWS:
        raise RuntimeError(
            "screening/checkpoints.jsonl does not contain exactly "
            f"{EXPECTED_CLASSIFIER_ROWS:,} decisions: {len(checkpoint_rows):,}"
        )
    require_same_key_universe(
        membership_keys,
        set(checkpoint_decisions),
        layer="screening/checkpoints.jsonl",
    )

    format_batches = 0
    batch_rows: list[dict[str, Any]] = []
    batch_ids: set[str] = set()
    batch_input_hashes: dict[str, str] = {}
    batch_output_hashes: dict[str, str] = {}
    batch_manifest_hashes: dict[str, str] = {}
    evidence_hash = sha256(EVIDENCE)
    prompt_hash = sha256(PROMPT)
    prompt_path = PROMPT.relative_to(ROOT).as_posix()
    for question_id in ORDER:
        manifest_path = BATCHES / question_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_relative_path = manifest_path.relative_to(ROOT).as_posix()
        batch_manifest_hashes[manifest_relative_path] = sha256(manifest_path)
        if manifest.get("question_id") != question_id:
            raise RuntimeError(f"{manifest_path.name}: question_id differs from its directory")
        if manifest.get("evidence_map_sha256") != evidence_hash:
            raise RuntimeError(f"{manifest_relative_path}: evidence-map hash mismatch")
        if manifest.get("prompt_path") != prompt_path:
            raise RuntimeError(f"{manifest_relative_path}: prompt path mismatch")
        if manifest.get("prompt_sha256") != prompt_hash:
            raise RuntimeError(f"{manifest_relative_path}: prompt hash mismatch")

        reconstructed_inputs = expected_question_inputs(evidence_rows, question_id)
        input_offset = 0
        question_rows = 0
        for batch in manifest["batches"]:
            batch_id = batch.get("batch_id")
            if not isinstance(batch_id, str) or not batch_id:
                raise RuntimeError(f"{manifest_relative_path}: invalid batch_id")
            if batch_id in batch_ids:
                raise RuntimeError(f"duplicate classifier batch_id: {batch_id}")
            batch_ids.add(batch_id)

            input_path = ROOT / batch["input_path"]
            input_hash = sha256(input_path)
            if input_hash != batch.get("input_sha256"):
                raise RuntimeError(f"{batch_id}: input hash differs from manifest")
            input_relative_path = input_path.relative_to(ROOT).as_posix()
            batch_input_hashes[input_relative_path] = input_hash
            declared_row_count = int(batch.get("row_count", -1))
            input_rows = read_jsonl(input_path)
            expected_input_slice = reconstructed_inputs[
                input_offset:input_offset + declared_row_count
            ]
            require_same_batch_inputs(
                expected_input_slice,
                input_rows,
                batch_id=batch_id,
            )
            input_offset += len(input_rows)

            rows = validate_output(batch)
            if len(rows) != declared_row_count:
                raise RuntimeError(f"{batch_id}: validated output count differs from manifest")
            if any(row["question_id"] != question_id for row in rows):
                raise RuntimeError(f"{batch_id}: output contains a different question_id")
            output_path = ROOT / batch["output_path"]
            batch_output_hashes[output_path.relative_to(ROOT).as_posix()] = sha256(output_path)
            batch_rows.extend(rows)
            question_rows += len(rows)
            format_batches += 1
        if input_offset != len(reconstructed_inputs):
            raise RuntimeError(
                f"{question_id}: manifest batches cover {input_offset} reconstructed inputs, "
                f"expected {len(reconstructed_inputs)}"
            )
        if int(manifest.get("row_count", -1)) != len(reconstructed_inputs):
            raise RuntimeError(
                f"{question_id}: manifest row_count differs from reconstructed evidence-map membership"
            )
        if question_rows != len(reconstructed_inputs):
            raise RuntimeError(
                f"{question_id}: validated output count {question_rows} differs from reconstructed inputs"
            )

    batch_decisions = index_decisions(batch_rows, layer="normalized classifier batch outputs")
    if (format_batches, len(batch_rows)) != (EXPECTED_BATCH_COUNT, EXPECTED_CLASSIFIER_ROWS):
        raise RuntimeError(
            "classifier batch contract mismatch: "
            f"{format_batches}/{len(batch_rows)} != {EXPECTED_BATCH_COUNT}/{EXPECTED_CLASSIFIER_ROWS}"
        )
    require_same_key_universe(
        membership_keys,
        set(batch_decisions),
        layer="normalized classifier batch outputs",
    )
    require_same_decisions(
        batch_decisions,
        checkpoint_decisions,
        reference_layer="normalized classifier batch outputs",
        candidate_layer="screening/checkpoints.jsonl",
    )
    require_same_decisions(
        batch_decisions,
        classifier_decisions,
        reference_layer="normalized classifier batch outputs",
        candidate_layer="classifier_decisions.csv",
    )

    classifier = {(row["record_id"], row["question_id"]): row for row in classifier_rows}

    seen_categories: set[str] = set()
    observed_cases: list[dict[str, Any]] = []
    for index, definition in enumerate(CASES, 1):
        key = (definition["record_id"], definition["question_id"])
        if key not in classifier or definition["record_id"] not in evidence:
            raise RuntimeError(f"missing invariant record: {key}")
        source = evidence[definition["record_id"]]
        observed = classifier[key]
        seen_categories.update(definition["categories"])
        observed_cases.append(
            {
                "case_id": f"INV-{index:03d}",
                **definition,
                "title": source["title"],
                "has_abstract": bool(source["abstract"].strip()),
                "observed_decision": observed["decision"],
                "observed_reason_codes": [code for code in observed["reason_codes"].split(";") if code],
                "observed_confidence": observed["confidence"],
                "observed_evidence_basis": observed["evidence_basis"],
                "passed": observed["decision"] == definition["expected"],
            }
        )
    missing_categories = sorted(REQUIRED_CATEGORIES - seen_categories)
    if missing_categories:
        raise RuntimeError(f"required invariant categories missing: {missing_categories}")

    format_rows = len(batch_rows)

    v4_manifest = json.loads(V4_MANIFEST.read_text(encoding="utf-8"))
    v4_classifier_rows = int(v4_manifest["classified_rows"])
    v4_uncertain = int(v4_manifest["decision_distribution"]["uncertain"])
    v4_by_basis = v4_manifest["decision_by_evidence_basis"]
    v5_by_basis = Counter(
        (row["evidence_basis"], row["decision"]) for row in classifier_rows
    )
    v5_abstract_rows = sum(row["evidence_basis"] == "abstract" for row in classifier_rows)
    v5_title_only_rows = len(classifier_rows) - v5_abstract_rows
    v5_uncertain = sum(row["decision"] == "uncertain" for row in classifier_rows)
    question_stats = {}
    for question_id in ORDER:
        subset = [row for row in classifier_rows if row["question_id"] == question_id]
        uncertain = sum(row["decision"] == "uncertain" for row in subset)
        question_stats[question_id] = {
            "rows": len(subset),
            "uncertain": uncertain,
            "uncertain_rate": rate(uncertain, len(subset)),
        }

    abstract_lengths = {
        row["record_id"]: len(row["abstract"].strip()) for row in read_csv(EVIDENCE)
    }
    uncertain_abstract_lengths = sorted(
        abstract_lengths[row["record_id"]]
        for row in classifier_rows
        if row["decision"] == "uncertain" and row["evidence_basis"] == "abstract"
    )
    mid = len(uncertain_abstract_lengths) // 2
    median_length = (
        uncertain_abstract_lengths[mid]
        if len(uncertain_abstract_lengths) % 2
        else (uncertain_abstract_lengths[mid - 1] + uncertain_abstract_lengths[mid]) / 2
    )
    v5_uncertain_abstract = v5_by_basis[("abstract", "uncertain")]
    v5_uncertain_title = v5_by_basis[("title_only", "uncertain")]
    v5_uncertain_abstract_at_least_180 = sum(length >= 180 for length in uncertain_abstract_lengths)
    v5_uncertain_abstract_at_least_600 = sum(length >= 600 for length in uncertain_abstract_lengths)

    pass_count = sum(case["passed"] for case in observed_cases)
    payload = {
        "schema_version": "1.1.0",
        "artifact_role": "supplemental_classifier_integrity_validation",
        "frozen_classifier_validation": {
            "path": FROZEN_VALIDATION.relative_to(ROOT).as_posix(),
            "exists": True,
            "sha256": sha256(FROZEN_VALIDATION),
            "modified_by_this_validator": False,
            "primary_contract_validated": True,
            "schema_version": frozen_primary["schema_version"],
            "case_count": frozen_primary["case_count"],
            "pass_count": frozen_primary["pass_count"],
            "fail_count": frozen_primary["fail_count"],
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_scope": "classifier_output_contract_and_ai_authored_real_record_invariants",
        "semantic_classifier_function_preserved": False,
        "semantic_classifier_function_note": (
            "light_screening_pipeline.py contains prepare, output validation, and ingest logic but no callable "
            "semantic classify function; semantic checks therefore compare immutable outputs with AI-authored expectations."
        ),
        "ai_reference_standard": "codex_ai_authored_invariant_expectations",
        "human_reference_rows": 0,
        "independent_blinding": False,
        "independent_blinding_ai": False,
        "release_ready": False,
        "classifier_layer": {
            "path": CLASSIFIER.relative_to(ROOT).as_posix(),
            "sha256": sha256(CLASSIFIER),
            "rows": len(classifier_rows),
            "decision_distribution": dict(sorted(Counter(row["decision"] for row in classifier_rows).items())),
        },
        "cross_layer_integrity": {
            "expected_screening_units": EXPECTED_CLASSIFIER_ROWS,
            "normalized_decision_fields": list(DECISION_FIELDS),
            "evidence_map_record_count": len(evidence_rows),
            "evidence_map_membership_key_count": len(membership_keys),
            "classifier_checkpoint_row_count": len(checkpoint_rows),
            "classifier_batch_count": format_batches,
            "classifier_batch_output_row_count": len(batch_rows),
            "classifier_decisions_csv_row_count": len(classifier_rows),
            "key_universe_exact_match": True,
            "batch_input_evidence_fields_and_order_exact_match": True,
            "six_normalized_decision_fields_exact_match": True,
            "batch_input_files_sha256": dict(sorted(batch_input_hashes.items())),
            "batch_output_files_sha256": dict(sorted(batch_output_hashes.items())),
        },
        "format_contract": {
            "batch_count": format_batches,
            "row_count": format_rows,
            "expected_batch_count": EXPECTED_BATCH_COUNT,
            "expected_row_count": EXPECTED_CLASSIFIER_ROWS,
            "passed": (
                format_batches == EXPECTED_BATCH_COUNT
                and format_rows == EXPECTED_CLASSIFIER_ROWS
            ),
            "checks": [
                "input_output_row_count",
                "record_question_key_and_order",
                "six_field_output_schema",
                "decision_reason_confidence_enums",
                "evidence_basis_matches_abstract_presence",
                "title_only_confidence_is_low",
                "evidence_map_membership_key_universe",
                "batch_input_evidence_fields_and_order",
                "five_manifests_frozen_prompt_path_and_hash",
                "checkpoint_key_universe",
                "classifier_csv_key_universe",
                "batch_checkpoint_csv_six_field_exact_agreement",
            ],
        },
        "required_categories": sorted(REQUIRED_CATEGORIES),
        "covered_categories": sorted(seen_categories),
        "case_sampling": {
            "method": "purposefully_selected_boundary_non_probability_sample",
            "random_sample": False,
            "corpus_performance_inference_allowed": False,
            "note_ko": "42건은 필수 경계 유형과 알려진 오분류 후보를 의도적으로 포함한 비확률 표본이다. 이 표본으로 전체 코퍼스의 분류 성능을 추정할 수 없다.",
        },
        "case_count": len(observed_cases),
        "pass_count": pass_count,
        "fail_count": len(observed_cases) - pass_count,
        "agreement_vs_ai_reference": rate(pass_count, len(observed_cases)),
        "cases": observed_cases,
        "uncertain_comparison": {
            "comparison_unit": "classifier_output_row",
            "v4_0": {
                "classifier_output_rows": v4_classifier_rows,
                "uncertain": v4_uncertain,
                "uncertain_rate": rate(v4_uncertain, v4_classifier_rows),
                "abstract_rows": int(v4_manifest["evidence_basis_distribution"]["title_abstract"]),
                "abstract_uncertain": int(v4_by_basis["title_abstract|uncertain"]),
                "abstract_uncertain_rate": rate(
                    int(v4_by_basis["title_abstract|uncertain"]),
                    int(v4_manifest["evidence_basis_distribution"]["title_abstract"]),
                ),
                "title_only_rows": int(v4_manifest["evidence_basis_distribution"]["title_only"]),
                "title_only_uncertain": int(v4_by_basis["title_only|uncertain"]),
                "title_only_uncertain_rate": rate(
                    int(v4_by_basis["title_only|uncertain"]),
                    int(v4_manifest["evidence_basis_distribution"]["title_only"]),
                ),
            },
            "v5_0_classifier_layer": {
                "classifier_output_rows": len(classifier_rows),
                "uncertain": v5_uncertain,
                "uncertain_rate": rate(v5_uncertain, len(classifier_rows)),
                "abstract_rows": v5_abstract_rows,
                "abstract_uncertain": v5_uncertain_abstract,
                "abstract_uncertain_rate": rate(v5_uncertain_abstract, v5_abstract_rows),
                "title_only_rows": v5_title_only_rows,
                "title_only_uncertain": v5_uncertain_title,
                "title_only_uncertain_rate": rate(v5_uncertain_title, v5_title_only_rows),
                "uncertain_with_abstract_share": rate(v5_uncertain_abstract, v5_uncertain),
                "uncertain_abstract_length_median": median_length,
                "uncertain_abstract_at_least_180_chars": v5_uncertain_abstract_at_least_180,
                "uncertain_abstract_at_least_600_chars": v5_uncertain_abstract_at_least_600,
                "questions": question_stats,
            },
            "difference": {
                "uncertain_rate_percentage_point_change": 100 * (
                    rate(v5_uncertain, len(classifier_rows)) - rate(v4_uncertain, v4_classifier_rows)
                ),
                "uncertain_rate_ratio": rate(v5_uncertain, len(classifier_rows)) / rate(v4_uncertain, v4_classifier_rows),
            },
            "causal_interpretation": {
                "status": "unverified_hypotheses",
                "causal_inference_supported": False,
                "note_ko": "관찰값은 입력과 출력에서 직접 계산했다. 원인 설명은 대조 실험으로 검증하지 않은 가설이다.",
            },
            "descriptive_findings_ko": [
                f"분류 출력 행은 v4.0의 {v4_classifier_rows:,}건에서 v5.0의 {len(classifier_rows):,}건으로 늘었다.",
                f"v5.0 uncertain은 {v5_uncertain:,}건이며, 이 중 초록 보유 행은 {v5_uncertain_abstract:,}건이다.",
                (
                    f"초록 보유 uncertain 중 {v5_uncertain_abstract_at_least_180:,}건"
                    f"({rate(v5_uncertain_abstract_at_least_180, v5_uncertain_abstract):.1%})은 초록 길이가 180자 이상이다."
                ),
                "사람 참조표준은 0건이므로 이 비교만으로 분류기의 실제 성능을 추정할 수 없다.",
            ],
            "unverified_causal_hypotheses_ko": [
                (
                    "검색 범위 확대에 따른 입력 집합 변화가 uncertain 비율 변화에 기여했을 수 있다. "
                    "이 검증은 검색 범위의 효과를 따로 분리하지 않았다."
                ),
                (
                    "노출과 결과 신호를 함께 요구하는 결정 규칙이 일부 긴 초록도 uncertain으로 분류했을 수 있다. "
                    "보존된 호출 가능 분류 함수가 없어 규칙의 인과 효과를 재현할 수 없다."
                ),
                (
                    "v4.0과 v5.0의 분류 규칙 및 이유 코드 차이가 uncertain 비율 변화에 기여했을 수 있다. "
                    "동일 입력에 두 분류기를 적용한 대조 결과가 없어 원인으로 확정할 수 없다."
                ),
            ],
        },
        "limitations": [
            "The semantic expectations were authored by Codex and are not a human reference standard.",
            "The historical semantic classifier implementation is not preserved as a callable function.",
            "The 42 cases are a purposefully selected boundary/non-probability sample; agreement_vs_ai_reference is not a corpus performance estimate.",
            "The causal explanations for the uncertain-rate difference are unverified hypotheses, not findings.",
            "Failed invariant cases are recorded for adjudication and do not mutate the classifier layer.",
        ],
        "source_hashes": {
            "evidence_map.csv": sha256(EVIDENCE),
            "frozen_light_screening_prompt.md": sha256(PROMPT),
            "classifier_decisions.csv": sha256(CLASSIFIER),
            "classifier_checkpoints.jsonl": sha256(CLASSIFIER_CHECKPOINTS),
            "classifier_batch_manifests": dict(sorted(batch_manifest_hashes.items())),
            "classifier_validation_v50.py": sha256(VALIDATOR),
            "light_screening_pipeline.py": sha256(V5 / "light_screening_pipeline.py"),
            "v4_screening_manifest.json": sha256(V4_MANIFEST),
            "v4_evidence_map.csv": sha256(V4_EVIDENCE),
            "v4_checkpoints.jsonl": sha256(V4_CHECKPOINTS),
        },
    }
    dry_run = supplemental_output is None
    result: dict[str, Any] = {
        "path": (
            supplemental_output.relative_to(ROOT).as_posix()
            if supplemental_output is not None
            else None
        ),
        "dry_run": dry_run,
        "output_written": supplemental_output is not None,
        "evidence_map_membership_key_count": len(membership_keys),
        "batch_count": format_batches,
        "batch_input_row_count": sum(len(expected_question_inputs(evidence_rows, q)) for q in ORDER),
        "batch_output_row_count": len(batch_rows),
        "checkpoint_row_count": len(checkpoint_rows),
        "classifier_csv_row_count": len(classifier_rows),
        "prompt_hash_verified_for_manifest_count": len(batch_manifest_hashes),
        "frozen_primary_contract_validated": True,
        "case_count": len(observed_cases),
        "pass_count": pass_count,
        "fail_count": len(observed_cases) - pass_count,
    }
    if dry_run:
        result["frozen_validation_path"] = FROZEN_VALIDATION.relative_to(ROOT).as_posix()
        result["frozen_validation_sha256"] = (
            sha256(FROZEN_VALIDATION) if FROZEN_VALIDATION.exists() else None
        )
    else:
        atomic_json(supplemental_output, payload)
        result["sha256"] = sha256(supplemental_output)
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate current inputs without writing a supplemental artifact (the default)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "write only research_v3/otc/literature/v5/screening/"
            "classifier_validation_cross_layer.json"
        ),
    )
    arguments = parser.parse_args()
    if arguments.dry_run and arguments.output is not None:
        parser.error("--dry-run and --output cannot be used together")
    raise SystemExit(main(output_path=arguments.output))
