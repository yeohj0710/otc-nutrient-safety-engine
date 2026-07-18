from __future__ import annotations

import argparse
import json
from pathlib import Path


CLAIMS_BY_DIRECTION = {
    "korean_otc_product_safety": {
        "official_designation_candidates": ("후보", "안전상비의약품"),
        "products_verified_from_source": ("검증", "제품"),
        "rules_total": ("규칙", "rule"),
        "rules_released": ("released", "규칙"),
        "development_scenarios": ("개발", "시나리오"),
        "independent_scenarios": ("독립", "시나리오"),
        "research_tests_passed": ("연구", "테스트"),
        "app_tests_passed": ("앱", "테스트"),
        "static_paths_generated": ("정적", "경로", "페이지"),
    },
    "high_dose_nutrient_ingredient_safety": {
        "search_occurrences": ("검색",),
        "unique_pmids": ("PMID",),
        "dedup_candidates": ("중복",),
        "normative_candidates": ("기준", "후보"),
        "rules_total": ("규칙",),
        "development_scenarios": ("개발", "시나리오"),
    },
}


def validate(manifest_path: Path, documents: list[Path]) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = manifest["metrics"]
    direction = manifest.get("research_direction", "high_dose_nutrient_ingredient_safety")
    claims = CLAIMS_BY_DIRECTION.get(direction)
    if claims is None:
        return {"schema_version": "2.0.0", "checks": [], "errors": [{"code": "UNSUPPORTED_RESEARCH_DIRECTION", "research_direction": direction}], "valid": False}
    errors: list[dict[str, object]] = []
    checks: list[dict[str, object]] = []
    for document in documents:
        text = document.read_text(encoding="utf-8-sig")
        if direction == "korean_otc_product_safety" and any(term in text for term in ("비타민 D 100", "비타민 B6 50", "고함량 영양성분 연구의 원문 방향")):
            errors.append({"code": "SUPERSEDED_NUTRIENT_CLAIM", "document": str(document)})
        for metric, label_terms in claims.items():
            if metric not in metrics:
                errors.append({"code": "METRIC_MISSING_FROM_MANIFEST", "document": str(document), "metric": metric})
                continue
            value = metrics[metric]["value"]
            accepted_forms = {str(value), f"{value:,}" if isinstance(value, int) else str(value)}
            number_present = any(form in text for form in accepted_forms)
            label_present = any(term.lower() in text.lower() for term in label_terms)
            present = number_present and label_present
            checks.append({"document": str(document), "metric": metric, "value": value, "number_present": number_present, "label_present": label_present, "present": present})
            if not present:
                errors.append({"code": "METRIC_NOT_FOUND", "document": str(document), "metric": metric, "value": value})
        for forbidden in ("여형준",):
            if forbidden in text:
                errors.append({"code": "FORBIDDEN_CLAIM_OR_IDENTITY", "document": str(document), "text": forbidden})
    return {"schema_version": "2.0.0", "research_direction": direction, "checks": checks, "errors": errors, "valid": not errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--document", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.manifest.resolve(), [path.resolve() for path in args.document])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
