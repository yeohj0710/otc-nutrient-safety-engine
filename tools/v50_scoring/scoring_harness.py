#!/usr/bin/env python3
"""v5.0 채점 카드 배포, 판정 검증, 실행 시작 기록, 라벨 잠금."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARM = ROOT / "research_v3" / "otc" / "validation" / "screening_ai_reference_v50"
CARDS_PATH = ARM / "blinded_cards.json"
MANIFEST_PATH = ARM / "manifest.json"
ROUNDS_DIR = ARM / "rounds"
EXECUTION_RECEIPT = ARM / "scoring_execution_receipt.json"
LOCKED_PATH = ARM / "scored_labels_locked.json"
LOCK_RECEIPT = ARM / "lock_receipt.json"
FROZEN_PROMPT = (
    ROOT
    / "research_v3"
    / "otc"
    / "literature"
    / "v5"
    / "prompts"
    / "frozen_semantic_adjudication_prompt.md"
)

MAX_PER_ROUND = 30
CHAR_BUDGET = 60_000
JUDGMENT_FIELDS = {
    "record_id",
    "question_id",
    "decision",
    "reason_codes",
    "confidence",
    "evidence_basis",
}
DECISIONS = {"retain", "deprioritize", "uncertain"}
REASON_CODES = {
    "population",
    "exposure",
    "outcome",
    "human_signal",
    "design_signal",
    "animal_term_present",
    "insufficient_abstract",
    "off_topic",
}
CONFIDENCE = {"high", "medium", "low"}
EVIDENCE_BASIS = {"abstract", "title_only"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def configure_output_utf8(stream: Any = sys.stdout) -> None:
    """Windows 콘솔 기본 CP949에서도 카드 원문을 잘리지 않게 출력한다."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def load_cards() -> list[dict[str, str]]:
    return json.loads(CARDS_PATH.read_text(encoding="utf-8"))


def load_round_files() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    judgments: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for path in sorted(ROUNDS_DIR.glob("round_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("judgments") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise RuntimeError(f"{path.name}: judgments 배열이 없다")
        judgments.extend(rows)
        inventory.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
                "rows": len(rows),
                "mtime_utc": dt.datetime.fromtimestamp(
                    path.stat().st_mtime, tz=dt.timezone.utc
                ).isoformat(),
            }
        )
    return judgments, inventory


