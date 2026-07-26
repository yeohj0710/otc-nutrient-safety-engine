from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
REPORT_PATH = ROOT / "research_v3/logs/v40_run_report.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    picos_path = ROOT / "research_v3/otc/literature/picos/picos_definition.json"
    evidence_path = ROOT / "research_v3/otc/literature/evidence_map.csv"
    screening_path = ROOT / "research_v3/otc/literature/screening/screening_manifest.json"
    amendment_path = ROOT / "research_v3/protocol/amendments.csv"
    protocol_path = ROOT / "research_v3/protocol/protocol-v4.0-full-ai.md"
    metrics_path = ROOT / "research_v3/metrics_manifest.json"

    picos = read_json(picos_path)
    evidence = csv_rows(evidence_path)
    screening = read_json(screening_path)
    finished_at = datetime.now(KST)
    now = finished_at.isoformat(timespec="seconds")
    p5_started_at = datetime(2026, 7, 27, 7, 58, tzinfo=KST)
    sync_started_at = datetime(2026, 7, 27, 8, 16, tzinfo=KST)

    synced = [
        (picos_path, r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\picos_definition.json", True),
        (ROOT / "research_v3/otc/rules/supporting_literature.csv", r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\supporting_literature.csv", True),
        (metrics_path, r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\metrics_manifest.json", True),
        (amendment_path, r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\amendments.csv", True),
        (protocol_path, r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\protocol-v4.0-full-ai.md", True),
        (ROOT / "research_v3/reports/notion_update.md", r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\notion_update.md", True),
        (ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.docx", r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\01_논문_최종본\권혁찬_졸업논문_최종본.docx", True),
        (ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.pdf", r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\01_논문_최종본\권혁찬_졸업논문_최종본.pdf", True),
        (ROOT / "research_v3/reports/발표원고_v4.0.md", r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\04_발표자료\발표원고_v4.0.md", True),
        (REPORT_PATH, r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\v40_run_report.json", None),
    ]

    report: dict[str, Any] = {
        "schema_version": "4.0",
        "generated_at": now,
        "language": "ko",
        "phases": {
            "P0": {"status": "complete", "started_at": "2026-07-27T01:30:00+09:00", "ended_at": "2026-07-27T01:35:00+09:00", "elapsed_minutes": 5},
            "P1": {"status": "complete", "started_at": "2026-07-27T01:35:00+09:00", "ended_at": "2026-07-27T01:47:00+09:00", "elapsed_minutes": 12},
            "P2": {"status": "partial", "started_at": "2026-07-27T01:47:00+09:00", "ended_at": "2026-07-27T07:58:00+09:00", "elapsed_minutes": 371, "cutoff_decision_at": "2026-07-27T07:50:00+09:00"},
            "P3": {"status": "not_run", "started_at": None, "ended_at": None, "elapsed_minutes": None, "reason": "P2 coverage가 1.0이 아니어서 시작하지 않음"},
            "P4": {"status": "not_run", "started_at": None, "ended_at": None, "elapsed_minutes": None, "reason": "07:50 종료 전환 규칙 적용"},
            "P5": {"status": "complete_with_partial_research_state", "started_at": "2026-07-27T07:58:00+09:00", "ended_at": now, "elapsed_minutes": int((finished_at - p5_started_at).total_seconds() // 60)},
            "g_drive_sync_and_report": {"status": "complete", "started_at": "2026-07-27T08:16:00+09:00", "ended_at": now, "elapsed_minutes": int((finished_at - sync_started_at).total_seconds() // 60)},
        },
        "picos": {
            "ai_question_count": len(picos["questions"]),
            "prompt_sha256": picos["prompt_sha256"],
            "search_hit_count_before_deduplication": picos["last_search"]["total_hits_before_deduplication"],
            "source": "PubMed E-utilities",
            "query_definitions": rel(picos_path),
        },
        "corpus": {
            "rows": len(evidence),
            "with_abstract": sum(row["has_abstract"] == "true" for row in evidence),
            "title_only": sum(row["has_abstract"] != "true" for row in evidence),
            "input_sha256": screening["input_sha256"],
            "raw_response_checksum_files_verified": 25,
            "evidence_path": rel(evidence_path),
        },
        "screening": {
            "status": "partial",
            "coverage": screening["coverage"],
            "classified_rows": screening["classified_rows"],
            "remaining_rows": screening["corpus_rows"] - screening["classified_rows"],
            "decision_distribution": screening["decision_distribution"],
            "evidence_basis_distribution": screening["evidence_basis_distribution"],
            "prompt_sha256": screening["prompt_sha256"],
            "execution_mode": "local_gpu",
            "model": screening["model"],
            "batch_size": 100,
            "append_only_checkpoint": True,
            "run_complete": screening["run_complete"],
            "partial_reason": screening["partial_reason"],
            "evidence_path": rel(screening_path),
        },
        "ai_reference": {
            "status": "not_run",
            "sample_size": None,
            "unresolved": None,
            "inter_round_agreement": None,
            "sensitivity_vs_ai_reference": None,
            "specificity_vs_ai_reference": None,
            "precision_vs_ai_reference": None,
            "f1_vs_ai_reference": None,
            "calibrated_estimate": None,
            "calibrated_estimate_95_ci": None,
            "evidence_path": None,
        },
        "blind_eval": {
            "status": "not_run",
            "case_count": None,
            "unresolved": None,
            "sensitivity": None,
            "specificity": None,
            "f1": None,
            "critical_false_negatives": None,
            "by_rule_type": None,
            "legacy_13_case_recheck_comparison": None,
            "evidence_path": None,
        },
        "state_flags": {
            "amendment_adopted": {"value": True, "evidence_path": rel(amendment_path)},
            "independent_blinding": {"value": False, "reason": "사람 맹검을 뜻하며 이번 v4.0 체인에서 사용하지 않음", "evidence_path": rel(protocol_path)},
            "independent_blinding_ai": {"value": False, "reason": "AI 맹검 독립평가 미실행", "evidence_path": None},
            "independent_evaluation_ai_complete": {"value": False, "reason": "P3 미실행", "evidence_path": None},
            "performance_claim_allowed": {"value": False, "reason": "AI 참조표준과 맹검평가가 없음", "evidence_path": rel(screening_path)},
            "complete": {"value": False, "reason": "P2, P3, P4 미완료", "evidence_path": rel(screening_path)},
            "release_ready": {"value": False, "reason": "연구 종결과 배포 게이트를 통과하지 않음", "evidence_path": rel(metrics_path)},
            "human_judgment_used": {"value": False, "reason": "사람 판정 파일을 v4.0 입력·정답·링크로 사용하지 않음", "evidence_path": rel(protocol_path)},
        },
        "rule_evidence": {
            "rule_types_total": 16,
            "rules_released": 15,
            "rules_with_v40_literature_evidence": None,
            "new_literature_connections_this_run": 0,
            "conflict_count": None,
            "status": "not_run",
            "reason": "P4 문장 locator 연결과 conflict 감사를 실행하지 않음",
        },
        "site": {
            "status": "not_run",
            "tests": None,
            "typecheck": None,
            "lint": None,
            "build": None,
            "consistency_audit": None,
            "deployment": "not_run",
            "reason": "P4를 시작하지 않았고 배포 금지를 유지함",
        },
        "thesis": {
            "docx_path": "research_v3/thesis/권혁찬_졸업논문_최종본.docx",
            "pdf_path": "research_v3/thesis/권혁찬_졸업논문_최종본.pdf",
            "page_count": 7,
            "render_checked_all_pages": True,
            "pretendard_verified_in_docx_xml": True,
            "pretendard_embedded_in_pdf": True,
            "backup_paths": [
                r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\01_논문_최종본\권혁찬_졸업논문_최종본_v3백업.docx",
                r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\01_논문_최종본\권혁찬_졸업논문_최종본_v3백업.pdf",
                r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\03_연구데이터_research_v3\metrics_manifest_v3백업.json",
            ],
        },
        "notion_updated": {
            "value": True,
            "reason": "지정 페이지의 현재 상태 절을 v4.0 부분 실행 결과로 갱신하고 하위 페이지 4개 보존을 재확인함",
            "url": "https://app.notion.com/p/3723b1f9b9ae802b9561d4487802e046",
        },
        "files_synced": [
            {
                "source": rel(source),
                "target": target,
                "sha256_match_verified": verified,
                "verification": "원본·복사본 SHA-256 일치" if verified else "보고서 생성 뒤 복사하고 JSON 파싱으로 확인",
            }
            for source, target, verified in synced
        ],
        "closure": {
            "research_complete": False,
            "blocking_reasons": [
                "AI 문헌 선별이 300/5,724행으로 coverage=1.0 미달",
                "AI 참조표준 미생성",
                "규칙엔진 AI 맹검 독립평가 미실행",
                "규칙별 문장 locator와 conflict 감사 미실행",
                "사이트 테스트·빌드·정합성 감사 미실행",
            ],
        },
        "scope_reductions": [
            {"item": "P2 AI 선별", "planned": "5,724행 100%", "actual": "300행", "reason": "07:50 종료 전환 규칙"},
            {"item": "P3 AI 참조표준·맹검평가", "planned": "실행", "actual": "미실행", "reason": "P2 완료 게이트 미충족"},
            {"item": "P4 문헌 locator·사이트", "planned": "실행", "actual": "미실행", "reason": "07:50 종료 전환 규칙"},
        ],
        "unresolved": [
            {"item": "남은 문헌 선별", "value": 5424, "reason": "이번 실행 시간 내 처리하지 못함"},
            {"item": "screener_vs_ai_reference.json", "value": None, "reason": "P3-A 미실행으로 파일을 생성하지 않음"},
            {"item": "ai_independent_evaluation.json", "value": None, "reason": "P3-B 미실행으로 파일을 생성하지 않음"},
            {"item": "AI 참조표준 대비 성능 지표", "value": None, "reason": "참조표준이 없음"},
            {"item": "규칙별 v4.0 문헌 locator와 conflict 수", "value": None, "reason": "P4 미실행"},
            {"item": "사이트 검증 결과", "value": None, "reason": "이번 실행에서 사이트를 변경하거나 검증하지 않음"},
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
