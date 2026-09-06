"""Package existing screened abstracts and verify candidate quotes; no model calls."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "src/generated/recollect/rule-literature-pool.json"
CORPUS = ROOT.parent / "evidence-recollect/data/kwon/final/evidence_map.csv"
TARGET = ROOT / "research/counseling"
csv.field_size_limit(1 << 30)

pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
sources = {}
with CORPUS.open(encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle):
        pmid = row.get("pmid", "")
        record_id = f"PMID-{pmid}"
        if record_id not in pool["papers"] or not row.get("abstract"):
            continue
        sources[record_id] = {
            "abstract": row["abstract"],
            "publicationTypes": row.get("publication_types", ""),
        }

quote_count = 0
for rule in pool["rules"].values():
    for record_id, quote in rule["quotes"].items():
        source = sources.get(record_id)
        if source and quote.get("locator", "").startswith("abstract:"):
            normalized = lambda text: " ".join(text.split())
            if normalized(quote["quote"]) in normalized(source["abstract"]):
                source.setdefault("verifiedQuotes", []).append(quote["quote"])
                quote_count += 1

sources = {key: value for key, value in sources.items() if value.get("verifiedQuotes")}
for value in sources.values():
    value["verifiedQuotes"] = sorted(set(value["verifiedQuotes"]))
TARGET.resolve().relative_to(ROOT)
TARGET.mkdir(parents=True, exist_ok=True)
payload = gzip.compress(json.dumps(sources, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0)
(TARGET / "sources.json.gz").write_bytes(payload)
manifest = {
    "source": "existing_screening_candidates",
    "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
    "pool_sha256": hashlib.sha256(POOL_PATH.read_bytes()).hexdigest(),
    "payload_sha256": hashlib.sha256(payload).hexdigest(),
    "records": len(sources), "quote_matches": quote_count,
    "verification": "literal_quote_in_saved_abstract_only",
    "semantic_review": False, "supports_rule_release": False,
}
(TARGET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"records":len(sources),"quote_matches":quote_count,"bytes":len(payload)}))
