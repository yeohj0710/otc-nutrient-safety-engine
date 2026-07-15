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
        {"requirement": "independent_evaluation_complete", "status": "achieved" if m["independent_scenarios"]["evaluated"] == m["independent_scenarios"]["value"] and m["independent_scenarios"].get("performance_claim_allowed", False) else "incomplete", "evidence": m["independent_scenarios"]},
        {"requirement": "critical_false_negative_reported", "status": "achieved" if m["critical_false_negatives"]["value"] is not None else "incomplete", "evidence": m["critical_false_negatives"]},
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
    return {"schema_version": "1.0.0", "research_direction": "korean_otc_product_safety", "complete": not incomplete, "requirements": requirements, "incomplete_requirements": incomplete, "release_ready": False}


def main() -> int:
    result = audit()
    target = OTC / "audit" / "completion_audit.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": result["complete"], "achieved": len(result["requirements"]) - len(result["incomplete_requirements"]), "incomplete": len(result["incomplete_requirements"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
