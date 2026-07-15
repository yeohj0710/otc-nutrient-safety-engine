from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.research.otc.audit_runtime_alignment import audit as audit_runtime_alignment
except ModuleNotFoundError:  # Direct script execution from the repository root.
    from audit_runtime_alignment import audit as audit_runtime_alignment


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def json_data(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def build() -> dict:
    selection_sources = csv_rows(OTC / "selection" / "source_evidence.csv")
    candidates = csv_rows(OTC / "selection" / "official_designation_candidates.csv")
    classes = csv_rows(OTC / "selection" / "included_classes.csv")
    products = csv_rows(OTC / "normalized" / "product_master.csv")
    ingredients = csv_rows(OTC / "normalized" / "ingredient_master.csv")
    product_ingredients = csv_rows(OTC / "normalized" / "product_ingredient.csv")
    analysis_exclusions = csv_rows(OTC / "normalized" / "analysis_exclusions.csv")
    administration_constraints = [
        row for row in csv_rows(OTC / "normalized" / "administration_constraints.csv")
        if row.get("record_status") == "verified_from_authorization_source"
    ]
    rejected = csv_rows(OTC / "normalized" / "rejected_rows.csv")
    rules = csv_rows(OTC / "rules" / "rules.csv")
    evidence_candidates = csv_rows(OTC / "rules" / "official_evidence_candidates.csv")
    development = csv_rows(OTC / "validation" / "development_scenarios.csv")
    independent = csv_rows(OTC / "validation" / "independent_scenarios.csv")
    evaluation = json_data(OTC / "validation" / "independent_evaluation.json", {"status": "not_run"})
    product_search = json_data(OTC / "validation" / "product_search_evaluation.json", {"status": "not_run"})
    normalization_reference = csv_rows(OTC / "validation" / "normalization_reference.csv")
    normalization_reviewed = [row for row in normalization_reference if row.get("human_reference_name")]
    normalization_correct = [row for row in normalization_reviewed if row["human_reference_name"] == row["system_normalized_name"]]
    software_validation = json_data(OTC / "audit" / "software_validation.json", {"status": "not_run"})
    preview_verification = json_data(OTC / "audit" / "preview_deployment_verification.json", {"valid": False})
    g_drive_sync = json_data(OTC / "audit" / "g_drive_working_sync_verification.json", {"valid": False})
    released = [row for row in rules if row["status"] == "released"]
    released_linked = [row for row in released if row["source_id"].strip() and row["source_locator"].strip()]
    verified_products = [row for row in products if row.get("record_status") == "verified_from_source"]
    calculation_ready = [row for row in verified_products if row.get("calculation_ready") == "true"]
    analysis_products = [row for row in products if row.get("analysis_status") == "included"]
    analysis_product_ids = {row["product_id"] for row in analysis_products}
    analysis_variant_rows = [row for row in product_ingredients if row["product_id"] in analysis_product_ids]
    selected_bindings = [row for row in product_ingredients if row.get("selected_for_calculation") == "true"]
    analysis_ingredient_ids = {row["ingredient_id"] for row in selected_bindings}
    analysis_normalization_reference = [row for row in normalization_reference if row["ingredient_id"] in analysis_ingredient_ids]
    analysis_normalization_reviewed = [row for row in analysis_normalization_reference if row.get("human_reference_name")]
    analysis_normalization_correct = [
        row for row in analysis_normalization_reviewed
        if row["human_reference_name"] == row["system_normalized_name"]
    ]
    runtime = json_data(ROOT / "src" / "generated" / "otc-runtime.json", {"products": [], "officialCandidates": []})
    runtime_alignment = audit_runtime_alignment()
    software_results = software_validation.get("results", {})
    blockers = []
    if not verified_products:
        blockers.append("MFDS 허가 원문에서 검증된 실제 일반의약품 제품 마스터가 아직 없음")
    if not released:
        blockers.append("source/locator가 검증된 released OTC 규칙이 아직 없음")
    if not evaluation.get("performance_claim_allowed", False):
        if evaluation.get("scenarios_evaluated", 0):
            blockers.append("Codex 사전판정 외부 확인은 완료됐으나 블라인드 독립 평가는 아직 없음")
        else:
            blockers.append("독립 시나리오 사람 기준정답과 성능 평가가 아직 없음")
    data_limitations = []
    if analysis_exclusions:
        data_limitations.append("신신파스아렉스는 4매 포장이 7×10㎠와 10×14㎠를 모두 가리켜 단일 규격을 결정할 수 없으므로 원문 자료만 보존하고 분석·사이트 대상에서 제외함")
    if not preview_verification.get("valid"):
        blockers.append("preview 브라우저 검증이 아직 없음")
    if not g_drive_sync.get("valid"):
        blockers.append("G 드라이브 작업본 패키지 동기화가 아직 없음")
    return {
        "schema_version": "2.0.0",
        "lineage": "research_v3",
        "research_direction": "korean_otc_product_safety",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "claim_boundary": "evidence_traceable_korean_otc_product_safety_research_working_state",
        "prior_direction": {"status": "superseded", "metrics_included": False},
        "metrics": {
            "selection_sources": {"status": "registered_or_verified", "value": len(selection_sources)},
            "representative_classes": {"status": "mixed_initial_and_pending", "value": len(classes)},
            "official_designation_candidates": {"status": "candidate_not_authorization_verified", "value": len(candidates)},
            "products_total": {"status": "authorization_candidate_master", "value": len(products)},
            "products_verified_from_source": {"status": "authorization_candidate_master", "value": len(verified_products)},
            "products_calculation_ready": {"status": "analysis_included", "value": len(calculation_ready)},
            "ingredients_total": {"status": "authorization_candidate_master", "value": len(ingredients)},
            "product_ingredient_rows": {"status": "authorization_candidate_product_ingredient_variant_rows", "value": len(product_ingredients)},
            "analysis_products": {"status": "site_aligned_analysis_set", "value": len(analysis_products)},
            "analysis_ingredients": {"status": "site_aligned_unique_ingredients", "value": len(analysis_ingredient_ids)},
            "analysis_product_ingredient_variant_rows": {"status": "analysis_products_all_authorized_variants", "value": len(analysis_variant_rows)},
            "runtime_product_ingredient_bindings": {"status": "selected_calculation_bindings", "value": len(selected_bindings)},
            "verified_administration_constraints": {"status": "verified_from_authorization_source_not_separately_pharmacist_reviewed", "value": len(administration_constraints)},
            "analysis_exclusions": {"status": "source_records_preserved", "value": len(analysis_exclusions)},
            "runtime_research_alignment": {"status": "audited", "value": runtime_alignment["valid"], "audit": "research_v3/otc/audit/runtime_research_alignment.json"},
            "normalization_rejections": {"status": "active_otc_only", "value": len(rejected)},
            "rules_total": {"status": "active_otc_only", "value": len(rules)},
            "rules_draft": {"status": "not_expert_released", "value": sum(row["status"] == "draft" for row in rules)},
            "rules_released": {"status": "active_otc_only", "value": len(released)},
            "official_rule_evidence_candidates": {"status": "codex_candidate_not_expert_verified", "value": len(evidence_candidates)},
            "released_source_locator_rate": {"status": "not_applicable_no_released_rules" if not released else "evaluated", "value": len(released_linked) / len(released) if released else None, "numerator": len(released_linked), "denominator": len(released)},
            "development_scenarios": {"status": "specification_only" if development and all(row["status"].startswith("specification_only") for row in development) else "mixed", "value": len(development)},
            "independent_scenarios": {"status": evaluation.get("status", "not_run"), "value": len(independent), "evaluated": evaluation.get("scenarios_evaluated", 0), "independent_blinding": evaluation.get("independent_blinding", False), "performance_claim_allowed": evaluation.get("performance_claim_allowed", False)},
            "critical_false_negatives": {"status": evaluation.get("status", "not_run"), "value": evaluation.get("critical_false_negatives")},
            "sensitivity": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("sensitivity") or {}).get("value")},
            "sensitivity_ci95": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("sensitivity") or {}).get("ci95")},
            "specificity": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("specificity") or {}).get("value")},
            "specificity_ci95": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("specificity") or {}).get("ci95")},
            "positive_predictive_value": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("positive_predictive_value") or {}).get("value")},
            "negative_predictive_value": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("negative_predictive_value") or {}).get("value")},
            "accuracy": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("accuracy") or {}).get("value")},
            "accuracy_ci95": {"status": evaluation.get("status", "not_run"), "value": (evaluation.get("accuracy") or {}).get("ci95")},
            "product_search_success_rate": {"status": product_search.get("status", "not_run"), "value": product_search.get("value"), "numerator": product_search.get("successes", 0), "denominator": product_search.get("cases", 0)},
            "ingredient_normalization_accuracy": {"status": "evaluated_human_locked_reference" if len(normalization_reviewed) == len(normalization_reference) and normalization_reference else "not_evaluated_missing_human_reference", "value": len(normalization_correct) / len(normalization_reviewed) if normalization_reviewed else None, "numerator": len(normalization_correct), "denominator": len(normalization_reviewed), "planned": len(normalization_reference)},
            "analysis_ingredient_normalization_accuracy": {"status": "evaluated_human_locked_reference" if len(analysis_normalization_reviewed) == len(analysis_normalization_reference) and analysis_normalization_reference else "not_evaluated_missing_human_reference", "value": len(analysis_normalization_correct) / len(analysis_normalization_reviewed) if analysis_normalization_reviewed else None, "numerator": len(analysis_normalization_correct), "denominator": len(analysis_normalization_reviewed), "planned": len(analysis_normalization_reference)},
            "runtime_products": {"status": "verified_products_only", "value": len(runtime.get("products", []))},
            "runtime_official_candidates": {"status": "not_selectable", "value": len(runtime.get("officialCandidates", []))},
            "research_tests_passed": {"status": software_results.get("research_tests", {}).get("status", "not_run"), "value": software_results.get("research_tests", {}).get("passed")},
            "app_tests_passed": {"status": software_results.get("app_tests", {}).get("status", "not_run"), "value": software_results.get("app_tests", {}).get("passed")},
            "static_paths_generated": {"status": software_results.get("build", {}).get("status", "not_run"), "value": software_results.get("build", {}).get("static_paths_generated")},
            "lint_typecheck_build_passed": {"status": software_validation.get("status", "not_run"), "value": all(software_results.get(name, {}).get("status") == "passed" for name in ("lint", "typecheck", "build")) if software_results else False},
            "software_validation": software_validation
        },
        "release_ready": False,
        "release_blockers": blockers,
        "data_limitations": data_limitations,
    }


def write(manifest: dict) -> None:
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "research_v3" / "metrics_manifest.json").write_text(payload, encoding="utf-8")
    (OTC / "metrics_manifest.json").write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    manifest = build()
    write(manifest)
    print(json.dumps({"release_ready": manifest["release_ready"], "blockers": len(manifest["release_blockers"])}, ensure_ascii=False))
