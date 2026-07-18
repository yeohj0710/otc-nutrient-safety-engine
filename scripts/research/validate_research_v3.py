from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(root: Path) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    identity = json.loads((root / "project_identity.json").read_text(encoding="utf-8"))
    if identity["researcher"]["name"] != "권혁찬":
        errors.append({"code": "IDENTITY_NAME", "message": "연구자명이 권혁찬이 아님"})
    if identity["researcher"]["student_id"] != "2021194024":
        errors.append({"code": "IDENTITY_STUDENT_ID", "message": "학번 불일치"})
    if identity["lineage"] != "research_v3":
        errors.append({"code": "LINEAGE", "message": "research_v3 계보가 아님"})

    rule_rows = rows(root / "rules" / "rules.csv")
    for row in rule_rows:
        for field in ("conditions_json", "exceptions_json"):
            try:
                json.loads(row[field])
            except json.JSONDecodeError as exc:
                errors.append({
                    "code": "RULE_JSON_INVALID",
                    "message": f"{row['rule_id']} {field}: {exc}",
                })
    released = [row for row in rule_rows if row["review_status"] == "released"]
    for row in released:
        missing = [
            field for field in ("source_id", "locator", "evidence_quote", "reviewer_id", "reviewed_at")
            if not row[field].strip()
        ]
        if missing:
            errors.append({
                "code": "RELEASED_RULE_PROVENANCE",
                "message": f"{row['rule_id']}: {','.join(missing)} 누락",
            })

    full_text = rows(root / "screening" / "full_text.csv")
    for row in full_text:
        if row["decision"] in {"include", "exclude"} and not all(
            row[field].strip() for field in ("reviewer_id", "reviewed_at", "locator")
        ):
            errors.append({
                "code": "FULL_TEXT_REVIEW_PROVENANCE",
                "message": f"{row['record_id']}: 검토자·시각·locator 누락",
            })

    independent = rows(root / "validation" / "independent_scenarios.csv")
    development = rows(root / "validation" / "development_scenarios.csv")
    for row in development:
        for field in ("input_json", "expected_hazards_json"):
            try:
                json.loads(row[field])
            except json.JSONDecodeError as exc:
                errors.append({
                    "code": "DEVELOPMENT_SCENARIO_JSON_INVALID",
                    "message": f"{row['scenario_id']} {field}: {exc}",
                })
    for row in independent:
        if row["locked_before_test"].lower() != "true":
            errors.append({
                "code": "SCENARIO_NOT_LOCKED",
                "message": f"{row['scenario_id']}: 시험 전 잠금 증거 없음",
            })

    if not released:
        warnings.append({"code": "NO_RELEASED_RULES", "message": "released 규칙 0개"})
    if not full_text:
        warnings.append({"code": "NO_FULL_TEXT_REVIEW", "message": "전문 판정 0건"})
    if not independent:
        warnings.append({"code": "NO_INDEPENDENT_SCENARIOS", "message": "독립 평가 시나리오 0건"})
    warnings.append({
        "code": "RELEASE_GOVERNANCE_PENDING",
        "message": "canonical 제출본 승격과 공개 운영 배포 승인이 완료되지 않음",
    })

    return {
        "schema_version": "1.0.0",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "rules_total": len(rule_rows),
            "rules_released": len(released),
            "full_text_decisions": len(full_text),
            "independent_scenarios": len(independent),
            "development_scenarios": len(development),
        },
        "valid": not errors,
        "release_ready": not errors and not warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.root.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
