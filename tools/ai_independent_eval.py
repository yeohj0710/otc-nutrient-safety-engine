"""P3-B 규칙엔진 AI 맹검 독립평가 지원 도구.

이 스크립트는 **판정하지 않는다.** 블라인드 카드 렌더링, 에이전트가 직접 쓴 판정의 검증·적재,
명시적 코드 규칙에 의한 종합 라벨 도출, 라벨 파일 잠금(SHA-256 + 생성 시각), 잠금 이후의
지표 산출만 수행한다. 엔진 예측 연결은 잠금 이후 별도 단계(`scripts/research/otc/
predict-ai-independent.ts`)에서만 이뤄지며, 이 스크립트의 `finalize` 는 잠금 시각이 예측 시각보다
앞선다는 것을 검증한 뒤에만 지표를 계산한다.

서브커맨드
    render-round    라운드별 무작위 순서 블라인드 카드 렌더링(별칭만 노출)
    ingest-round    에이전트가 쓴 판정 적재·검증 후 종합 라벨 도출
    lock            3라운드 다수결 라벨을 확정하고 SHA-256 + 생성 시각으로 잠근다
    finalize        잠금 이후 기록된 엔진 예측을 연결해 지표를 계산한다
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "research_v3" / "otc" / "validation"
CASE_DIR = VALIDATION / "ai_independent_cases"
CASE_MANIFEST = CASE_DIR / "case_manifest.json"
LEGACY_CASE_DIR = VALIDATION / "independent_cases"
NORMALIZED = ROOT / "research_v3" / "otc" / "normalized"
RULES_CSV = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
PROMPT = ROOT / "research_v3" / "otc" / "validation" / "ai_independent_eval_prompt.md"

EVAL_DIR = VALIDATION / "ai_independent_evaluation"
ROUNDS_DIR = EVAL_DIR / "rounds"
LOCK_PATH = EVAL_DIR / "ai_reference_labels.locked.json"
PREDICTION_AUDIT = EVAL_DIR / "ai_independent_prediction_audit.json"
OUTPUT = VALIDATION / "ai_independent_evaluation.json"

ROUND_SEEDS = {1: 20260727101, 2: 20260727102, 3: 20260727103}
CHUNK_ROWS = 30
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260727888

ELEMENT_KEYS = ("E", "T")
ELEMENT_VALUES = ("Y", "N", "U")
LABELS = ("warning", "no_warning", "uncertain")

COMPOSITE_RULE_TEXT_KO = (
    "1) E 또는 T 가 N 이면 no_warning. 2) E=Y 이고 T=Y 이면 warning. 3) 그 외(E 또는 T 가 U)는 "
    "uncertain. E 는 규칙 유형이 겨냥하는 성분·조합 노출의 존재, T 는 발동 조건(사용자 조건 "
    "또는 허가 수량 기준 초과)의 충족을 뜻한다."
)

RULE_TYPE_DEFINITION_KO = {
    "duplicate_ingredient": "같은 유효성분이 둘 이상의 제품에 중복되어 총량이 늘어나는 상황",
    "duplicate_pharmacologic_class": "같은 약효 계열(예: NSAID) 성분을 둘 이상 함께 복용하는 상황",
    "max_daily_dose": "계산한 하루 총 성분량이 허가된 1일 최대량을 넘는 상황",
    "minimum_interval": "허가된 최소 복용 간격이 지나기 전에 다시 복용하는 상황",
    "age_restriction": "입력한 연령이 해당 제품의 허가 연령 기준에 맞지 않는 상황",
    "pregnancy_lactation": "임신 또는 수유 중 주의가 필요한 성분을 복용하는 상황",
    "hepatic_disease": "간질환이 있는 사람이 간독성 주의 성분을 복용하는 상황",
    "renal_disease": "신장질환이 있는 사람이 신독성 주의 성분을 복용하는 상황",
    "gi_bleeding_ulcer": "위장관 출혈·궤양 병력이 있는 사람이 위장관 위험 성분을 복용하는 상황",
    "sedation_driving": "졸림을 유발할 수 있는 성분을 복용하고 운전·기계 조작을 하는 상황",
    "alcohol": "음주와 함께 복용할 때 주의가 필요한 성분을 복용하는 상황",
    "anticoagulant_antiplatelet": "항응고제·항혈소판제 복용자가 출혈 위험 성분을 함께 쓰는 상황",
    "sedative_medication": "진정 작용이 있는 다른 약과 겹쳐 복용하는 상황",
    "decongestant_hypertension": "고혈압·심혈관질환자가 비충혈제거 성분을 복용하는 상황",
    "maximum_duration": "허가된 연속 복용 기간을 넘겨 계속 복용하는 상황",
    "urgent_referral": "즉시 상담·진료가 필요한 중대 이상 증상이 입력된 상황",
}

# 규칙 유형별 허가원문(사용상의 주의, NB) 발췌 키워드.
# 규칙표가 아니라 허가원문에서 뽑는다. 규칙 바인딩·심각도·규칙 ID 는 카드에 넣지 않는다.
RULE_TYPE_SOURCE_KEYWORDS = {
    "duplicate_ingredient": ("다른 감기약", "해열", "진통", "함께 복용", "병용"),
    "duplicate_pharmacologic_class": ("다른 감기약", "해열", "진통", "함께 복용", "병용"),
    "max_daily_dose": ("정해진 용량", "초과", "1일", "최대"),
    "minimum_interval": ("간격", "시간마다", "재복용"),
    "age_restriction": ("소아", "세 미만", "세 이하", "영아", "어린이"),
    "pregnancy_lactation": ("임부", "임신", "수유", "모유", "태아", "산부"),
    "hepatic_disease": ("간장애", "간질환", "간장", "간기능"),
    "renal_disease": ("신장", "신질환", "신기능", "콩팥"),
    "gi_bleeding_ulcer": ("위장관", "궤양", "위출혈", "위장출혈", "소화성궤양", "천공"),
    "sedation_driving": ("운전", "기계조작", "기계 조작", "졸음", "졸릴"),
    "alcohol": ("음주", "술", "알코올", "알콜"),
    "anticoagulant_antiplatelet": ("항응고", "와파린", "쿠마린", "혈액응고", "아스피린"),
    "sedative_medication": ("진정제", "수면제", "안정제", "중추신경", "진정작용", "진정 작용"),
    "decongestant_hypertension": ("고혈압", "심장", "심혈관", "혈압"),
    "maximum_duration": ("장기간", "장기복용", "장기투여", "일 이상", "연용"),
    "urgent_referral": ("쇼크", "아나필락시", "호흡곤란", "즉각", "의사", "중대한"),
}
# 규칙 유형이 없는 카드(legacy 전건 질문)에 쓰는 기본 키워드.
ANY_WARNING_SOURCE_KEYWORDS = (
    "임부",
    "수유",
    "간장애",
    "신장",
    "위장관",
    "고혈압",
    "운전",
    "음주",
    "항응고",
    "소아",
)
# 맹검 훼손 사례. 사례 생성 중 `independent_scenarios.csv` 앞 2행을 확인하다가 해당 행의
# `human_reference_label` 과 기존 `prediction` 값이 평가자에게 노출됐다. 판정 자체는 카드만
#보고 수행했지만 노출 사실이 사라지지 않으므로 별도 표시하고 1차 지표에서 제외한다.
BLINDING_COMPROMISED_CASE_IDS = ("IND-OTC-001", "IND-OTC-002")
BLINDING_COMPROMISE_REASON_KO = (
    "사례 생성 단계에서 independent_scenarios.csv 앞 2행의 human_reference_label 과 "
    "기존 prediction 이 평가자에게 노출됐다. 노출 이후에는 잠금 전까지 해당 파일을 다시 열지 "
    "않았으나, 이 2건은 맹검이 성립하지 않으므로 모든 1차 지표에서 제외하고 별도 보고한다."
)

SOURCE_EXCERPT_MAX_LINES = 3
SOURCE_EXCERPT_MAX_CHARS = 150
# 용법·용량(UD) 은 적응증 나열이 길어 카드가 비대해진다. 정규화된 허가 상한이 이미 용량·간격을
# 담고 있으므로, UD 에서는 상한 표에 없는 기준(연령)에 해당하는 문장만 뽑는다.
USAGE_AGE_KEYWORDS = ("세", "개월", "소아", "성인", "어린이", "영아", "연령")
USAGE_EXCERPT_MAX_LINES = 3

PROFILE_LABEL_KO = {
    "ageYears": "나이",
    "pregnant": "임신",
    "lactating": "수유",
    "liverDisease": "간질환",
    "kidneyDisease": "신장질환",
    "giBleedingOrUlcer": "위장관 출혈·궤양",
    "hypertensionOrCardiovascularDisease": "고혈압·심혈관질환",
    "willDrive": "운전 예정",
    "alcohol": "음주",
    "medications": "복용 중 약물",
    "redFlagSymptoms": "입력 증상",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 종합 라벨 도출 — 명시적 코드 규칙
# --------------------------------------------------------------------------
def derive_case_label(elements: dict[str, str]) -> str:
    for key in ELEMENT_KEYS:
        if elements.get(key) not in ELEMENT_VALUES:
            raise ValueError(f"invalid element value for {key}: {elements.get(key)!r}")
    if elements["E"] == "N" or elements["T"] == "N":
        return "no_warning"
    if elements["E"] == "Y" and elements["T"] == "Y":
        return "warning"
    return "uncertain"


def majority_label(labels: Sequence[str]) -> str:
    counts = Counter(labels)
    top, top_count = counts.most_common(1)[0]
    return "unresolved" if top_count == 1 else top


# --------------------------------------------------------------------------
# 카드 렌더링
# --------------------------------------------------------------------------
def load_reference_products() -> dict[str, dict[str, Any]]:
    from tools.ai_independent_cases import load_products

    return load_products()


def load_cards() -> list[dict[str, Any]]:
    products = load_reference_products()
    cards: list[dict[str, Any]] = []

    manifest = _read_json(CASE_MANIFEST)
    for entry in manifest["cases"]:
        payload = _read_json(CASE_DIR / entry["path"])
        cards.append(
            {
                "card_id": payload["caseId"],
                "track": "generated",
                "question": "rule_type",
                "target_rule_type": payload["targetRuleType"],
                "product_inputs": payload["productInputs"],
                "user_profile": payload["userProfile"],
            }
        )

    for path in sorted(LEGACY_CASE_DIR.glob("IND-OTC-*.json")):
        payload = _read_json(path)
        if payload.get("referenceLabel") is not None or payload.get("prediction") is not None:
            raise SystemExit(f"legacy case is not blind: {path.name}")
        cards.append(
            {
                "card_id": payload["scenarioId"],
                "track": "legacy_reevaluation",
                "question": "any_warning",
                "target_rule_type": None,
                "scenario_family": payload.get("scenarioFamily"),
                "product_inputs": payload["productInputs"],
                "user_profile": payload["userProfile"],
            }
        )

    for card in cards:
        card["products_rendered"] = [
            _render_product(item, products) for item in card["product_inputs"]
        ]
        card["profile_rendered"] = _render_profile(card["user_profile"])
        card["source_rendered"] = _render_source_excerpt(card)
    return cards


def _extracted_dir(item_sequence: str) -> Path:
    return ROOT / "research_v3" / "otc" / "extracted" / "nedrug" / item_sequence


def _read_extracted(item_sequence: str, name: str) -> str:
    path = _extracted_dir(item_sequence) / f"{name}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _match_lines(text: str, keywords: Sequence[str], limit: int) -> list[str]:
    picked: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or line in picked:
            continue
        if any(keyword in line for keyword in keywords):
            picked.append(line[:SOURCE_EXCERPT_MAX_CHARS])
        if len(picked) >= limit:
            break
    return picked


def _render_source_excerpt(card: dict[str, Any]) -> list[str]:
    """허가원문(용법·용량 UD, 사용상의 주의 NB) 발췌를 카드에 붙인다.

    규칙표(rules.csv)·엔진 설정은 절대 참조하지 않는다. 참조표준 평가자가 비교할 허가 기준이
    카드에 없어 U 로 몰리는 것을 막기 위한 것이며, 출처는 식약처 허가원문 추출 텍스트뿐이다.
    """
    rule_type = card.get("target_rule_type")
    keywords = (
        RULE_TYPE_SOURCE_KEYWORDS.get(rule_type, ())
        if rule_type
        else ANY_WARNING_SOURCE_KEYWORDS
    )
    lines: list[str] = []
    for item in card["product_inputs"]:
        if item.get("inputType") != "verified_product":
            continue
        seq = item["itemSequence"]
        usage = _match_lines(
            _read_extracted(seq, "UD"), USAGE_AGE_KEYWORDS, USAGE_EXCERPT_MAX_LINES
        )
        cautions = _match_lines(_read_extracted(seq, "NB"), keywords, SOURCE_EXCERPT_MAX_LINES)
        if not usage and not cautions:
            continue
        lines.append(f"    허가원문 발췌 [{seq}]")
        for line in usage:
            lines.append(f"      용법·용량(UD): {line}")
        for caution in cautions:
            lines.append(f"      사용상의주의(NB): {caution}")
    return lines


def _render_product(item: dict[str, Any], products: dict[str, dict[str, Any]]) -> list[str]:
    if item.get("inputType") != "verified_product":
        return [f"제품검색어: {item.get('productNameQuery', '')}"]
    product = products.get(item["itemSequence"])
    if product is None:
        return [f"미확인 품목: {item['itemSequence']}"]
    head = (
        f"{product['productName']} | 1회 {item['unitsPerDose']} × 1일 {item['dosesPerDay']}회"
    )
    extras = []
    if item.get("hoursSincePreviousDose") is not None:
        extras.append(f"직전 복용 후 {item['hoursSincePreviousDose']}시간")
    if item.get("continuousDays") is not None:
        extras.append(f"연속 복용 {item['continuousDays']}일")
    if extras:
        head += " | " + ", ".join(extras)
    lines = [head]
    for ingredient in product["ingredients"]:
        lines.append(
            f"      성분 {ingredient['nameKo']} {ingredient['amountPerUnit']}{ingredient['unit']}"
            f" ({ingredient['unitBasis']})"
        )
    if product["administrationConstraints"]:
        limits = "; ".join(
            f"{c['type']} {c['value']}{c['valueUnit']}"
            + (f" [{c['ingredientId']}]" if c["ingredientId"] else "")
            for c in product["administrationConstraints"]
        )
        lines.append(f"      허가 상한: {limits}")
    return lines


def _render_profile(profile: dict[str, Any]) -> str:
    parts = []
    for key, label in PROFILE_LABEL_KO.items():
        value = profile.get(key)
        if value in (None, False, [], ""):
            continue
        if isinstance(value, list):
            parts.append(f"{label}={'/'.join(str(v) for v in value)}")
        elif value is True:
            parts.append(f"{label}=예")
        else:
            parts.append(f"{label}={value}")
    return ", ".join(parts) if parts else "특이사항 없음"


def cmd_render_round(args: argparse.Namespace) -> int:
    round_no = args.round
    if round_no not in ROUND_SEEDS:
        raise SystemExit(f"unknown round: {round_no}")
    cards = load_cards()
    rng = random.Random(ROUND_SEEDS[round_no])
    order = list(range(len(cards)))
    rng.shuffle(order)

    round_dir = ROUNDS_DIR / f"round{round_no}"
    round_dir.mkdir(parents=True, exist_ok=True)
    alias_map: dict[str, str] = {}
    rendered: list[str] = []
    for position, index in enumerate(order, start=1):
        card = cards[index]
        alias = f"C{round_no}-{position:03d}"
        alias_map[alias] = card["card_id"]
        if card["question"] == "rule_type":
            header = (
                f"[{alias}] 질문: 규칙유형 `{card['target_rule_type']}` 경고가 필요한가?\n"
                f"  규칙 정의: {RULE_TYPE_DEFINITION_KO[card['target_rule_type']]}"
            )
        else:
            header = (
                f"[{alias}] 질문: 이 사례에서 허가상 주의 경고가 하나라도 필요한가?\n"
                f"  규칙 정의: 16개 규칙 유형 중 어느 하나라도 발동해야 하는 상황인지 판단한다."
            )
        lines = [header, "  제품:"]
        for product_lines in card["products_rendered"]:
            lines.append(f"    - {product_lines[0]}")
            lines.extend(product_lines[1:])
        if card["source_rendered"]:
            lines.extend(card["source_rendered"])
        lines.append(f"  사용자: {card['profile_rendered']}")
        rendered.append("\n".join(lines))

    chunks = []
    for start in range(0, len(rendered), CHUNK_ROWS):
        chunk_index = start // CHUNK_ROWS + 1
        chunk_rows = rendered[start : start + CHUNK_ROWS]
        path = round_dir / f"cards_{chunk_index:02d}.txt"
        header = (
            f"===== AI 맹검 독립평가 ROUND {round_no} / CHUNK {chunk_index} "
            f"({len(chunk_rows)} cases) =====\n"
        )
        path.write_text(header + "\n\n".join(chunk_rows) + "\n", encoding="utf-8", newline="\n")
        chunks.append({"chunk": chunk_index, "rows": len(chunk_rows), "path": path.name})

    _write_json(
        round_dir / "alias_map.json",
        {"round": round_no, "seed": ROUND_SEEDS[round_no], "alias_to_case": alias_map},
    )
    _write_json(
        round_dir / "render_manifest.json",
        {
            "round": round_no,
            "seed": ROUND_SEEDS[round_no],
            "cases": len(cards),
            "chunk_rows": CHUNK_ROWS,
            "chunks": chunks,
            "rendered_at_utc": _now(),
            "note_ko": "카드에는 별칭만 노출하며 case_id·정답 라벨·엔진 예측은 포함하지 않는다.",
        },
    )
    print(f"round={round_no} cases={len(cards)} chunks={len(chunks)} seed={ROUND_SEEDS[round_no]}")
    return 0


# --------------------------------------------------------------------------
def cmd_ingest_round(args: argparse.Namespace) -> int:
    round_no = args.round
    round_dir = ROUNDS_DIR / f"round{round_no}"
    alias_map = _read_json(round_dir / "alias_map.json")["alias_to_case"]
    sources = sorted(round_dir.glob("judgements_*.jsonl"))
    if not sources:
        raise SystemExit(f"missing judgement file(s) in {round_dir}")

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for source in sources:
        with source.open(encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                alias = payload.get("alias")
                if alias not in alias_map:
                    raise SystemExit(f"{source.name}:{lineno}: unknown alias {alias!r}")
                if alias in seen:
                    raise SystemExit(f"{source.name}:{lineno}: duplicated alias {alias!r}")
                seen.add(alias)
                elements = {key: payload.get(key) for key in ELEMENT_KEYS}
                for key, value in elements.items():
                    if value not in ELEMENT_VALUES:
                        raise SystemExit(f"{source.name}:{lineno}: invalid {key}={value!r}")
                records.append(
                    {
                        "case_id": alias_map[alias],
                        "alias": alias,
                        "round": round_no,
                        **elements,
                        "label": derive_case_label(elements),
                    }
                )

    missing = sorted(set(alias_map) - seen)
    if missing:
        raise SystemExit(f"missing {len(missing)} aliases, first={missing[:5]}")

    records.sort(key=lambda row: row["case_id"])
    target = round_dir / "labels.jsonl"
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        f"round={round_no} ingested={len(records)} "
        f"labels={dict(sorted(Counter(r['label'] for r in records).items()))}"
    )
    return 0


# --------------------------------------------------------------------------
def cmd_lock(_: argparse.Namespace) -> int:
    if LOCK_PATH.exists():
        raise SystemExit(f"lock already exists: {LOCK_PATH}")
    cards = {card["card_id"]: card for card in load_cards()}
    rounds: dict[int, dict[str, dict[str, Any]]] = {}
    for round_no in sorted(ROUND_SEEDS):
        path = ROUNDS_DIR / f"round{round_no}" / "labels.jsonl"
        if not path.exists():
            raise SystemExit(f"missing round labels: {path}")
        payload = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                payload[row["case_id"]] = row
        if set(payload) != set(cards):
            raise SystemExit(f"round {round_no} does not cover all cases")
        rounds[round_no] = payload

    entries = []
    for case_id in sorted(cards):
        labels = [rounds[r][case_id]["label"] for r in sorted(rounds)]
        entries.append(
            {
                "case_id": case_id,
                "track": cards[case_id]["track"],
                "target_rule_type": cards[case_id]["target_rule_type"],
                "round_labels": labels,
                "round_elements": {
                    str(r): {key: rounds[r][case_id][key] for key in ELEMENT_KEYS}
                    for r in sorted(rounds)
                },
                "ai_reference_label": majority_label(labels),
                "blinding_compromised": case_id in BLINDING_COMPROMISED_CASE_IDS,
            }
        )

    pairwise = []
    ids = sorted(cards)
    for a in sorted(rounds):
        for b in sorted(rounds):
            if a >= b:
                continue
            first = [rounds[a][i]["label"] for i in ids]
            second = [rounds[b][i]["label"] for i in ids]
            pairwise.append(
                {
                    "rounds": f"{a}-{b}",
                    "agreement": sum(1 for x, y in zip(first, second) if x == y) / len(ids),
                    "cohen_kappa": cohen_kappa(first, second),
                }
            )

    payload = {
        "schema_version": "1.0.0",
        "created_at_utc": _now(),
        "purpose_ko": "P3-B AI 참조 라벨 잠금본. 이 파일이 만들어진 뒤에만 엔진 예측을 연결한다.",
        "human_decisions": 0,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
        "engine_predictions_read_before_lock": False,
        "composite_label_rule_ko": COMPOSITE_RULE_TEXT_KO,
        "round_seeds": ROUND_SEEDS,
        "round_label_sha256": {
            str(r): sha256_file(ROUNDS_DIR / f"round{r}" / "labels.jsonl")
            for r in sorted(rounds)
        },
        "inter_round": {
            "pairwise": pairwise,
            "mean_pairwise_agreement": statistics.fmean([p["agreement"] for p in pairwise]),
            "unresolved_rows": sum(
                1 for e in entries if e["ai_reference_label"] == "unresolved"
            ),
            "interpretation_ko": (
                "동일 평가자가 같은 명시적 규칙을 재적용한 결과이므로 판정 안정성이지 "
                "평가자 간 신뢰도가 아니다."
            ),
        },
        "label_distribution": dict(
            sorted(Counter(e["ai_reference_label"] for e in entries).items())
        ),
        "cases_total": len(entries),
        "blinding_compromised_cases": {
            "case_ids": list(BLINDING_COMPROMISED_CASE_IDS),
            "count": sum(1 for e in entries if e["blinding_compromised"]),
            "reason_ko": BLINDING_COMPROMISE_REASON_KO,
            "excluded_from_primary": True,
        },
        "labels": entries,
    }
    _write_json(LOCK_PATH, payload)
    digest = sha256_file(LOCK_PATH)
    _write_json(
        EVAL_DIR / "ai_reference_labels.lock.sha256.json",
        {
            "locked_file": str(LOCK_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": digest,
            "locked_at_utc": payload["created_at_utc"],
        },
    )
    print(f"locked={len(entries)} sha256={digest}")
    print(f"distribution={payload['label_distribution']}")
    return 0


# --------------------------------------------------------------------------
# 통계
# --------------------------------------------------------------------------
def confusion(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row in rows:
        if row["engine_positive"] and row["reference_positive"]:
            counts["tp"] += 1
        elif row["engine_positive"] and not row["reference_positive"]:
            counts["fp"] += 1
        elif not row["engine_positive"] and row["reference_positive"]:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator <= 0 else numerator / denominator


def metrics_from(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts = confusion(rows)
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    sensitivity = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    precision = _ratio(tp, tp + fp)
    f1 = (
        None
        if sensitivity is None or precision is None or (precision + sensitivity) == 0
        else 2 * precision * sensitivity / (precision + sensitivity)
    )
    return {
        "cases": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "sensitivity_vs_ai_reference": sensitivity,
        "specificity_vs_ai_reference": specificity,
        "precision_vs_ai_reference": precision,
        "f1_vs_ai_reference": f1,
        "agreement_vs_ai_reference": _ratio(tp + tn, len(rows)),
        "sensitivity_wilson_ci95": wilson_interval(tp, tp + fn),
        "specificity_wilson_ci95": wilson_interval(tn, tn + fp),
        "agreement_wilson_ci95": wilson_interval(tp + tn, len(rows)),
    }


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = proportion + z**2 / (2 * total)
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    return [max(0.0, (centre - margin) / denominator), min(1.0, (centre + margin) / denominator)]


def cohen_kappa(first: Sequence[str], second: Sequence[str]) -> float | None:
    if len(first) != len(second) or not first:
        return None
    categories = sorted(set(first) | set(second))
    total = len(first)
    observed = sum(1 for a, b in zip(first, second) if a == b) / total
    expected = sum(
        (sum(1 for a in first if a == c) / total) * (sum(1 for b in second if b == c) / total)
        for c in categories
    )
    return None if expected >= 1 else (observed - expected) / (1 - expected)


def bootstrap_metrics(
    rows: Sequence[dict[str, Any]],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """규칙 유형별 층 안에서 복원추출하는 층화 부트스트랩."""
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_stratum[row.get("target_rule_type") or "legacy"].append(row)
    rng = random.Random(seed)
    sensitivities: list[float] = []
    specificities: list[float] = []
    agreements: list[float] = []
    undefined = 0
    for _ in range(replicates):
        resampled: list[dict[str, Any]] = []
        for stratum_rows in by_stratum.values():
            size = len(stratum_rows)
            resampled.extend(stratum_rows[rng.randrange(size)] for _ in range(size))
        result = metrics_from(resampled)
        if (
            result["sensitivity_vs_ai_reference"] is None
            or result["specificity_vs_ai_reference"] is None
        ):
            undefined += 1
            continue
        sensitivities.append(result["sensitivity_vs_ai_reference"])
        specificities.append(result["specificity_vs_ai_reference"])
        agreements.append(result["agreement_vs_ai_reference"])

    def _ci(values: list[float]) -> list[float] | None:
        if not values:
            return None
        ordered = sorted(values)
        low = ordered[max(0, int(math.floor(0.025 * (len(ordered) - 1))))]
        high = ordered[min(len(ordered) - 1, int(math.ceil(0.975 * (len(ordered) - 1))))]
        return [low, high]

    return {
        "replicates": replicates,
        "seed": seed,
        "undefined_replicates": undefined,
        "sensitivity_ci95": _ci(sensitivities),
        "specificity_ci95": _ci(specificities),
        "agreement_ci95": _ci(agreements),
    }


# --------------------------------------------------------------------------
def cmd_finalize(_: argparse.Namespace) -> int:
    if not LOCK_PATH.exists():
        raise SystemExit("lock file missing; run `lock` before finalize")
    if not PREDICTION_AUDIT.exists():
        raise SystemExit("prediction audit missing; run predict-ai-independent.ts after lock")

    lock = _read_json(LOCK_PATH)
    audit = _read_json(PREDICTION_AUDIT)
    lock_digest = sha256_file(LOCK_PATH)
    if audit.get("verified_lock_sha256") != lock_digest:
        raise SystemExit("prediction audit was produced against a different lock file")
    locked_at = datetime.fromisoformat(lock["created_at_utc"])
    predicted_at = datetime.fromisoformat(audit["predicted_at_utc"])
    if not locked_at < predicted_at:
        raise SystemExit("prediction timestamp must be after the label lock timestamp")

    severity_by_type = {
        row["rule_type"]: row["severity"]
        for row in csv.DictReader(RULES_CSV.open(encoding="utf-8-sig"))
    }
    status_by_type = {
        row["rule_type"]: row["status"]
        for row in csv.DictReader(RULES_CSV.open(encoding="utf-8-sig"))
    }
    released_types = {t for t, s in status_by_type.items() if s == "released"}

    predictions = {row["caseId"]: row for row in audit["cases"]}
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    uncertain: list[str] = []
    compromised: list[dict[str, Any]] = []
    for entry in lock["labels"]:
        case_id = entry["case_id"]
        label = entry["ai_reference_label"]
        if entry.get("blinding_compromised"):
            prediction = predictions.get(case_id)
            compromised.append(
                {
                    "case_id": case_id,
                    "ai_reference_label": label,
                    "engine_finding_rule_types": (
                        prediction["findingRuleTypes"] if prediction else None
                    ),
                }
            )
            continue
        if label == "unresolved":
            unresolved.append(case_id)
            continue
        if label == "uncertain":
            uncertain.append(case_id)
            continue
        prediction = predictions.get(case_id)
        if prediction is None:
            raise SystemExit(f"missing engine prediction for {case_id}")
        target = entry["target_rule_type"]
        engine_positive = (
            target in prediction["findingRuleTypes"]
            if target
            else bool(prediction["findingRuleTypes"])
        )
        rows.append(
            {
                "case_id": case_id,
                "track": entry["track"],
                "target_rule_type": target,
                "reference_positive": label == "warning",
                "engine_positive": engine_positive,
                "engine_finding_rule_types": prediction["findingRuleTypes"],
                "round_labels": entry["round_labels"],
            }
        )

    generated = [row for row in rows if row["track"] == "generated"]
    legacy = [row for row in rows if row["track"] == "legacy_reevaluation"]
    released_rows = [row for row in generated if row["target_rule_type"] in released_types]
    draft_rows = [row for row in generated if row["target_rule_type"] not in released_types]
    draft_types = {t for t in status_by_type if t not in released_types}
    lock_target_by_case = {e["case_id"]: e["target_rule_type"] for e in lock["labels"]}
    draft_uncertain_ids = [
        case_id for case_id in uncertain if lock_target_by_case.get(case_id) in draft_types
    ]

    # 커버리지 공백: 참조표준이 warning 인데 엔진이 발동하지 않은 사례를 제품 단위로 모은다.
    products_by_case = {
        row["caseId"]: row for row in audit["cases"]
    }
    coverage_gaps: dict[str, Any] = {}
    for rule_type in sorted({row["target_rule_type"] for row in generated if row["target_rule_type"]}):
        misses = [
            row["case_id"]
            for row in generated
            if row["target_rule_type"] == rule_type
            and row["reference_positive"]
            and not row["engine_positive"]
        ]
        if not misses:
            continue
        product_names: Counter[str] = Counter()
        for case_id in misses:
            payload = _read_json(CASE_DIR / f"{case_id}.json")
            for item in payload["productInputs"]:
                if item.get("inputType") == "verified_product":
                    product_names[item["itemSequence"]] += 1
        coverage_gaps[rule_type] = {
            "missed_cases": len(misses),
            "missed_case_ids": misses,
            "product_item_sequences": dict(product_names.most_common()),
        }

    per_rule_type: dict[str, Any] = {}
    for rule_type in sorted({row["target_rule_type"] for row in generated}):
        subset = [row for row in generated if row["target_rule_type"] == rule_type]
        per_rule_type[rule_type] = {
            "rule_status": status_by_type.get(rule_type),
            "rule_severity": severity_by_type.get(rule_type),
            **metrics_from(subset),
        }

    critical_false_negatives = [
        {
            "case_id": row["case_id"],
            "target_rule_type": row["target_rule_type"],
            "rule_severity": severity_by_type.get(row["target_rule_type"]),
            "rule_status": status_by_type.get(row["target_rule_type"]),
            "engine_finding_rule_types": row["engine_finding_rule_types"],
        }
        for row in generated
        if row["reference_positive"]
        and not row["engine_positive"]
        and severity_by_type.get(row["target_rule_type"]) in ("high", "urgent")
    ]
    failures = [
        {
            "case_id": row["case_id"],
            "track": row["track"],
            "target_rule_type": row["target_rule_type"],
            "ai_reference": "warning" if row["reference_positive"] else "no_warning",
            "engine": "warning" if row["engine_positive"] else "no_warning",
            "engine_finding_rule_types": row["engine_finding_rule_types"],
        }
        for row in rows
        if row["reference_positive"] != row["engine_positive"]
    ]

    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": _now(),
        "phase": "P3-B",
        "purpose_ko": "released 규칙엔진을 AI 맹검 참조 라벨과 대조한 독립평가",
        "reference_standard_type": "ai_reference_standard",
        "ai_reference_standard": True,
        "ai_cross_checked": True,
        "human_reference_standard": False,
        "human_decisions": 0,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
        "evaluator_ko": "판정 주체는 Claude 에이전트 본인이며 카드를 직접 읽고 직접 기록했다.",
        "independence_limitation_ko": (
            "동일 에이전트가 사례 설계와 참조 라벨 판정을 모두 수행했다. 절차적 맹검은 "
            "정답 라벨 미생성, 별칭 카드, 라운드별 무작위 순서, 잠금 후 예측 연결로 "
            "구현했으나 평가자 독립성은 외부 사람 평가와 동등하지 않다."
        ),
        "lock": {
            "path": str(LOCK_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": lock_digest,
            "created_at_utc": lock["created_at_utc"],
        },
        "prediction": {
            "path": str(PREDICTION_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "predicted_at_utc": audit["predicted_at_utc"],
            "verified_lock_sha256": audit["verified_lock_sha256"],
            "runtime_sha256": audit["runtime_sha256"],
            "released_rule_types": audit["releasedRuleTypes"],
        },
        "order_proof_ko": (
            "잠금 파일 생성 시각과 SHA-256을 예측 스크립트가 먼저 검증한 뒤 예측을 기록했고, "
            "finalize 는 두 시각의 선후와 해시 일치를 다시 검증한 뒤에만 지표를 계산한다."
        ),
        "prompt_path": str(PROMPT.relative_to(ROOT)).replace("\\", "/"),
        "prompt_sha256": sha256_file(PROMPT),
        "case_manifest_sha256": sha256_file(CASE_MANIFEST),
        "composite_label_rule_ko": COMPOSITE_RULE_TEXT_KO,
        "inter_round": lock["inter_round"],
        "ai_reference_label_distribution": lock["label_distribution"],
        "cases_total": lock["cases_total"],
        "excluded_uncertain": len(uncertain),
        "excluded_uncertain_case_ids": uncertain,
        "excluded_unresolved": len(unresolved),
        "excluded_unresolved_case_ids": unresolved,
        "excluded_blinding_compromised": len(compromised),
        "blinding_compromised_cases": {
            "reason_ko": BLINDING_COMPROMISE_REASON_KO,
            "cases": compromised,
        },
        "positive_class_ko": "warning",
        "primary_analysis_scope_ko": "released 15개 규칙 유형을 겨냥한 생성 사례",
        "primary_analysis": metrics_from(released_rows),
        "all_rule_types_analysis": metrics_from(generated),
        "draft_rule_analysis": {
            "rule_types": sorted(draft_types),
            "scored_cases": len(draft_rows),
            "uncertain_cases": len(draft_uncertain_ids),
            "uncertain_case_ids": draft_uncertain_ids,
            "note_ko": (
                "maximum_duration 은 draft 상태로 런타임 released 목록에 없어 엔진이 절대 "
                "발동하지 않는다. 동시에 AI 참조표준도 이 14건을 전부 uncertain 으로 판정해 "
                "채점 가능한 사례가 0건이다. 대상 제품(판콜에이내복액)의 허가원문이 '장기간 "
                "계속 복용하지 말 것'이라고만 적고 일수 기준을 주지 않아 초과 여부를 비교할 "
                "수 없기 때문이다. 즉 이 규칙이 draft 인 이유가 참조표준 쪽에서 독립적으로 "
                "확인된다. 수치를 만들기 위해 임의의 일수를 가정하지 않았다."
            ),
            **metrics_from(draft_rows),
        },
        "coverage_gap_analysis": {
            "definition_ko": (
                "AI 참조표준은 허가원문에 그 주의가 적혀 있으면 warning 으로 판정하고, 엔진은 "
                "규칙이 특정 제품에 바인딩된 경우에만 발동한다. 두 판정이 갈리는 지점이 곧 "
                "규칙 바인딩의 커버리지 공백이다."
            ),
            "false_positive_total": sum(1 for row in rows if row["engine_positive"] and not row["reference_positive"]),
            "false_negative_total": sum(1 for row in rows if row["reference_positive"] and not row["engine_positive"]),
            "by_rule_type": coverage_gaps,
        },
        "legacy_reevaluation": {
            "note_ko": (
                "기존 13건을 같은 AI 절차로 재평가했다. 사람 라벨과 기존 예측은 잠금 후에만 "
                "비교하며 이 지표는 AI 참조 라벨 대비 엔진 성능이다."
            ),
            **metrics_from(legacy),
        },
        "per_rule_type": per_rule_type,
        "critical_false_negatives": critical_false_negatives,
        "critical_false_negative_count": len(critical_false_negatives),
        "critical_definition_ko": (
            "AI 참조 라벨이 warning 인데 엔진이 해당 규칙 유형을 발동하지 않았고 규칙 "
            "severity 가 high 또는 urgent 인 경우"
        ),
        "bootstrap": bootstrap_metrics(released_rows),
        "failure_cases": failures[:20],
        "failure_case_total": len(failures),
        "per_case": rows,
    }
    _write_json(OUTPUT, payload)
    primary = payload["primary_analysis"]
    print(
        "released: sensitivity={} specificity={} precision={} f1={} agreement={}".format(
            *(
                "n/a" if primary[key] is None else f"{primary[key]:.4f}"
                for key in (
                    "sensitivity_vs_ai_reference",
                    "specificity_vs_ai_reference",
                    "precision_vs_ai_reference",
                    "f1_vs_ai_reference",
                    "agreement_vs_ai_reference",
                )
            )
        )
    )
    print(
        f"cases={payload['cases_total']} uncertain={len(uncertain)} unresolved={len(unresolved)} "
        f"critical_fn={len(critical_false_negatives)} failures={len(failures)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3-B AI blinded independent evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render-round")
    render.add_argument("round", type=int)
    render.set_defaults(func=cmd_render_round)
    ingest = sub.add_parser("ingest-round")
    ingest.add_argument("round", type=int)
    ingest.set_defaults(func=cmd_ingest_round)
    sub.add_parser("lock").set_defaults(func=cmd_lock)
    sub.add_parser("finalize").set_defaults(func=cmd_finalize)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
