"""v4.0 P2 에이전트 직접 선별 지원 도구.

판정 자체는 수행하지 않는다. 배치 생성, 판정 카드 렌더링, 판정 결과 검증·적재,
커버리지 검증, 매니페스트 생성만 담당한다. 언어모델을 로드하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIT = ROOT / "research_v3" / "otc" / "literature"
CORPUS = LIT / "evidence_map.csv"
SCREEN = LIT / "screening"
BATCH_DIR = SCREEN / "batches"
CARD_DIR = SCREEN / "cards"
DEC_DIR = SCREEN / "agent_decisions"
CHECKPOINTS = SCREEN / "checkpoints.jsonl"
MANIFEST = SCREEN / "screening_manifest.json"
PROMPT = LIT / "prompts" / "agent_screening_prompt.md"

BATCH_SIZE = 50
ABSTRACT_CHARS = 600
MESH_TERMS = 12

DECISIONS = {"retain", "deprioritize", "uncertain"}
CONFIDENCES = {"high", "medium", "low"}
REASON_CODES = {
    "exposure_outcome_direct",
    "exposure_outcome_class_level",
    "case_report_relevant",
    "exposure_only",
    "outcome_only",
    "off_topic",
    "animal_or_in_vitro_only",
    "mechanism_or_assay_only",
    "population_mismatch",
    "route_or_formulation_mismatch",
    "insufficient_detail",
    "title_only_probable_relevant",
    "title_only_probable_off_topic",
    "title_only_insufficient",
}
TITLE_ONLY_CODES = {
    "title_only_probable_relevant",
    "title_only_probable_off_topic",
    "title_only_insufficient",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_corpus() -> list[dict[str, str]]:
    with CORPUS.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def batch_id(index: int) -> str:
    return f"AGT-B{index:04d}"


def cmd_make_batches(_: argparse.Namespace) -> int:
    rows = load_corpus()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    for old in BATCH_DIR.glob("AGT-B*.json"):
        old.unlink()
    seen: set[str] = set()
    index = 0
    for start in range(0, len(rows), BATCH_SIZE):
        index += 1
        chunk = rows[start : start + BATCH_SIZE]
        payload_rows = []
        for row in chunk:
            rid = row["record_id"]
            if rid in seen:
                raise SystemExit(f"duplicate record_id in corpus: {rid}")
            seen.add(rid)
            payload_rows.append(
                {
                    "record_id": rid,
                    "pmid": row["pmid"],
                    "question_id": row["question_ids"],
                    "title": row["title"],
                    "abstract": row["abstract"],
                }
            )
        body = {
            "batch_id": batch_id(index),
            "input_sha256": sha256_text(
                "\n".join(f"{r['record_id']}\t{r['question_id']}" for r in payload_rows)
            ),
            "rows": payload_rows,
        }
        text = json.dumps(body, ensure_ascii=False, indent=1) + "\n"
        (BATCH_DIR / f"{body['batch_id']}.json").write_text(text, encoding="utf-8")
    if len(seen) != len(rows):
        raise SystemExit("row coverage mismatch during batch generation")
    print(f"batches={index} rows={len(seen)} batch_size={BATCH_SIZE}")
    return 0


def _card_for(row: dict[str, str], corpus_row: dict[str, str], ordinal: int) -> str:
    abstract = (corpus_row.get("abstract") or "").strip()
    basis = "title_abstract" if corpus_row.get("has_abstract") == "true" else "title_only"
    if len(abstract) > ABSTRACT_CHARS:
        abstract = abstract[:ABSTRACT_CHARS].rstrip() + " …"
    mesh = [m for m in (corpus_row.get("mesh_terms") or "").split(";") if m][:MESH_TERMS]
    ptypes = [p for p in (corpus_row.get("publication_types") or "").split(";") if p][:4]
    qid = corpus_row["question_ids"].replace("OTC-LIT-", "")
    lines = [
        f"[{ordinal}] {row['record_id']} | {qid} | {basis} | {corpus_row.get('publication_year', '')}",
        f"T: {corpus_row['title']}",
        f"A: {abstract if abstract else '(초록 없음)'}",
        f"M: PT={'/'.join(ptypes)} | MeSH={'; '.join(mesh)}",
    ]
    return "\n".join(lines)


def cmd_render(args: argparse.Namespace) -> int:
    corpus = {row["record_id"]: row for row in load_corpus()}
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    for bid in args.batch_ids:
        path = BATCH_DIR / f"{bid}.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        out_parts = [f"===== BATCH {bid} ({len(body['rows'])} rows) ====="]
        for i, row in enumerate(body["rows"], start=1):
            out_parts.append(_card_for(row, corpus[row["record_id"]], i))
        target = CARD_DIR / f"{bid}.txt"
        target.write_text("\n".join(out_parts) + "\n", encoding="utf-8")
        print(str(target.relative_to(ROOT)).replace("\\", "/"))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    corpus = {row["record_id"]: row for row in load_corpus()}
    existing: set[str] = set()
    if CHECKPOINTS.exists():
        with CHECKPOINTS.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    existing.add(json.loads(line)["record_id"])
    appended = 0
    out_lines: list[str] = []
    for bid in args.batch_ids:
        batch = json.loads((BATCH_DIR / f"{bid}.json").read_text(encoding="utf-8"))
        wanted = [r["record_id"] for r in batch["rows"]]
        dec_path = DEC_DIR / f"{bid}.jsonl"
        raw = [ln.strip() for ln in dec_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        decisions: dict[str, dict] = {}
        for ln in raw:
            obj = json.loads(ln)
            rid = obj["record_id"]
            if rid in decisions:
                raise SystemExit(f"{bid}: duplicate decision for {rid}")
            if obj["decision"] not in DECISIONS:
                raise SystemExit(f"{bid}/{rid}: bad decision {obj['decision']}")
            if obj["confidence"] not in CONFIDENCES:
                raise SystemExit(f"{bid}/{rid}: bad confidence {obj['confidence']}")
            codes = obj["reason_codes"]
            if not isinstance(codes, list) or not 1 <= len(codes) <= 3:
                raise SystemExit(f"{bid}/{rid}: reason_codes must hold 1-3 entries")
            bad = [c for c in codes if c not in REASON_CODES]
            if bad:
                raise SystemExit(f"{bid}/{rid}: unknown reason codes {bad}")
            decisions[rid] = obj
        missing = [r for r in wanted if r not in decisions]
        extra = [r for r in decisions if r not in set(wanted)]
        if missing or extra:
            raise SystemExit(f"{bid}: missing={missing[:5]}({len(missing)}) extra={extra[:5]}({len(extra)})")
        for rid in wanted:
            if rid in existing:
                raise SystemExit(f"{bid}: {rid} already present in checkpoints")
            obj = decisions[rid]
            crow = corpus[rid]
            basis = "title_abstract" if crow["has_abstract"] == "true" else "title_only"
            confidence = obj["confidence"]
            codes = obj["reason_codes"]
            if basis == "title_only":
                confidence = "low"
                if not any(c in TITLE_ONLY_CODES for c in codes):
                    raise SystemExit(f"{bid}/{rid}: title_only row needs a title_only_* reason code")
            else:
                if any(c in TITLE_ONLY_CODES for c in codes):
                    raise SystemExit(f"{bid}/{rid}: title_only_* reason code used on an abstract row")
            out_lines.append(
                json.dumps(
                    {
                        "record_id": rid,
                        "question_id": crow["question_ids"],
                        "decision": obj["decision"],
                        "reason_codes": codes,
                        "confidence": confidence,
                        "evidence_basis": basis,
                        "status": "screened",
                        "batch_id": bid,
                        "screener": "agent_direct",
                    },
                    ensure_ascii=False,
                )
            )
            existing.add(rid)
            appended += 1
    SCREEN.mkdir(parents=True, exist_ok=True)
    with CHECKPOINTS.open("a", encoding="utf-8", newline="\n") as fh:
        for line in out_lines:
            fh.write(line + "\n")
    print(f"appended={appended} total={len(existing)}")
    return 0


def _coverage() -> tuple[list[dict], list[str], list[str]]:
    corpus = load_corpus()
    wanted = [row["record_id"] for row in corpus]
    records: list[dict] = []
    seen = Counter()
    if CHECKPOINTS.exists():
        with CHECKPOINTS.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    records.append(obj)
                    seen[obj["record_id"]] += 1
    missing = [r for r in wanted if seen[r] == 0]
    duplicated = [r for r, c in seen.items() if c > 1]
    return records, missing, duplicated


def cmd_coverage(args: argparse.Namespace) -> int:
    records, missing, duplicated = _coverage()
    total = len(load_corpus())
    covered = total - len(missing)
    print(f"corpus={total} classified={covered} coverage={covered / total:.6f}")
    print(f"missing={len(missing)} duplicated={len(duplicated)}")
    if missing[:10]:
        print("missing_sample=" + ",".join(missing[:10]))
    if duplicated[:10]:
        print("duplicated_sample=" + ",".join(duplicated[:10]))
    print("decisions=" + json.dumps(Counter(r["decision"] for r in records), ensure_ascii=False))
    if args.strict and (missing or duplicated):
        return 1
    return 0


def cmd_manifest(_: argparse.Namespace) -> int:
    records, missing, duplicated = _coverage()
    corpus = load_corpus()
    total = len(corpus)
    if duplicated:
        raise SystemExit(f"duplicated record decisions: {len(duplicated)}")
    coverage = (total - len(missing)) / total
    batches = []
    for path in sorted(BATCH_DIR.glob("AGT-B*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        bid = body["batch_id"]
        dec_path = DEC_DIR / f"{bid}.jsonl"
        batches.append(
            {
                "batch_id": bid,
                "requested_rows": len(body["rows"]),
                "returned_rows": sum(1 for r in records if r.get("batch_id") == bid),
                "batch_sha256": sha256_file(path),
                "decisions_sha256": sha256_file(dec_path) if dec_path.exists() else None,
            }
        )
    reason_counter: Counter[str] = Counter()
    for r in records:
        reason_counter.update(r["reason_codes"])
    manifest = {
        "schema_version": "2.0.0",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "screener": "agent_direct",
        "execution_mode": "agent_direct_judgment",
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
        "human_decisions": 0,
        "prompt_path": str(PROMPT.relative_to(ROOT)).replace("\\", "/"),
        "prompt_sha256": sha256_file(PROMPT),
        "input_path": str(CORPUS.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": sha256_file(CORPUS),
        "corpus_declared_input_sha256": corpus[0]["input_sha256"],
        "checkpoint_path": str(CHECKPOINTS.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": sha256_file(CHECKPOINTS) if CHECKPOINTS.exists() else None,
        "batch_size": BATCH_SIZE,
        "card_render": {
            "abstract_chars": ABSTRACT_CHARS,
            "mesh_terms": MESH_TERMS,
            "note_ko": "판정 카드는 제목 전문, 초록 앞 600자, 게재유형, MeSH 상위 12개를 제시한다.",
        },
        "corpus_rows": total,
        "classified_rows": total - len(missing),
        "coverage": coverage,
        "missing_ids": missing,
        "duplicated_ids": duplicated,
        "decision_distribution": dict(sorted(Counter(r["decision"] for r in records).items())),
        "confidence_distribution": dict(sorted(Counter(r["confidence"] for r in records).items())),
        "evidence_basis_distribution": dict(
            sorted(Counter(r["evidence_basis"] for r in records).items())
        ),
        "decision_by_evidence_basis": {
            f"{b}|{d}": c
            for (b, d), c in sorted(
                Counter((r["evidence_basis"], r["decision"]) for r in records).items()
            )
        },
        "reason_code_distribution": dict(sorted(reason_counter.items())),
        "batch_count": len(batches),
        "batches": batches,
        "run_complete": coverage == 1.0 and not duplicated,
        "partial_reason": None if coverage == 1.0 else f"coverage={coverage:.6f}",
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"coverage={coverage} run_complete={manifest['run_complete']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("make-batches").set_defaults(func=cmd_make_batches)
    p_render = sub.add_parser("render")
    p_render.add_argument("batch_ids", nargs="+")
    p_render.set_defaults(func=cmd_render)
    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("batch_ids", nargs="+")
    p_ingest.set_defaults(func=cmd_ingest)
    p_cov = sub.add_parser("coverage")
    p_cov.add_argument("--strict", action="store_true")
    p_cov.set_defaults(func=cmd_coverage)
    sub.add_parser("manifest").set_defaults(func=cmd_manifest)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
