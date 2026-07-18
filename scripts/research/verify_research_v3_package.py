from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(name: str, command: list[str], cwd: Path) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    return {
        "name": name, "command": command, "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--delivery-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="include npm test/lint/typecheck/build")
    args = parser.parse_args()
    repo = args.repo.resolve()
    py = sys.executable
    commands = [
        ("research_tests", [py, "-m", "pytest", "tests/research", "-q"]),
        ("research_validator", [py, "scripts/research/validate_research_v3.py", "--root", "research_v3", "--output", "research_v3/audit/validation_report.json"]),
        ("source_validator", [py, "scripts/research/validate_research_v3_sources.py", "--root", "research_v3/sources", "--output", "research_v3/audit/source_validation_report.json"]),
        ("claim_validator", [py, "scripts/research/validate_research_v3_claims.py", "--manifest", "research_v3/metrics_manifest.json", "--document", "research_v3/reports/FINAL_RESEARCH_REPORT.md", "--document", "research_v3/thesis/thesis_draft_evidence_bound.md", "--output", "research_v3/audit/claim_consistency_report.json"]),
        ("expert_review_validator", [py, "scripts/research/validate_expert_rule_review.py", "--packet", "research_v3/rules/expert_rule_review_packet.csv", "--output", "research_v3/audit/expert_rule_review_validation.json"]),
        ("independent_evaluation", [py, "scripts/research/evaluate_research_v3_independent.py", "--scenarios", "research_v3/validation/independent_scenarios.csv", "--predictions", "research_v3/validation/independent_predictions.csv", "--output", "research_v3/validation/independent_results.json"]),
        ("codex_ai_review", [py, "scripts/research/build_codex_ai_reviews.py", "--root", "research_v3", "--query-dir", "research_v2/search/pubmed_queries"]),
        ("identity_audit", [py, "scripts/research/audit_research_v3_identity.py", "--protocol", str(args.protocol.resolve()), "--delivery-root", str(args.delivery_root.resolve()), "--output", "research_v3/audit/active_identity_audit_report.json"]),
        ("delivery_audit", [py, "scripts/research/audit_research_v3_delivery.py", "--root", str(args.delivery_root.resolve()), "--output", "research_v3/audit/delivery_structure_report.json"]),
    ]
    if args.full:
        npm = "npm.cmd" if os.name == "nt" else "npm"
        commands.extend([
            ("app_tests", [npm, "test", "--", "--run"]), ("lint", [npm, "run", "lint"]),
            ("typecheck", [npm, "run", "typecheck"]), ("production_build", [npm, "run", "build"]),
        ])
    checks = [run(name, command, repo) for name, command in commands]
    release_audit_checks = {"delivery_audit"}
    release_check_failures = [
        item["name"] for item in checks
        if item["exit_code"] != 0 and item["name"] in release_audit_checks
    ]
    technical_failures = [item["name"] for item in checks if item["exit_code"] != 0 and item["name"] not in release_audit_checks]
    manifest = json.loads((repo / "research_v3/metrics_manifest.json").read_text(encoding="utf-8"))
    metrics = manifest["metrics"]
    release_blockers = list(manifest.get("release_blockers", []))
    if manifest.get("release_ready") is not True:
        release_blockers.append("release_governance_pending")
    if metrics["rules_released"]["value"] == 0:
        release_blockers.append("released_rules_zero")
    if metrics["human_full_text_decisions"]["value"] == 0:
        release_blockers.append("human_full_text_decisions_zero")
    if metrics["independent_scenarios"]["value"] == 0:
        release_blockers.append("independent_scenarios_zero")
    if "delivery_audit" in release_check_failures:
        release_blockers.append("canonical_final_thesis_missing")
    release_blockers = list(dict.fromkeys(release_blockers))
    report = {
        "schema_version": "1.0.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": str(repo), "delivery_root": str(args.delivery_root.resolve()), "checks": checks,
        "technical_checks_passed": not technical_failures, "technical_failures": technical_failures,
        "release_audit_checks": sorted(release_audit_checks),
        "observed_release_check_failures": release_check_failures,
        "release_blockers": release_blockers,
        "release_ready": not technical_failures and not release_check_failures and not release_blockers,
        "interpretation": "Technical checks exclude explicitly classified release audits. Observed release-audit failures and human-review blockers still prevent release.",
    }
    output = args.output if args.output.is_absolute() else repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("technical_checks_passed", "technical_failures", "release_blockers", "release_ready")}, ensure_ascii=False))
    return 0 if not technical_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
