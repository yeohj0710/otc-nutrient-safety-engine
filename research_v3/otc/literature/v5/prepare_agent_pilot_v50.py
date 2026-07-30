"""Create disjoint Q01 pilot batches for the Codex-agent screening prompt."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
CORPUS = V5 / "evidence_map.csv"
PROMPT = V5 / "prompts" / "agent_screening_prompt_v50.md"
PILOT = V5 / "etc" / "agent_pilot_v2"
QUESTION_ID = "OTC-LIT-Q01-ACETAMINOPHEN"
SLICES = (
    ("PILOT2-Q01-A", 3200, 40),
    ("PILOT2-Q01-B", 6000, 40),
    ("PILOT2-Q01-C", 9000, 40),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> None:
    if PILOT.exists():
        raise RuntimeError(f"pilot directory already exists: {PILOT}")
    with CORPUS.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if QUESTION_ID in row["question_ids"].split(";")
        ]
    if len(rows) != 9259:
        raise RuntimeError(f"unexpected Q01 units: {len(rows)}")

    prompt_sha256 = sha256_file(PROMPT)
    corpus_sha256 = sha256_file(CORPUS)
    batches = []
    seen: set[str] = set()
    for batch_id, offset, size in SLICES:
        selected = rows[offset : offset + size]
        if len(selected) != size:
            raise RuntimeError(f"short pilot slice: {batch_id}")
        records = []
        for row in selected:
            if row["record_id"] in seen:
                raise RuntimeError(f"overlapping pilot record: {row['record_id']}")
            seen.add(row["record_id"])
            records.append(
                {
                    "record_id": row["record_id"],
                    "pmid": row["pmid"],
                    "question_id": QUESTION_ID,
                    "title": row["title"],
                    "abstract": row["abstract"],
                    "has_abstract": row["has_abstract"],
                    "publication_types": row["publication_types"],
                    "mesh_terms": row["mesh_terms"],
                }
            )
        batch = {
            "schema_version": "1.0.0",
            "pilot_id": "pilot-002-pre-freeze",
            "batch_id": batch_id,
            "question_id": QUESTION_ID,
            "offset": offset,
            "row_count": size,
            "prompt_path": "research_v3/otc/literature/v5/prompts/agent_screening_prompt_v50.md",
            "prompt_sha256": prompt_sha256,
            "corpus_sha256": corpus_sha256,
            "input_sha256": canonical_sha256(records),
            "rows": records,
        }
        path = PILOT / "inputs" / f"{batch_id}.json"
        write_json(path, batch)
        batches.append(
            {
                "batch_id": batch_id,
                "offset": offset,
                "row_count": size,
                "input_path": path.relative_to(ROOT).as_posix(),
                "input_sha256": batch["input_sha256"],
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "pilot_id": "pilot-002-pre-freeze",
        "status": "prepared",
        "prepared_at_utc": datetime.now(UTC).isoformat(),
        "question_id": QUESTION_ID,
        "prompt_sha256": prompt_sha256,
        "corpus_sha256": corpus_sha256,
        "total_rows": len(seen),
        "overlapping_batches": False,
        "human_reference_inputs_used": False,
        "formal_checkpoint_eligible": False,
        "batches": batches,
    }
    write_json(PILOT / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
