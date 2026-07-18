from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


NODE_RULE_INGREDIENTS = {
    "K1": {"vitamin_d", "calcium"},
    "K2": {"vitamin_b6"},
    "K3": {"iron"},
    "K4": {"magnesium"},
    "K5": {"zinc"},
}


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(root: Path) -> dict[str, object]:
    candidate_path = root / "extraction" / "ai_full_text_evidence_candidates.csv"
    rule_path = root / "rules" / "rules.csv"
    with candidate_path.open(encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with rule_path.open(encoding="utf-8-sig", newline="") as handle:
        rules = list(csv.DictReader(handle))

    invalid = [row["evidence_candidate_id"] for row in candidates if row["review_status"] != "ai_extracted_not_human_verified"]
    if invalid:
        raise ValueError(f"unexpected candidate status: {invalid[:5]}")
    non_draft_rules = [row["rule_id"] for row in rules if row["review_status"] != "draft"]
    if non_draft_rules:
        raise ValueError(f"non-draft rules cannot receive AI candidate links: {non_draft_rules}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[row["clinical_node_id"]].append(row)

    summaries: list[dict[str, object]] = []
    linkages: list[dict[str, object]] = []
    for node, rows in sorted(grouped.items()):
        signals = Counter(item for row in rows for item in split_values(row["signal_types"]))
        doses = Counter(item for row in rows for item in split_values(row["dose_mentions"]))
        populations = Counter(item.lower() for row in rows for item in split_values(row["population_mentions"]))
        durations = Counter(item.lower() for row in rows for item in split_values(row["duration_mentions"]))
        top = sorted(rows, key=lambda row: (-int(row["ai_relevance_score"]), row["evidence_candidate_id"]))[:10]
        summaries.append({
            "clinical_node_id": node,
            "ingredient": rows[0]["ingredient"],
            "candidate_passages": len(rows),
            "unique_pmids": len({row["pmid"] for row in rows}),
            "unique_pmcids": len({row["pmcid"] for row in rows}),
            "passages_with_dose": sum(bool(row["dose_mentions"]) for row in rows),
            "passages_with_population": sum(bool(row["population_mentions"]) for row in rows),
            "passages_with_duration": sum(bool(row["duration_mentions"]) for row in rows),
            "top_safety_signals": ";".join(f"{key}:{value}" for key, value in signals.most_common(10)),
            "top_dose_mentions": ";".join(f"{key}:{value}" for key, value in doses.most_common(10)),
            "top_population_mentions": ";".join(f"{key}:{value}" for key, value in populations.most_common(10)),
            "top_duration_mentions": ";".join(f"{key}:{value}" for key, value in durations.most_common(10)),
            "top_candidate_ids": ";".join(row["evidence_candidate_id"] for row in top),
            "synthesis_status": "ai_aggregate_not_human_verified",
            "human_verified_candidates": 0,
        })
        node_rules = [rule for rule in rules if rule["ingredient_id"] in NODE_RULE_INGREDIENTS.get(node, set())]
        for rule in node_rules:
            for rank, candidate in enumerate(top, 1):
                linkages.append({
                    "rule_id": rule["rule_id"],
                    "rule_review_status": rule["review_status"],
                    "clinical_node_id": node,
                    "rank": rank,
                    "evidence_candidate_id": candidate["evidence_candidate_id"],
                    "pmid": candidate["pmid"],
                    "pmcid": candidate["pmcid"],
                    "locator": candidate["locator"],
                    "source_sha256": candidate["source_sha256"],
                    "link_basis": "same_prespecified_clinical_node_and_ai_relevance_rank",
                    "link_status": "ai_candidate_link_not_expert_verified",
                    "supports_threshold_claim": "false",
                    "human_verification_required": "true",
                })

    output = root / "extraction"
    summary_path = output / "ai_full_text_node_synthesis.csv"
    linkage_path = output / "ai_draft_rule_evidence_links.csv"
    write_csv(summary_path, summaries, list(summaries[0]) if summaries else ["clinical_node_id"])
    write_csv(linkage_path, linkages, list(linkages[0]) if linkages else ["rule_id"])
    report = {
        "schema_version": "1.0.0",
        "method": "deterministic_aggregation_of_codex_ai_passage_candidates",
        "clinical_nodes": len(summaries),
        "candidate_passages": len(candidates),
        "draft_rules_linked": len({row["rule_id"] for row in linkages}),
        "candidate_rule_links": len(linkages),
        "released_rules_created": 0,
        "human_verified_candidates": 0,
        "expert_verified_links": 0,
        "claim_boundary": "Navigation candidates only; links do not support thresholds, causality, or clinical recommendations.",
    }
    (output / "ai_full_text_synthesis_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
