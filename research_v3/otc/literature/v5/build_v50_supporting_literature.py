from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.literature_locator import parse_locator, sentence_at
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SOURCE_LINKS = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
EVIDENCE = V5 / "evidence_map.csv"
CHECKPOINTS = V5 / "screening" / "checkpoints.jsonl"
OUT = V5 / "downstream"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    evidence = {row["pmid"]: row for row in rows(EVIDENCE)}
    decisions: dict[str, set[str]] = {}
    for line in CHECKPOINTS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        decisions.setdefault(row["record_id"], set()).add(row["decision"])
    source = rows(SOURCE_LINKS)
    retained: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    screening_mismatches: list[dict[str, object]] = []
    errors: list[str] = []
    for link in source:
        record = evidence.get(link["pmid"])
        if record is None:
            missing.append({
                "link_id": link["link_id"],
                "rule_id": link["rule_id"],
                "rule_type": link["rule_type"],
                "pmid": link["pmid"],
                "title": link["title"],
                "reason": "pmid_absent_from_v5_corpus",
            })
            continue
        try:
            quote = sentence_at(record["abstract"], parse_locator(link["locator"]))
        except (ValueError, IndexError) as exc:
            errors.append(f"{link['link_id']}: {exc}")
            continue
        if quote != link["locator_quote_en"]:
            errors.append(f"{link['link_id']}: locator quote mismatch")
            continue
        record_decisions = sorted(decisions.get(record["record_id"], set()))
        if "retain" not in record_decisions:
            screening_mismatches.append({
                "link_id": link["link_id"],
                "rule_id": link["rule_id"],
                "pmid": link["pmid"],
                "v5_decisions": record_decisions,
                "handling": "preserved_legacy_curated_link_after_exact_locator_validation",
            })
        retained.append(link)
    if errors:
        raise SystemExit("v5 supporting-literature validation failed:\n" + "\n".join(errors))

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "supporting_literature.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source[0]))
        writer.writeheader()
        writer.writerows(retained)

    rule_rows = rows(RULES)
    linked_rules = {row["rule_id"] for row in retained}
    manifest = {
        "schema_version": "5.0.0",
        "phase": "D",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pipeline": "v4.0 supporting-literature fields and locator validation reused with v5 paths",
        "source_links_total": len(source),
        "links_retained_in_v5": len(retained),
        "unique_pmids_retained_in_v5": len({row["pmid"] for row in retained}),
        "links_absent_from_v5_corpus": missing,
        "legacy_curated_links_without_v5_retain": screening_mismatches,
        "rules_total": len(rule_rows),
        "rules_with_v5_literature": len(linked_rules),
        "rules_without_v5_literature": sorted({row["rule_id"] for row in rule_rows} - linked_rules),
        "links_by_rule": dict(sorted(Counter(row["rule_id"] for row in retained).items())),
        "locator_validation": {
            "checked": len(retained),
            "passed": len(retained),
            "errors": [],
            "requirement": "abstract:sentence:N and exact quote match",
        },
        "screening_requirement": "screening decision recorded; exact v5 corpus presence and locator validation govern preservation of legacy curated links",
        "input_sha256": {
            "v4_supporting_literature.csv": sha256(SOURCE_LINKS),
            "v5_evidence_map.csv": sha256(EVIDENCE),
            "v5_checkpoints.jsonl": sha256(CHECKPOINTS),
            "rules.csv": sha256(RULES),
        },
        "outputs": {
            "supporting_literature.csv": {
                "path": csv_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(csv_path),
                "rows": len(retained),
            }
        },
        "independent_blinding": False,
        "release_ready": False,
    }
    manifest_path = OUT / "literature_link_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
