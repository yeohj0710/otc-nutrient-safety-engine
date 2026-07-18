from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DISCLAIMER = (
    "SIMULATION ONLY: no human review, expert approval, adjudication, or screening occurred. "
    "These files must not be merged into authoritative research data or used for release claims."
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def simulate_scenarios(source: Path, output: Path) -> list[dict[str, str]]:
    _, rows = read_csv(source)
    fields = [
        "scenario_id", "scenario_type", "input_json", "gold_hazards_json", "critical",
        "adjudicator_id", "adjudicated_at", "locked_before_test", "notes",
    ]
    simulated = []
    for row in rows:
        simulated.append({
            "scenario_id": row["scenario_id"].replace("DEV-", "SIM-", 1),
            "scenario_type": row["scenario_type"],
            "input_json": row["input_json"],
            "gold_hazards_json": row["expected_hazards_json"],
            "critical": row["critical"],
            "adjudicator_id": "hypothetical_not_a_person",
            "adjudicated_at": "",
            "locked_before_test": "false",
            "notes": DISCLAIMER,
        })
    write_csv(output, fields, simulated)
    return simulated


def simulate_expert_review(source: Path, output: Path) -> int:
    fields, rows = read_csv(source)
    for row in rows:
        for field in (
            "threshold_correct", "scope_correct", "conditions_correct", "exceptions_correct",
            "message_safe", "next_action_safe", "source_locator_verified",
        ):
            row[field] = "assumed_true_not_reviewed"
        row["overall_decision"] = "simulation_assume_approve"
        row["reviewer_id"] = "hypothetical_not_a_person"
        row["reviewer_role"] = "simulation"
        row["reviewed_at"] = ""
        row["evidence_quote"] = ""
        row["notes"] = DISCLAIMER
    write_csv(output, fields, rows)
    return len(rows)


def simulate_press(source: Path, output: Path) -> int:
    fields, rows = read_csv(source)
    for row in rows:
        row["reviewer_id"] = "hypothetical_not_a_person"
        row["rating"] = "assumed_acceptable_not_reviewed"
        row["comment"] = DISCLAIMER
        row["status"] = "simulation_only"
    write_csv(output, fields, rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    args = parser.parse_args()
    root = args.root
    out = root / "simulation" / "hypothetical_human_completion"
    scenarios = simulate_scenarios(
        root / "validation" / "development_scenarios.csv", out / "independent_scenarios_simulated.csv"
    )
    expert_count = simulate_expert_review(
        root / "rules" / "expert_rule_review_packet.csv", out / "expert_rule_review_simulated.csv"
    )
    press_count = simulate_press(
        root / "search" / "provisional_pubmed_20260710" / "peer_review.csv",
        out / "press_review_simulated.csv",
    )
    report = {
        "schema_version": "1.0.0",
        "status": "simulation_only",
        "disclaimer": DISCLAIMER,
        "source": "developer-authored scenarios and unreviewed packets",
        "simulated_scenario_count": len(scenarios),
        "simulated_expert_review_count": expert_count,
        "simulated_press_review_count": press_count,
        "human_actions_completed": 0,
        "released_rules": 0,
        "performance_claim_allowed": False,
        "release_ready": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "simulation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "README.md").write_text(
        "# 사람 검토 완료 가정 시뮬레이션\n\n"
        f"> {DISCLAIMER}\n\n"
        "사용자 요청에 따라 후속 흐름의 파일 형태만 검증한다. 실제 검토 결과, 논문 성능 결과, "
        "released 규칙, 배포 승인으로 사용하지 않는다. authoritative CSV와 metrics manifest는 변경하지 않았다.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