def validate_judgments(
    cards: list[dict[str, str]],
    judgments: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> list[str]:
    problems: list[str] = []
    card_by_key = {f"{card['question_id']}|{card['record_id']}": card for card in cards}
    if len(card_by_key) != len(cards):
        problems.append("카드 키가 중복된다")

    seen: set[str] = set()
    for index, judgment in enumerate(judgments):
        if set(judgment) != JUDGMENT_FIELDS:
            problems.append(
                f"judgment[{index}] 여섯 필드 계약 불일치: {sorted(judgment)}"
            )
            continue
        key = f"{judgment['question_id']}|{judgment['record_id']}"
        if key not in card_by_key:
            problems.append(f"judgment[{index}] 카드에 없는 키: {key}")
            continue
        if key in seen:
            problems.append(f"중복 판정: {key}")
        seen.add(key)

        decision = judgment["decision"]
        if decision not in DECISIONS:
            problems.append(f"{key}: decision 부적합 {decision!r}")
        reason_codes = judgment["reason_codes"]
        if (
            not isinstance(reason_codes, list)
            or not reason_codes
            or len(reason_codes) != len(set(reason_codes))
            or not set(reason_codes) <= REASON_CODES
        ):
            problems.append(f"{key}: reason_codes 부적합 {reason_codes!r}")
        confidence = judgment["confidence"]
        if confidence not in CONFIDENCE:
            problems.append(f"{key}: confidence 부적합 {confidence!r}")
        evidence_basis = judgment["evidence_basis"]
        expected_basis = "abstract" if card_by_key[key]["abstract"] else "title_only"
        if evidence_basis not in EVIDENCE_BASIS or evidence_basis != expected_basis:
            problems.append(
                f"{key}: evidence_basis={evidence_basis!r}, expected={expected_basis!r}"
            )
        if expected_basis == "title_only":
            if confidence != "low":
                problems.append(f"{key}: title_only은 confidence=low여야 한다")
            if (
                isinstance(reason_codes, list)
                and "insufficient_abstract" not in reason_codes
            ):
                problems.append(f"{key}: title_only은 insufficient_abstract가 필요하다")

    if require_complete:
        missing = set(card_by_key) - seen
        if missing:
            problems.append(f"미채점 {len(missing)}건")
    return problems


def plan_rounds(cards: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    planned: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    chars = 0
    for card in cards:
        size = sum(
            len(card[field])
            for field in ("title", "abstract", "publication_types", "mesh_terms")
        )
        if current and (len(current) >= MAX_PER_ROUND or chars + size > CHAR_BUDGET):
            planned.append(current)
            current = []
            chars = 0
        current.append(card)
        chars += size
    if current:
        planned.append(current)
    return planned


def cmd_start(_: argparse.Namespace) -> None:
    if EXECUTION_RECEIPT.exists():
        payload = json.loads(EXECUTION_RECEIPT.read_text(encoding="utf-8"))
        print(
            f"existing_start_receipt={EXECUTION_RECEIPT.relative_to(ROOT).as_posix()} "
            f"started_at_utc={payload['started_at_utc']}"
        )
        return
    if LOCKED_PATH.exists() or LOCK_RECEIPT.exists():
        raise SystemExit("잠금 산출물이 이미 있는데 시작 영수증이 없다")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema_version": "1.0.0",
        "event": "blinded_scoring_started",
        "started_at_utc": utc_now(),
        "executor": {
            "agent_path": "/root",
            "codex_thread_id": os.environ.get("CODEX_THREAD_ID"),
            "provider": "OpenAI",
            "model": "GPT-5 (Codex; exact deployment identifier not exposed)",
        },
        "scoring_criteria": "frozen_semantic_adjudication_prompt.md unchanged",
        "frozen_prompt_sha256": sha256_file(FROZEN_PROMPT),
        "blinded_cards_sha256": sha256_file(CARDS_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "manifest_truth_sha256_only": manifest["artifacts"]["v50_truth_sealed"][
            "sha256"
        ],
        "truth_file_opened_before_start": False,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
        "independent_blinding": False,
        "release_ready": False,
    }
    EXECUTION_RECEIPT.write_bytes(json_bytes(payload))
    print(
        f"started_at_utc={payload['started_at_utc']} "
        f"receipt={EXECUTION_RECEIPT.relative_to(ROOT).as_posix()}"
    )


def _show_round(round_number: int, cards: list[dict[str, str]]) -> None:
    print(f"### ROUND {round_number:03d} ({len(cards)}건)")
    print(
        "### output: "
        f"research_v3/otc/validation/screening_ai_reference_v50/rounds/round_{round_number:03d}.json"
    )
    for card in cards:
        print(f"\n--- {card['record_id']} | {card['question_id']}")
        print(f"TITLE: {card['title']}")
        print(f"PUBTYPES: {card['publication_types'] or '(없음)'}")
        print(f"MESH: {card['mesh_terms'] or '(없음)'}")
        print(f"ABSTRACT: {card['abstract'] or '(초록 없음 — title_only)'}")


def cmd_cards(args: argparse.Namespace) -> None:
    cards = load_cards()
    planned = plan_rounds(cards)
    if args.round is not None:
        if args.round < 1 or args.round > len(planned):
            raise SystemExit(f"round 범위는 1..{len(planned)}")
        _show_round(args.round, planned[args.round - 1])
        return

    judgments, _ = load_round_files()
    seen = {f"{row.get('question_id')}|{row.get('record_id')}" for row in judgments}
    for number, group in enumerate(planned, start=1):
        group_keys = {f"{card['question_id']}|{card['record_id']}" for card in group}
        if not group_keys <= seen:
            _show_round(number, group)
            return
    print(f"전량 채점 파일 존재: {len(seen)}/{len(cards)}. validate 후 lock 실행.")


def cmd_status(_: argparse.Namespace) -> None:
    cards = load_cards()
    judgments, inventory = load_round_files()
    problems = validate_judgments(cards, judgments, require_complete=False)
    valid_keys = {
        f"{row.get('question_id')}|{row.get('record_id')}" for row in judgments
    }
    print(
        f"cards={len(cards)} judgments={len(judgments)} unique={len(valid_keys)} "
        f"remaining={len(cards) - len(valid_keys)} round_files={len(inventory)} "
        f"problems={len(problems)}"
    )


def cmd_validate(_: argparse.Namespace) -> None:
    cards = load_cards()
    judgments, inventory = load_round_files()
    problems = validate_judgments(cards, judgments, require_complete=False)
    if problems:
        for problem in problems[:30]:
            print("!", problem)
        raise SystemExit(f"검증 실패 {len(problems)}건")
    keys = {f"{row['question_id']}|{row['record_id']}" for row in judgments}
    missing = len(cards) - len(keys)
    print(
        f"validation=pass judgments={len(judgments)} cards={len(cards)} "
        f"missing={missing} round_files={len(inventory)}"
    )


def cmd_lock(_: argparse.Namespace) -> None:
    if LOCKED_PATH.exists() or LOCK_RECEIPT.exists():
        raise SystemExit("잠금 산출물이 이미 존재한다. 최초 잠금을 덮어쓰지 않는다")
    if not EXECUTION_RECEIPT.exists():
        raise SystemExit("scoring_execution_receipt.json이 없다. start를 먼저 실행하라")
    execution = json.loads(EXECUTION_RECEIPT.read_text(encoding="utf-8"))
    if execution.get("truth_file_opened_before_start") is not False:
        raise SystemExit(
            "시작 영수증의 truth_file_opened_before_start가 false가 아니다"
        )

    cards = load_cards()
    judgments, inventory = load_round_files()
    problems = validate_judgments(cards, judgments, require_complete=True)
    if problems:
        for problem in problems[:30]:
            print("!", problem)
        raise SystemExit(f"잠금 전 검증 실패 {len(problems)}건")

    by_key = {f"{row['question_id']}|{row['record_id']}": row for row in judgments}
    labels: dict[str, dict[str, Any]] = {}
    for card in cards:
        key = f"{card['question_id']}|{card['record_id']}"
        row = by_key[key]
        labels[key] = {
            "record_id": row["record_id"],
            "question_id": row["question_id"],
            "decision": row["decision"],
            "reason_codes": sorted(row["reason_codes"]),
            "confidence": row["confidence"],
            "evidence_basis": row["evidence_basis"],
        }
    locked_payload = {
        "schema_version": "1.0.0",
        "arm": "screening_ai_reference_v50",
        "labels": labels,
    }
    locked_bytes = json_bytes(locked_payload)
    LOCKED_PATH.write_bytes(locked_bytes)
    locked_at = utc_now()
    receipt = {
        "schema_version": "1.0.0",
        "event": "scoring_labels_locked",
        "scoring_started_at_utc": execution["started_at_utc"],
        "locked_at_utc": locked_at,
        "executor": execution["executor"],
        "scored_rows": len(labels),
        "scored_labels_sha256": hashlib.sha256(locked_bytes).hexdigest(),
        "blinded_cards_sha256": sha256_file(CARDS_PATH),
        "frozen_prompt_sha256": sha256_file(FROZEN_PROMPT),
        "round_files": inventory,
        "round_inventory_sha256": hashlib.sha256(json_bytes(inventory)).hexdigest(),
        "truth_opened_before_lock": False,
        "truth_may_be_opened_after_utc": locked_at,
        "independent_blinding": False,
        "independent_blinding_ai": True,
        "release_ready": False,
        "local_language_model_used": False,
        "external_llm_api_used": False,
        "subagents_used": False,
    }
    LOCK_RECEIPT.write_bytes(json_bytes(receipt))
    print(f"locked_rows={len(labels)}")
    print(f"locked_at_utc={locked_at}")
    print(f"scored_labels_sha256={receipt['scored_labels_sha256']}")
    print("truth_opened_before_lock=false")


def main() -> None:
    configure_output_utf8()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.set_defaults(handler=cmd_start)
    cards = sub.add_parser("cards")
    cards.add_argument("--round", type=int)
    cards.set_defaults(handler=cmd_cards)
    status = sub.add_parser("status")
    status.set_defaults(handler=cmd_status)
    validate = sub.add_parser("validate")
    validate.set_defaults(handler=cmd_validate)
    lock = sub.add_parser("lock")
    lock.set_defaults(handler=cmd_lock)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
