from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"


def audit() -> dict[str, object]:
    metrics = json.loads((OTC / "metrics_manifest.json").read_text(encoding="utf-8"))
    m = metrics["metrics"]
    identity = json.loads((OTC / "audit" / "active_identity_audit.json").read_text(encoding="utf-8"))
    claims = json.loads((OTC / "audit" / "claim_consistency.json").read_text(encoding="utf-8"))
    alignment = json.loads((OTC / "audit" / "runtime_research_alignment.json").read_text(encoding="utf-8"))
    document_qa = json.loads((OTC / "audit" / "document_visual_qa.json").read_text(encoding="utf-8"))
    preview_path = OTC / "audit" / "preview_deployment_verification.json"
    preview = json.loads(preview_path.read_text(encoding="utf-8")) if preview_path.exists() else {"valid": False}
    sync_path = OTC / "audit" / "g_drive_working_sync_verification.json"
    sync = json.loads(sync_path.read_text(encoding="utf-8-sig")) if sync_path.exists() else {"valid": False}
    promotion_path = OTC / "review" / "canonical_promotion_receipt.json"
    promotion = json.loads(promotion_path.read_text(encoding="utf-8-sig")) if promotion_path.exists() else {"valid": False}
    product_site_evidence = preview.get("valid", False) and alignment.get("valid", False)

    # P3-B AI 맹검 독립평가. 사람 블라인드 평가(`independent_blinding`)는 여전히 false 이고,
    # 완료 판정은 AI 평가(`independent_blinding_ai`)로 대체한다. 둘을 섞어 쓰지 않는다.
    ai_eval_path = OTC / "validation" / "ai_independent_evaluation.json"
    ai_eval = json.loads(ai_eval_path.read_text(encoding="utf-8-sig")) if ai_eval_path.exists() else {}
    ai_primary = ai_eval.get("primary_analysis", {})
    ai_lock = ai_eval.get("lock", {})
    ai_prediction = ai_eval.get("prediction", {})
    ai_complete = bool(
        ai_eval
        and ai_eval.get("ai_reference_standard") is True
        and ai_eval.get("human_reference_standard") is False
        and ai_eval.get("human_decisions") == 0
        and ai_eval.get("local_language_model_used") is False
        and ai_eval.get("external_llm_api_used") is False
        and ai_eval.get("subagents_used") is False
        and ai_eval.get("excluded_unresolved") == 0
        and ai_lock.get("sha256")
        and ai_prediction.get("verified_lock_sha256") == ai_lock.get("sha256")
        and ai_lock.get("created_at_utc") < ai_prediction.get("predicted_at_utc", "")
        and (ai_primary.get("cases") or 0) >= 200
    )
    ai_evidence = {
        "status": "evaluated_ai_reference_standard_blinded" if ai_complete else "incomplete",
        "evidence_path": "research_v3/otc/validation/ai_independent_evaluation.json",
        "lock_path": ai_lock.get("path"),
        "lock_sha256": ai_lock.get("sha256"),
        "prediction_path": ai_prediction.get("path"),
        "cases_total": ai_eval.get("cases_total"),
        "scored_cases": ai_primary.get("cases"),
        "excluded_uncertain": ai_eval.get("excluded_uncertain"),
        "excluded_unresolved": ai_eval.get("excluded_unresolved"),
        "excluded_blinding_compromised": ai_eval.get("excluded_blinding_compromised"),
        "sensitivity_vs_ai_reference": ai_primary.get("sensitivity_vs_ai_reference"),
        "specificity_vs_ai_reference": ai_primary.get("specificity_vs_ai_reference"),
        "independent_blinding_ai": ai_complete,
        "independent_blinding": False,
        "performance_claim_allowed": ai_complete,
        "performance_claim_condition_ko": (
            "AI 참조표준 대비 지표라는 사실과 평가자가 사람이 아니라는 사실을 항상 병기할 것"
        ),
    }
    document_evidence = document_qa.get("valid", False) and all(
        item.get("pages_rendered") == item.get("pages_inspected")
        and item.get("pages_inspected", 0) > 0
        and not any(item.get("accessibility_findings", {}).values())
        and item.get("pdf_fonts_embedded") is True
        and item.get("pretendard_embedded") is True
        for item in document_qa.get("documents", [])
    )
    requirements = [
        {"requirement": "actual_korean_otc_products_and_authorizations", "status": "achieved" if m["products_verified_from_source"]["value"] > 0 else "incomplete", "evidence": {"verified_products": m["products_verified_from_source"]["value"]}},
        {"requirement": "compound_ingredients_and_amounts_normalized", "status": "achieved" if alignment.get("valid") and m["runtime_product_ingredient_bindings"]["value"] > 0 else "incomplete", "evidence": {"candidate_master_ingredients": m["ingredients_total"]["value"], "candidate_product_ingredient_variant_rows": m["product_ingredient_rows"]["value"], "analysis_ingredients": m["analysis_ingredients"]["value"], "runtime_product_ingredient_bindings": m["runtime_product_ingredient_bindings"]["value"], "runtime_alignment": alignment.get("valid")}},
        {"requirement": "otc_selection_rationale", "status": "achieved" if m["selection_sources"]["value"] > 0 else "incomplete", "evidence": {"sources": m["selection_sources"]["value"]}},
        {"requirement": "released_rules_source_locator_100_percent", "status": "achieved" if m["rules_released"]["value"] > 0 and m["released_source_locator_rate"]["value"] == 1 else "incomplete", "evidence": m["released_source_locator_rate"]},
        {"requirement": "independent_evaluation_ai_complete", "status": "achieved" if ai_complete else "incomplete", "evidence": ai_evidence},
        {"requirement": "critical_false_negative_reported", "status": "achieved" if ai_eval.get("critical_false_negative_count") is not None else "incomplete", "evidence": {"status": ai_evidence["status"], "value": ai_eval.get("critical_false_negative_count"), "reference": "ai_reference_standard", "evidence_path": ai_evidence["evidence_path"]}},
        {"requirement": "product_search_success_rate_reported", "status": "achieved" if m["product_search_success_rate"]["denominator"] > 0 else "incomplete", "evidence": m["product_search_success_rate"]},
        {"requirement": "ingredient_normalization_accuracy_reported", "status": "achieved" if m["ingredient_normalization_accuracy"]["value"] is not None else "incomplete", "evidence": m["ingredient_normalization_accuracy"]},
        {"requirement": "product_name_centered_site", "status": "achieved" if m["runtime_products"]["value"] == m["analysis_products"]["value"] and product_site_evidence and alignment.get("valid") else "incomplete", "evidence": {"analysis_products": m["analysis_products"]["value"], "runtime_products": m["runtime_products"]["value"], "runtime_alignment": alignment.get("valid"), "browser_qa": product_site_evidence}},
        {"requirement": "documents_app_report_metrics_consistent", "status": "achieved" if claims.get("valid") else "incomplete", "evidence": {"claim_consistency": claims.get("valid")}},
        {"requirement": "tests_lint_typecheck_build_pass", "status": "achieved" if m["lint_typecheck_build_passed"]["value"] else "incomplete", "evidence": {"research_tests": m["research_tests_passed"]["value"], "app_tests": m["app_tests_passed"]["value"]}},
        {"requirement": "docx_pdf_all_pages_visual_qa", "status": "achieved" if document_evidence else "incomplete", "evidence": {"audit": "research_v3/otc/audit/document_visual_qa.json", "document_checks_passed": document_evidence}},
        {"requirement": "preview_browser_verified", "status": "achieved" if preview.get("valid") else "incomplete", "evidence": {"audit": "research_v3/otc/audit/preview_deployment_verification.json", "valid": preview.get("valid", False)}},
        {"requirement": "g_drive_working_package_synced", "status": "achieved" if sync.get("valid") else "incomplete", "evidence": {"audit": "research_v3/otc/audit/g_drive_working_sync_verification.json", "valid": sync.get("valid", False)}},
        {"requirement": "canonical_promotion", "status": "achieved" if promotion.get("valid") and promotion.get("canonical_promoted") else "incomplete", "evidence": {"audit": "research_v3/otc/review/canonical_promotion_receipt.json", "valid": promotion.get("valid", False)}},
        {"requirement": "no_cross_student_contamination", "status": "achieved" if identity["valid"] else "incomplete", "evidence": {"identity_audit_valid": identity["valid"], "findings": identity["cross_student_findings"]}},
    ]
    incomplete = [item["requirement"] for item in requirements if item["status"] != "achieved"]
    complete = not incomplete
    return {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "complete": complete,
        "requirements": requirements,
        "incomplete_requirements": incomplete,
        # 각 플래그와 근거 파일 경로. 사람 블라인드와 AI 블라인드를 절대 합치지 않는다.
        "status_flags": {
            "independent_blinding_ai": {
                "value": ai_complete,
                "evidence": ai_evidence["evidence_path"],
            },
            "independent_evaluation_ai_complete": {
                "value": ai_complete,
                "evidence": ai_evidence["evidence_path"],
            },
            "performance_claim_allowed": {
                "value": ai_complete,
                "evidence": ai_evidence["evidence_path"],
                "condition_ko": ai_evidence["performance_claim_condition_ko"],
            },
            "complete": {
                "value": complete,
                "evidence": "research_v3/otc/audit/completion_audit.json",
            },
            "release_ready": {
                "value": False,
                "evidence": "research_v3/otc/audit/completion_audit.json",
                "reason_ko": "임상 배포 승인 절차가 없으므로 항상 false 를 유지한다.",
            },
            "independent_blinding": {
                "value": False,
                "evidence": "research_v3/otc/validation/independent_evaluation.json",
                "reason_ko": (
                    "사람 블라인드 독립평가는 수행되지 않았다. AI 맹검 평가로 대체했으며 "
                    "이 플래그는 사람 평가 전용이라 false 를 유지한다."
                ),
            },
        },
        "release_ready": False,
    }


def main() -> int:
    result = audit()
    target = OTC / "audit" / "completion_audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": result["complete"], "achieved": len(result["requirements"]) - len(result["incomplete_requirements"]), "incomplete": len(result["incomplete_requirements"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
