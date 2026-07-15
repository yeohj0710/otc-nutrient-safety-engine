from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "audit" / "claim_consistency.json"

DOCUMENTS = [
    ROOT / "research_v3" / "thesis" / "otc_thesis_working.md",
    ROOT / "research_v3" / "protocol" / "otc_research_plan_working.md",
    ROOT / "research_v3" / "reports" / "FINAL_RESEARCH_REPORT.md",
    ROOT / "research_v3" / "README.md",
]

FORBIDDEN_STALE_CLAIMS = [
    "연구 테스트 97",
    "released 규칙 0개",
    "맹검 독립 기준정답이 0건",
    "사람 필드는 비어 있다",
    "신신파스아렉스 지정 포장 규격 확인",
    "canonical 최종본 아님",
]


def audit() -> dict:
    manifest = json.loads((OTC / "metrics_manifest.json").read_text(encoding="utf-8"))
    metrics = manifest["metrics"]
    required_counts = {
        "후보 제품 16개": metrics["products_total"]["value"],
        "분석 제품 13개": metrics["analysis_products"]["value"],
        "분석 성분 28개": metrics["analysis_ingredients"]["value"],
        "계산 연결 47개": metrics["runtime_product_ingredient_bindings"]["value"],
        "복용 조건 32개": metrics["verified_administration_constraints"]["value"],
        "released 규칙 15개": metrics["rules_released"]["value"],
    }
    errors: list[dict[str, str]] = []
    checks = []
    for document in DOCUMENTS:
        text = document.read_text(encoding="utf-8-sig")
        count_checks = {
            label: str(value) in text
            for label, value in required_counts.items()
        }
        boundary_ok = all(value in text for value in ("complete=false", "release_ready=false", "performance_claim_allowed=false"))
        shinshin_ok = "신신파스아렉스" in text and "제외" in text and "원문" in text
        stale = [claim for claim in FORBIDDEN_STALE_CLAIMS if claim in text]
        if not all(count_checks.values()):
            missing = [label for label, present in count_checks.items() if not present]
            errors.append({"code": "METRIC_NOT_PRESENT", "document": str(document), "detail": ", ".join(missing)})
        if not boundary_ok:
            errors.append({"code": "CLAIM_BOUNDARY_MISSING", "document": str(document), "detail": "complete/release/performance boundary"})
        if not shinshin_ok:
            errors.append({"code": "EXCLUSION_DECISION_MISSING", "document": str(document), "detail": "신신파스아렉스 원문 보존·분석 제외"})
        if stale:
            errors.append({"code": "STALE_CLAIM", "document": str(document), "detail": ", ".join(stale)})
        checks.append({
            "document": str(document),
            "counts": count_checks,
            "claim_boundary": boundary_ok,
            "shinshin_exclusion": shinshin_ok,
            "stale_claims": stale,
        })

    thesis = DOCUMENTS[0].read_text(encoding="utf-8-sig")
    order = [
        "## 국문초록", "## Abstract", "## 1. 서론", "## 2. 연구방법",
        "## 3. 연구결과", "## 4. 고찰", "## 5. 결론", "## 참고문헌", "## 부록 A.",
    ]
    positions = [thesis.find(heading) for heading in order]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append({"code": "THESIS_SECTION_ORDER", "document": str(DOCUMENTS[0]), "detail": str(positions)})

    evaluation = json.loads((OTC / "validation" / "independent_evaluation.json").read_text(encoding="utf-8"))
    if evaluation.get("independent_blinding") is not False or evaluation.get("performance_claim_allowed") is not False:
        errors.append({"code": "AUTHORITATIVE_EVALUATION_BOUNDARY", "document": str(OTC / "validation" / "independent_evaluation.json"), "detail": str(evaluation)})

    return {
        "schema_version": "3.0.0",
        "research_direction": "korean_otc_product_safety",
        "valid": not errors,
        "required_counts": required_counts,
        "checks": checks,
        "errors": errors,
    }


def write(result: dict) -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return OUTPUT


def main() -> int:
    result = audit()
    write(result)
    print(json.dumps({"valid": result["valid"], "errors": len(result["errors"])}, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
