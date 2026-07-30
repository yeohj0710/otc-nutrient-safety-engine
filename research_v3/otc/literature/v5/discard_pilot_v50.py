"""Archive the failed v5 screening pilot without deleting its audit trail."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
SCREENING = V5 / "screening"
PILOT = SCREENING / "discarded_pilots" / "pilot-001"
HISTORY = SCREENING / "pilot_discard_history.jsonl"
SOURCE = V5 / "screen_v50.py"
SMOKE = V5 / "etc" / "screening_smoke_test.json"
EXPECTED_PROMPT_SHA256 = "796d75bd8744296737f32d5821c6635bbbdbb42d4abe0f5d9bbe3a3492a7da54"
EXPECTED_QUESTION = "OTC-LIT-Q01-ACETAMINOPHEN"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> None:
    if PILOT.exists():
        raise RuntimeError(f"pilot archive already exists: {PILOT}")
    lock_path = SCREENING / "prompt_lock.json"
    checkpoint_path = SCREENING / "checkpoints.jsonl"
    batch_path = SCREENING / "batches.jsonl"
    for path in (lock_path, checkpoint_path, batch_path):
        if not path.is_file():
            raise RuntimeError(f"required pilot artifact missing: {path}")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise RuntimeError("pilot prompt hash is not the audited first prompt")

    checkpoints = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not checkpoints or {row.get("question_id") for row in checkpoints} != {
        EXPECTED_QUESTION
    }:
        raise RuntimeError("pilot checkpoints are empty or contain a non-Q01 question")
    keys = [(row.get("record_id"), row.get("question_id")) for row in checkpoints]
    if len(keys) != len(set(keys)):
        raise RuntimeError("pilot checkpoints contain duplicate screening units")

    source_sha256 = sha256_file(SOURCE)
    artifact_names = [
        ".screen_v50.lock",
        "agent_screening_prompt_v50.frozen.md",
        "batches.jsonl",
        "checkpoints.jsonl",
        "prompt_lock.json",
    ]
    original_files = {
        name: {
            "bytes": (SCREENING / name).stat().st_size,
            "sha256": sha256_file(SCREENING / name),
        }
        for name in artifact_names
        if (SCREENING / name).is_file()
    }
    batches = [
        json.loads(line)
        for line in batch_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    started_times = [row.get("started_at_utc") for row in batches if row.get("started_at_utc")]
    finished_times = [
        row.get("completed_at_utc") for row in batches if row.get("completed_at_utc")
    ]

    audit = {
        "audit_scope": {
            "question_id": EXPECTED_QUESTION,
            "snapshot_rows": 1200,
            "snapshot_batches": 6,
            "sample_rows": 150,
            "sampling": {
                "retain_evenly_spaced": 80,
                "uncertain": {"abstract": 15, "title_only": 15},
                "deprioritize_reason_stratified": 40,
            },
            "human_reference_inputs_used": False,
        },
        "errors": {
            "label_errors": {"retain": 18, "uncertain": 23, "deprioritize": 6, "total": 47},
            "reason_only_errors": {"retain": 10, "uncertain": 0, "deprioritize": 11, "total": 21},
            "total_findings": 68,
            "note": "The sample was stratified; 47/150 is not a population error-rate estimate.",
        },
        "systematic_failure_modes": [
            "attribution of another drug, surgery, or efficacy result to acetaminophen",
            "IV-only formulation retained despite the OTC route rule",
            "title and MeSH co-mention treated as sufficient attribution",
            "retain_kind=maybe instability after attributable harm was accepted",
            "exact acetaminophen exposure mislabeled as class-level evidence",
            "reviews incorrectly tagged as case reports",
            "APAP automatic-positive-airway-pressure acronym collision",
            "reason-code instability across exposure, outcome, route, and off-topic",
        ],
        "known_label_error_pmids": {
            "retain_to_uncertain": [
                "20461991", "21189276", "21189278", "21696021", "22568925", "22664763"
            ],
            "retain_to_deprioritize": [
                "20676066", "20969503", "21116816", "21344260", "21353105",
                "21586623", "21915939", "21986980", "22179455", "22271694",
                "22354127", "22638604"
            ],
            "uncertain_to_retain": [
                "19779704", "20193831", "20197596", "20332167", "20456332",
                "20805751", "20935107", "21135993", "21477658", "22149359",
                "22352734", "22730906", "20227233"
            ],
            "uncertain_to_deprioritize": [
                "20071472", "21811632", "22186009", "20860264", "21210596",
                "21385733", "22021566", "22458031", "22546155", "22729522"
            ],
            "deprioritize_to_retain": ["20492543", "20179054"],
            "deprioritize_to_uncertain": ["20447712", "21294782", "21793979", "22266143"],
        },
        "conclusion": "discard_all_pilot_decisions_and_restart_Q01_from_row_zero",
    }

    PILOT.mkdir(parents=True)
    shutil.copy2(SOURCE, PILOT / "screen_v50.pilot-001.py")
    if SMOKE.is_file():
        shutil.move(str(SMOKE), str(PILOT / SMOKE.name))
    for name in artifact_names:
        source = SCREENING / name
        if source.is_file():
            shutil.move(str(source), str(PILOT / name))

    archived_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(PILOT.iterdir())
        if path.is_file()
    }
    if any(
        archived_files[name] != metadata for name, metadata in original_files.items()
    ):
        raise RuntimeError("archived pilot file hash differs from its original hash")

    manifest = {
        "schema_version": "1.0.0",
        "pilot_id": "pilot-001",
        "status": "discarded",
        "discarded_at_utc": datetime.now(UTC).isoformat(),
        "question_id": EXPECTED_QUESTION,
        "processed_screening_units": len(checkpoints),
        "unique_record_ids": len({row[0] for row in keys}),
        "decision_distribution": dict(Counter(row.get("decision") for row in checkpoints)),
        "evidence_basis_distribution": dict(Counter(row.get("evidence_basis") for row in checkpoints)),
        "prompt_sha256": EXPECTED_PROMPT_SHA256,
        "screening_code_sha256": source_sha256,
        "checkpoint_sha256": original_files["checkpoints.jsonl"]["sha256"],
        "batch_log_sha256": original_files["batches.jsonl"]["sha256"],
        "started_at_utc": min(started_times) if started_times else None,
        "last_completed_batch_at_utc": max(finished_times) if finished_times else None,
        "discard_reason": (
            "systematic attribution, route, title-only, retain-kind, and reason-code failures"
        ),
        "formal_use_allowed": False,
        "restart_requirement": "restart Q01 from the first screening unit under a new frozen prompt hash",
        "audit_report": "audit_report.json",
        "archived_files": archived_files,
    }
    write_json(PILOT / "audit_report.json", audit)
    manifest["archived_files"]["audit_report.json"] = {
        "bytes": (PILOT / "audit_report.json").stat().st_size,
        "sha256": sha256_file(PILOT / "audit_report.json"),
    }
    write_json(PILOT / "discard_manifest.json", manifest)
    history_row = {
        key: manifest[key]
        for key in (
            "pilot_id", "status", "discarded_at_utc", "question_id",
            "processed_screening_units", "prompt_sha256", "screening_code_sha256",
            "checkpoint_sha256", "discard_reason", "formal_use_allowed",
            "restart_requirement",
        )
    }
    with HISTORY.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(history_row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
