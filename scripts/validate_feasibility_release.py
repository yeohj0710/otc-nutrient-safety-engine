#!/usr/bin/env python3
"""Validate the PubMed feasibility release without weakening clinical release gates."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "research_v2"


def main() -> None:
    checks: dict[str, dict[str, object]] = {}
    boundary = json.loads((ROOT / "protocol" / "claim_boundary.json").read_text(encoding="utf-8"))
    checks["claim_boundary"] = {"pass": boundary.get("study_design") == "pubmed_single_reviewer_feasibility"}
    seeds = json.loads((ROOT / "search" / "seed_recall_summary.json").read_text(encoding="utf-8"))
    checks["seed_recall"] = {"pass": seeds == {"retrieved": 22, "total": 22, "recall": 1.0, "node_retrieved": {"K1": 5, "K2": 4, "K3": 4, "K4": 5, "K5": 4}, "gate": "pass"}, "value": f"{seeds['retrieved']}/{seeds['total']}"}
    with (ROOT / "extraction" / "seed_abstract_evidence.csv").open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    checks["abstract_provenance"] = {"pass": len(evidence) == 22 and all(row["pmid"] and row["abstract_locator_quote"] and row["full_text_status"] == "not_reviewed" for row in evidence), "rows": len(evidence)}
    with (ROOT / "rules" / "rule_trace.csv").open(encoding="utf-8-sig", newline="") as handle:
        rules = list(csv.DictReader(handle))
    checks["rules_not_released"] = {"pass": len(rules) == 5 and all(row["status"] == "draft_ai" for row in rules), "draft_ai": len(rules)}
    metrics = json.loads((ROOT / "thesis" / "metrics_manifest.json").read_text(encoding="utf-8"))["metrics"]
    unavailable = ["ai_screening_heldout_recall", "scenario_hazard_sensitivity", "critical_false_negatives", "expert_content_validity"]
    checks["unsupported_metrics_absent"] = {"pass": all(metrics[key]["status"] == "not_evaluated" and metrics[key]["value"] is None for key in unavailable)}
    pdf = next(ROOT.joinpath("thesis").glob("*.pdf"), None)
    page_chars = [len(page.extract_text() or "") for page in PdfReader(pdf).pages] if pdf else []
    checks["rendered_thesis"] = {"pass": bool(pdf) and len(page_chars) >= 5 and min(page_chars) >= 100, "pages": len(page_chars), "minimum_page_characters": min(page_chars) if page_chars else 0}
    test_python = REPO / ".venv-research" / "Scripts" / "python.exe"
    tests = subprocess.run([str(test_python if test_python.exists() else Path(sys.executable)), "-m", "pytest", "tests/research_v2", "-q"], cwd=REPO, capture_output=True, text=True)
    checks["research_tests"] = {"pass": tests.returncode == 0, "last_line": tests.stdout.strip().splitlines()[-1] if tests.stdout.strip() else tests.stderr.strip()}
    report = {"scope": "pubmed_single_reviewer_feasibility", "pass": all(item["pass"] for item in checks.values()), "checks": checks, "clinical_release_authorized": False}
    out = ROOT / "audit" / "feasibility_release_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
