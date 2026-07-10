#!/usr/bin/env python3
"""Create the research_v2 scaffold without overwriting existing work."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

DIRECTORIES = [
    "audit",
    "config",
    "protocol",
    "search/raw",
    "search/normalized",
    "screening",
    "full_text/private",
    "extraction",
    "risk_of_bias",
    "synthesis",
    "ai_eval/raw_outputs",
    "rules",
    "validation",
    "thesis/figures",
    "legacy_untrusted",
]

TEMPLATE_MAP = {
    "00_normalized_records.csv": "search/normalized/records.csv",
    "02_search_run_log.csv": "search/search_run_log.csv",
    "03_dedup_log.csv": "search/dedup_log.csv",
    "04_title_abstract_screening.csv": "screening/title_abstract.csv",
    "05_full_text_screening.csv": "screening/full_text.csv",
    "06_extraction.csv": "extraction/extraction.csv",
    "07_risk_of_bias.csv": "risk_of_bias/assessments.csv",
    "08_grade_certainty.csv": "synthesis/grade.csv",
    "09_rule_trace.csv": "rules/rule_trace.csv",
    "10_ai_gold_standard.csv": "ai_eval/gold_standard.csv",
    "11_ai_predictions.csv": "ai_eval/predictions.csv",
    "12_scenario_validation.csv": "validation/scenarios.csv",
    "13_expert_review.csv": "validation/expert_review.csv",
    "14_thesis_claim_ledger.csv": "thesis/claim_ledger.csv",
    "15_full_text_retrieval_log.csv": "full_text/retrieval_log.csv",
    "16_source_quote.csv": "extraction/source_quotes.csv",
    "17_seed_recall.csv": "search/seed_recall.csv",
    "18_ai_extraction_metrics.csv": "ai_eval/extraction_field_metrics.csv",
    "19_research_decisions.csv": "audit/research_decisions.csv",
    "20_error_log.csv": "audit/error_log.csv",
}


def copy_if_missing(source: Path, destination: Path) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--package-root", default=str(Path(__file__).resolve().parents[1])
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    package_root = Path(args.package_root).resolve()
    research_root = repo_root / "research_v2"
    created: list[str] = []
    preserved: list[str] = []

    for directory in DIRECTORIES:
        path = research_root / directory
        path.mkdir(parents=True, exist_ok=True)

    for filename, destination in TEMPLATE_MAP.items():
        source = package_root / "templates" / filename
        target = research_root / destination
        if copy_if_missing(source, target):
            created.append(str(target.relative_to(repo_root)))
        else:
            preserved.append(str(target.relative_to(repo_root)))

    for filename in ("project_identity.json", "clinical_nodes.json", "quality_thresholds.json"):
        source = package_root / "config" / filename
        target = research_root / "config" / filename
        if copy_if_missing(source, target):
            created.append(str(target.relative_to(repo_root)))
        else:
            preserved.append(str(target.relative_to(repo_root)))

    active_identity = research_root / "project_identity.json"
    if not active_identity.exists():
        config = json.loads((package_root / "config" / "project_identity.json").read_text(encoding="utf-8"))
        config["initialized_at"] = datetime.now(timezone.utc).isoformat()
        config["mode"] = "kwon_primary_research"
        active_identity.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        created.append(str(active_identity.relative_to(repo_root)))
    else:
        preserved.append(str(active_identity.relative_to(repo_root)))

    for name, content in {
        "DECISIONS.md": "# Research decisions\n\n",
        "CHANGELOG_RESEARCH.md": "# Research changelog\n\n",
        "HUMAN_ACTION_REQUIRED.md": "# Human actions required\n\n",
        "legacy_untrusted/README.md": (
            "# Quarantined legacy assets\n\nFiles here are preserved for audit only and are not valid v2 evidence or metrics.\n"
        ),
    }.items():
        path = research_root / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(str(path.relative_to(repo_root)))
        else:
            preserved.append(str(path.relative_to(repo_root)))

    result = {
        "repo_root": str(repo_root),
        "research_root": str(research_root),
        "created": created,
        "preserved_existing": preserved,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
