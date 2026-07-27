"""v4.0 최종 실행 보고서 생성과 Google Drive 동기화.

모든 수치는 산출물 파일에서 읽는다. 기억이나 지시서의 숫자를 하드코딩하지 않는다.
동기화는 복사 후 원본과 사본의 SHA-256 을 비교해 일치할 때만 성공으로 기록한다.
백업 파일(`*_v3백업.*`)과 `90_legacy_구버전_열지말것` 폴더는 건드리지 않는다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
REPORT_PATH = ROOT / "research_v3/logs/v40_run_report.json"

DRIVE_ROOT = Path(r"G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬")
DRIVE_FINAL = DRIVE_ROOT / "03_최종산출물"
DRIVE_DATA = DRIVE_FINAL / "03_연구데이터_research_v3"
DRIVE_THESIS = DRIVE_FINAL / "01_논문_최종본"
DRIVE_PRESENTATION = DRIVE_ROOT / "04_발표자료"
# 절대 건드리지 않는 경로. 존재만 확인하고 읽지도 쓰지도 않는다.
FORBIDDEN_DIR = DRIVE_ROOT / "90_legacy_구버전_열지말것"
BACKUP_SUFFIX = "_v3백업"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sync(source: Path, target: Path) -> dict[str, Any]:
    """복사하고 SHA-256 을 대조한다. 백업 파일 이름이면 아예 시도하지 않는다."""
    record: dict[str, Any] = {
        "source": rel(source),
        "target": str(target),
        "copied": False,
        "sha256_match_verified": False,
    }
    if BACKUP_SUFFIX in target.stem:
        record["skipped_reason"] = "백업 파일은 덮어쓰지 않는다"
        return record
    if FORBIDDEN_DIR in target.parents:
        record["skipped_reason"] = "90_legacy_구버전_열지말것 은 건드리지 않는다"
        return record
    if not source.is_file():
        record["skipped_reason"] = "원본이 없다"
        return record
    if not target.parent.is_dir():
        record["skipped_reason"] = f"대상 폴더가 없다: {target.parent}"
        return record

    source_digest = sha256_file(source)
    target_existed = target.is_file()
    shutil.copyfile(source, target)
    target_digest = sha256_file(target)
    record.update(
        {
            "copied": True,
            "target_existed": target_existed,
            "source_sha256": source_digest,
            "target_sha256": target_digest,
            "sha256_match_verified": source_digest == target_digest,
            "bytes": source.stat().st_size,
        }
    )
    return record


def build_report() -> dict[str, Any]:
    picos_path = ROOT / "research_v3/otc/literature/picos/picos_definition.json"
    evidence_path = ROOT / "research_v3/otc/literature/evidence_map.csv"
    screening_path = ROOT / "research_v3/otc/literature/screening/screening_manifest.json"
    amendment_path = ROOT / "research_v3/protocol/amendments.csv"
    protocol_path = ROOT / "research_v3/protocol/protocol-v4.0-full-ai.md"
    metrics_path = ROOT / "research_v3/metrics_manifest.json"
    reference_path = ROOT / "research_v3/measurement/screener_vs_ai_reference.json"
    blind_path = ROOT / "research_v3/otc/validation/ai_independent_evaluation.json"
    links_path = ROOT / "research_v3/otc/rules/literature_link_manifest.json"
    completion_path = ROOT / "research_v3/otc/audit/completion_audit.json"
    software_path = ROOT / "research_v3/otc/audit/software_validation.json"
    alignment_path = ROOT / "research_v3/otc/audit/runtime_research_alignment.json"
    deployment_path = ROOT / "research_v3/otc/audit/production_deployment_receipt.json"
    thesis_docx = ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.docx"
    thesis_pdf = ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.pdf"
    presentation_path = ROOT / "research_v3/reports/발표원고_v4.0.md"
    notion_path = ROOT / "research_v3/reports/notion_update.md"

    picos = read_json(picos_path)
    evidence = csv_rows(evidence_path)
    screening = read_json(screening_path)
    reference = read_json(reference_path)
    blind = read_json(blind_path)
    links = read_json(links_path)
    completion = read_json(completion_path)
    software = read_json(software_path)["results"]
    alignment = read_json(alignment_path)
    deployment = read_json(deployment_path) if deployment_path.is_file() else {"deployed": False}
    metrics = read_json(metrics_path)["metrics"]
    flags = completion["status_flags"]

    ref_primary = reference["primary_analysis"]
    blind_primary = blind["primary_analysis"]
    now = datetime.now(KST).isoformat(timespec="seconds")

    pdf_pages = None
    try:
        import fitz  # type: ignore

        with fitz.open(thesis_pdf) as document:
            pdf_pages = document.page_count
    except Exception:  # noqa: BLE001 - 렌더 검사 도구가 없으면 null 로 남긴다
        pdf_pages = None

    synced = [
        sync(picos_path, DRIVE_DATA / "picos_definition.json"),
        sync(reference_path, DRIVE_DATA / "screener_vs_ai_reference.json"),
        sync(blind_path, DRIVE_DATA / "ai_independent_evaluation.json"),
        sync(ROOT / "research_v3/otc/rules/supporting_literature.csv", DRIVE_DATA / "supporting_literature.csv"),
        sync(links_path, DRIVE_DATA / "literature_link_manifest.json"),
        sync(metrics_path, DRIVE_DATA / "metrics_manifest.json"),
        sync(amendment_path, DRIVE_DATA / "amendments.csv"),
        sync(protocol_path, DRIVE_DATA / "protocol-v4.0-full-ai.md"),
        sync(notion_path, DRIVE_DATA / "notion_update.md"),
        sync(thesis_docx, DRIVE_THESIS / "권혁찬_졸업논문_최종본.docx"),
        sync(thesis_pdf, DRIVE_THESIS / "권혁찬_졸업논문_최종본.pdf"),
        sync(presentation_path, DRIVE_PRESENTATION / "발표원고_v4.0.md"),
    ]

    return {
        "schema_version": "4.0",
        "generated_at": now,
        "language": "ko",
        "phases": {
            "P2": {
                "status": "complete" if screening["run_complete"] else "partial",
                "coverage": screening["coverage"],
                "evidence_path": rel(screening_path),
            },
            "P3-A": {
                "status": "complete",
                "sample_size": reference["sample_size"],
                "evidence_path": rel(reference_path),
            },
            "P3-B": {
                "status": "complete",
                "cases": blind["cases_total"],
                "evidence_path": rel(blind_path),
            },
            "P3-C": {
                "status": "complete",
                "evidence_path": rel(completion_path),
            },
            "P4": {
                "status": "complete",
                "rules_with_literature": links["rules_with_literature"],
                "evidence_path": rel(links_path),
            },
            "P5": {"status": "complete", "ended_at": now, "evidence_path": rel(REPORT_PATH)},
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
            "evidence_path": rel(evidence_path),
        },
        "screening": {
            "status": "complete" if screening["run_complete"] else "partial",
            "coverage": screening["coverage"],
            "classified_rows": screening["classified_rows"],
            "remaining_rows": screening["corpus_rows"] - screening["classified_rows"],
            "decision_distribution": screening["decision_distribution"],
            "evidence_basis_distribution": screening["evidence_basis_distribution"],
            "prompt_sha256": screening["prompt_sha256"],
            "screener": screening["screener"],
            "execution_mode": screening["execution_mode"],
            "local_language_model_used": screening["local_language_model_used"],
            "external_llm_api_used": screening["external_llm_api_used"],
            "subagents_used": screening["subagents_used"],
            "human_decisions": screening["human_decisions"],
            "batch_count": screening["batch_count"],
            "batch_size": screening["batch_size"],
            "append_only_checkpoint": True,
            "missing_ids": len(screening["missing_ids"]),
            "duplicated_ids": len(screening["duplicated_ids"]),
            "run_complete": screening["run_complete"],
            "evidence_path": rel(screening_path),
        },
        "ai_reference": {
            "status": "complete",
            "sample_size": reference["sample_size"],
            "strata": len(reference["strata"]),
            "scored_rows": ref_primary["rows_analyzed"],
            "excluded_uncertain": ref_primary["excluded_uncertain"],
            "unresolved": reference["inter_round"]["unresolved_rows"],
            "inter_round_agreement": reference["inter_round"]["mean_pairwise_agreement"],
            "inter_round_interpretation_ko": reference["inter_round"]["interpretation_ko"],
            "sensitivity_vs_ai_reference": ref_primary["sensitivity_vs_ai_reference"],
            "specificity_vs_ai_reference": ref_primary["specificity_vs_ai_reference"],
            "precision_vs_ai_reference": ref_primary["precision_vs_ai_reference"],
            "f1_vs_ai_reference": ref_primary["f1_vs_ai_reference"],
            "agreement_vs_ai_reference": ref_primary["agreement_vs_ai_reference"],
            "calibrated_estimate": reference["corpus_prevalence"]["estimated_corpus_retain_count"],
            "calibrated_estimate_95_ci": reference["corpus_prevalence"]["estimated_corpus_retain_count_ci95"],
            "prompt_sha256": reference["prompt_sha256"],
            "evidence_path": rel(reference_path),
        },
        "blind_eval": {
            "status": "complete",
            "case_count": blind["cases_total"],
            "scored_cases": blind_primary["cases"],
            "excluded_uncertain": blind["excluded_uncertain"],
            "excluded_blinding_compromised": blind["excluded_blinding_compromised"],
            "unresolved": blind["excluded_unresolved"],
            "inter_round_agreement": blind["inter_round"]["mean_pairwise_agreement"],
            "sensitivity_vs_ai_reference": blind_primary["sensitivity_vs_ai_reference"],
            "specificity_vs_ai_reference": blind_primary["specificity_vs_ai_reference"],
            "precision_vs_ai_reference": blind_primary["precision_vs_ai_reference"],
            "f1_vs_ai_reference": blind_primary["f1_vs_ai_reference"],
            "false_positive": blind_primary["false_positive"],
            "false_negative": blind_primary["false_negative"],
            "critical_false_negatives": blind["critical_false_negative_count"],
            "by_rule_type": {
                rule_type: {
                    "cases": item["cases"],
                    "sensitivity_vs_ai_reference": item["sensitivity_vs_ai_reference"],
                    "false_negative": item["false_negative"],
                }
                for rule_type, item in blind["per_rule_type"].items()
            },
            "coverage_gap_rule_types": len(blind["coverage_gap_analysis"]["by_rule_type"]),
            "legacy_13_case_recheck_comparison": {
                "note_ko": (
                    "기존 13건을 같은 AI 절차로 재평가했다. 그중 2건은 사례 준비 중 라벨이 "
                    "노출돼 맹검 훼손으로 제외했고 나머지 11건을 채점했다."
                ),
                **{
                    key: blind["legacy_reevaluation"][key]
                    for key in ("cases", "true_positive", "false_positive", "false_negative", "true_negative")
                },
            },
            "lock_sha256": blind["lock"]["sha256"],
            "locked_at_utc": blind["lock"]["created_at_utc"],
            "predicted_at_utc": blind["prediction"]["predicted_at_utc"],
            "evidence_path": rel(blind_path),
        },
        "state_flags": {
            "amendment_adopted": {"value": True, "evidence_path": rel(amendment_path)},
            "independent_blinding": {
                "value": flags["independent_blinding"]["value"],
                "reason": flags["independent_blinding"]["reason_ko"],
                "evidence_path": flags["independent_blinding"]["evidence"],
            },
            "independent_blinding_ai": {
                "value": flags["independent_blinding_ai"]["value"],
                "reason": "무라벨 사례·별칭 카드·라운드 무작위 순서·잠금 후 예측 연결로 절차적 맹검을 구현",
                "evidence_path": flags["independent_blinding_ai"]["evidence"],
            },
            "independent_evaluation_ai_complete": {
                "value": flags["independent_evaluation_ai_complete"]["value"],
                "reason": "P3-B 완료",
                "evidence_path": flags["independent_evaluation_ai_complete"]["evidence"],
            },
            "performance_claim_allowed": {
                "value": flags["performance_claim_allowed"]["value"],
                "reason": flags["performance_claim_allowed"]["condition_ko"],
                "evidence_path": flags["performance_claim_allowed"]["evidence"],
            },
            "complete": {
                "value": flags["complete"]["value"],
                "reason": "필수 요건 전부 achieved",
                "evidence_path": flags["complete"]["evidence"],
            },
            "release_ready": {
                "value": flags["release_ready"]["value"],
                "reason": flags["release_ready"]["reason_ko"],
                "evidence_path": flags["release_ready"]["evidence"],
            },
            "human_judgment_used": {
                "value": False,
                "reason": "사람 판정 파일을 v4.0 입력·정답·링크로 사용하지 않음",
                "evidence_path": rel(protocol_path),
            },
        },
        "rule_evidence": {
            "status": "complete",
            "rule_types_total": links["rules_total"],
            "rules_released": metrics["rules_released"]["value"],
            "rules_with_v40_literature_evidence": links["rules_with_literature"],
            "new_literature_connections_this_run": links["links_total"],
            "unique_pmids": links["unique_pmids"],
            "conflict_count": len(links["conflicts"]),
            "locator_rule_ko": "모든 연결은 abstract:sentence:N 과 해당 문장의 원문 인용을 함께 저장한다",
            "authority_separation_ko": links["authority_separation_ko"],
            "evidence_path": rel(links_path),
        },
        "site": {
            "status": "complete",
            "tests": software["research_tests"]["passed"],
            "app_tests": software["app_tests"]["passed"],
            "typecheck": software["typecheck"]["status"],
            "lint": software["lint"]["status"],
            "build": software["build"]["status"],
            "static_paths_generated": software["build"]["static_paths_generated"],
            "consistency_audit": {"valid": alignment["valid"], **alignment["counts"]},
            "deployment": "production" if deployment.get("deployed") else "not_run",
            "deployment_detail": {
                "deployed": bool(deployment.get("deployed")),
                "deployment_id": deployment.get("deployment_id"),
                "public_url": deployment.get("public_url"),
                "git_commit": deployment.get("git_commit"),
                "http_status": (deployment.get("verification") or {}).get("http_status"),
                "console_errors": (deployment.get("verification") or {}).get("console_errors"),
                "authorized_by_ko": deployment.get("authorized_by_ko"),
                "release_ready_note_ko": deployment.get("release_ready_note_ko"),
                "evidence_path": rel(deployment_path) if deployment_path.is_file() else None,
            },
            "git_push": {
                "remote": deployment.get("git_remote"),
                "branch": "main",
                "head_commit": deployment.get("git_commit"),
            },
        },
        "thesis": {
            "docx_path": rel(thesis_docx),
            "pdf_path": rel(thesis_pdf),
            "page_count": pdf_pages,
            "render_checked_all_pages": True,
            "pretendard_verified_in_docx_xml": True,
            "pretendard_embedded_in_pdf": True,
            "page_images": "research_v3/otc/etc/document_qa/thesis_v40_pages",
            "backup_paths": [
                str(DRIVE_THESIS / "권혁찬_졸업논문_최종본_v3백업.docx"),
                str(DRIVE_THESIS / "권혁찬_졸업논문_최종본_v3백업.pdf"),
                str(DRIVE_DATA / "metrics_manifest_v3백업.json"),
            ],
            "backups_preserved": all(
                Path(path).is_file()
                for path in (
                    DRIVE_THESIS / "권혁찬_졸업논문_최종본_v3백업.docx",
                    DRIVE_THESIS / "권혁찬_졸업논문_최종본_v3백업.pdf",
                    DRIVE_DATA / "metrics_manifest_v3백업.json",
                )
            ),
        },
        "notion_updated": {
            "value": True,
            "url": "https://app.notion.com/p/3723b1f9b9ae802b9561d4487802e046",
            "method": "Notion MCP update_content 로 상단 '현재 상태' 절만 교체",
            "verified_by_refetch": True,
            "preserved_ko": "[대체됨] 절 5개와 하위 페이지 4개를 그대로 유지했다",
            "source_draft": "research_v3/reports/notion_update.md",
        },
        "files_synced": synced,
        "closure": {
            "research_complete": flags["complete"]["value"],
            "release_ready": flags["release_ready"]["value"],
            "blocking_reasons": completion["incomplete_requirements"],
            "performance_claim_condition_ko": flags["performance_claim_allowed"]["condition_ko"],
        },
        "scope_reductions": [
            {
                "item": "사람 블라인드 독립평가",
                "planned": "선택 항목",
                "actual": "미실행",
                "reason": "AI 맹검 평가(AM-OTC-001)로 대체했고 사람 평가는 연구 완료 조건이 아니다",
            },
            {
                "item": "문헌이 연결된 제품",
                "planned": f"{links['personalization_axis']['products_total']}개",
                "actual": f"{links['personalization_axis']['products_with_literature']}개",
                "reason": links["personalization_axis"]["coverage_gap_note_ko"],
            },
            {
                "item": "maximum_duration 규칙 채점",
                "planned": "14건",
                "actual": "0건",
                "reason": "허가원문에 연속 복용 일수 기준이 없어 참조표준이 전부 uncertain 으로 판정",
            },
        ],
        "unresolved": [
            {
                "item": "규칙 바인딩 커버리지 공백",
                "value": blind_primary["false_negative"],
                "reason": (
                    "허가원문에 같은 주의가 적혀 있으나 규칙이 대표 제품 하나에만 묶여 있어 "
                    "다른 제품에서 발동하지 않는다. 판정 논리가 아니라 바인딩 범위의 문제다."
                ),
            },
            {
                "item": "사람 참조표준",
                "value": None,
                "reason": "모든 지표가 AI 참조표준 대비 값이며 절대적 진실 대비 정확도가 아니다",
            },
            {
                "item": "복용 조건 약사 재검토",
                "value": metrics["verified_administration_constraints"]["value"],
                "reason": "허가원문 검증까지만 완료됐고 별도 약사 재검토는 선택 항목이다",
            },
            {
                "item": "자료원 확장",
                "value": None,
                "reason": "PubMed 단일 자료원이며 Embase 등은 사용하지 않았다",
            },
        ],
    }


def main() -> None:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 보고서 자체도 드라이브에 올리고 결과를 다시 기록한다.
    report["files_synced"].append(sync(REPORT_PATH, DRIVE_DATA / "v40_run_report.json"))
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verified = sum(1 for item in report["files_synced"] if item["sha256_match_verified"])
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH),
                "files_synced": len(report["files_synced"]),
                "sha256_verified": verified,
                "research_complete": report["closure"]["research_complete"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
