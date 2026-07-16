from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
TARGET = ROOT / "src" / "generated" / "otc-supporting-literature.json"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
REVIEW_STATUS = "codex_curated_supporting_not_rule_release_evidence"
PROFILE_CONDITIONS = {
    "pregnant",
    "lactating",
    "liverDisease",
    "kidneyDisease",
    "giBleedingOrUlcer",
    "hypertensionOrCardiovascularDisease",
    "willDrive",
    "alcohol",
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build() -> list[dict]:
    released_rule_types = {
        row["rule_type"] for row in _rows(RULES) if row["status"] == "released"
    }
    papers: list[dict] = []
    seen_pmids: set[str] = set()
    for row in _rows(SOURCE):
        pmid = row["pmid"].strip()
        if not re.fullmatch(r"\d{7,8}", pmid):
            raise ValueError(f"invalid PMID: {pmid}")
        if pmid in seen_pmids:
            raise ValueError(f"duplicate PMID: {pmid}")
        seen_pmids.add(pmid)
        rule_types = [value for value in row["rule_types"].split(";") if value]
        unknown_rule_types = set(rule_types) - released_rule_types
        if unknown_rule_types:
            raise ValueError(f"unknown or unreleased rule types for PMID {pmid}: {sorted(unknown_rule_types)}")
        if row["review_status"] != REVIEW_STATUS:
            raise ValueError(f"invalid review status for PMID {pmid}")
        if row["supports_rule_release"].lower() != "false":
            raise ValueError(f"supporting literature cannot release a rule: {pmid}")
        expected_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if row["url"] != expected_url:
            raise ValueError(f"non-PubMed URL for PMID {pmid}")
        evidence_relation = row["evidence_relation"]
        if evidence_relation not in {
            "supports_caution",
            "contextualizes_uncertainty",
            "supports_mechanism",
        }:
            raise ValueError(f"invalid evidence relation for PMID {pmid}: {evidence_relation}")
        profile_conditions = [
            value for value in (row.get("profile_conditions") or "").split(";") if value
        ]
        unknown_profile_conditions = set(profile_conditions) - PROFILE_CONDITIONS
        if unknown_profile_conditions:
            raise ValueError(
                f"invalid profile conditions for PMID {pmid}: {sorted(unknown_profile_conditions)}"
            )
        required = ["doi", "title", "study_design", "key_finding_ko", "selection_reason_ko", "limitation_ko"]
        missing = [field for field in required if not row[field].strip()]
        if missing:
            raise ValueError(f"missing fields for PMID {pmid}: {missing}")
        papers.append(
            {
                "pmid": pmid,
                "doi": row["doi"],
                "title": row["title"],
                "publicationYear": int(row["publication_year"]),
                "studyDesign": row["study_design"],
                "evidenceRelation": evidence_relation,
                "ruleTypes": rule_types,
                "ingredientIds": [value for value in row["ingredient_ids"].split(";") if value],
                "profileConditions": profile_conditions,
                "keyFindingKo": row["key_finding_ko"],
                "selectionReasonKo": row["selection_reason_ko"],
                "limitationKo": row["limitation_ko"],
                "reviewStatus": row["review_status"],
                "supportsRuleRelease": False,
                "url": row["url"],
            }
        )
    return papers


def write(target: Path = TARGET) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    papers = build()
    write()
    print(f"supporting_literature={len(papers)} target={TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
