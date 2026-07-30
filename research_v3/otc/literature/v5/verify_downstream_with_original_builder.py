"""Run the original OTC literature builder's checks against v5 without writing site data."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ORIGINAL = ROOT / "scripts" / "research" / "otc" / "build_supporting_literature.py"
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SOURCE = V5 / "downstream" / "supporting_literature.csv"
EVIDENCE_MAP = V5 / "evidence_map.csv"
DOWNSTREAM_MANIFEST = V5 / "downstream" / "literature_link_manifest.json"
DECISIONS = V5 / "screening" / "decisions.csv"
ADJUDICATION_MANIFEST = V5 / "screening" / "adjudication_manifest.json"
CANDIDATES = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
QUERY_DEFINITIONS = V5 / "query_definitions.json"
OUTPUT = V5 / "downstream" / "locator_verification.json"
EXPECTED_SITE_TARGET = ROOT / "src" / "generated" / "otc-supporting-literature.json"
REVIEW_STATUS = "agent_curated_from_v50_final_screening_layer"
EXPECTED_FINAL_ROWS = 43_207
EXPECTED_ADJUDICATED_ROWS = 5_000
EXPECTED_CANDIDATE_ROWS = 20


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require_current_generation(links: list[dict[str, str]]) -> tuple[dict, dict]:
    downstream = load_json(DOWNSTREAM_MANIFEST)
    adjudication = load_json(ADJUDICATION_MANIFEST)
    downstream_output = downstream.get("outputs", {}).get("supporting_literature", {})
    downstream_inputs = downstream.get("inputs", {})
    downstream_results = downstream.get("results", {})
    decision_input = downstream_inputs.get("screening_decisions", {})
    adjudication_input = downstream_inputs.get("adjudication_manifest", {})
    evidence_input = downstream_inputs.get("evidence_map", {})
    candidate_input = downstream_inputs.get("v4_candidate_links", {})
    rules_input = downstream_inputs.get("rules", {})
    query_input = downstream_inputs.get("query_definitions", {})
    validation_policy = downstream.get("validation_policy", {})
    compiled = adjudication.get("layers", {}).get("compiled_decisions", {})
    counts = adjudication.get("counts", {})

    checks = (
        downstream_output.get("path") == SOURCE.relative_to(ROOT).as_posix(),
        downstream_output.get("sha256") == sha256(SOURCE),
        downstream_output.get("row_count") == len(links),
        downstream_results.get("emitted_link_count") == len(links),
        len(links) > 0,
        len(downstream_results.get("links", [])) == len(links),
        downstream_results.get("emitted_link_count", 0)
        + downstream_results.get("rejected_candidate_count", 0)
        == EXPECTED_CANDIDATE_ROWS,
        decision_input.get("path") == DECISIONS.relative_to(ROOT).as_posix(),
        decision_input.get("sha256") == sha256(DECISIONS),
        decision_input.get("distinct_decision_count") == EXPECTED_FINAL_ROWS,
        adjudication_input.get("path") == ADJUDICATION_MANIFEST.relative_to(ROOT).as_posix(),
        adjudication_input.get("sha256") == sha256(ADJUDICATION_MANIFEST),
        adjudication_input.get("run_complete") is True,
        adjudication_input.get("adjudicated_rows") == EXPECTED_ADJUDICATED_ROWS,
        adjudication_input.get("compiled_decision_rows") == EXPECTED_FINAL_ROWS,
        evidence_input.get("path") == EVIDENCE_MAP.relative_to(ROOT).as_posix(),
        evidence_input.get("sha256") == sha256(EVIDENCE_MAP),
        candidate_input.get("path") == CANDIDATES.relative_to(ROOT).as_posix(),
        candidate_input.get("sha256") == sha256(CANDIDATES),
        candidate_input.get("candidate_count") == EXPECTED_CANDIDATE_ROWS,
        rules_input.get("path") == RULES.relative_to(ROOT).as_posix(),
        rules_input.get("sha256") == sha256(RULES),
        rules_input.get("rule_count") == 16,
        rules_input.get("read_only") is True,
        query_input.get("path") == QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
        query_input.get("sha256") == sha256(QUERY_DEFINITIONS),
        query_input.get("mapping_field") == "questions[].rule_types",
        query_input.get("question_count") == 5,
        query_input.get("read_only") is True,
        validation_policy.get("candidate_resolution_identifiers")
        == ["record_id", "pmid_including_all_pmids", "normalized_doi", "exact_title"],
        validation_policy.get("rule_question_mapping_source")
        == QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
        validation_policy.get("candidate_resolution_requirement")
        == "every_supplied_identifier_resolves_uniquely_to_the_same_v5_record",
        adjudication.get("run_complete") is True,
        counts.get("adjudicated_rows") == EXPECTED_ADJUDICATED_ROWS,
        counts.get("compiled_decision_rows") == EXPECTED_FINAL_ROWS,
        compiled.get("path") == DECISIONS.relative_to(ROOT).as_posix(),
        compiled.get("sha256") == sha256(DECISIONS),
        compiled.get("row_count") == EXPECTED_FINAL_ROWS,
        compiled.get("adjudication_labels_applied") is True,
        adjudication.get("hashes", {}).get("evidence_map_sha256") == sha256(EVIDENCE_MAP),
        adjudication.get("adjudication_input_blinded_to_classifier_labels") is True,
        adjudication.get("agent_identity_recorded") is False,
        adjudication.get("specific_agent_attribution_supported") is False,
        adjudication.get("execution_receipts_recorded") is False,
        adjudication.get("independent_blinding_ai") is False,
        adjudication.get("independent_blinding") is False,
        adjudication.get("release_ready") is False,
    )
    if not all(checks):
        raise ValueError(
            "downstream CSV, downstream manifest, final decisions, and adjudication manifest "
            "do not form one current complete generation"
        )
    return downstream, adjudication


def main() -> int:
    site_target = EXPECTED_SITE_TARGET
    site_before = sha256(site_target) if site_target.exists() else None
    spec = importlib.util.spec_from_file_location("original_otc_literature_builder", ORIGINAL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ORIGINAL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if Path(module.TARGET).resolve() != site_target.resolve():
        raise RuntimeError(
            f"original builder target changed: expected {site_target}, found {module.TARGET}"
        )
    if Path(module.RULES).resolve() != RULES.resolve():
        raise RuntimeError(
            f"original builder rules source changed: expected {RULES}, found {module.RULES}"
        )
    module.SOURCE = SOURCE
    module.EVIDENCE_MAP = EVIDENCE_MAP
    module.REVIEW_STATUS = REVIEW_STATUS
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        links = list(csv.DictReader(handle))
    if not links:
        raise ValueError("zero downstream links is not a successful locator verification")
    downstream_manifest, adjudication_manifest = require_current_generation(links)
    emitted_rule_ids = {row["rule_id"] for row in links}
    canonical_rules = Path(module.RULES)
    with canonical_rules.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("canonical rules CSV has no header")
        rule_fields = list(reader.fieldnames)
        canonical_rule_rows = list(reader)
        emitted_rules = [row for row in canonical_rule_rows if row["rule_id"] in emitted_rule_ids]
    if {row["rule_id"] for row in emitted_rules} != emitted_rule_ids:
        raise ValueError("an emitted link references a missing canonical rule")
    with tempfile.TemporaryDirectory(prefix="v50-original-builder-check-") as temporary_dir:
        scoped_rules = Path(temporary_dir) / "rules.csv"
        with scoped_rules.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rule_fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(emitted_rules)
        module.RULES = scoped_rules
        papers = module.build()
    site_after = sha256(site_target) if site_target.exists() else None
    if site_before != site_after:
        raise RuntimeError("read-only check changed the site artifact")

    distinct_pmids = {row["pmid"] for row in links}
    if len(papers) != len(distinct_pmids):
        raise RuntimeError(
            f"original builder returned {len(papers)} papers for {len(distinct_pmids)} PMIDs"
        )
    payload = {
        "schema_version": "1.1.0",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "method": "original_build_supporting_literature_build_function_read_only",
        "check_scope": {
            "rule_scope": "emitted_link_rule_ids_only",
            "emitted_rule_ids": sorted(emitted_rule_ids),
            "reason": (
                "The v5 no-invention policy permits unresolved rules; the original builder's global "
                "all-rule guard is scoped to emitted rules while every emitted link retains the original checks."
            ),
        },
        "original_script": {
            "path": ORIGINAL.relative_to(ROOT).as_posix(),
            "sha256": sha256(ORIGINAL),
            "function": "build",
        },
        "inputs": {
            "supporting_literature": {
                "path": SOURCE.relative_to(ROOT).as_posix(),
                "sha256": sha256(SOURCE),
                "link_rows": len(links),
            },
            "evidence_map": {
                "path": EVIDENCE_MAP.relative_to(ROOT).as_posix(),
                "sha256": sha256(EVIDENCE_MAP),
            },
            "canonical_rules": {
                "path": canonical_rules.relative_to(ROOT).as_posix(),
                "sha256": sha256(canonical_rules),
                "canonical_rule_count": len(canonical_rule_rows),
                "emitted_rule_count": len(emitted_rules),
            },
            "downstream_manifest": {
                "path": DOWNSTREAM_MANIFEST.relative_to(ROOT).as_posix(),
                "sha256": sha256(DOWNSTREAM_MANIFEST),
            },
            "final_decisions": {
                "path": DECISIONS.relative_to(ROOT).as_posix(),
                "sha256": sha256(DECISIONS),
                "rows": adjudication_manifest["counts"]["compiled_decision_rows"],
            },
            "adjudication_manifest": {
                "path": ADJUDICATION_MANIFEST.relative_to(ROOT).as_posix(),
                "sha256": sha256(ADJUDICATION_MANIFEST),
                "adjudicated_rows": adjudication_manifest["counts"]["adjudicated_rows"],
            },
            "v4_candidate_links": {
                "path": CANDIDATES.relative_to(ROOT).as_posix(),
                "sha256": sha256(CANDIDATES),
                "candidate_rows": downstream_manifest["inputs"]["v4_candidate_links"]["candidate_count"],
            },
            "query_definitions": {
                "path": QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
                "sha256": sha256(QUERY_DEFINITIONS),
                "mapping_field": "questions[].rule_types",
                "question_count": downstream_manifest["inputs"]["query_definitions"][
                    "question_count"
                ],
            },
            "site_output": {
                "path": site_target.relative_to(ROOT).as_posix(),
                "sha256_before_original_builder_import": site_before,
                "sha256_after_read_only_check": site_after,
            },
        },
        "checks": {
            "locator_quote_exact_match_for_every_link": True,
            "literature_authority_boundary": True,
            "rule_and_relation_contract": True,
            "distinct_papers": len(papers),
            "site_output_unchanged": True,
            "site_output_hash_captured_before_original_builder_import": True,
            "nonzero_link_set": True,
            "rules_and_query_source_hashes_match_downstream_manifest": True,
        },
        "independent_blinding": False,
        "release_ready": False,
    }
    rendered = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = OUTPUT.with_name(f".{OUTPUT.name}.tmp")
    temporary.write_bytes(rendered)
    os.replace(temporary, OUTPUT)
    print(
        json.dumps(
            {
                "path": OUTPUT.relative_to(ROOT).as_posix(),
                "status": "pass",
                "link_rows": len(links),
                "distinct_papers": len(papers),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
