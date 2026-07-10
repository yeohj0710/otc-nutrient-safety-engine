#!/usr/bin/env python3
"""Consolidate PubMed exports, deduplicate, and score every record transparently."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NODES = ["K1", "K2", "K3", "K4", "K5"]
DESIGN_TERMS = (
    "randomized", "randomised", "clinical trial", "cohort", "case-control",
    "case report", "case series", "retrospective", "prospective", "systematic review",
    "meta-analysis", "cross-sectional", "pharmacovigilance",
)
EXPOSURE_TERMS = (
    "supplement", "oral", "dose", "dosage", "daily", "intake", "tablet", "capsule",
    "lozenge", "bolus", "administered", "treatment",
)
HUMAN_TERMS = (
    "patient", "adult", "participant", "subject", "women", "woman", "men", "man",
    "volunteer", "older", "elderly", "pregnan",
)
OUTCOME_TERMS = {
    "K1": ("hypercalcemia", "hypercalciuria", "kidney stone", "nephrolith", "urolith", "adverse", "toxicity"),
    "K2": ("neuropath", "neurotoxic", "paresthes", "paraesthes", "sensory", "gait"),
    "K3": ("nausea", "vomiting", "constipation", "diarr", "abdominal pain", "tolerab", "adverse", "iron overload"),
    "K4": ("diarr", "hypermagnes", "renal insufficiency", "kidney failure", "adverse", "toxic"),
    "K5": ("copper deficiency", "hypocuprem", "anemia", "anaemia", "neutropenia", "neuropath", "nausea", "vomiting", "abdominal pain", "diarr", "toxic"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_doi(value: str) -> str:
    return value.strip().casefold().removeprefix("https://doi.org/").removeprefix("doi:")


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def contains_any(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def screen_record(record: dict[str, str], nodes: list[str]) -> dict[str, Any]:
    text = f"{record.get('title', '')} {record.get('abstract_or_summary', '')}".casefold()
    design = contains_any(text, DESIGN_TERMS)
    exposure = contains_any(text, EXPOSURE_TERMS)
    human = contains_any(text, HUMAN_TERMS)
    outcomes = sorted({term for node in nodes for term in OUTCOME_TERMS[node] if term in text})
    animal = contains_any(text, ("mice", "mouse", "rats", "rat model", "animal study", "in vivo model"))
    in_vitro = contains_any(text, ("in vitro", "cell line", "cultured cells", "cell culture"))
    pediatric = contains_any(text, ("children", "child", "pediatric", "paediatric", "infant", "neonatal"))
    adult_signal = bool(human) and any(term in text for term in ("adult", "women", "men", "patient", "participant", "older", "elderly"))
    explicit_flags = []
    if animal and not human:
        explicit_flags.append("animal_only_signal")
    if in_vitro and not human:
        explicit_flags.append("in_vitro_only_signal")
    if pediatric and not adult_signal:
        explicit_flags.append("pediatric_only_signal")
    score = min(2, len(design)) * 2 + min(2, len(exposure)) + min(2, len(outcomes)) * 2 + int(bool(human))
    if explicit_flags:
        proposal = "explicit_exclude_candidate"
        rationale = ";".join(explicit_flags)
    elif score >= 6:
        proposal = "priority_include_candidate"
        rationale = "design+exposure+outcome signals"
    else:
        proposal = "retain_uncertain"
        rationale = "insufficient explicit information for computational exclusion"
    return {
        "score": score,
        "proposal": proposal,
        "rationale": rationale,
        "matched_design_terms": ";".join(design),
        "matched_exposure_terms": ";".join(exposure),
        "matched_human_terms": ";".join(human),
        "matched_outcome_terms": ";".join(outcomes),
        "explicit_exclusion_flags": ";".join(explicit_flags),
    }


def consolidate(node_rows: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, Any]]]:
    occurrences: list[dict[str, str]] = []
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in NODES:
        for row in node_rows[node]:
            pmid = row["pmid"].strip()
            doi = normalized_doi(row.get("doi", ""))
            title_key = normalized_title(row.get("title", ""))
            key = f"pmid:{pmid}" if pmid else (f"doi:{doi}" if doi else f"title:{title_key}")
            item = {**row, "node": node, "dedup_key_v2": key}
            occurrences.append(item)
            groups[key].append(item)

    records: list[dict[str, str]] = []
    dedup_rows: list[dict[str, str]] = []
    screening: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        representative = max(items, key=lambda row: (len(row.get("abstract_or_summary", "")), len(row.get("title", "")), row["node"]))
        rep_id = f"pubmed:{representative['pmid']}:{representative['node']}"
        nodes = sorted({row["node"] for row in items})
        for index, row in enumerate(sorted(items, key=lambda value: value["node"])):
            record_id = f"pubmed:{row['pmid']}:{row['node']}"
            duplicate = record_id != rep_id
            records.append(
                {
                    "record_id": record_id,
                    "search_run_id": row["search_run_id"],
                    "clinical_node_candidate": row["node"],
                    "source_database": "PubMed",
                    "database_record_id": row["pmid"],
                    "pmid": row["pmid"],
                    "doi": row.get("doi", ""),
                    "title": row.get("title", ""),
                    "abstract": row.get("abstract_or_summary", ""),
                    "year": row.get("year", ""),
                    "language": "",
                    "authors": "",
                    "journal": row.get("journal_or_source", ""),
                    "is_duplicate": str(duplicate).lower(),
                    "duplicate_of": rep_id if duplicate else "",
                    "removed_before_screening": "false",
                    "removal_reason": "cross_node_duplicate" if duplicate else "",
                    "raw_source_path": f"research_v2/search/raw/pubmed/{row['node']}",
                    "raw_source_sha256": "",
                    "normalization_version": "feasibility-v1",
                }
            )
            if duplicate:
                dedup_rows.append(
                    {
                        "candidate_pair_id": f"DUP-{len(dedup_rows)+1:05d}",
                        "record_id_a": rep_id,
                        "record_id_b": record_id,
                        "match_basis": key.split(":", 1)[0],
                        "similarity_score": "1.0",
                        "auto_proposal": "duplicate",
                        "human_decision": "not_evaluated_scope_reduction",
                        "representative_record_id": rep_id,
                        "reviewer_id": "codex_deterministic_dedup_v1",
                        "timestamp": "2026-07-10T00:00:00Z",
                    }
                )
        result = screen_record(representative, nodes)
        screening.append(
            {
                "record_id": rep_id,
                "pmid": representative["pmid"],
                "clinical_node_candidates": ";".join(nodes),
                "year": representative.get("year", ""),
                "title": representative.get("title", ""),
                "abstract": representative.get("abstract_or_summary", ""),
                **result,
                "review_mode": "deterministic_computational_screening",
                "final_human_decision": "not_evaluated_scope_reduction",
            }
        )
    return records, dedup_rows, screening


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_search_log(root: Path) -> list[dict[str, Any]]:
    rows = []
    for node in NODES:
        query = (root / "search" / "pubmed_queries" / f"{node}.txt").read_text(encoding="utf-8").strip()
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        candidates = list((root / "search" / "raw" / "pubmed" / node).rglob("raw_manifest.json"))
        manifest_path = next(
            (
                path
                for path in sorted(candidates, reverse=True)
                if json.loads(path.read_text(encoding="utf-8"))["query_sha256"] == query_hash
            ),
            None,
        )
        if manifest_path is None:
            raise FileNotFoundError(f"no raw manifest matches active query for {node}: {query_hash}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_hash = manifest.get("raw_files_sha256") or hashlib.sha256(
            json.dumps(manifest["raw_files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        rows.append(
            {
                "search_run_id": f"pubmed_{node}_{manifest['search_date']}_{manifest['query_sha256'][:8]}",
                "clinical_node_id": node,
                "database_name": "MEDLINE",
                "platform": "PubMed",
                "exact_query_file": f"research_v2/search/pubmed_queries/{node}.txt",
                "date_time_utc": f"{manifest['search_date']}T00:00:00Z",
                "coverage_start": "inception",
                "coverage_end": manifest["search_date"],
                "limits": "none; PubMed-only feasibility scope",
                "hit_count": manifest["hit_count"],
                "exported_count": manifest["exported_count"],
                "imported_count": manifest["imported_count"],
                "raw_file_path": manifest_path.parent.relative_to(root.parent).as_posix(),
                "raw_file_sha256": raw_hash,
                "operator": "codex_agent",
                "status": "complete",
                "notes": f"contact_source={manifest['contact_source']};contact_value_stored=false",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", default="research_v2")
    args = parser.parse_args()
    root = Path(args.research_root)
    node_rows = {node: read_csv(root / "search" / "normalized" / f"{node}_pubmed_records.csv") for node in NODES}
    records, dedup_rows, screening = consolidate(node_rows)
    record_fields = ["record_id", "search_run_id", "clinical_node_candidate", "source_database", "database_record_id", "pmid", "doi", "title", "abstract", "year", "language", "authors", "journal", "is_duplicate", "duplicate_of", "removed_before_screening", "removal_reason", "raw_source_path", "raw_source_sha256", "normalization_version"]
    dedup_fields = ["candidate_pair_id", "record_id_a", "record_id_b", "match_basis", "similarity_score", "auto_proposal", "human_decision", "representative_record_id", "reviewer_id", "timestamp"]
    screening_fields = ["record_id", "pmid", "clinical_node_candidates", "year", "title", "abstract", "score", "proposal", "rationale", "matched_design_terms", "matched_exposure_terms", "matched_human_terms", "matched_outcome_terms", "explicit_exclusion_flags", "review_mode", "final_human_decision"]
    search_fields = ["search_run_id", "clinical_node_id", "database_name", "platform", "exact_query_file", "date_time_utc", "coverage_start", "coverage_end", "limits", "hit_count", "exported_count", "imported_count", "raw_file_path", "raw_file_sha256", "operator", "status", "notes"]
    write_csv(root / "search" / "normalized" / "records.csv", records, record_fields)
    write_csv(root / "search" / "dedup_log.csv", dedup_rows, dedup_fields)
    write_csv(root / "screening" / "computational_screening.csv", screening, screening_fields)
    write_csv(root / "search" / "search_run_log.csv", build_search_log(root), search_fields)
    summary = {
        "identified_occurrences": len(records),
        "duplicates_removed": len(dedup_rows),
        "unique_records": len(screening),
        "proposal_counts": dict(sorted(Counter(row["proposal"] for row in screening).items())),
        "node_membership_counts": dict(sorted(Counter(node for row in screening for node in row["clinical_node_candidates"].split(";")).items())),
        "human_final_decisions": 0,
        "claim_boundary": "pubmed_single_reviewer_feasibility",
    }
    (root / "screening" / "computational_screening_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
