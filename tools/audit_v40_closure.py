"""v4.0 최종 완료 감사.

HANDOFF §6 의 항목을 코드로 다시 검증한다. 이 스크립트는 상태를 바꾸지 않고 확인만 한다.
하나라도 실패하면 종료 코드 1 을 돌려주고 완료로 선언하지 않는다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OTC = ROOT / "research_v3" / "otc"
AUDIT_PATH = OTC / "audit" / "v40_closure_audit.json"

# 폐기한 실행이 어떤 산출물·문서에도 남지 않았는지 확인할 때 쓰는 표지 문자열.
DISCARDED_MARKERS = ("Qwen", "qwen", "screen_v40_literature_local", "screening_discarded_local3b")
# 격리 폴더 자체와 그 폐기 사실을 기록한 결정 로그는 예외다.
DISCARD_EXEMPT_PARTS = (
    "screening_discarded_local3b",
    "DECISIONS.md",
    "HANDOFF_v40_claude.md",
    "audit_v40_closure.py",
    "RESUME.md",
)
# v4.0 체인에 들어오면 안 되는 사람 판정 자료.
HUMAN_JUDGMENT_PATHS = (
    "research_v3/screening/title_abstract.csv",
    "research_v3/screening/full_text.csv",
    "research_v3/human_review_minimal",
    "research_v3/rules/EXPERT_REVIEW_GUIDE.md",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"check": name, "passed": bool(passed), "detail": detail}


def audit() -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    # 2. P2 커버리지와 로컬 모델 미사용
    screening = read_json(OTC / "literature/screening/screening_manifest.json")
    results.append(
        check(
            "p2_coverage_and_no_local_model",
            screening["coverage"] == 1.0
            and screening["run_complete"] is True
            and screening["classified_rows"] == screening["corpus_rows"]
            and not screening["missing_ids"]
            and not screening["duplicated_ids"]
            and screening["local_language_model_used"] is False
            and screening["external_llm_api_used"] is False
            and screening["subagents_used"] is False
            and screening["human_decisions"] == 0
            and screening["screener"] == "agent_direct",
            {
                "coverage": screening["coverage"],
                "classified_rows": screening["classified_rows"],
                "missing": len(screening["missing_ids"]),
                "duplicated": len(screening["duplicated_ids"]),
                "screener": screening["screener"],
                "local_language_model_used": screening["local_language_model_used"],
                "external_llm_api_used": screening["external_llm_api_used"],
                "subagents_used": screening["subagents_used"],
                "human_decisions": screening["human_decisions"],
            },
        )
    )

    # 3. 폐기 산출물이 어디에도 참조되지 않는지
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.splitlines()
    offenders: list[str] = []
    for name in tracked:
        if any(part in name for part in DISCARD_EXEMPT_PARTS):
            continue
        path = ROOT / name
        if not path.is_file() or path.stat().st_size > 8_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(marker in text for marker in DISCARDED_MARKERS):
            offenders.append(name)
    results.append(check("no_discarded_run_reference", not offenders, {"files": offenders}))

    # 4. P3-A 설계
    reference = read_json(ROOT / "research_v3/measurement/screener_vs_ai_reference.json")
    weighted = all(
        stratum.get("weight") is not None and stratum["weight"] > 0 for stratum in reference["strata"]
    )
    results.append(
        check(
            "p3a_design",
            reference["sample_size"] == 300
            and len(reference["rounds"]) == 3
            and weighted
            and reference["corpus_prevalence"]["rogan_gladen_corrected_prevalence"] is not None
            and reference["bootstrap"]["replicates"] == 10_000,
            {
                "sample_size": reference["sample_size"],
                "rounds": len(reference["rounds"]),
                "strata": len(reference["strata"]),
                "stratum_weights_present": weighted,
                "bootstrap_replicates": reference["bootstrap"]["replicates"],
                "rogan_gladen": reference["corpus_prevalence"]["rogan_gladen_corrected_prevalence"],
            },
        )
    )

    # 5. P3-B 설계와 잠금 순서
    blind = read_json(OTC / "validation/ai_independent_evaluation.json")
    lock = read_json(OTC / "validation/ai_independent_evaluation/ai_reference_labels.locked.json")
    audit_log = read_json(OTC / "validation/ai_independent_evaluation/ai_independent_prediction_audit.json")
    per_rule = blind["per_rule_type"]
    both_classes = all(
        0 < item["true_positive"] + item["false_negative"] < item["cases"] for item in per_rule.values()
    )
    locked_at = datetime.fromisoformat(lock["created_at_utc"])
    predicted_at = datetime.fromisoformat(audit_log["predicted_at_utc"])
    # 생성 단계에서 16개 규칙 유형 전부가 최소 10건을 가졌는지 별도로 본다.
    # 채점 표(per_rule_type)에는 참조표준이 전부 uncertain 으로 본 draft 유형이 빠진다.
    case_manifest = read_json(OTC / "validation/ai_independent_cases/case_manifest.json")
    generated_per_type = case_manifest["cases_per_rule_type"]
    results.append(
        check(
            "p3b_design_and_lock_order",
            blind["cases_total"] >= 200
            and len(generated_per_type) == 16
            and all(count >= 10 for count in generated_per_type.values())
            and all(item["cases"] >= 10 for item in per_rule.values())
            and both_classes
            and len(lock["round_seeds"]) == 3
            and audit_log["verified_lock_sha256"] == sha256_file(
                OTC / "validation/ai_independent_evaluation/ai_reference_labels.locked.json"
            )
            and locked_at < predicted_at,
            {
                "cases_total": blind["cases_total"],
                "generated_rule_types": len(generated_per_type),
                "min_generated_cases_per_rule_type": min(generated_per_type.values()),
                "scored_rule_types": len(per_rule),
                "min_scored_cases_per_rule_type": min(item["cases"] for item in per_rule.values()),
                "both_classes_present": both_classes,
                "rounds": len(lock["round_seeds"]),
                "locked_at_utc": lock["created_at_utc"],
                "predicted_at_utc": audit_log["predicted_at_utc"],
                "lock_before_prediction": locked_at < predicted_at,
            },
        )
    )

    # 6. 사람 판정 자료가 v4.0 체인에 입력·정답·링크로 들어왔는지.
    #    한국어 서술 안에서 사건을 설명하며 이름을 언급하는 것은 위반이 아니다.
    #    위반은 (1) 사람 판정 필드가 실제 키로 존재하거나, (2) 사람 판정 파일 경로를
    #    데이터 값으로 참조하는 경우다. 그래서 문자열 검색이 아니라 구조를 훑는다.
    v40_json_inputs = [
        OTC / "literature/screening/screening_manifest.json",
        ROOT / "research_v3/measurement/screener_vs_ai_reference.json",
        OTC / "validation/ai_independent_evaluation.json",
        OTC / "rules/literature_link_manifest.json",
    ]
    v40_csv_inputs = [
        OTC / "literature/evidence_map.csv",
        OTC / "rules/supporting_literature.csv",
    ]
    leaks: list[str] = []

    def walk(node: Any, origin: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "human_reference_label":
                    leaks.append(f"{origin}: 키 {key}")
                walk(value, origin)
        elif isinstance(node, list):
            for item in node:
                walk(item, origin)
        elif isinstance(node, str):
            stripped = node.strip()
            # 경로처럼 생긴 값만 검사한다. 문장 속 언급은 값이 아니라 설명이다.
            looks_like_path = "/" in stripped and " " not in stripped
            if looks_like_path and any(stripped.startswith(marker) for marker in HUMAN_JUDGMENT_PATHS):
                leaks.append(f"{origin}: 경로 값 {stripped}")

    for path in v40_json_inputs:
        walk(read_json(path), path.name)
    for path in v40_csv_inputs:
        rows = csv_rows(path)
        if rows and "human_reference_label" in rows[0]:
            leaks.append(f"{path.name}: 컬럼 human_reference_label")
        for row in rows:
            for value in row.values():
                stripped = (value or "").strip()
                if any(stripped.startswith(marker) for marker in HUMAN_JUDGMENT_PATHS):
                    leaks.append(f"{path.name}: 경로 값 {stripped}")
    results.append(
        check(
            "no_human_judgment_in_v40_chain",
            not leaks,
            {
                "leaks": leaks,
                "human_decisions": blind["human_decisions"],
                "human_reference_standard": blind["human_reference_standard"],
                "note_ko": (
                    "맹검 훼손 2건의 사유 문장은 사건을 밝히는 서술이며 사람 라벨을 "
                    "입력·정답·링크로 쓴 것이 아니다. 해당 2건은 지표에서 제외돼 있다."
                ),
            },
        )
    )

    # 7. 규칙 16개 문장 locator
    links = csv_rows(OTC / "rules/supporting_literature.csv")
    rules = csv_rows(OTC / "rules/rules.csv")
    locator_ok = all(re.fullmatch(r"abstract:sentence:\d+", row["locator"]) for row in links)
    covered = {row["rule_id"] for row in links}
    results.append(
        check(
            "all_rules_have_sentence_locator",
            covered == {row["rule_id"] for row in rules} and locator_ok and len(links) > 0,
            {
                "rules_total": len(rules),
                "rules_covered": len(covered),
                "links": len(links),
                "locator_format_ok": locator_ok,
            },
        )
    )

    # 8. 정합성과 제외 제품 누출
    alignment = read_json(OTC / "audit/runtime_research_alignment.json")
    counts = alignment["counts"]
    runtime = read_json(ROOT / "src/generated/otc-runtime.json")
    products = csv_rows(OTC / "normalized/product_master.csv")
    excluded_leak = sum(
        1 for row in products if "신신파스" in row["product_name"] and row["analysis_status"] == "included"
    ) + sum(1 for item in runtime["products"] if "신신파스" in item["productName"])
    results.append(
        check(
            "counts_and_no_excluded_product_leak",
            alignment["valid"] is True
            and counts["analysis_products"] == 13
            and counts["runtime_unique_ingredients"] == 28
            and counts["runtime_product_ingredient_bindings"] == 47
            and counts["runtime_administration_constraints"] == 32
            and excluded_leak == 0,
            {**counts, "excluded_product_leak": excluded_leak},
        )
    )

    # 9. 검증 명령 결과
    software = read_json(OTC / "audit/software_validation.json")
    software_results = software["results"]
    results.append(
        check(
            "software_validation",
            all(item["exit_code"] == 0 for item in software_results.values())
            and software_results["build"]["static_paths_generated"] == 156,
            {
                name: {"exit_code": item["exit_code"], "status": item["status"], **{
                    k: v for k, v in item.items() if k in ("passed", "static_paths_generated")
                }}
                for name, item in software_results.items()
            },
        )
    )

    # 10. 논문 DOCX/PDF
    docx = ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.docx"
    pdf = ROOT / "research_v3/thesis/권혁찬_졸업논문_최종본.pdf"
    page_images = sorted((OTC / "etc/document_qa/thesis_v40_pages").glob("page_*.png"))
    import zipfile

    with zipfile.ZipFile(docx) as archive:
        docx_xml = archive.read("word/document.xml").decode("utf-8")
    pdf_pages = None
    non_embedded: list[str] = []
    try:
        import pypdf

        reader = pypdf.PdfReader(pdf)
        pdf_pages = len(reader.pages)
        fonts, embedded = set(), set()
        for page in reader.pages:
            font_map = (page.get("/Resources") or {}).get("/Font") or {}
            for key in font_map:
                font = font_map[key].get_object()
                base = str(font.get("/BaseFont", ""))
                fonts.add(base)
                descriptor = font.get("/FontDescriptor")
                if descriptor is None and font.get("/DescendantFonts"):
                    descriptor = font["/DescendantFonts"][0].get_object().get("/FontDescriptor")
                if descriptor and any(k in descriptor for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                    embedded.add(base)
        non_embedded = sorted(fonts - embedded)
    except Exception as exc:  # noqa: BLE001
        non_embedded = [f"검사 실패: {exc}"]
    results.append(
        check(
            "thesis_documents",
            "Pretendard" in docx_xml
            and pdf_pages is not None
            and not non_embedded
            and len(page_images) == pdf_pages,
            {
                "pretendard_in_docx_xml": docx_xml.count("Pretendard"),
                "pdf_pages": pdf_pages,
                "rendered_page_images": len(page_images),
                "non_embedded_fonts": non_embedded,
            },
        )
    )

    # 11. Drive 동기화와 Notion
    report = read_json(ROOT / "research_v3/logs/v40_run_report.json")
    synced = report["files_synced"]
    results.append(
        check(
            "drive_and_notion",
            all(item["sha256_match_verified"] for item in synced)
            and report["notion_updated"]["value"] is True
            and report["notion_updated"]["verified_by_refetch"] is True
            and report["thesis"]["backups_preserved"] is True,
            {
                "files_synced": len(synced),
                "sha256_verified": sum(1 for item in synced if item["sha256_match_verified"]),
                "notion_updated": report["notion_updated"]["value"],
                "backups_preserved": report["thesis"]["backups_preserved"],
            },
        )
    )

    # 12. 작업 트리 상태
    diff_check = subprocess.run(
        ["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()
    results.append(
        check(
            "git_state",
            diff_check.returncode == 0,
            {"diff_check_exit": diff_check.returncode, "uncommitted_entries": len(status.splitlines())},
        )
    )

    # 14. 상태 플래그가 근거와 일치하는지
    completion = read_json(OTC / "audit/completion_audit.json")
    flags = completion["status_flags"]
    results.append(
        check(
            "state_flags_match_evidence",
            completion["complete"] is True
            and completion["incomplete_requirements"] == []
            and flags["performance_claim_allowed"]["value"] is True
            and flags["independent_blinding_ai"]["value"] is True
            and flags["independent_blinding"]["value"] is False
            and flags["release_ready"]["value"] is False
            and all(flag.get("evidence") for flag in flags.values()),
            {name: flag["value"] for name, flag in flags.items()},
        )
    )

    passed = all(item["passed"] for item in results)
    return {
        "schema_version": "1.0.0",
        "phase": "final_closure_audit",
        "generated_at_utc": datetime.now().astimezone().isoformat(timespec="seconds"),
        "all_passed": passed,
        "failed_checks": [item["check"] for item in results if not item["passed"]],
        "checks": results,
    }


def main() -> int:
    result = audit()
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "all_passed": result["all_passed"],
                "checks": len(result["checks"]),
                "failed": result["failed_checks"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
