"""P3-A 독립 AI 참조표준 지원 도구.

이 스크립트는 **판정하지 않는다.** 표본 추출, 블라인드 카드 렌더링, 에이전트가 직접 쓴
PICOS 판정의 검증·적재, 종합 라벨 도출(명시적 코드 규칙), 통계 산출만 수행한다.
지역 언어모델이나 외부 LLM API를 호출하지 않는다.

서브커맨드
    sample          P2 판정을 strata 로 사용한 층화 무작위 표본 추출
    render-round    라운드별 무작위 순서로 블라인드 카드 렌더링(별칭만 노출)
    ingest-round    에이전트가 쓴 PICOS 판정 적재·검증 후 종합 라벨 도출
    finalize        다수결·일치도·층화 지표·Rogan-Gladen·부트스트랩 산출
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
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
LITERATURE_DIR = ROOT / "research_v3" / "otc" / "literature"
EVIDENCE_MAP = LITERATURE_DIR / "evidence_map.csv"
CHECKPOINTS = LITERATURE_DIR / "screening" / "checkpoints.jsonl"
PICOS_DEFINITION = LITERATURE_DIR / "picos" / "picos_definition.json"
REFERENCE_PROMPT = LITERATURE_DIR / "prompts" / "ai_reference_prompt.md"

MEASURE_DIR = ROOT / "research_v3" / "measurement"
AIREF_DIR = MEASURE_DIR / "ai_reference"
SAMPLE_MANIFEST = AIREF_DIR / "sample_manifest.json"
BLIND_SAMPLE = AIREF_DIR / "blind_sample.jsonl"
ROUNDS_DIR = AIREF_DIR / "rounds"
OUTPUT_JSON = MEASURE_DIR / "screener_vs_ai_reference.json"

SAMPLE_SIZE = 300
SAMPLE_SEED = 20260727
ROUND_SEEDS = {1: 20260727001, 2: 20260727002, 3: 20260727003}
STRATUM_FLOOR = 20
CHUNK_ROWS = 40
ABSTRACT_CHARS = 900
MESH_TERMS = 14
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260727999

PICOS_VALUES = ("Y", "N", "U")
PICOS_KEYS = ("P", "I", "C", "O", "S")
LABELS = ("retain", "deprioritize", "uncertain")


# --------------------------------------------------------------------------
# 공통 유틸
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_corpus() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with EVIDENCE_MAP.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["record_id"]] = row
    return rows


def load_screener_labels() -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    with CHECKPOINTS.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            labels[payload["record_id"]] = payload
    return labels


# --------------------------------------------------------------------------
# 종합 라벨 도출 — 명시적 코드 규칙
# --------------------------------------------------------------------------
COMPOSITE_RULE_TEXT_KO = (
    "1) P·I·O·S 중 하나라도 N 이면 deprioritize. "
    "2) 그렇지 않고 I=Y 이고 O=Y 이면 retain. "
    "3) 그 외(I 또는 O 가 U)는 uncertain. "
    "C 는 기록만 하고 라벨 도출에 사용하지 않는다."
)


def derive_composite_label(picos: dict[str, str]) -> str:
    """P/I/C/O/S 개별 판정에서 종합 라벨을 도출한다(주제 적합성을 통째로 묻지 않는다)."""
    for key in PICOS_KEYS:
        value = picos.get(key)
        if value not in PICOS_VALUES:
            raise ValueError(f"invalid PICOS value for {key}: {value!r}")
    if any(picos[key] == "N" for key in ("P", "I", "O", "S")):
        return "deprioritize"
    if picos["I"] == "Y" and picos["O"] == "Y":
        return "retain"
    return "uncertain"


# --------------------------------------------------------------------------
# 층화 표본 추출
# --------------------------------------------------------------------------
def allocate_sample(frames: dict[str, int], total: int, floor: int) -> dict[str, int]:
    """층별 표본 수를 배분한다. 최소 배정(floor) 후 잔여를 프레임 크기에 비례 배분한다."""
    if total > sum(frames.values()):
        raise ValueError("sample size exceeds frame size")
    allocation = {key: min(floor, size) for key, size in frames.items()}
    remaining = total - sum(allocation.values())
    if remaining < 0:
        raise ValueError("floor allocation exceeds requested sample size")
    while remaining > 0:
        capacity = {k: frames[k] - allocation[k] for k in frames if frames[k] > allocation[k]}
        if not capacity:
            raise ValueError("no capacity left to allocate")
        weight_total = sum(frames[k] for k in capacity)
        shares: dict[str, float] = {k: remaining * frames[k] / weight_total for k in capacity}
        added = 0
        for key, share in shares.items():
            take = min(int(share), capacity[key])
            allocation[key] += take
            added += take
        remaining -= added
        if added == 0:
            # 잔여를 프레임이 큰 순서대로 1건씩 배분
            for key in sorted(capacity, key=lambda k: (-frames[k], k)):
                if remaining == 0:
                    break
                allocation[key] += 1
                remaining -= 1
    return allocation


def cmd_sample(_: argparse.Namespace) -> int:
    corpus = load_corpus()
    screener = load_screener_labels()
    missing = set(corpus) - set(screener)
    if missing:
        raise SystemExit(f"screener labels missing for {len(missing)} records")

    strata: dict[str, list[str]] = defaultdict(list)
    for record_id, payload in screener.items():
        key = f"{payload['evidence_basis']}|{payload['decision']}"
        strata[key].append(record_id)
    for key in strata:
        strata[key].sort()

    frames = {key: len(values) for key, values in strata.items()}
    allocation = allocate_sample(frames, SAMPLE_SIZE, STRATUM_FLOOR)

    rng = random.Random(SAMPLE_SEED)
    selected: list[dict[str, Any]] = []
    stratum_rows: list[dict[str, Any]] = []
    for key in sorted(strata):
        picks = rng.sample(strata[key], allocation[key])
        picks.sort()
        weight = frames[key] / allocation[key]
        stratum_rows.append(
            {
                "stratum": key,
                "frame_size": frames[key],
                "sample_size": allocation[key],
                "weight": weight,
                "sampling_fraction": allocation[key] / frames[key],
            }
        )
        for record_id in picks:
            selected.append({"record_id": record_id, "stratum": key, "weight": weight})

    selected.sort(key=lambda row: row["record_id"])
    AIREF_DIR.mkdir(parents=True, exist_ok=True)
    with BLIND_SAMPLE.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            record = corpus[row["record_id"]]
            handle.write(
                json.dumps(
                    {
                        "record_id": row["record_id"],
                        "stratum": row["stratum"],
                        "weight": row["weight"],
                        "question_id": record["question_ids"].split(";")[0],
                        "question_ids": record["question_ids"],
                        "pmid": record["pmid"],
                        "title": record["title"],
                        "abstract": record["abstract"],
                        "has_abstract": record["has_abstract"],
                        "journal": record["journal"],
                        "publication_year": record["publication_year"],
                        "publication_types": record["publication_types"],
                        "mesh_terms": record["mesh_terms"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    manifest = {
        "schema_version": "1.0.0",
        "generated_at_utc": _now(),
        "purpose_ko": "P3-A 독립 AI 참조표준용 층화 무작위 표본",
        "frame_source": str(CHECKPOINTS.relative_to(ROOT)).replace("\\", "/"),
        "frame_source_sha256": sha256_file(CHECKPOINTS),
        "corpus_source": str(EVIDENCE_MAP.relative_to(ROOT)).replace("\\", "/"),
        "corpus_source_sha256": sha256_file(EVIDENCE_MAP),
        "stratification_variable_ko": "P2 근거 형태(evidence_basis) × P2 판정(decision)",
        "sample_size": SAMPLE_SIZE,
        "sample_seed": SAMPLE_SEED,
        "stratum_floor": STRATUM_FLOOR,
        "allocation_rule_ko": "층별 최소 20건(프레임이 작으면 전수) 배정 후 잔여를 프레임 크기 비례 배분",
        "corpus_rows": len(corpus),
        "strata": stratum_rows,
        "blind_sample_path": str(BLIND_SAMPLE.relative_to(ROOT)).replace("\\", "/"),
        "blind_sample_sha256": sha256_file(BLIND_SAMPLE),
        "blind_sample_excluded_fields": [
            "decision",
            "confidence",
            "reason_codes",
            "batch_id",
            "screener",
            "status",
        ],
        "round_seeds": ROUND_SEEDS,
    }
    _write_json(SAMPLE_MANIFEST, manifest)
    print(f"sampled={len(selected)} strata={len(stratum_rows)}")
    for row in stratum_rows:
        print(
            f"  {row['stratum']}: frame={row['frame_size']} n={row['sample_size']} "
            f"w={row['weight']:.4f}"
        )
    return 0


# --------------------------------------------------------------------------
# 라운드 렌더링
# --------------------------------------------------------------------------
def load_blind_sample() -> list[dict[str, Any]]:
    rows = []
    with BLIND_SAMPLE.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_questions() -> dict[str, dict[str, Any]]:
    definition = _read_json(PICOS_DEFINITION)
    questions = {}
    for question in definition["questions"]:
        full = question["question_id"]
        questions[full] = question
        questions[full.replace("OTC-LIT-", "")] = question
    return questions


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


def cmd_render_round(args: argparse.Namespace) -> int:
    round_no = args.round
    if round_no not in ROUND_SEEDS:
        raise SystemExit(f"unknown round: {round_no}")
    rows = load_blind_sample()
    questions = load_questions()

    rng = random.Random(ROUND_SEEDS[round_no])
    order = list(range(len(rows)))
    rng.shuffle(order)

    round_dir = ROUNDS_DIR / f"round{round_no}"
    round_dir.mkdir(parents=True, exist_ok=True)
    alias_map: dict[str, str] = {}
    chunks: list[dict[str, Any]] = []

    rendered: list[str] = []
    for position, index in enumerate(order, start=1):
        row = rows[index]
        alias = f"R{round_no}-{position:03d}"
        alias_map[alias] = row["record_id"]
        block = [
            f"[{alias}] {row['question_id']} | {row['publication_year']} | "
            f"abstract={'yes' if row['has_abstract'] == 'true' else 'no'}",
            f"  TITLE: {_clip(row['title'], 400)}",
            f"  ABSTRACT: {_clip(row['abstract'], ABSTRACT_CHARS) or '(초록 없음)'}",
            f"  TYPES: {_clip(row['publication_types'], 200)}",
            "  MESH: "
            + _clip("; ".join([t for t in row["mesh_terms"].split(";") if t][:MESH_TERMS]), 400),
        ]
        rendered.append("\n".join(block))

    legend_lines = ["----- 질문별 PICOS 정의 -----"]
    for question_id in sorted({row["question_id"] for row in rows}):
        picos = questions.get(question_id, {}).get("picos", {})
        legend_lines.extend(
            [
                f"{question_id}",
                f"  Q-P: {_clip(picos.get('population', ''), 200)}",
                f"  Q-I: {_clip(picos.get('intervention_or_exposure', ''), 240)}",
                f"  Q-C: {_clip(picos.get('comparator', ''), 200)}",
                f"  Q-O: {_clip(picos.get('outcomes', ''), 240)}",
                f"  Q-S: {_clip(picos.get('study_design', ''), 200)}",
            ]
        )
    legend = "\n".join(legend_lines)

    for start in range(0, len(rendered), CHUNK_ROWS):
        chunk_index = start // CHUNK_ROWS + 1
        chunk_rows = rendered[start : start + CHUNK_ROWS]
        path = round_dir / f"cards_{chunk_index:02d}.txt"
        header = (
            f"===== AI REFERENCE ROUND {round_no} / CHUNK {chunk_index} "
            f"({len(chunk_rows)} rows) =====\n{legend}\n----- 카드 -----\n"
        )
        path.write_text(header + "\n\n".join(chunk_rows) + "\n", encoding="utf-8", newline="\n")
        chunks.append({"chunk": chunk_index, "rows": len(chunk_rows), "path": path.name})

    _write_json(round_dir / "alias_map.json", {"round": round_no, "seed": ROUND_SEEDS[round_no], "alias_to_record": alias_map})
    _write_json(
        round_dir / "render_manifest.json",
        {
            "round": round_no,
            "seed": ROUND_SEEDS[round_no],
            "rows": len(rows),
            "chunk_rows": CHUNK_ROWS,
            "abstract_chars": ABSTRACT_CHARS,
            "mesh_terms": MESH_TERMS,
            "chunks": chunks,
            "rendered_at_utc": _now(),
            "note_ko": "카드에는 별칭만 노출하며 record_id·PMID·P2 판정은 포함하지 않는다.",
        },
    )
    print(f"round={round_no} rows={len(rows)} chunks={len(chunks)} seed={ROUND_SEEDS[round_no]}")
    return 0


# --------------------------------------------------------------------------
# 라운드 적재
# --------------------------------------------------------------------------
def cmd_ingest_round(args: argparse.Namespace) -> int:
    round_no = args.round
    round_dir = ROUNDS_DIR / f"round{round_no}"
    alias_map = _read_json(round_dir / "alias_map.json")["alias_to_record"]
    sources = sorted(round_dir.glob("picos_*.jsonl"))
    if (round_dir / "picos.jsonl").exists():
        sources.append(round_dir / "picos.jsonl")
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
                picos = {key: payload.get(key) for key in PICOS_KEYS}
                for key, value in picos.items():
                    if value not in PICOS_VALUES:
                        raise SystemExit(f"{source.name}:{lineno}: invalid {key}={value!r}")
                label = derive_composite_label(picos)
                records.append(
                    {
                        "record_id": alias_map[alias],
                        "alias": alias,
                        "round": round_no,
                        **picos,
                        "label": label,
                    }
                )

    missing = sorted(set(alias_map) - seen)
    if missing:
        raise SystemExit(f"missing {len(missing)} aliases, first={missing[:5]}")

    records.sort(key=lambda row: row["record_id"])
    target = round_dir / "labels.jsonl"
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    distribution = Counter(row["label"] for row in records)
    print(f"round={round_no} ingested={len(records)} labels={dict(sorted(distribution.items()))}")
    return 0


# --------------------------------------------------------------------------
# 통계
# --------------------------------------------------------------------------
def weighted_confusion(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    """행별 층화 가중치를 적용한 혼동행렬. rows 는 screener_positive/reference_positive/weight 필요."""
    counts = {"tp": 0.0, "fp": 0.0, "fn": 0.0, "tn": 0.0}
    for row in rows:
        weight = float(row["weight"])
        if row["screener_positive"] and row["reference_positive"]:
            counts["tp"] += weight
        elif row["screener_positive"] and not row["reference_positive"]:
            counts["fp"] += weight
        elif not row["screener_positive"] and row["reference_positive"]:
            counts["fn"] += weight
        else:
            counts["tn"] += weight
    return counts


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def stratified_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float | None]:
    counts = weighted_confusion(rows)
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    sensitivity = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    precision = _ratio(tp, tp + fp)
    if sensitivity is None or precision is None or (precision + sensitivity) == 0:
        f1 = None
    else:
        f1 = 2 * precision * sensitivity / (precision + sensitivity)
    agreement = _ratio(tp + tn, tp + fp + fn + tn)
    return {
        "weighted_true_positive": tp,
        "weighted_false_positive": fp,
        "weighted_false_negative": fn,
        "weighted_true_negative": tn,
        "sensitivity_vs_ai_reference": sensitivity,
        "specificity_vs_ai_reference": specificity,
        "precision_vs_ai_reference": precision,
        "f1_vs_ai_reference": f1,
        "agreement_vs_ai_reference": agreement,
    }


def rogan_gladen(apparent_prevalence: float, sensitivity: float, specificity: float) -> float | None:
    """Rogan-Gladen 보정. 분모가 0 이하이면 정의되지 않는다."""
    denominator = sensitivity + specificity - 1.0
    if denominator <= 0:
        return None
    corrected = (apparent_prevalence + specificity - 1.0) / denominator
    return min(1.0, max(0.0, corrected))


def stratified_bootstrap(
    rows: Sequence[dict[str, Any]],
    apparent_prevalence: float,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """층 내부 복원추출 부트스트랩으로 민감도·특이도·보정 유병률의 95% CI 를 계산한다."""
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_stratum[row["stratum"]].append(row)

    rng = random.Random(seed)
    sensitivities: list[float] = []
    specificities: list[float] = []
    corrected: list[float] = []
    undefined = 0
    for _ in range(replicates):
        resampled: list[dict[str, Any]] = []
        for stratum_rows in by_stratum.values():
            size = len(stratum_rows)
            resampled.extend(stratum_rows[rng.randrange(size)] for _ in range(size))
        metrics = stratified_metrics(resampled)
        sensitivity = metrics["sensitivity_vs_ai_reference"]
        specificity = metrics["specificity_vs_ai_reference"]
        if sensitivity is None or specificity is None:
            undefined += 1
            continue
        sensitivities.append(sensitivity)
        specificities.append(specificity)
        value = rogan_gladen(apparent_prevalence, sensitivity, specificity)
        if value is None:
            undefined += 1
        else:
            corrected.append(value)

    def _percentile_ci(values: list[float]) -> list[float] | None:
        if not values:
            return None
        ordered = sorted(values)
        lower = ordered[max(0, int(math.floor(0.025 * (len(ordered) - 1))))]
        upper = ordered[min(len(ordered) - 1, int(math.ceil(0.975 * (len(ordered) - 1))))]
        return [lower, upper]

    return {
        "replicates": replicates,
        "seed": seed,
        "undefined_replicates": undefined,
        "sensitivity_ci95": _percentile_ci(sensitivities),
        "specificity_ci95": _percentile_ci(specificities),
        "corrected_prevalence_ci95": _percentile_ci(corrected),
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
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def majority_label(labels: Sequence[str]) -> str:
    counts = Counter(labels)
    top, top_count = counts.most_common(1)[0]
    if top_count == 1:
        return "unresolved"
    return top


# --------------------------------------------------------------------------
# finalize
# --------------------------------------------------------------------------
def cmd_finalize(_: argparse.Namespace) -> int:
    manifest = _read_json(SAMPLE_MANIFEST)
    corpus = load_corpus()
    screener = load_screener_labels()
    blind = {row["record_id"]: row for row in load_blind_sample()}

    rounds: dict[int, dict[str, dict[str, Any]]] = {}
    for round_no in sorted(ROUND_SEEDS):
        path = ROUNDS_DIR / f"round{round_no}" / "labels.jsonl"
        if not path.exists():
            raise SystemExit(f"missing round labels: {path}")
        payload: dict[str, dict[str, Any]] = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    payload[row["record_id"]] = row
        if set(payload) != set(blind):
            raise SystemExit(f"round {round_no} does not cover the blind sample")
        rounds[round_no] = payload

    record_ids = sorted(blind)
    combined: list[dict[str, Any]] = []
    for record_id in record_ids:
        labels = [rounds[r][record_id]["label"] for r in sorted(rounds)]
        reference = majority_label(labels)
        combined.append(
            {
                "record_id": record_id,
                "stratum": blind[record_id]["stratum"],
                "weight": blind[record_id]["weight"],
                "question_id": blind[record_id]["question_id"],
                "title": corpus[record_id]["title"],
                "round_labels": labels,
                "round_picos": {
                    str(r): {key: rounds[r][record_id][key] for key in PICOS_KEYS}
                    for r in sorted(rounds)
                },
                "ai_reference_label": reference,
                "screener_decision": screener[record_id]["decision"],
                "screener_confidence": screener[record_id]["confidence"],
                "evidence_basis": screener[record_id]["evidence_basis"],
            }
        )

    # 라운드 간 일치도와 κ
    pairwise = []
    for a in sorted(rounds):
        for b in sorted(rounds):
            if a >= b:
                continue
            first = [rounds[a][rid]["label"] for rid in record_ids]
            second = [rounds[b][rid]["label"] for rid in record_ids]
            agreement = sum(1 for x, y in zip(first, second) if x == y) / len(record_ids)
            pairwise.append(
                {
                    "rounds": f"{a}-{b}",
                    "agreement": agreement,
                    "cohen_kappa": cohen_kappa(first, second),
                }
            )
    unanimous = sum(1 for row in combined if len(set(row["round_labels"])) == 1)
    unresolved = [row for row in combined if row["ai_reference_label"] == "unresolved"]

    # 지표 계산 대상 선정
    def build_rows(uncertain_as_negative: bool) -> list[dict[str, Any]]:
        rows = []
        for row in combined:
            reference = row["ai_reference_label"]
            if reference == "unresolved":
                continue
            if reference == "uncertain":
                if not uncertain_as_negative:
                    continue
                reference_positive = False
            else:
                reference_positive = reference == "retain"
            rows.append(
                {
                    "record_id": row["record_id"],
                    "stratum": row["stratum"],
                    "weight": row["weight"],
                    "screener_positive": row["screener_decision"] == "retain",
                    "reference_positive": reference_positive,
                }
            )
        return rows

    primary_rows = build_rows(uncertain_as_negative=False)
    secondary_rows = build_rows(uncertain_as_negative=True)
    primary = stratified_metrics(primary_rows)
    secondary = stratified_metrics(secondary_rows)

    corpus_retain = sum(1 for payload in screener.values() if payload["decision"] == "retain")
    apparent_prevalence = corpus_retain / len(screener)

    sensitivity = primary["sensitivity_vs_ai_reference"]
    specificity = primary["specificity_vs_ai_reference"]
    corrected = (
        rogan_gladen(apparent_prevalence, sensitivity, specificity)
        if sensitivity is not None and specificity is not None
        else None
    )
    bootstrap = stratified_bootstrap(primary_rows, apparent_prevalence)

    corpus_estimate = None
    corpus_ci = None
    if corrected is not None:
        corpus_estimate = corrected * len(screener)
    if bootstrap["corrected_prevalence_ci95"]:
        corpus_ci = [value * len(screener) for value in bootstrap["corrected_prevalence_ci95"]]

    # 위양성·위음성 사례
    false_positives = [
        {
            "record_id": row["record_id"],
            "title": row["title"],
            "question_id": row["question_id"],
            "stratum": row["stratum"],
            "round_labels": row["round_labels"],
            "ai_reference_label": row["ai_reference_label"],
        }
        for row in combined
        if row["screener_decision"] == "retain" and row["ai_reference_label"] == "deprioritize"
    ]
    false_negatives = [
        {
            "record_id": row["record_id"],
            "title": row["title"],
            "question_id": row["question_id"],
            "stratum": row["stratum"],
            "round_labels": row["round_labels"],
            "ai_reference_label": row["ai_reference_label"],
        }
        for row in combined
        if row["screener_decision"] != "retain" and row["ai_reference_label"] == "retain"
    ]

    reference_distribution = Counter(row["ai_reference_label"] for row in combined)
    cross = Counter(
        (row["screener_decision"], row["ai_reference_label"]) for row in combined
    )

    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": _now(),
        "phase": "P3-A",
        "purpose_ko": "P2 선별기(agent_direct)를 독립 AI 참조표준과 대조한 측정 결과",
        "reference_standard_type": "ai_reference_standard",
        "ai_reference_standard": True,
        "ai_cross_checked": True,
        "human_reference_standard": False,
        "human_decisions": 0,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
        "evaluator_ko": "판정 주체는 Claude 에이전트 본인이며 파일을 직접 읽고 직접 기록했다.",
        "independence_limitation_ko": (
            "동일 에이전트가 P2 선별과 P3-A 참조표준을 모두 수행했다. 절차적 블라인드는 "
            "P2 라벨을 제외한 카드, 라운드별 무작위 순서, 별칭 표기로 구현했으나 평가자 "
            "독립성은 사람 이중검토와 동등하지 않다."
        ),
        "prompt_path": str(REFERENCE_PROMPT.relative_to(ROOT)).replace("\\", "/"),
        "prompt_sha256": sha256_file(REFERENCE_PROMPT),
        "screening_prompt_sha256": sha256_file(
            LITERATURE_DIR / "prompts" / "agent_screening_prompt.md"
        ),
        "sample_manifest_path": str(SAMPLE_MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "sample_manifest_sha256": sha256_file(SAMPLE_MANIFEST),
        "blind_sample_path": str(BLIND_SAMPLE.relative_to(ROOT)).replace("\\", "/"),
        "blind_sample_sha256": sha256_file(BLIND_SAMPLE),
        "sample_size": len(combined),
        "sample_seed": manifest["sample_seed"],
        "strata": manifest["strata"],
        "rounds": [
            {
                "round": round_no,
                "seed": ROUND_SEEDS[round_no],
                "labels_path": f"research_v3/measurement/ai_reference/rounds/round{round_no}/labels.jsonl",
                "labels_sha256": sha256_file(ROUNDS_DIR / f"round{round_no}" / "labels.jsonl"),
                "picos_part_sha256": {
                    part.name: sha256_file(part)
                    for part in sorted((ROUNDS_DIR / f"round{round_no}").glob("picos_*.jsonl"))
                },
                "label_distribution": dict(
                    sorted(Counter(rounds[round_no][rid]["label"] for rid in record_ids).items())
                ),
            }
            for round_no in sorted(rounds)
        ],
        "composite_label_rule_ko": COMPOSITE_RULE_TEXT_KO,
        "inter_round": {
            "pairwise": pairwise,
            "mean_pairwise_agreement": statistics.fmean([p["agreement"] for p in pairwise]),
            "mean_pairwise_cohen_kappa": statistics.fmean(
                [p["cohen_kappa"] for p in pairwise if p["cohen_kappa"] is not None]
            ),
            "unanimous_rows": unanimous,
            "unanimous_rate": unanimous / len(combined),
            "unresolved_rows": len(unresolved),
            "unresolved_record_ids": [row["record_id"] for row in unresolved],
        },
        "ai_reference_label_distribution": dict(sorted(reference_distribution.items())),
        "screener_by_reference": {
            f"{screener_label}|{reference_label}": count
            for (screener_label, reference_label), count in sorted(cross.items())
        },
        "positive_class_ko": "retain",
        "screener_positive_definition_ko": "P2 판정이 retain 인 경우를 양성으로 본다(uncertain 은 음성 처리).",
        "reference_positive_definition_ko": "AI 참조표준 다수결 라벨이 retain 인 경우를 양성으로 본다.",
        "primary_analysis": {
            "rows_analyzed": len(primary_rows),
            "excluded_uncertain": sum(
                1 for row in combined if row["ai_reference_label"] == "uncertain"
            ),
            "excluded_unresolved": len(unresolved),
            **primary,
        },
        "sensitivity_analysis_uncertain_as_negative": {
            "rows_analyzed": len(secondary_rows),
            **secondary,
        },
        "reference_positive_classifier_positive": primary["weighted_true_positive"],
        "corpus_prevalence": {
            "corpus_rows": len(screener),
            "screener_retain_rows": corpus_retain,
            "apparent_retain_prevalence": apparent_prevalence,
            "rogan_gladen_corrected_prevalence": corrected,
            "rogan_gladen_corrected_prevalence_ci95": bootstrap["corrected_prevalence_ci95"],
            "estimated_corpus_retain_count": corpus_estimate,
            "estimated_corpus_retain_count_ci95": corpus_ci,
            "method_ko": (
                "겉보기 유병률은 코퍼스 전수의 P2 retain 비율이며, 민감도·특이도는 층화 "
                "가중 표본 추정치다. 95% CI 는 층 내부 복원추출 부트스트랩 10,000회의 "
                "백분위 구간이다."
            ),
        },
        "bootstrap": bootstrap,
        "wilson_ci95": {
            "unweighted_sensitivity": None,
            "unweighted_specificity": None,
        },
        "false_positive_examples": false_positives[:20],
        "false_positive_total": len(false_positives),
        "false_negative_examples": false_negatives[:20],
        "false_negative_total": len(false_negatives),
        "per_record": combined,
    }

    unweighted_tp = sum(
        1 for row in primary_rows if row["screener_positive"] and row["reference_positive"]
    )
    unweighted_fn = sum(
        1 for row in primary_rows if not row["screener_positive"] and row["reference_positive"]
    )
    unweighted_tn = sum(
        1 for row in primary_rows if not row["screener_positive"] and not row["reference_positive"]
    )
    unweighted_fp = sum(
        1 for row in primary_rows if row["screener_positive"] and not row["reference_positive"]
    )
    payload["wilson_ci95"]["unweighted_sensitivity"] = wilson_interval(
        unweighted_tp, unweighted_tp + unweighted_fn
    )
    payload["wilson_ci95"]["unweighted_specificity"] = wilson_interval(
        unweighted_tn, unweighted_tn + unweighted_fp
    )

    _write_json(OUTPUT_JSON, payload)
    print(
        "sensitivity={} specificity={} precision={} f1={} agreement={}".format(
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
        f"unresolved={len(unresolved)} uncertain="
        f"{payload['primary_analysis']['excluded_uncertain']} "
        f"fp={len(false_positives)} fn={len(false_negatives)}"
    )
    print(
        "corrected_prevalence={} ci={}".format(
            "n/a" if corrected is None else f"{corrected:.4f}",
            bootstrap["corrected_prevalence_ci95"],
        )
    )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3-A AI reference standard support tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sample").set_defaults(func=cmd_sample)

    render = sub.add_parser("render-round")
    render.add_argument("round", type=int)
    render.set_defaults(func=cmd_render_round)

    ingest = sub.add_parser("ingest-round")
    ingest.add_argument("round", type=int)
    ingest.set_defaults(func=cmd_ingest_round)

    sub.add_parser("finalize").set_defaults(func=cmd_finalize)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
