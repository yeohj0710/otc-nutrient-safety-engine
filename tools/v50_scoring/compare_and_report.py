#!/usr/bin/env python3
"""Compare locked v5.0 scoring labels with the sealed AI reference."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
ARM = ROOT / "research_v3" / "otc" / "validation" / "screening_ai_reference_v50"
LOCKED = ARM / "scored_labels_locked.json"
LOCK_RECEIPT = ARM / "lock_receipt.json"
TRUTH = ARM / "v50_truth_sealed.json"
MANIFEST = ARM / "manifest.json"
SYNTHESIS = (
    ROOT / "research_v3" / "otc" / "synthesis" / "screener_vs_ai_reference_v50.json"
)
RUN_REPORT = ROOT / "research_v3" / "logs" / "v50_scoring_report.json"
FINAL_REPORT = ROOT / "research_v3" / "logs" / "v50_SCORING_FINAL.md"
RESULT_MANIFEST = ARM / "result_manifest.json"
DISAGREEMENTS = ARM / "disagreements.json"

LABELS = ("retain", "deprioritize", "uncertain")
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = "20260730-v50-scoring-bootstrap"
EXPECTED_POPULATION = 43_207
EXPECTED_SAMPLE = 894


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def pct(value: float | None) -> str:
    return "정의되지 않음" if value is None else f"{value * 100:.1f}%"


def interval_text(interval: list[float] | None) -> str:
    if interval is None:
        return "정의되지 않음"
    return f"{interval[0] * 100:.1f}%–{interval[1] * 100:.1f}%"


def number_interval_text(interval: list[float] | None) -> str:
    if interval is None:
        return "정의되지 않음"
    return f"{interval[0]:.3f}–{interval[1]:.3f}"


def render_markdown(payload: dict[str, Any], design_manifest: dict[str, Any]) -> str:
    lines = [
        "# v5.0 선별 채점 arm 최종 보고",
        "",
        f"생성 시각: `{payload['generated_at_utc']}`",
        "",
        "## 결론",
        "",
        (
            "동결 프롬프트를 보지 않은 것이 아니라 정답 라벨을 보지 않은 상태에서, "
            "동결 프롬프트를 그대로 사용해 894건을 새로 판정했다. 이 채점 arm에는 "
            "사람 참조 행이 없으므로 아래 수치는 사람 판단과의 성능이 아니라 AI 참조와의 일치도다."
        ),
        "",
        "## 라벨 잠금은 정답 공개보다 먼저 끝났다",
        "",
        f"- 잠금 시각(UTC): `{payload['lock']['locked_at_utc']}`",
        f"- 잠금 SHA-256: `{payload['lock']['scored_labels_sha256']}`",
        "- `truth_opened_before_lock=false`",
        "- `independent_blinding=false`, `independent_blinding_ai=true`, `release_ready=false`",
        "",
        "## 표본층은 43,207건을 빠짐없이 한 번씩 나눈다",
        "",
        "층 축은 질문 × 최종 라벨 × 재판정 여부다. 불변식 실패가 있는 기본층은 실패 행 전수층과 나머지 확률표본층으로 나눴다.",
        "",
        "| 질문 / 재판정 여부 / 최종 라벨 | population_N | sample_n | 불변식 실패 전수 n |",
        "|---|---:|---:|---:|",
    ]
    for stratum_id, spec in design_manifest["design"]["base_strata"].items():
        label = stratum_id.replace("|", " / ")
        lines.append(
            f"| {label} | {spec['population_N']:,} | {spec['sample_n']:,} | "
            f"{spec['invariant_failure_census_N']:,} |"
        )
    base = design_manifest["design"]["base_strata"].values()
    lines.extend(
        [
            f"| **합계** | **{sum(x['population_N'] for x in base):,}** | "
            f"**{sum(x['sample_n'] for x in base):,}** | **15** |",
            "",
            "검산: 기본층 `population_N` 합계는 43,207이다. 기본층 25개를 불변식 실패 여부로 나눈 실제 표집층은 33개다. 확률표본층 가중치는 `N_h/n_h`, 전수층 가중치는 1이다.",
            "",
            "## 전체·분류기층·재판정층 결과",
            "",
            "retain을 양성으로 두고 deprioritize와 uncertain을 비양성으로 묶었다. 괄호는 전수층을 고정한 층화 부트스트랩 10,000회 95% 구간이다.",
            "",
            "| 분석층 | 표본 n | 추정 모집단 N | sensitivity_vs_ai_reference | specificity_vs_ai_reference | precision_vs_ai_reference | f1_vs_ai_reference | agreement_vs_ai_reference | Cohen κ(가중) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, title in (
        ("overall", "전체"),
        ("classifier", "분류기층"),
        ("adjudicated", "재판정층"),
    ):
        layer = payload["layers"][name]
        metrics = layer["weighted_metrics"]
        intervals = layer["stratified_bootstrap_95_ci"]
        cells = []
        for metric in (
            "sensitivity_vs_ai_reference",
            "specificity_vs_ai_reference",
            "precision_vs_ai_reference",
            "f1_vs_ai_reference",
            "agreement_vs_ai_reference",
            "cohen_kappa_vs_ai_reference_weighted",
        ):
            if metric == "cohen_kappa_vs_ai_reference_weighted":
                cells.append(
                    f"{metrics[metric]:.3f} ({number_interval_text(intervals[metric])})"
                )
            else:
                cells.append(
                    f"{pct(metrics[metric])} ({interval_text(intervals[metric])})"
                )
        lines.append(
            f"| {title} | {layer['sample_n']:,} | {layer['estimated_population_N']:,.0f} | "
            + " | ".join(cells)
            + " |"
        )

    lines.extend(
        [
            "",
            "표본의 단순 이항비율에 대한 Wilson 95% 구간은 다음과 같다. 층화 설계의 주 추론 구간은 위 부트스트랩 구간이다.",
            "",
            "| 분석층 | sensitivity_vs_ai_reference | specificity_vs_ai_reference | precision_vs_ai_reference | agreement_vs_ai_reference |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, title in (
        ("overall", "전체"),
        ("classifier", "분류기층"),
        ("adjudicated", "재판정층"),
    ):
        intervals = payload["layers"][name]["wilson_95_ci_unweighted_sample"]
        lines.append(
            f"| {title} | "
            + " | ".join(
                interval_text(intervals[metric])
                for metric in (
                    "sensitivity_vs_ai_reference",
                    "specificity_vs_ai_reference",
                    "precision_vs_ai_reference",
                    "agreement_vs_ai_reference",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 불일치는 어느 방향으로 발생했나",
            "",
            f"정확한 3개 라벨 불일치는 표본 {payload['design']['sample_n']:,}건 중 {payload['disagreements']['raw_total']:,}건이다.",
            "",
            "| AI 참조 → 새 채점 | 표본 건수 | 설계가중 추정 건수 |",
            "|---|---:|---:|",
        ]
    )
    for direction, count in payload["disagreements"]["raw_by_direction"].items():
        weighted = payload["disagreements"]["design_weighted_by_direction"][direction]
        lines.append(f"| {direction} | {count:,} | {weighted:,.1f} |")

    lines.extend(
        [
            "",
            "## 질문별 정확한 3개 라벨 일치율",
            "",
            "| 질문 | 표본 n | 추정 모집단 N | 설계가중 일치율 | 표본 불일치 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for question_id, result in payload["question_agreement"].items():
        lines.append(
            f"| {question_id} | {result['sample_n']:,} | {result['estimated_population_N']:,.0f} | "
            f"{pct(result['exact_three_label_agreement_vs_ai_reference_weighted'])} | "
            f"{result['raw_disagreements']:,} |"
        )

    focus = payload["focus_classifier_unadjudicated_retain"]
    focus_metric = focus["weighted_metrics"]["sensitivity_vs_ai_reference"]
    focus_ci = focus["stratified_bootstrap_95_ci"]["sensitivity_vs_ai_reference"]
    lines.extend(
        [
            "",
            "## 최종 retain 중 미재판정 6,682건에서 확인한 범위",
            "",
            f"독립층에서 {focus['sample_n']:,}건을 확률표집했다. 새 채점도 retain을 준 설계가중 비율은 {pct(focus_metric)}이며, 층화 부트스트랩 95% 구간은 {interval_text(focus_ci)}다.",
            "",
            "이 표본은 6,682건에서 동결 프롬프트를 새로 적용했을 때 기존 최종 retain 라벨이 얼마나 재현되는지를 추정한다. 표본은 사람 판단과의 일치, 임상적 타당성, 또는 미재판정 6,682건 전부의 개별 오분류 여부를 말해 주지 않는다.",
            "",
            "## 전수층과 로건-글래든 식의 해석",
            "",
            "불변식 실패 전수층은 부트스트랩에서 다시 뽑지 않고 매 반복에 그대로 넣었다. 전수층만 분석하면 구간이 한 점으로 수축하는 것이 맞다.",
            "",
            f"로건-글래든 식과 설계가중 새 채점 retain 비율의 절대차는 `{payload['rogan_gladen']['absolute_difference']:.3g}`다. 층을 AI 참조 라벨로 정하고 같은 표본에서 두 오류모수를 계산했기 때문에 생기는 대수적 항등식이다. 외부 검증연구의 오류모수를 쓰지 않은 이 계산은 독립 교차확인이 아니다.",
            "",
            "## 소급할 수 없는 v5.0 한계",
            "",
            "v5.0 재판정의 실행자·모델·실행 시각·선행 질문 영수증은 당시 기록되지 않아 소급 생성할 수 없다. 이번 채점 arm의 새 영수증은 별도 검증층의 provenance만 보완하며, 기존 재판정의 공백을 메우지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def f1_value(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def wilson_95(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def weighted_counts(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    counts = {"tp": 0.0, "tn": 0.0, "fp": 0.0, "fn": 0.0}
    for row in rows:
        reference_positive = row["ai_reference_decision"] == "retain"
        scoring_positive = row["scoring_decision"] == "retain"
        weight = float(row["weight"])
        if reference_positive and scoring_positive:
            counts["tp"] += weight
        elif reference_positive:
            counts["fn"] += weight
        elif scoring_positive:
            counts["fp"] += weight
        else:
            counts["tn"] += weight
    return counts


def raw_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for row in rows:
        reference_positive = row["ai_reference_decision"] == "retain"
        scoring_positive = row["scoring_decision"] == "retain"
        if reference_positive and scoring_positive:
            counts["tp"] += 1
        elif reference_positive:
            counts["fn"] += 1
        elif scoring_positive:
            counts["fp"] += 1
        else:
            counts["tn"] += 1
    return counts


def weighted_kappa(rows: Iterable[dict[str, Any]]) -> float | None:
    matrix = {(ref, score): 0.0 for ref in LABELS for score in LABELS}
    for row in rows:
        matrix[(row["ai_reference_decision"], row["scoring_decision"])] += float(
            row["weight"]
        )
    total = sum(matrix.values())
    if not total:
        return None
    observed = sum(matrix[(label, label)] for label in LABELS) / total
    reference_margin = {
        label: sum(matrix[(label, score)] for score in LABELS) for label in LABELS
    }
    scoring_margin = {
        label: sum(matrix[(ref, label)] for ref in LABELS) for label in LABELS
    }
    expected = sum(
        reference_margin[label] * scoring_margin[label] for label in LABELS
    ) / (total * total)
    return safe_ratio(observed - expected, 1 - expected)


def metric_values(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    counts = weighted_counts(rows)
    precision = safe_ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = safe_ratio(counts["tp"], counts["tp"] + counts["fn"])
    return {
        "sensitivity_vs_ai_reference": recall,
        "specificity_vs_ai_reference": safe_ratio(
            counts["tn"], counts["tn"] + counts["fp"]
        ),
        "precision_vs_ai_reference": precision,
        "f1_vs_ai_reference": f1_value(precision, recall),
        "agreement_vs_ai_reference": safe_ratio(
            counts["tp"] + counts["tn"], sum(counts.values())
        ),
        "cohen_kappa_vs_ai_reference_weighted": weighted_kappa(rows),
    }


def wilson_intervals(rows: list[dict[str, Any]]) -> dict[str, list[float] | None]:
    counts = raw_counts(rows)
    return {
        "sensitivity_vs_ai_reference": wilson_95(
            counts["tp"], counts["tp"] + counts["fn"]
        ),
        "specificity_vs_ai_reference": wilson_95(
            counts["tn"], counts["tn"] + counts["fp"]
        ),
        "precision_vs_ai_reference": wilson_95(
            counts["tp"], counts["tp"] + counts["fp"]
        ),
        "agreement_vs_ai_reference": wilson_95(
            counts["tp"] + counts["tn"], sum(counts.values())
        ),
    }


def bootstrap_intervals(
    rows: list[dict[str, Any]], *, draws: int = BOOTSTRAP_DRAWS, seed_suffix: str
) -> tuple[dict[str, list[float] | None], dict[str, Any]]:
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[row["sampling_stratum_id"]].append(row)

    random_source = random.Random(f"{BOOTSTRAP_SEED}|{seed_suffix}")
    observed = metric_values(rows)
    samples: dict[str, list[float]] = {name: [] for name in observed}
    census_rows = [row for row in rows if row["census"]]
    probability_rows = [row for row in rows if not row["census"]]

    if not probability_rows:
        point = {
            name: ([value, value] if value is not None else None)
            for name, value in observed.items()
        }
        return point, {
            "draws": draws,
            "census_strata_fixed": True,
            "probability_strata_resampled": 0,
            "census_strata_fixed_count": len(strata),
            "interval_collapsed_to_point": True,
        }

    for _ in range(draws):
        replicate: list[dict[str, Any]] = []
        for stratum_rows in strata.values():
            if stratum_rows[0]["census"]:
                replicate.extend(stratum_rows)
            else:
                replicate.extend(
                    random_source.choices(stratum_rows, k=len(stratum_rows))
                )
        values = metric_values(replicate)
        for name, value in values.items():
            if value is not None:
                samples[name].append(value)

    intervals = {
        name: (
            [percentile(values, 0.025), percentile(values, 0.975)] if values else None
        )
        for name, values in samples.items()
    }
    return intervals, {
        "draws": draws,
        "seed": f"{BOOTSTRAP_SEED}|{seed_suffix}",
        "census_strata_fixed": True,
        "probability_strata_resampled": len(
            {row["sampling_stratum_id"] for row in probability_rows}
        ),
        "census_strata_fixed_count": len(
            {row["sampling_stratum_id"] for row in census_rows}
        ),
        "interval_collapsed_to_point": False,
    }


def matrix(
    rows: list[dict[str, Any]], *, weighted: bool
) -> dict[str, dict[str, float]]:
    result = {ref: {score: 0.0 for score in LABELS} for ref in LABELS}
    for row in rows:
        amount = float(row["weight"]) if weighted else 1.0
        result[row["ai_reference_decision"]][row["scoring_decision"]] += amount
    return result


def layer_summary(rows: list[dict[str, Any]], layer_name: str) -> dict[str, Any]:
    boot, boot_design = bootstrap_intervals(rows, seed_suffix=layer_name)
    raw = raw_counts(rows)
    return {
        "sample_n": len(rows),
        "estimated_population_N": sum(float(row["weight"]) for row in rows),
        "probability_sample_n": sum(not row["census"] for row in rows),
        "census_n": sum(bool(row["census"]) for row in rows),
        "weighted_metrics": metric_values(rows),
        "stratified_bootstrap_95_ci": boot,
        "stratified_bootstrap_design": boot_design,
        "wilson_95_ci_unweighted_sample": wilson_intervals(rows),
        "raw_binary_confusion": raw,
        "weighted_binary_confusion": weighted_counts(rows),
        "raw_three_label_matrix": matrix(rows, weighted=False),
        "weighted_three_label_matrix": matrix(rows, weighted=True),
    }


def exact_agreement(rows: list[dict[str, Any]]) -> float:
    numerator = sum(
        float(row["weight"])
        for row in rows
        if row["ai_reference_decision"] == row["scoring_decision"]
    )
    return numerator / sum(float(row["weight"]) for row in rows)


def rogan_gladen_identity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = weighted_counts(rows)
    total = sum(counts.values())
    apparent_reference_prevalence = (counts["tp"] + counts["fn"]) / total
    reverse_se = safe_ratio(counts["tp"], counts["tp"] + counts["fp"])
    reverse_sp = safe_ratio(counts["tn"], counts["tn"] + counts["fn"])
    scorer_retain_prevalence = (counts["tp"] + counts["fp"]) / total
    if reverse_se is None or reverse_sp is None or reverse_se + reverse_sp == 1:
        formula_value = None
        difference = None
    else:
        formula_value = (apparent_reference_prevalence + reverse_sp - 1) / (
            reverse_se + reverse_sp - 1
        )
        difference = abs(formula_value - scorer_retain_prevalence)
    return {
        "status": "algebraic_identity_not_independent_correction",
        "formula_value": formula_value,
        "design_weighted_scorer_retain_prevalence": scorer_retain_prevalence,
        "absolute_difference": difference,
        "interpretation": (
            "Reference-label strata reconstruct the reference population totals. "
            "Estimating both error parameters from the same sample makes the "
            "Rogan-Gladen expression reduce algebraically to the scorer retain prevalence. "
            "It is not an independent cross-check; external validation parameters would be required."
        ),
    }


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    lock_receipt = read_json(LOCK_RECEIPT)
    assert lock_receipt["truth_opened_before_lock"] is False
    assert sha256_file(LOCKED) == lock_receipt["scored_labels_sha256"]

    locked = read_json(LOCKED)["labels"]
    truth = read_json(TRUTH)
    assert set(locked) == set(truth)
    assert len(locked) == EXPECTED_SAMPLE

    rows = []
    for key in sorted(truth):
        reference = truth[key]
        scoring = locked[key]
        assert scoring["decision"] in LABELS
        row = dict(reference)
        row["key"] = key
        row["scoring_decision"] = scoring["decision"]
        row["scoring_reason_codes"] = scoring["reason_codes"]
        row["scoring_confidence"] = scoring["confidence"]
        row["scoring_evidence_basis"] = scoring["evidence_basis"]
        rows.append(row)
    return rows, lock_receipt, read_json(MANIFEST)


def main() -> None:
    rows, lock_receipt, design_manifest = build_rows()
    assert round(sum(float(row["weight"]) for row in rows)) == EXPECTED_POPULATION
    assert sum(row["ai_reference_decision"] == "retain" for row in rows) > 0

    layers = {
        "overall": rows,
        "classifier": [
            row for row in rows if row["adjudication_status"] == "classifier"
        ],
        "adjudicated": [
            row for row in rows if row["adjudication_status"] == "adjudicated"
        ],
    }
    summaries = {name: layer_summary(layer, name) for name, layer in layers.items()}

    question_agreement = {}
    for question_id in sorted({row["question_id"] for row in rows}):
        subset = [row for row in rows if row["question_id"] == question_id]
        question_agreement[question_id] = {
            "sample_n": len(subset),
            "estimated_population_N": sum(float(row["weight"]) for row in subset),
            "exact_three_label_agreement_vs_ai_reference_weighted": exact_agreement(
                subset
            ),
            "binary_agreement_vs_ai_reference_weighted": metric_values(subset)[
                "agreement_vs_ai_reference"
            ],
            "raw_disagreements": sum(
                row["ai_reference_decision"] != row["scoring_decision"]
                for row in subset
            ),
        }

    raw_directions = Counter(
        f"{row['ai_reference_decision']}->{row['scoring_decision']}"
        for row in rows
        if row["ai_reference_decision"] != row["scoring_decision"]
    )
    weighted_directions: Counter[str] = Counter()
    disagreement_rows = []
    for row in rows:
        if row["ai_reference_decision"] == row["scoring_decision"]:
            continue
        direction = f"{row['ai_reference_decision']}->{row['scoring_decision']}"
        weighted_directions[direction] += float(row["weight"])
        disagreement_rows.append(
            {
                "record_id": row["record_id"],
                "question_id": row["question_id"],
                "adjudication_status": row["adjudication_status"],
                "ai_reference_decision": row["ai_reference_decision"],
                "scoring_decision": row["scoring_decision"],
                "sampling_stratum_id": row["sampling_stratum_id"],
                "weight": row["weight"],
            }
        )

    focus_rows = [
        row
        for row in rows
        if row["adjudication_status"] == "classifier"
        and row["ai_reference_decision"] == "retain"
    ]
    focus = layer_summary(focus_rows, "classifier_unadjudicated_retain")
    assert round(focus["estimated_population_N"]) == 6_682

    generated_at = utc_now()
    payload = {
        "schema_version": "1.0.0",
        "arm": "screening_ai_reference_v50",
        "generated_at_utc": generated_at,
        "reference_type": "frozen_prompt_ai_reference",
        "human_reference_rows": 0,
        "independent_blinding": False,
        "independent_blinding_ai": True,
        "release_ready": False,
        "labels_locked_before_truth_open": True,
        "lock": {
            "locked_at_utc": lock_receipt["locked_at_utc"],
            "scored_labels_sha256": lock_receipt["scored_labels_sha256"],
            "truth_opened_before_lock": lock_receipt["truth_opened_before_lock"],
        },
        "design": {
            "seed": design_manifest["seed"],
            "rank_function": design_manifest["design"]["rank_function"],
            "population_N": EXPECTED_POPULATION,
            "sample_n": EXPECTED_SAMPLE,
            "sampling_strata": len(design_manifest["design"]["strata"]),
            "population_N_sum_asserted": True,
            "weights": "probability stratum N_h/n_h; census stratum 1",
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_census_handling": "census strata held fixed; probability strata resampled within stratum",
        },
        "layers": summaries,
        "question_agreement": question_agreement,
        "disagreements": {
            "raw_total": len(disagreement_rows),
            "raw_by_direction": dict(sorted(raw_directions.items())),
            "design_weighted_by_direction": dict(sorted(weighted_directions.items())),
        },
        "focus_classifier_unadjudicated_retain": {
            **focus,
            "population_N": 6_682,
            "interpretation": {
                "supported": (
                    "The probability sample estimates agreement with a newly blinded AI scoring pass "
                    "for the 6,682 final retain rows that did not receive v5.0 semantic adjudication."
                ),
                "not_supported": (
                    "It does not establish agreement with a human reference, a clinical conclusion, "
                    "or the error rate of every unreviewed row."
                ),
            },
        },
        "rogan_gladen": rogan_gladen_identity(rows),
        "permanent_v50_limitation": (
            "The v5.0 re-adjudication executor, model, execution time, and pre-question receipt "
            "were not recorded and cannot be reconstructed retrospectively. This scoring arm "
            "does not repair that separate provenance gap."
        ),
    }

    write_json(SYNTHESIS, payload)
    write_json(RUN_REPORT, payload)
    FINAL_REPORT.write_text(render_markdown(payload, design_manifest), encoding="utf-8")
    write_json(
        DISAGREEMENTS,
        {
            "schema_version": "1.0.0",
            "arm": "screening_ai_reference_v50",
            "generated_at_utc": generated_at,
            "rows": disagreement_rows,
        },
    )
    write_json(
        RESULT_MANIFEST,
        {
            "schema_version": "1.0.0",
            "arm": "screening_ai_reference_v50",
            "status": "completed",
            "generated_at_utc": generated_at,
            "human_reference_rows": 0,
            "independent_blinding": False,
            "independent_blinding_ai": True,
            "release_ready": False,
            "local_language_model_used": False,
            "external_llm_api_used": False,
            "lock": payload["lock"],
            "files": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                for path in (
                    SYNTHESIS,
                    RUN_REPORT,
                    FINAL_REPORT,
                    DISAGREEMENTS,
                    ARM / "blinded_cards.json",
                    ARM / "scoring_execution_receipt.json",
                    LOCKED,
                    LOCK_RECEIPT,
                    TRUTH,
                    ARM / "SCORER_RUBRIC.md",
                    ROOT / "tools" / "v50_scoring" / "sample_and_build_cards.py",
                    ROOT / "tools" / "v50_scoring" / "scoring_harness.py",
                    ROOT / "tools" / "v50_scoring" / "compare_and_report.py",
                )
            },
        },
    )
    print(
        f"completed sample={len(rows)} population={EXPECTED_POPULATION} "
        f"disagreements={len(disagreement_rows)} output={SYNTHESIS.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
