from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


DECISION_FIELDS = ["human_decision", "reason_code", "reviewer_id", "reviewed_at", "notes"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(screening_source: Path, shortlist_source: Path, output_dir: Path) -> dict[str, object]:
    computational = read_csv(screening_source)
    queue_rows: list[dict[str, str]] = []
    rank_order = {"priority_include_candidate": 0, "retain_uncertain": 1, "explicit_exclude_candidate": 2}
    for source in computational:
        row = {
            "record_id": source["record_id"],
            "pmid": source["pmid"],
            "clinical_node_candidates": source["clinical_node_candidates"],
            "year": source["year"],
            "title": source["title"],
            "abstract": source["abstract"],
            "computational_score": source["score"],
            "computational_proposal": source["proposal"],
            "computational_rationale": source["rationale"],
            "explicit_exclusion_flags": source["explicit_exclusion_flags"],
            **{field: "" for field in DECISION_FIELDS},
        }
        queue_rows.append(row)
    queue_rows.sort(key=lambda row: (
        rank_order.get(row["computational_proposal"], 9),
        -int(row["computational_score"] or 0),
        row["record_id"],
    ))
    queue_fields = list(queue_rows[0]) if queue_rows else ["record_id", *DECISION_FIELDS]
    queue_path = output_dir / "title_abstract_full_queue.csv"
    write_csv(queue_path, queue_fields, queue_rows)

    shortlist = read_csv(shortlist_source)
    packet_rows: list[dict[str, str]] = []
    for source in shortlist:
        packet_rows.append({
            **source,
            "human_title_abstract_decision": "",
            "human_title_abstract_reason": "",
            "full_text_retrieval_status": "",
            "full_text_path": "",
            "human_full_text_decision": "",
            "human_full_text_reason": "",
            "full_text_locator": "",
            "reviewer_id": "",
            "reviewed_at": "",
            "review_notes": "",
        })
    packet_fields = list(packet_rows[0]) if packet_rows else ["evidence_candidate_id"]
    packet_path = output_dir / "priority_118_review_packet.csv"
    write_csv(packet_path, packet_fields, packet_rows)

    manifest = {
        "schema_version": "1.0.0",
        "full_queue": {
            "path": str(queue_path),
            "rows": len(queue_rows),
            "sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
            "human_decisions_prefilled": sum(bool(row["human_decision"]) for row in queue_rows),
        },
        "priority_packet": {
            "path": str(packet_path),
            "rows": len(packet_rows),
            "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "human_decisions_prefilled": sum(bool(row["human_title_abstract_decision"] or row["human_full_text_decision"]) for row in packet_rows),
        },
        "warning": "computational_proposal is ordering metadata, not a human inclusion decision",
    }
    manifest_path = output_dir / "review_packet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screening-source", type=Path, required=True)
    parser.add_argument("--shortlist-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.screening_source.resolve(), args.shortlist_source.resolve(), args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
