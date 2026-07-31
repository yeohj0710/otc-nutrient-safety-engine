"""v5.0 연구 정보 화면이 쓸 수치를 원장에서 뽑아 런타임 JSON 으로 굽는다.

`.vercelignore` 가 `research_v3` 를 통째로 빼기 때문에 사이트는 원장을 직접 읽을 수 없다.
화면에 필요한 값만 여기서 옮겨 두고, 값이 어긋나면 테스트가 잡는다.

원장을 수정하지 않는다. 읽기만 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research_v3" / "logs" / "v50_run_report.json"
SCORING = ROOT / "research_v3" / "logs" / "v50_scoring_report.json"
LINKS = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "downstream"
    / "literature_link_manifest.json"
)
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
TARGET = ROOT / "src" / "generated" / "v50-research-summary.json"


def pct(value: float) -> float:
    return round(value * 100, 2)


def main() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    scoring = json.loads(SCORING.read_text(encoding="utf-8"))
    links = json.loads(LINKS.read_text(encoding="utf-8"))

    phase_c = ledger["phases"]["C"]
    final = phase_c["final_layer"]["decision_distribution"]
    classifier = phase_c["classifier_layer"]["decision_distribution"]
    adjudication = phase_c["semantic_adjudication_layer"]
    overall = scoring["layers"]["overall"]
    weighted = overall["weighted_metrics"]
    ci = overall["stratified_bootstrap_95_ci"]
    results = links["results"]

    questions = [
        {
            "id": q["question_id"],
            "titleKo": q["title_ko"],
            "hits": q["v5_hit_count"],
            "previousHits": q["v4_hit_count"],
            "dateFrom": q["date_range_start"],
        }
        for q in [
            {
                "question_id": item["question_id"],
                "title_ko": next(
                    d["title_ko"]
                    for d in ledger["query_definitions"]["full_record"]["questions"]
                    if d["question_id"] == item["question_id"]
                ),
                "v5_hit_count": item["v5_hit_count"],
                "v4_hit_count": item["v4_hit_count"],
                "date_range_start": next(
                    d["date_range"]["start"]
                    for d in ledger["query_definitions"]["full_record"]["questions"]
                    if d["question_id"] == item["question_id"]
                ),
            }
            for item in ledger["v4_to_v5_hit_count_change"]
        ]
    ]

    rule_rows = RULES.read_text(encoding="utf-8-sig").splitlines()
    released = sum(1 for line in rule_rows[1:] if ",released," in line)

    summary = {
        "schemaVersion": "1.0.0",
        "track": "v5.0-mecir-search",
        "generatedFrom": {
            "ledger": "research_v3/logs/v50_run_report.json",
            "scoring": "research_v3/logs/v50_scoring_report.json",
            "links": "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
        },
        "authorization": {
            "analysedProducts": 13,
            "collectedProducts": 16,
            "uniqueIngredients": ledger["ingredient_coverage"]["included_count"],
            "productIngredientLinks": 47,
            "administrationConstraints": 32,
            "ruleCount": results["rule_count"],
            "releasedRuleCount": released,
        },
        "literature": {
            "questions": questions,
            "hitTotal": sum(q["hits"] for q in questions),
            "previousHitTotal": sum(q["previousHits"] for q in questions),
            "uniquePapers": links["inputs"]["evidence_map"]["record_count"],
            "screeningUnits": phase_c["final_layer"]["rows"],
            "xmlFiles": 105,
        },
        "screening": {
            "classifier": classifier,
            "adjudicatedRows": adjudication["selected_rows"],
            "adjudicationDisagreements": adjudication["disagreement_count"],
            "adjudicationDisagreementRate": pct(adjudication["disagreement_rate"]),
            "final": final,
            "finalRetainFromAdjudication": 1193,
            "finalRetainFromClassifierOnly": 6682,
            "classifierValidation": {
                "cases": phase_c["classifier_validation"]["case_count"],
                "passed": phase_c["classifier_validation"]["pass_count"],
                "failed": phase_c["classifier_validation"]["fail_count"],
            },
        },
        "scoring": {
            "sampleRows": scoring["design"]["sample_n"],
            "populationRows": scoring["design"]["population_N"],
            "strata": scoring["design"]["sampling_strata"],
            "bootstrapDraws": scoring["design"]["bootstrap_draws"],
            "agreement": pct(weighted["agreement_vs_ai_reference"]),
            "agreementCi": [pct(v) for v in ci["agreement_vs_ai_reference"]],
            "sensitivity": pct(weighted["sensitivity_vs_ai_reference"]),
            "sensitivityCi": [pct(v) for v in ci["sensitivity_vs_ai_reference"]],
            "specificity": pct(weighted["specificity_vs_ai_reference"]),
            "specificityCi": [pct(v) for v in ci["specificity_vs_ai_reference"]],
            "kappa": round(weighted["cohen_kappa_vs_ai_reference_weighted"], 3),
            "pipelineRetainShare": pct(
                final["retain"] / phase_c["final_layer"]["rows"]
            ),
            "scorerRetainShare": pct(
                scoring["rogan_gladen"]["design_weighted_scorer_retain_prevalence"]
            ),
            "disagreementByDirection": scoring["disagreements"]["raw_by_direction"],
            "truthOpenedBeforeLock": scoring["lock"]["truth_opened_before_lock"],
        },
        "ruleLiterature": {
            "ruleCount": results["rule_count"],
            "resolvedRuleCount": results["resolved_rule_count"],
            "unresolvedRuleCount": results["unresolved_rule_count"],
            "unresolvedRuleIds": results["unresolved_rule_ids"],
            "linkCount": results["emitted_link_count"],
            "rejectedCount": results["rejected_candidate_count"],
            "rejectionCounts": results["rejection_counts"],
        },
        "flags": {
            "independentBlinding": ledger["state_flags"]["independent_blinding"],
            "releaseReady": ledger["state_flags"]["release_ready"],
            "humanReferenceRows": ledger["state_flags"]["human_reference_rows"],
            "overallExecutionStatus": ledger["overall_execution_status"],
        },
        "limitations": [
            item["detail"]
            for item in ledger["limitations_and_unresolved_items"]
            if item.get("status") == "limitation"
        ],
    }

    TARGET.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"v50 research summary -> {TARGET}")
    print(
        f"  선별 단위 {summary['literature']['screeningUnits']:,} · "
        f"retain {final['retain']:,} · 규칙 연결 "
        f"{results['resolved_rule_count']}/{results['rule_count']}"
    )


if __name__ == "__main__":
    main()
