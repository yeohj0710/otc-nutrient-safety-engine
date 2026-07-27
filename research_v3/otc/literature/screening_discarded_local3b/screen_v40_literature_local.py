from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LITERATURE_ROOT = ROOT / "research_v3" / "otc" / "literature"
EVIDENCE_MAP = LITERATURE_ROOT / "evidence_map.csv"
PICOS_PATH = LITERATURE_ROOT / "picos" / "picos_definition.json"
PROMPT_PATH = LITERATURE_ROOT / "prompts" / "screening_prompt.md"
PROMPT_HASH_PATH = LITERATURE_ROOT / "prompts" / "screening_prompt.sha256"
CHECKPOINT_PATH = LITERATURE_ROOT / "screening" / "screening_checkpoints.jsonl"
RESULTS_PATH = LITERATURE_ROOT / "screening" / "screening_results.csv"
MANIFEST_PATH = LITERATURE_ROOT / "screening" / "screening_manifest.json"

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MODEL_REVISION = "aa8e72537993ba99e69dfaafa59ed015b17504d1"
MODEL_CACHE_PATH = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--Qwen--Qwen2.5-3B-Instruct"
    / "snapshots"
    / MODEL_REVISION
)
BATCH_SIZE = 100
MICRO_BATCH_SIZE = 16
MAX_INPUT_TOKENS = 1280
MAX_NEW_TOKENS = 20
SEED = 20260727

OUTPUT_PATTERN = re.compile(
    r"\b(retain|deprioritize|uncertain)\s*\|\s*(high|medium|low)\s*\|\s*(.*)",
    flags=re.IGNORECASE | re.DOTALL,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def load_checkpoint_batches() -> list[dict[str, Any]]:
    if not CHECKPOINT_PATH.exists():
        return []
    batches = []
    with CHECKPOINT_PATH.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            batch = json.loads(line)
            expected_hash = batch["batch_sha256"]
            hashable = {key: value for key, value in batch.items() if key != "batch_sha256"}
            actual_hash = canonical_sha256(hashable)
            if actual_hash != expected_hash:
                raise ValueError(f"체크포인트 해시 불일치: {line_number}")
            batches.append(batch)
    return batches


def flatten_decisions(batches: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [decision for batch in batches for decision in batch["decisions"]]


def validate_coverage(corpus_ids: Iterable[str], decisions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    corpus_ids = list(corpus_ids)
    decision_ids = [decision["record_id"] for decision in decisions]
    counts = Counter(decision_ids)
    duplicates = sorted(record_id for record_id, count in counts.items() if count != 1)
    corpus_set = set(corpus_ids)
    decision_set = set(decision_ids)
    unexpected = sorted(decision_set - corpus_set)
    missing = sorted(corpus_set - decision_set)
    if duplicates or unexpected:
        raise ValueError(f"체크포인트 ID 오류: duplicates={duplicates[:10]}, unexpected={unexpected[:10]}")
    return {
        "corpus_rows": len(corpus_ids),
        "classified_rows": len(decision_ids),
        "missing_ids": missing,
        "coverage": len(decision_ids) / len(corpus_ids) if corpus_ids else 1.0,
    }


def parse_model_output(raw_output: str, has_abstract: bool) -> dict[str, str]:
    normalized = " ".join(raw_output.strip().split())
    match = OUTPUT_PATTERN.search(normalized)
    if not match:
        return {
            "label": "uncertain",
            "confidence": "low",
            "rationale": "모델 출력 형식을 해석하지 못함",
            "parse_status": "fallback_invalid_output",
        }
    label, confidence, rationale = match.groups()
    rationale = rationale.strip().strip("`\"")[:240]
    return {
        "label": label.lower(),
        "confidence": confidence.lower() if has_abstract else "low",
        "rationale": rationale or "근거 설명 없음",
        "parse_status": "parsed",
    }


def question_contexts(picos: dict[str, Any]) -> dict[str, str]:
    contexts = {}
    for question in picos["questions"]:
        p = question["picos"]
        contexts[question["question_id"]] = (
            f"질문: {question['title_ko']}\n"
            f"대상: {p['population']}\n"
            f"노출: {p['intervention_or_exposure']}\n"
            f"비교: {p['comparator']}\n"
            f"결과: {p['outcomes']}\n"
            f"설계: {p['study_design']}"
        )
    return contexts


def build_record_prompt(row: dict[str, str], contexts: dict[str, str]) -> str:
    question_ids = [value for value in row["question_ids"].split(";") if value]
    context = "\n\n".join(contexts[question_id] for question_id in question_ids)
    abstract = row["abstract"] if row["has_abstract"] == "true" else "[초록 없음]"
    return (
        f"{PROMPT_PATH.read_text(encoding='utf-8')}\n\n"
        f"[PICOS 질문]\n{context}\n\n"
        f"[문헌]\n제목: {row['title']}\n초록: {abstract}\n"
    )


def load_model() -> tuple[Any, Any, str, str]:
    if not MODEL_CACHE_PATH.is_dir():
        raise FileNotFoundError(f"로컬 모델 스냅샷이 없습니다: {MODEL_CACHE_PATH}")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_CACHE_PATH, local_files_only=True)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_CACHE_PATH,
        local_files_only=True,
        dtype=torch.float16,
    ).to("cuda")
    model.generation_config.temperature = None
    model.generation_config.top_p = None
    model.generation_config.top_k = None
    model.eval()
    return model, tokenizer, torch.__version__, getattr(sys.modules.get("transformers"), "__version__", "")


def classify_prompts(model: Any, tokenizer: Any, prompts: list[str]) -> list[str]:
    import torch

    chat_prompts = [
        tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )
        for prompt in prompts
    ]
    inputs = tokenizer(
        chat_prompts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    ).to(model.device)
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    continuation = generated[:, inputs["input_ids"].shape[1] :]
    return tokenizer.batch_decode(continuation, skip_special_tokens=True)


