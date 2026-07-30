#!/usr/bin/env python3
"""v5.0 채점 arm의 완전분할 층화 표본과 맹검 카드를 만든다.

판정은 하지 않는다. 기존 v5.0 최종 라벨은 봉인 파일에만 쓰고, 카드에는
record_id·question_id·title·abstract·publication_types·mesh_terms만 남긴다.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREEN = V5 / "screening"
OUT = ROOT / "research_v3" / "otc" / "validation" / "screening_ai_reference_v50"

CLASSIFIER = SCREEN / "classifier_decisions.csv"
FINAL = SCREEN / "decisions.csv"
ADJUDICATIONS = SCREEN / "semantic_adjudications.json"
CLASSIFIER_VALIDATION = SCREEN / "classifier_validation.json"
CORPUS = V5 / "evidence_map.csv"
FROZEN_PROMPT = V5 / "prompts" / "frozen_semantic_adjudication_prompt.md"

SEED = "20260730-v50-scoring-arm"
PER_BASE_STRATUM = 38
EXPECTED_POPULATION = 43_207
EXPECTED_SAMPLE = 894
EXPECTED_FINAL_DISTRIBUTION = {
    "retain": 7_875,
    "deprioritize": 34_965,
    "uncertain": 367,
}
EXPECTED_ADJUDICATION_STATUS = {"classifier": 38_207, "adjudicated": 5_000}
EXPECTED_UNADJUDICATED_RETAIN = 6_682
EXPECTED_INVARIANT_FAILURES = 15

CARD_FIELDS = (
    "record_id",
    "question_id",
    "title",
    "abstract",
    "publication_types",
    "mesh_terms",
)
FORBIDDEN_CARD_KEYS = {
    "decision",
    "final_label",
    "classifier_label",
    "adjudication_label",
    "adjudication_status",
    "label_source",
    "reason_codes",
    "confidence",
    "evidence_basis",
    "selection_reason",
    "selected_for_adjudication",
    "sampling_stratum_id",
    "base_stratum_id",
    "weight",
    "invariant_failure",
}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank_key(question_id: str, record_id: str) -> str:
    raw = f"{SEED}|{question_id}|{record_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _decision_fields(row: dict[str, Any]) -> dict[str, Any]:
    reason_codes = row["reason_codes"]
    if isinstance(reason_codes, str):
        reason_codes = [part for part in reason_codes.split(";") if part]
    return {
        "decision": row["decision"],
        "reason_codes": list(reason_codes),
        "confidence": row["confidence"],
        "evidence_basis": row["evidence_basis"],
    }


def load_final_population() -> list[dict[str, Any]]:
    """원본 분류기와 재판정을 합성하고 봉인된 최종 CSV와 전량 대조한다."""
    classifier_rows = _read_csv(CLASSIFIER)
    final_rows = _read_csv(FINAL)
    adjudication_payload = json.loads(ADJUDICATIONS.read_text(encoding="utf-8"))
    adjudication_rows = adjudication_payload["records"]

    classifier = {
        (row["question_id"], row["record_id"]): _decision_fields(row)
        for row in classifier_rows
    }
    final = {
        (row["question_id"], row["record_id"]): _decision_fields(row)
        for row in final_rows
    }
    adjudicated = {
        (row["question_id"], row["record_id"]): _decision_fields(row)
        for row in adjudication_rows
    }

    if len(classifier) != len(classifier_rows):
        raise RuntimeError("classifier_decisions.csv에 중복 키가 있다")
    if len(final) != len(final_rows):
        raise RuntimeError("decisions.csv에 중복 키가 있다")
    if len(adjudicated) != len(adjudication_rows):
        raise RuntimeError("semantic_adjudications.json에 중복 키가 있다")
    if set(classifier) != set(final):
        raise RuntimeError("분류기와 최종 결정의 키 집합이 다르다")
    if set(adjudicated) - set(classifier):
        raise RuntimeError("재판정 키가 분류기 코퍼스 밖에 있다")

    population: list[dict[str, Any]] = []
    for question_id, record_id in sorted(classifier):
        key_tuple = (question_id, record_id)
        expected = adjudicated.get(key_tuple, classifier[key_tuple])
        if expected != final[key_tuple]:
            raise RuntimeError(f"최종 라벨 재구성 불일치: {question_id}|{record_id}")
        status = "adjudicated" if key_tuple in adjudicated else "classifier"
        label = expected["decision"]
        base_stratum_id = f"{question_id}|{status}|{label}"
        population.append(
            {
                "key": f"{question_id}|{record_id}",
                "record_id": record_id,
                "question_id": question_id,
                "final_label": label,
                "reference_reason_codes": expected["reason_codes"],
                "reference_confidence": expected["confidence"],
                "reference_evidence_basis": expected["evidence_basis"],
                "adjudication_status": status,
                "base_stratum_id": base_stratum_id,
            }
        )

    _assert_population_margins(population)
    return population


def _assert_population_margins(population: list[dict[str, Any]]) -> None:
    if len(population) != EXPECTED_POPULATION:
        raise RuntimeError(f"코퍼스 {len(population)} != {EXPECTED_POPULATION}")
    if len({row["key"] for row in population}) != len(population):
        raise RuntimeError("코퍼스 키가 중복된다")
    labels = Counter(row["final_label"] for row in population)
    if dict(labels) != EXPECTED_FINAL_DISTRIBUTION:
        raise RuntimeError(f"최종 라벨 분포 불일치: {dict(labels)}")
    statuses = Counter(row["adjudication_status"] for row in population)
    if dict(statuses) != EXPECTED_ADJUDICATION_STATUS:
        raise RuntimeError(f"재판정 여부 분포 불일치: {dict(statuses)}")
    unadjudicated_retain = sum(
        row["final_label"] == "retain" and row["adjudication_status"] == "classifier"
        for row in population
    )
    if unadjudicated_retain != EXPECTED_UNADJUDICATED_RETAIN:
        raise RuntimeError(
            "재판정하지 않은 최종 retain 분포 불일치: "
            f"{unadjudicated_retain} != {EXPECTED_UNADJUDICATED_RETAIN}"
        )


def load_invariant_failure_keys() -> set[str]:
    payload = json.loads(CLASSIFIER_VALIDATION.read_text(encoding="utf-8"))
    failures = {
        f"{case['question_id']}|{case['record_id']}"
        for case in payload["cases"]
        if case.get("passed") is False
    }
    if len(failures) != EXPECTED_INVARIANT_FAILURES:
        raise RuntimeError(
            f"불변식 실패 {len(failures)} != {EXPECTED_INVARIANT_FAILURES}"
        )
    return failures


def _stratum_spec(
    *,
    sampling_stratum_id: str,
    base_stratum_id: str,
    population_n: int,
    sample_n: int,
    census: bool,
    invariant_failure_census: bool,
) -> dict[str, Any]:
    question_id, status, final_label = base_stratum_id.split("|")
    return {
        "sampling_stratum_id": sampling_stratum_id,
        "base_stratum_id": base_stratum_id,
        "question_id": question_id,
        "adjudication_status": status,
        "final_label": final_label,
        "invariant_failure_census": invariant_failure_census,
        "population_N": population_n,
        "sample_n": sample_n,
        "census": census,
        "weight": 1.0 if census else population_n / sample_n,
    }


def build_sample(
    population: list[dict[str, Any]], failure_keys: set[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """기본 층을 완전분할하고, 실패행 전수와 층별 확률표본을 합친다."""
    population_keys = {row["key"] for row in population}
    if not failure_keys <= population_keys:
        raise RuntimeError("불변식 실패 키가 최종 코퍼스 밖에 있다")

    base_pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in population:
        base_pools[row["base_stratum_id"]].append(row)

    selected: list[dict[str, Any]] = []
    strata: dict[str, dict[str, Any]] = {}
    base_summary: dict[str, dict[str, Any]] = {}

    def add_stratum(
        base_id: str,
        suffix: str,
        pool: list[dict[str, Any]],
        take_n: int,
        *,
        invariant_failure_census: bool,
    ) -> None:
        if not pool:
            return
        ordered = sorted(
            pool, key=lambda row: rank_key(row["question_id"], row["record_id"])
        )
        census = take_n == len(ordered)
        sampling_id = f"{base_id}|{suffix}"
        spec = _stratum_spec(
            sampling_stratum_id=sampling_id,
            base_stratum_id=base_id,
            population_n=len(ordered),
            sample_n=take_n,
            census=census,
            invariant_failure_census=invariant_failure_census,
        )
        strata[sampling_id] = spec
        for row in ordered[:take_n]:
            chosen = dict(row)
            chosen["sampling_stratum_id"] = sampling_id
            chosen["invariant_failure"] = invariant_failure_census
            selected.append(chosen)

    for base_id in sorted(base_pools):
        pool = base_pools[base_id]
        failures = [row for row in pool if row["key"] in failure_keys]
        probability_pool = [row for row in pool if row["key"] not in failure_keys]

        add_stratum(
            base_id,
            "invariant_failure_census",
            failures,
            len(failures),
            invariant_failure_census=True,
        )
        probability_n = min(PER_BASE_STRATUM, len(probability_pool))
        add_stratum(
            base_id,
            "probability",
            probability_pool,
            probability_n,
            invariant_failure_census=False,
        )
        base_summary[base_id] = {
            "base_stratum_id": base_id,
            "population_N": len(pool),
            "invariant_failure_census_N": len(failures),
            "probability_population_N": len(probability_pool),
            "sample_n": len(failures) + probability_n,
        }

    population_total = sum(spec["population_N"] for spec in strata.values())
    if population_total != len(population) or population_total != EXPECTED_POPULATION:
        raise RuntimeError(
            f"층 population_N 합 {population_total} != 코퍼스 {len(population)}"
        )
    if sum(row["population_N"] for row in base_summary.values()) != EXPECTED_POPULATION:
        raise RuntimeError("기본 층 population_N 합이 코퍼스와 다르다")
    if len({row["key"] for row in selected}) != len(selected):
        raise RuntimeError("표본 층이 겹치거나 표본 키가 중복된다")
    if failure_keys - {row["key"] for row in selected}:
        raise RuntimeError("불변식 실패 전수 층에서 누락이 생겼다")
    if len(selected) != EXPECTED_SAMPLE:
        raise RuntimeError(f"표본 {len(selected)} != 설계값 {EXPECTED_SAMPLE}")

    selected.sort(key=lambda row: rank_key(row["question_id"], row["record_id"]))
    design = {
        "seed": SEED,
        "rank_function": "SHA-256(seed|question_id|record_id) ascending",
        "partition_axes": ["final_label", "adjudication_status", "question_id"],
        "forced_census_rule": "classifier invariant failures are separate census substrata",
        "per_probability_stratum_target": PER_BASE_STRATUM,
        "partition_is_exhaustive": True,
        "partition_is_mutually_exclusive": True,
        "population_total": population_total,
        "sample_total": len(selected),
        "base_strata": base_summary,
        "strata": strata,
    }
    return selected, design


def build_cards(
    selected: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    wanted_record_ids = {row["record_id"] for row in selected}
    corpus: dict[str, dict[str, str]] = {}
    with CORPUS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            record_id = row["record_id"]
            if record_id in wanted_record_ids:
                if record_id in corpus:
                    raise RuntimeError(f"evidence_map.csv 중복 record_id: {record_id}")
                corpus[record_id] = row
    missing = wanted_record_ids - set(corpus)
    if missing:
        raise RuntimeError(f"evidence_map.csv에서 카드 원문 {len(missing)}건 누락")

    cards: list[dict[str, str]] = []
    for sampled in selected:
        source = corpus[sampled["record_id"]]
        cards.append(
            {
                "record_id": sampled["record_id"],
                "question_id": sampled["question_id"],
                "title": (source.get("title") or "").strip(),
                "abstract": (source.get("abstract") or "").strip(),
                "publication_types": (source.get("publication_types") or "").strip(),
                "mesh_terms": (source.get("mesh_terms") or "").strip(),
            }
        )

    stats = {
        "cards": len(cards),
        "abstract_present": sum(bool(card["abstract"]) for card in cards),
        "abstract_absent": sum(not card["abstract"] for card in cards),
        "mesh_present": sum(bool(card["mesh_terms"]) for card in cards),
        "mesh_absent": sum(not card["mesh_terms"] for card in cards),
    }
    return cards, stats


def leak_check(cards: list[dict[str, Any]]) -> dict[str, Any]:
    problems: list[str] = []
    for index, card in enumerate(cards):
        if tuple(card) != CARD_FIELDS:
            problems.append(f"card[{index}] field order/set mismatch: {tuple(card)}")
        leaked = set(card) & FORBIDDEN_CARD_KEYS
        if leaked:
            problems.append(f"card[{index}] forbidden keys: {sorted(leaked)}")
        for key in CARD_FIELDS:
            if not isinstance(card.get(key), str):
                problems.append(f"card[{index}].{key} is not a string")

    blob = json.dumps(cards, ensure_ascii=False)
    for key in FORBIDDEN_CARD_KEYS:
        if f'"{key}":' in blob:
            problems.append(f"serialized cards contain forbidden key: {key}")
    return {
        "checked_cards": len(cards),
        "allowed_fields": list(CARD_FIELDS),
        "forbidden_keys": sorted(FORBIDDEN_CARD_KEYS),
        "passed": not problems,
        "problems": problems,
    }


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    population = load_final_population()
    failure_keys = load_invariant_failure_keys()
    selected, design = build_sample(population, failure_keys)
    cards, card_stats = build_cards(selected)
    blinding_check = leak_check(cards)
    if not blinding_check["passed"]:
        raise RuntimeError(
            f"맹검 카드 누출 검사 실패: {blinding_check['problems'][:5]}"
        )

    cards_path = OUT / "blinded_cards.json"
    cards_bytes = _json_bytes(cards)
    cards_path.write_bytes(cards_bytes)

    truth: dict[str, dict[str, Any]] = {}
    for row in selected:
        spec = design["strata"][row["sampling_stratum_id"]]
        truth[row["key"]] = {
            "record_id": row["record_id"],
            "question_id": row["question_id"],
            "ai_reference_decision": row["final_label"],
            "ai_reference_reason_codes": row["reference_reason_codes"],
            "ai_reference_confidence": row["reference_confidence"],
            "ai_reference_evidence_basis": row["reference_evidence_basis"],
            "adjudication_status": row["adjudication_status"],
            "base_stratum_id": row["base_stratum_id"],
            "sampling_stratum_id": row["sampling_stratum_id"],
            "invariant_failure": row["invariant_failure"],
            "population_N": spec["population_N"],
            "sample_n": spec["sample_n"],
            "census": spec["census"],
            "weight": spec["weight"],
        }
    truth_path = OUT / "v50_truth_sealed.json"
    truth_bytes = _json_bytes(truth)
    truth_path.write_bytes(truth_bytes)

    created_at = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest = {
        "schema_version": "1.0.0",
        "track": "v5.0",
        "arm": "screening_ai_reference_v50",
        "status": "prepared_for_blinded_scoring",
        "created_at_utc": created_at,
        "seed": SEED,
        "human_reference_rows": 0,
        "independent_blinding": False,
        "independent_blinding_ai": None,
        "independent_blinding_ai_status": "pending_label_lock",
        "release_ready": False,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "design": design,
        "card_stats": card_stats,
        "blinding_check": blinding_check,
        "artifacts": {
            "blinded_cards": {
                "path": cards_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_bytes(cards_bytes),
                "rows": len(cards),
            },
            "v50_truth_sealed": {
                "path": truth_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_bytes(truth_bytes),
                "rows": len(truth),
                "opened_before_lock": False,
            },
        },
        "source_hashes": {
            "classifier_decisions.csv": sha256_file(CLASSIFIER),
            "decisions.csv": sha256_file(FINAL),
            "semantic_adjudications.json": sha256_file(ADJUDICATIONS),
            "classifier_validation.json": sha256_file(CLASSIFIER_VALIDATION),
            "evidence_map.csv": sha256_file(CORPUS),
            "frozen_semantic_adjudication_prompt.md": sha256_file(FROZEN_PROMPT),
        },
        "runtime_context": {
            "codex_thread_id": os.environ.get("CODEX_THREAD_ID"),
            "agent_path": "/root",
            "provider": "OpenAI",
            "model": "GPT-5 (Codex; exact deployment identifier not exposed)",
        },
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))

    print(f"population={design['population_total']} sample={design['sample_total']}")
    print(
        "final_labels="
        + json.dumps(EXPECTED_FINAL_DISTRIBUTION, ensure_ascii=False, sort_keys=True)
    )
    print(
        "adjudication_status="
        + json.dumps(EXPECTED_ADJUDICATION_STATUS, ensure_ascii=False, sort_keys=True)
    )
    print(
        f"invariant_failures_census={len(failure_keys)} "
        f"blinding_check={'pass' if blinding_check['passed'] else 'fail'}"
    )
    print(f"cards_sha256={sha256_bytes(cards_bytes)}")
    print(f"truth_sealed_sha256={sha256_bytes(truth_bytes)}")


if __name__ == "__main__":
    main()
