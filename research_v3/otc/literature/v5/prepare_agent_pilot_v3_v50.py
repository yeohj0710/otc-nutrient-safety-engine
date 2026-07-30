"""Prepare unseen Q01 batches for the post-refinement pre-freeze pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
CORPUS = V5 / "evidence_map.csv"
PROMPT = V5 / "prompts" / "agent_screening_prompt_v50.md"
DESTINATION = V5 / "etc" / "agent_pilot_v3"
QUESTION_ID = "OTC-LIT-Q01-ACETAMINOPHEN"
SLICES = (("PILOT3-Q01-A", 400, 30), ("PILOT3-Q01-B", 4000, 30), ("PILOT3-Q01-C", 8500, 30))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    os.replace(temporary, path)


def main() -> None:
    if DESTINATION.exists():
        raise RuntimeError(f"pilot directory already exists: {DESTINATION}")
    corpus_sha = sha256_bytes(CORPUS.read_bytes())
    prompt_sha = sha256_bytes(PROMPT.read_bytes())
    with CORPUS.open("r", encoding="utf-8", newline="") as handle:
        candidates = [
            row for row in csv.DictReader(handle)
            if QUESTION_ID in row["question_ids"].split(";")
        ]
    seen: set[str] = set()
    batches = []
    for batch_id, offset, count in SLICES:
        rows = candidates[offset : offset + count]
        if len(rows) != count:
            raise RuntimeError(f"short slice {batch_id}: {len(rows)}")
        records = []
        for row in rows:
            if row["record_id"] in seen:
                raise RuntimeError(f"overlap: {row['record_id']}")
            seen.add(row["record_id"])
            records.append({
                "record_id": row["record_id"],
                "pmid": row["pmid"],
                "question_id": QUESTION_ID,
                "title": row["title"],
                "abstract": row["abstract"],
                "has_abstract": row["has_abstract"].lower() == "true",
                "publication_types": [item for item in row["publication_types"].split(";") if item],
                "mesh_terms": [item for item in row["mesh_terms"].split(";") if item],
            })
        core = {
            "schema_version": "5.0.0-pilot3",
            "pilot_id": "pilot-003-post-refinement-pre-freeze",
            "batch_id": batch_id,
            "question_id": QUESTION_ID,
            "offset": offset,
            "row_count": count,
            "prompt_path": "research_v3/otc/literature/v5/prompts/agent_screening_prompt_v50.md",
            "prompt_sha256": prompt_sha,
            "corpus_sha256": corpus_sha,
            "formal_checkpoint_eligible": False,
            "rows": records,
        }
        core["input_sha256"] = sha256_bytes(canonical(core))
        path = DESTINATION / "inputs" / f"{batch_id}.json"
        write_json(path, core)
        batches.append({
            "batch_id": batch_id,
            "offset": offset,
            "rows": count,
            "input_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "input_sha256": core["input_sha256"],
        })
    write_json(DESTINATION / "manifest.json", {
        "schema_version": "5.0.0-pilot3",
        "pilot_id": "pilot-003-post-refinement-pre-freeze",
        "status": "prepared",
        "question_id": QUESTION_ID,
        "prompt_sha256": prompt_sha,
        "corpus_sha256": corpus_sha,
        "total_rows": len(seen),
        "overlapping_batches": False,
        "formal_checkpoint_eligible": False,
        "batches": batches,
    })
    print(json.dumps({"prompt_sha256": prompt_sha, "rows": len(seen), "batches": batches}, indent=2))


if __name__ == "__main__":
    main()
