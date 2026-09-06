"""Verify the agent-curated counseling candidates against saved abstracts and emit the runtime file.

No search and no model calls. Reads:
  research/counseling/curated-candidates.json   (hand-curated by the agent, source of truth)
  research/counseling/sources.json.gz            (abstracts packaged by build-counseling-sources.py)
  src/generated/recollect/rule-literature-pool.json (bibliographic fields, membership in the screening pool)
Writes:
  src/generated/otc-counseling-candidates.json

Every quote must appear literally in the saved abstract. A candidate that is not in the
screening pool, is retracted, or whose quote cannot be found stops the build.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "research/counseling/curated-candidates.json"
SOURCES = ROOT / "research/counseling/sources.json.gz"
POOL = ROOT / "src/generated/recollect/rule-literature-pool.json"
TARGET = ROOT / "src/generated/otc-counseling-candidates.json"

RETRACTED = re.compile(r"^(?:Retracted Publication|Retraction of Publication)$", re.IGNORECASE)
CONDITION = re.compile(r"^(?:[A-Za-z][A-Za-z0-9]*(?:>=|<=|=)[^\s]+|medications\.class=[a-z_]+)$")
RELATIONS = {"candidate", "candidate_background"}


def split_sentences(text: str) -> list[str]:
    """Same splitter as scripts/research/otc/build_rule_literature_pool.py so locators line up."""
    stripped = text.strip()
    if not stripped:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[])", stripped) if part.strip()]


def normalize(text: str) -> str:
    return " ".join(text.split())


def locate(quote: str, abstract: str) -> str:
    target = normalize(quote)
    for index, sentence in enumerate(split_sentences(abstract), start=1):
        if normalize(sentence) == target:
            return f"abstract:sentence:{index}"
    # Quote spans a splitter boundary (e.g. "P = .31)." followed by a lowercase word).
    for index, sentence in enumerate(split_sentences(abstract), start=1):
        if target in normalize(sentence) or normalize(sentence) in target:
            return f"abstract:sentence:{index}"
    return "abstract"


def main() -> int:
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    sources = json.loads(gzip.decompress(SOURCES.read_bytes()).decode("utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    papers = pool["papers"]
    rule_types = {rule["rule_type"] for rule in pool["rules"].values()}
    errors: list[str] = []
    entries = []
    seen: set[str] = set()

    for entry in curated["entries"]:
        pmid = str(entry["pmid"])
        record_id = f"PMID-{pmid}"
        if pmid in seen:
            errors.append(f"{record_id}: duplicate entry")
            continue
        seen.add(pmid)
        paper = papers.get(record_id)
        source = sources.get(record_id)
        if not paper:
            errors.append(f"{record_id}: not in the screening pool")
            continue
        if not source:
            errors.append(f"{record_id}: no saved abstract")
            continue
        if any(RETRACTED.match(part.strip()) for part in source["publicationTypes"].split("|")):
            errors.append(f"{record_id}: retracted publication")
            continue
        if entry["relation"] not in RELATIONS:
            errors.append(f"{record_id}: unknown relation {entry['relation']}")
        for rule_type in entry["ruleTypes"]:
            if rule_type not in rule_types:
                errors.append(f"{record_id}: unknown rule type {rule_type}")
        for condition in entry["appliesTo"]["profileConditions"]:
            if not CONDITION.match(condition):
                errors.append(f"{record_id}: bad profile condition {condition}")
        abstract = normalize(source["abstract"])
        quotes = []
        for quote in entry["quotes"]:
            if normalize(quote) not in abstract:
                errors.append(f"{record_id}: quote not found in abstract: {quote[:60]}")
                continue
            quotes.append({"quote": quote, "locator": locate(quote, source["abstract"])})
        if not quotes:
            errors.append(f"{record_id}: no verifiable quote")
            continue
        entries.append(
            {
                "pmid": pmid,
                "recordId": record_id,
                "title": paper["title"],
                "journal": paper["journal"],
                "year": paper["year"],
                "publicationTypes": source["publicationTypes"],
                "url": paper["url"],
                "ruleTypes": entry["ruleTypes"],
                "backgroundForRuleTypes": entry.get("backgroundForRuleTypes", []),
                "ingredientIds": entry["ingredientIds"],
                "relatedIngredients": entry.get("relatedIngredients", []),
                "relation": entry["relation"],
                "priority": entry.get("priority", 5),
                "quotes": quotes,
                "studyDesignKo": entry["studyDesignKo"],
                "populationKo": entry["populationKo"],
                "exposureKo": entry["exposureKo"],
                "outcomeKo": entry["outcomeKo"],
                "applicabilityKo": entry["applicabilityKo"],
                "appliesTo": entry["appliesTo"],
                "authorizationAlignment": entry.get("authorizationAlignment", "consistent"),
                "authorizationNoteKo": entry.get("authorizationNoteKo", ""),
                "abstractSha256": hashlib.sha256(source["abstract"].encode("utf-8")).hexdigest(),
            }
        )

    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    payload = {
        "schemaVersion": curated["schemaVersion"],
        "reviewStatus": curated["reviewStatus"],
        "reviewNoteKo": curated["reviewNoteKo"],
        "reviewedAt": curated["reviewedAt"],
        "humanExpertReviewed": False,
        "supportsRuleRelease": False,
        "changesAuthorizationDecision": False,
        "verification": "literal_quote_in_saved_abstract_and_agent_semantic_review",
        "sourcesSha256": hashlib.sha256(SOURCES.read_bytes()).hexdigest(),
        "curatedSha256": hashlib.sha256(CURATED.read_bytes()).hexdigest(),
        "entries": sorted(entries, key=lambda row: (row["priority"], row["pmid"])),
    }
    TARGET.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(entries), "ruleTypes": sorted({t for e in entries for t in e["ruleTypes"]})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
