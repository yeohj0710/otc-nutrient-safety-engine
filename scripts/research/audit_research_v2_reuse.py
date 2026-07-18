from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ARTIFACTS = {
    "search_runs": "search/search_run_log.csv",
    "normalized_records": "search/normalized/records.csv",
    "dedup_log": "search/dedup_log.csv",
    "title_abstract_screening": "screening/title_abstract.csv",
    "full_text_screening": "screening/full_text.csv",
    "extraction": "extraction/extraction.csv",
    "source_quotes": "extraction/source_quotes.csv",
    "rules": "rules/rule_trace.csv",
    "scenarios": "validation/scenarios.csv",
    "expert_review": "validation/expert_review.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def classify(name: str, rows: list[dict[str, str]]) -> tuple[str, str]:
    if not rows:
        return "template_only", "헤더만 존재하거나 행이 없음"
    if name in {"search_runs", "normalized_records", "dedup_log"}:
        return "reusable_after_integrity_check", "검색 계보·정규화·중복 제거 구조 재사용 가능"
    if name == "source_quotes":
        complete = all(row.get("source_url") and row.get("locator") and row.get("quote") for row in rows)
        return (
            "abstract_only_reusable" if complete else "not_reusable",
            "PubMed 초록 locator만 검증; 전문 근거로 승격 금지" if complete else "source/locator/quote 누락",
        )
    if name == "rules":
        released = [row for row in rows if row.get("status") == "released"]
        return (
            "draft_only",
            f"총 {len(rows)}개 중 released {len(released)}개; 사람 원문 검토 전 승격 금지",
        )
    return "review_required", "행 단위 검토 필요"


def audit(root: Path) -> dict[str, object]:
    inventory: list[dict[str, object]] = []
    for name, relative in ARTIFACTS.items():
        path = root / relative
        if not path.exists():
            inventory.append({"artifact": name, "path": relative, "status": "missing"})
            continue
        fields, rows = read_csv(path)
        reuse_status, reason = classify(name, rows)
        inventory.append({
            "artifact": name,
            "path": relative,
            "sha256": sha256(path),
            "row_count": len(rows),
            "field_count": len(fields),
            "reuse_status": reuse_status,
            "reason": reason,
        })

    by_name = {item["artifact"]: item for item in inventory}
    rules = read_csv(root / ARTIFACTS["rules"])[1]
    released = sum(row.get("status") == "released" for row in rules)
    source_quotes = read_csv(root / ARTIFACTS["source_quotes"])[1]
    return {
        "schema_version": "1.0.0",
        "source_lineage": "research_v2",
        "target_lineage": "research_v3",
        "inventory": inventory,
        "summary": {
            "search_occurrences": by_name["normalized_records"].get("row_count"),
            "dedup_pairs": by_name["dedup_log"].get("row_count"),
            "source_quotes": len(source_quotes),
            "released_rules": released,
            "human_title_abstract_decisions": by_name["title_abstract_screening"].get("row_count"),
            "human_full_text_decisions": by_name["full_text_screening"].get("row_count"),
            "expert_reviews": by_name["expert_review"].get("row_count"),
            "evaluation_scenarios": by_name["scenarios"].get("row_count"),
        },
        "decision": "검색 코드와 계보 구조만 우선 재사용; 결과·규칙·성능 수치는 v3로 자동 승격하지 않음",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v2"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