def append_batch(batch: dict[str, Any]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    hashable = {key: value for key, value in batch.items() if key != "batch_sha256"}
    batch["batch_sha256"] = canonical_sha256(hashable)
    with CHECKPOINT_PATH.open("a", encoding="utf-8", newline="\n") as target:
        target.write(json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + "\n")
        target.flush()
        os.fsync(target.fileno())


def write_results_and_manifest(
    corpus: list[dict[str, str]],
    batches: list[dict[str, Any]],
    torch_version: str,
    transformers_version: str,
    micro_batch_size: int = MICRO_BATCH_SIZE,
) -> dict[str, Any]:
    decisions = flatten_decisions(batches)
    coverage = validate_coverage([row["record_id"] for row in corpus], decisions)
    by_id = {decision["record_id"]: decision for decision in decisions}
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record_id",
        "pmid",
        "question_ids",
        "label",
        "confidence",
        "evidence_basis",
        "rationale",
        "parse_status",
        "batch_id",
        "model_id",
        "model_revision",
        "prompt_sha256",
        "input_sha256",
    ]
    with RESULTS_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for row in corpus:
            if row["record_id"] not in by_id:
                continue
            decision = by_id[row["record_id"]]
            writer.writerow({key: decision[key] for key in fieldnames})
    distribution = Counter(decision["label"] for decision in decisions)
    evidence_basis_distribution = Counter(decision["evidence_basis"] for decision in decisions)
    manifest = {
        "schema_version": "1.0.0",
        "updated_at_utc": utc_now(),
        "execution_mode": "agent_local",
        "inference_service": "offline_local_transformers",
        "openai_api_used": False,
        "human_decisions": 0,
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION},
        "runtime": {
            "python": platform.python_version(),
            "torch": torch_version,
            "transformers": transformers_version,
            "device": "cuda",
            "seed": SEED,
            "batch_size": BATCH_SIZE,
            "completed_batches_micro_batch_size": 16,
            "completed_batches_max_input_tokens": 1536,
            "completed_batches_max_new_tokens": 32,
            "resume_micro_batch_size": micro_batch_size,
            "resume_max_input_tokens": MAX_INPUT_TOKENS,
            "resume_max_new_tokens": MAX_NEW_TOKENS,
            "deterministic_decoding": True,
        },
        "prompt_path": PROMPT_PATH.relative_to(ROOT).as_posix(),
        "prompt_sha256": sha256_file(PROMPT_PATH),
        "input_path": EVIDENCE_MAP.relative_to(ROOT).as_posix(),
        "input_sha256": sha256_file(EVIDENCE_MAP),
        "checkpoint_path": CHECKPOINT_PATH.relative_to(ROOT).as_posix(),
        "checkpoint_sha256": sha256_file(CHECKPOINT_PATH) if CHECKPOINT_PATH.exists() else None,
        "results_path": RESULTS_PATH.relative_to(ROOT).as_posix(),
        "results_sha256": sha256_file(RESULTS_PATH),
        "coverage": coverage["coverage"],
        "corpus_rows": coverage["corpus_rows"],
        "classified_rows": coverage["classified_rows"],
        "missing_ids": coverage["missing_ids"],
        "decision_distribution": dict(sorted(distribution.items())),
        "evidence_basis_distribution": dict(sorted(evidence_basis_distribution.items())),
        "batch_count": len(batches),
        "batches": [
            {
                "batch_id": batch["batch_id"],
                "requested_rows": batch["requested_rows"],
                "returned_rows": batch["returned_rows"],
                "micro_batch_size": batch.get("micro_batch_size"),
                "max_input_tokens": batch.get("max_input_tokens"),
                "max_new_tokens": batch.get("max_new_tokens"),
                "batch_sha256": batch["batch_sha256"],
            }
            for batch in batches
        ],
        "run_complete": coverage["coverage"] == 1.0 and not coverage["missing_ids"],
        "partial_reason": (
            None
            if coverage["coverage"] == 1.0 and not coverage["missing_ids"]
            else "AI 전량 선별 실행 중"
        ),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(max_batches: int | None = None, micro_batch_size: int = MICRO_BATCH_SIZE) -> dict[str, Any]:
    prompt_hash = sha256_file(PROMPT_PATH)
    if PROMPT_HASH_PATH.exists():
        expected = PROMPT_HASH_PATH.read_text(encoding="utf-8").split()[0]
        if expected != prompt_hash:
            raise ValueError("고정된 선별 프롬프트 해시가 바뀌었습니다.")
    else:
        PROMPT_HASH_PATH.write_text(f"{prompt_hash}  {PROMPT_PATH.name}\n", encoding="utf-8")

    corpus = read_csv(EVIDENCE_MAP)
    picos = json.loads(PICOS_PATH.read_text(encoding="utf-8"))
    contexts = question_contexts(picos)
    batches = load_checkpoint_batches()
    decisions = flatten_decisions(batches)
    coverage = validate_coverage([row["record_id"] for row in corpus], decisions)
    processed = {decision["record_id"] for decision in decisions}
    missing_rows = [row for row in corpus if row["record_id"] not in processed]
    if max_batches == 0:
        torch_version = batches[-1].get("torch_version", "") if batches else ""
        transformers_version = batches[-1].get("transformers_version", "") if batches else ""
        return write_results_and_manifest(
            corpus, batches, torch_version, transformers_version, micro_batch_size
        )
    if not missing_rows:
        torch_version = batches[-1].get("torch_version", "") if batches else ""
        transformers_version = batches[-1].get("transformers_version", "") if batches else ""
        return write_results_and_manifest(
            corpus, batches, torch_version, transformers_version, micro_batch_size
        )

    model, tokenizer, torch_version, transformers_version = load_model()
    batches_done = 0
    next_batch_number = len(batches) + 1
    for offset in range(0, len(missing_rows), BATCH_SIZE):
        if max_batches is not None and batches_done >= max_batches:
            break
        rows = missing_rows[offset : offset + BATCH_SIZE]
        batch_decisions = []
        for micro_offset in range(0, len(rows), micro_batch_size):
            micro_rows = rows[micro_offset : micro_offset + micro_batch_size]
            prompts = [build_record_prompt(row, contexts) for row in micro_rows]
            raw_outputs = classify_prompts(model, tokenizer, prompts)
            for row, raw_output in zip(micro_rows, raw_outputs, strict=True):
                parsed = parse_model_output(raw_output, row["has_abstract"] == "true")
                batch_decisions.append(
                    {
                        "record_id": row["record_id"],
                        "pmid": row["pmid"],
                        "question_ids": row["question_ids"],
                        "label": parsed["label"],
                        "confidence": parsed["confidence"],
                        "evidence_basis": "title_abstract" if row["has_abstract"] == "true" else "title_only",
                        "rationale": parsed["rationale"],
                        "parse_status": parsed["parse_status"],
                        "batch_id": f"P2-B{next_batch_number:04d}",
                        "model_id": MODEL_ID,
                        "model_revision": MODEL_REVISION,
                        "prompt_sha256": prompt_hash,
                        "input_sha256": sha256_bytes(
                            json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
                        ),
                        "raw_model_output": raw_output,
                    }
                )
        batch = {
            "batch_id": f"P2-B{next_batch_number:04d}",
            "created_at_utc": utc_now(),
            "requested_rows": len(rows),
            "returned_rows": len(batch_decisions),
            "micro_batch_size": micro_batch_size,
            "max_input_tokens": MAX_INPUT_TOKENS,
            "max_new_tokens": MAX_NEW_TOKENS,
            "torch_version": torch_version,
            "transformers_version": transformers_version,
            "decisions": batch_decisions,
        }
        append_batch(batch)
        batches.append(batch)
        batches_done += 1
        next_batch_number += 1
        if len(batches) % 5 == 0:
            validate_coverage(
                [row["record_id"] for row in corpus], flatten_decisions(batches)
            )

    manifest = write_results_and_manifest(
        corpus, batches, torch_version, transformers_version, micro_batch_size
    )
    print(
        json.dumps(
            {
                "batch_count": manifest["batch_count"],
                "classified_rows": manifest["classified_rows"],
                "coverage": manifest["coverage"],
                "run_complete": manifest["run_complete"],
            }
        )
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 Qwen 모델로 v4.0 PubMed 코퍼스를 선별합니다.")
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--micro-batch-size", type=int, default=MICRO_BATCH_SIZE)
    args = parser.parse_args()
    run(max_batches=args.max_batches, micro_batch_size=args.micro_batch_size)


if __name__ == "__main__":
    main()
