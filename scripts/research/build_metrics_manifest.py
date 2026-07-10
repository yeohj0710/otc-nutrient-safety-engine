#!/usr/bin/env python3
"""Build thesis metrics from frozen, validated machine-readable artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOURCES = {
    "prisma": "screening/prisma_counts.json",
    "screening": "ai_eval/screening_metrics.json",
    "extraction": "ai_eval/extraction_metrics.json",
    "scenario": "validation/scenario_metrics.json",
    "content_validity": "validation/content_validity.json",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ci(metric: dict[str, Any], key: str) -> tuple[Any, Any]:
    value = metric.get(key)
    return (value[0], value[1]) if isinstance(value, list) and len(value) == 2 else (None, None)


def build(root: Path) -> dict[str, Any]:
    freeze_path = root / "audit" / "evidence_freeze.json"
    if not freeze_path.exists():
        raise ValueError("evidence_freeze.json is required before metrics generation")
    freeze = load(freeze_path)
    if freeze.get("status") != "frozen" or not freeze.get("pass"):
        raise ValueError("evidence freeze is not valid")
    loaded: dict[str, dict[str, Any]] = {}
    for name, relative in SOURCES.items():
        path = root / relative
        if not path.exists():
            raise ValueError(f"missing metric source: {relative}")
        loaded[name] = load(path)
        if loaded[name].get("pass") is False:
            raise ValueError(f"metric source failed validation: {relative}")

    screening_ci = ci(loaded["screening"], "sensitivity_ci95")
    scenario_ci = ci(loaded["scenario"], "hazard_sensitivity_ci95")
    specs = {
        "records_identified": (loaded["prisma"].get("records_identified"), loaded["prisma"].get("records_identified"), None, None, SOURCES["prisma"], "generate_prisma_counts.py"),
        "studies_included": (loaded["prisma"].get("studies_included"), loaded["prisma"].get("reports_included"), None, None, SOURCES["prisma"], "generate_prisma_counts.py"),
        "ai_screening_recall": (loaded["screening"].get("sensitivity"), loaded["screening"].get("gold_positive_count"), *screening_ci, SOURCES["screening"], "compute_ai_metrics.py"),
        "ai_extraction_required_accuracy": (loaded["extraction"].get("required_field_accuracy"), loaded["extraction"].get("required_field_count"), None, None, SOURCES["extraction"], "compute_extraction_metrics.py"),
        "scenario_hazard_sensitivity": (loaded["scenario"].get("hazard_sensitivity"), loaded["scenario"].get("n_scenarios"), *scenario_ci, SOURCES["scenario"], "validation_metrics.py"),
        "scenario_critical_false_negative": (loaded["scenario"].get("critical_false_negative_count"), loaded["scenario"].get("n_scenarios"), None, None, SOURCES["scenario"], "validation_metrics.py"),
        "scenario_provenance_completeness": (loaded["scenario"].get("provenance_completeness"), loaded["scenario"].get("n_scenarios"), None, None, SOURCES["scenario"], "validation_metrics.py"),
        "expert_s_cvi_ave": (loaded["content_validity"].get("s_cvi_ave"), loaded["content_validity"].get("n_experts"), None, None, SOURCES["content_validity"], "validation_metrics.py"),
    }
    metrics = {}
    for metric_id, (value, denominator, lower, upper, source, generator) in specs.items():
        if value is None or denominator is None:
            raise ValueError(f"metric value or denominator missing: {metric_id}")
        metrics[metric_id] = {
            "value": value,
            "denominator": denominator,
            "ci_lower": lower,
            "ci_upper": upper,
            "source_artifact": source,
            "generator": generator,
            "notes": "generated after evidence freeze",
        }
    return {
        "dataset_version": freeze["dataset_version"],
        "generated_at": freeze["frozen_at"],
        "source_commit": freeze["source_commit"],
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_root", nargs="?", default="research_v2")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    root = Path(args.research_root)
    result = build(root)
    out = Path(args.out) if args.out else root / "thesis" / "metrics_manifest.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
