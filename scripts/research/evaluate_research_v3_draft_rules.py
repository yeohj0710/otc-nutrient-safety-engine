from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def profile_key(payload: dict[str, object]) -> str | None:
    age = payload.get("age")
    sex = payload.get("sex")
    if not isinstance(age, (int, float)) or sex not in {"male", "female"}:
        return None
    return f"{sex}_{'19_29' if 19 <= age <= 29 else '30_plus' if age >= 30 else 'under_19'}"


def matches(rule: dict[str, str], payload: dict[str, object]) -> bool:
    if payload.get("ingredient") != rule["ingredient_id"]:
        return False
    conditions = json.loads(rule["conditions_json"])
    age = payload.get("age")
    if "age_min_years" in conditions and (not isinstance(age, (int, float)) or age < conditions["age_min_years"]):
        return False
    for key, threshold in conditions.items():
        if key.endswith("_gt"):
            value_key = key[:-3]
            value = payload.get(value_key)
            if not isinstance(value, (int, float)) or value <= threshold:
                return False
    if conditions.get("daily_total_mg_gt_profile_threshold"):
        key = profile_key(payload)
        thresholds = conditions["profile_thresholds_mg"]
        value = payload.get("daily_total_mg")
        if key not in thresholds or not isinstance(value, (int, float)) or value <= thresholds[key]:
            return False
    return True


def evaluate(rules: list[dict[str, str]], payload: dict[str, object]) -> list[str]:
    return [rule["rule_id"] for rule in rules if matches(rule, payload)]


def run(root: Path) -> dict[str, object]:
    rules = csv_rows(root / "rules" / "rules.csv")
    scenarios = csv_rows(root / "validation" / "development_scenarios.csv")
    results: list[dict[str, object]] = []
    for scenario in scenarios:
        payload = json.loads(scenario["input_json"])
        expected = json.loads(scenario["expected_hazards_json"])
        actual = evaluate(rules, payload)
        results.append({
            "scenario_id": scenario["scenario_id"],
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
        })
    return {
        "schema_version": "1.0.0",
        "scope": "development_scenarios_only",
        "rules_status": "draft",
        "scenario_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "results": results,
        "performance_claim_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
