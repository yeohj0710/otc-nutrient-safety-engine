from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: object) -> None:
        checks.append({"check": name, "status": "passed" if condition else "failed", "detail": detail})

    products = rows(OTC / "normalized" / "product_master.csv")
    ingredients = rows(OTC / "normalized" / "ingredient_master.csv")
    joins = rows(OTC / "normalized" / "product_ingredient.csv")
    exclusions = rows(OTC / "normalized" / "analysis_exclusions.csv")
    rules = rows(OTC / "rules" / "rules.csv")
    evidence = rows(OTC / "rules" / "official_evidence_candidates.csv")
    shortlist = rows(OTC / "rules" / "rule_evidence_shortlist.csv")
    bindings = rows(OTC / "rules" / "runtime_rule_bindings.csv")
    independent = rows(OTC / "validation" / "independent_scenarios.csv")
    normalization_reference = rows(OTC / "validation" / "normalization_reference.csv")
    runtime = json.loads((ROOT / "src" / "generated" / "otc-runtime.json").read_text(encoding="utf-8"))
    metrics = json.loads((OTC / "metrics_manifest.json").read_text(encoding="utf-8"))
    software = json.loads((OTC / "audit" / "software_validation.json").read_text(encoding="utf-8"))
    evaluation = json.loads((OTC / "validation" / "independent_evaluation.json").read_text(encoding="utf-8"))
    product_search = json.loads((OTC / "validation" / "product_search_evaluation.json").read_text(encoding="utf-8"))
    identity = json.loads((OTC / "audit" / "active_identity_audit.json").read_text(encoding="utf-8"))
    alignment = json.loads((OTC / "audit" / "runtime_research_alignment.json").read_text(encoding="utf-8"))
    document_qa = json.loads((OTC / "audit" / "document_visual_qa.json").read_text(encoding="utf-8"))
    manifest = json.loads((OTC / "raw" / "nedrug" / "manifest.json").read_text(encoding="utf-8"))

    verified = [row for row in products if row["record_status"] == "verified_from_source"]
    analysis_products = [row for row in products if row.get("analysis_status") == "included"]
    selected_bindings = [row for row in joins if row.get("selected_for_calculation") == "true"]
    released = [row for row in rules if row["status"] == "released"]
    drafts = [row for row in rules if row["status"] == "draft"]

    check("products", len(products) == 16 and len(verified) == 14, {"total": len(products), "verified": len(verified)})
    check(
        "analysis_set",
        len(analysis_products) == 13 and len(exclusions) == 1 and len(selected_bindings) == 47,
        {"products": len(analysis_products), "exclusions": len(exclusions), "selected_bindings": len(selected_bindings)},
    )
    check("candidate_master", len(ingredients) == 31 and len(joins) == 106, {"ingredients": len(ingredients), "variant_rows": len(joins)})
    check(
        "runtime_gate",
        len(runtime.get("products", [])) == 13 and runtime.get("rulesReleased") == 15 and runtime.get("releaseReady") is False,
        {"products": len(runtime.get("products", [])), "rules_released": runtime.get("rulesReleased"), "release_ready": runtime.get("releaseReady")},
    )
    check("runtime_research_alignment", alignment.get("valid") is True, alignment)
    check(
        "rules",
        len(rules) == 16
        and len(released) == 15
        and [row["rule_id"] for row in drafts] == ["OTC-RULE-015"]
        and all(row["source_id"] and row["source_locator"] for row in released),
        {"total": len(rules), "released": len(released), "drafts": [row["rule_id"] for row in drafts]},
    )
    check(
        "rule_evidence",
        bool(evidence)
        and len({row["rule_type"] for row in evidence}) == 16
        and bool(shortlist)
        and sum(row["recommendation"] == "recommended_primary" for row in shortlist) == 16,
        {"candidates": len(evidence), "rule_types": len({row["rule_type"] for row in evidence}), "shortlist": len(shortlist)},
    )
    check(
        "runtime_rule_bindings",
        len(bindings) == 13
        and all(row["binding_status"] == "human_expert_verified" and row["supports_release"] == "true" for row in bindings),
        {"rows": len(bindings), "statuses": sorted({row["binding_status"] for row in bindings})},
    )

    case_payloads = [OTC / "validation" / row["case_payload_ref"] for row in independent]
    payloads_unlabeled = all(
        (payload := json.loads(path.read_text(encoding="utf-8"))).get("referenceLabel") is None
        and payload.get("prediction") is None
        for path in case_payloads
    )
    check(
        "independent_evaluation_boundary",
        len(independent) == 13
        and all(path.is_file() for path in case_payloads)
        and payloads_unlabeled
        and evaluation.get("review_method") == "codex_prefilled_external_human_confirmation"
        and evaluation.get("independent_blinding") is False
        and evaluation.get("performance_claim_allowed") is False,
        {
            "cases": len(independent),
            "payloads_unlabeled": payloads_unlabeled,
            "review_method": evaluation.get("review_method"),
            "independent_blinding": evaluation.get("independent_blinding"),
            "performance_claim_allowed": evaluation.get("performance_claim_allowed"),
        },
    )
    normalization_metric = metrics["metrics"]["ingredient_normalization_accuracy"]
    check(
        "auxiliary_evaluation",
        product_search.get("status") == "evaluated_fixed_development_cases_not_external_user_study"
        and product_search.get("cases") == 26
        and product_search.get("successes") == 26
        and len(normalization_reference) == 31
        and all(row["human_reference_name"] for row in normalization_reference)
        and normalization_metric.get("status") == "evaluated_human_locked_reference"
        and normalization_metric.get("value") == 1.0,
        {"product_search": [product_search.get("successes"), product_search.get("cases")], "normalization": normalization_metric},
    )
    check("active_identity", identity.get("valid") is True and not identity.get("cross_student_findings"), identity)
    check("software_validation", software.get("status") == "passed", software.get("results"))
    check(
        "release_boundary",
        metrics.get("release_ready") is False
        and metrics["metrics"]["independent_scenarios"].get("performance_claim_allowed") is False,
        {"release_ready": metrics.get("release_ready"), "release_blockers": metrics.get("release_blockers")},
    )

    hash_errors: list[str] = []
    for record in manifest["records"]:
        for item in record["files"]:
            path = ROOT / item["path"]
            if sha256(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
                hash_errors.append(item["path"])
            if path.suffix.lower() == ".pdf" and not path.read_bytes().startswith(b"%PDF"):
                hash_errors.append(item["path"] + ":signature")
    check("raw_hashes_and_pdf_signatures", not hash_errors and len(manifest["records"]) == 16, {"records": len(manifest["records"]), "errors": hash_errors})

    fonts = ["Pretendard", "Pretendard Medium", "Pretendard SemiBold", "Pretendard ExtraBold"]
    document_errors: list[str] = []
    for item in document_qa.get("documents", []):
        docx = ROOT / item["docx"]
        pdf = ROOT / item["pdf"]
        with ZipFile(docx) as archive:
            xml = "".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.endswith(".xml")
            )
        if sha256(docx) != item["docx_sha256"] or sha256(pdf) != item["pdf_sha256"]:
            document_errors.append(item["type"] + ":hash")
        if not all(font in xml for font in fonts):
            document_errors.append(item["type"] + ":fonts")
        if item.get("pages_rendered") != item.get("pages_inspected") or any(item.get("accessibility_findings", {}).values()):
            document_errors.append(item["type"] + ":qa")
    check("document_visual_qa", document_qa.get("valid") is True and not document_errors and len(document_qa.get("documents", [])) == 2, {"errors": document_errors, "documents": len(document_qa.get("documents", []))})

    browser = [OTC / "etc" / "browser_qa" / name for name in ("otc-verified-product-desktop.png", "otc-verified-product-mobile.png", "otc-rule-gate-mobile.png")]
    check("browser_qa_artifacts", all(path.exists() and path.stat().st_size > 0 for path in browser), [path.name for path in browser])
    review_workflow = [OTC / "review" / "OTC_통합검토.html", OTC / "review" / "README.md", ROOT / "scripts" / "research" / "otc" / "import_review_result.py"]
    check("human_review_workflow", all(path.exists() and path.stat().st_size > 0 for path in review_workflow), [path.name for path in review_workflow])

    valid = all(item["status"] == "passed" for item in checks)
    report = {
        "schema_version": "2.0.0",
        "scope": "otc_current_working_and_canonical_package",
        "valid": valid,
        "release_ready": False,
        "checks": checks,
    }
    target = OTC / "audit" / "working_package_verification.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"valid": valid, "checks": len(checks), "failed": sum(item["status"] == "failed" for item in checks)}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
