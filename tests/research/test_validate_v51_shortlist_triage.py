from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.research.otc.validate_v51_shortlist_triage import (
    EXPECTED_RELATION_COUNTS,
    EXPECTED_STATUS_COUNTS,
    FIELDS,
    PRODUCTS,
    ROOT,
    RULES,
    SOURCE_SHORTLIST,
    TARGET_TRIAGE,
    validate,
)


SCRIPT = ROOT / "scripts" / "research" / "otc" / "validate_v51_shortlist_triage.py"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_current_manual_triage_matches_all_fixed_contracts() -> None:
    report = validate()

    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
    assert report["source_rows"] == 33
    assert report["target_rows"] == 33
    assert report["unique_target_ids"] == 33
    assert report["semantic_relation_counts"] == EXPECTED_RELATION_COUNTS
    assert report["recommended_status_counts"] == EXPECTED_STATUS_COUNTS


def test_high_risk_triage_keeps_unresolved_boundaries_inactive() -> None:
    rows = {
        row["evidence_candidate_id"]: row for row in read_rows(TARGET_TRIAGE)
    }
    expected = {
        "EXP-OTC-01-NB-P2-B17-pregnancy_lactation": {
            "semantic_relation": "potential_product_extension",
            "recommended_status": "needs_expert_review",
            "proposed_trigger": (
                "검토안: item_sequence=201110646 AND 임신 시기가 허가문구의 "
                "‘임신 6개월 이상’에 해당함. 현재 1·2·3기 입력만으로 6개월 경계를 "
                "정확히 표현할 수 없으므로 임신 주수 환산을 전문가가 승인하기 전에는 비활성"
            ),
            "expected_decision_ko": (
                "임신 6개월 이상이면 이 제품을 복용하지 않도록 안내한다."
            ),
            "decision_reason_ko": (
                "원문은 임신 6개월 이상에서 덱스피드 복용 금지를 직접 지지한다. "
                "현재 규칙은 어린이부루펜시럽의 임신 3기에 한정된다. 현재 엔진은 "
                "`pregnancyTrimester`를 입력받지만 월·주 단위 경계는 받지 않는다. "
                "따라서 6개월 이상을 단순히 3기로 치환하면 허가 범위를 누락하거나 "
                "넓힐 수 있다. 이 원문은 수유 조건을 지지하지 않는다."
            ),
            "expert_question_ko": (
                "허가문구의 임신 6개월 이상을 몇 주부터로 판정할 것인가? 현재 "
                "`pregnancyTrimester` 입력만으로 판정할 수 없다면 주수 입력을 추가할 "
                "것인가? 시기 미상과 수유 중은 비판정으로 둘 것인가?"
            ),
        },
        "EXP-OTC-02-NB-P8-B5-pregnancy_lactation": {
            "semantic_relation": "potential_product_extension",
            "recommended_status": "needs_expert_review",
            "proposed_trigger": (
                "검토안: item_sequence=197500016 AND 허가원문의 ‘임신 말기’에 해당하는 "
                "시기. `pregnancyTrimester=3` 대응과 문단 5~10의 완결 근거를 전문가가 "
                "승인하기 전에는 비활성"
            ),
            "expected_decision_ko": (
                "임신 말기이면 이 제품을 복용하지 않도록 안내한다."
            ),
            "decision_reason_ko": (
                "후보 문단 5는 제목뿐이고 문단 6~10이 임신 말기 투여 금지·회피를 "
                "설명한다. 현재 엔진은 `pregnancyTrimester`를 입력받지만 후보 locator와 "
                "text만으로는 ‘임신 말기’와 3기의 대응 및 판정을 재현할 수 없다. "
                "문단 11 이후의 임신 20주 이후 주의사항은 별도 조건이며 임신 말기 "
                "금기와 합치면 안 된다."
            ),
            "expert_question_ko": (
                "문단 5~10을 완결 근거로 묶고 ‘임신 말기’를 "
                "`pregnancyTrimester=3`으로 판정해도 되는가? 문단 11 이후의 임신 "
                "20~30주 조건은 별도 규칙으로 분리할 것인가?"
            ),
        },
        "EXP-OTC-02-NB-P3-B11-urgent_referral": {
            "semantic_relation": "potential_product_extension",
            "recommended_status": "needs_expert_review",
            "proposed_trigger": (
                "검토안: item_sequence=197500016 AND 전문가가 승인한 무균성 수막염 "
                "의심 증상 조합·중증도 조건을 충족함. 문단 10~11의 완결 근거와 조건을 "
                "확정하기 전에는 비활성"
            ),
            "expected_decision_ko": (
                "승인한 조건을 충족하면 이 제품 복용을 즉시 중지하고 의사와 상의하도록 "
                "안내한다."
            ),
            "decision_reason_ko": (
                "문단 10~11은 무균성 수막염 의심 증상과 즉시 중단·상담을 연결한다. "
                "후보 text는 문장 후반만 담고 있으며 구역·구토·불면·발열 같은 흔한 "
                "증상을 각각 단독 문자열로 매칭하면 오탐 위험이 있다. 전문가가 증상 "
                "조합과 중증도를 정의하기 전에는 단일 증상 trigger를 만들지 않는다."
            ),
            "expert_question_ko": (
                "문단 10~11을 완결 근거로 승인할 것인가, 그리고 어떤 증상 조합이나 "
                "중증도에서 긴급 판정을 낼 것인가?"
            ),
        },
    }

    for candidate_id, expected_fields in expected.items():
        assert {
            field: rows[candidate_id][field] for field in expected_fields
        } == expected_fields


def test_validator_rejects_duplicate_invalid_empty_and_activation_claim(
    tmp_path: Path,
) -> None:
    rows = read_rows(TARGET_TRIAGE)
    rows[1]["evidence_candidate_id"] = rows[0]["evidence_candidate_id"]
    rows[2]["semantic_relation"] = "unsupported_relation"
    rows[3]["expert_question_ko"] = ""
    rows[4]["expected_decision_ko"] = "전문가 검토 완료 후 운영 활성화"
    target = tmp_path / "triage.csv"
    write_rows(target, rows)

    report = validate(target_path=target)
    errors = "\n".join(report["errors"])

    assert report["valid"] is False
    assert "TARGET_DUPLICATE_IDS" in errors
    assert "TARGET_MISSING_IDS" in errors
    assert "INVALID_SEMANTIC_RELATION" in errors
    assert "EMPTY_FIELD" in errors
    assert "FORBIDDEN_REVIEW_OR_ACTIVATION_CLAIM" in errors
    assert "SEMANTIC_RELATION_COUNTS" in errors


def test_validator_rejects_allowed_values_when_fixed_counts_change(
    tmp_path: Path,
) -> None:
    rows = read_rows(TARGET_TRIAGE)
    extension = next(
        row
        for row in rows
        if row["semantic_relation"] == "potential_product_extension"
    )
    extension["semantic_relation"] = "direct_same_scope"
    expert_review = next(
        row for row in rows if row["recommended_status"] == "needs_expert_review"
    )
    expert_review["recommended_status"] = "provisional"
    target = tmp_path / "triage.csv"
    write_rows(target, rows)

    report = validate(target_path=target)
    errors = "\n".join(report["errors"])

    assert report["valid"] is False
    assert "INVALID_SEMANTIC_RELATION" not in errors
    assert "INVALID_RECOMMENDED_STATUS" not in errors
    assert "SEMANTIC_RELATION_COUNTS" in errors
    assert "RECOMMENDED_STATUS_COUNTS" in errors


def test_validator_cross_checks_rules_and_product_master(tmp_path: Path) -> None:
    rule_rows = read_rows(RULES)
    product_rows = read_rows(PRODUCTS)
    rule_rows[0]["scope"] = "tampered_scope"
    product_rows[0]["product_name"] = "변조 제품명"
    rules_path = tmp_path / "rules.csv"
    products_path = tmp_path / "products.csv"

    with rules_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rule_rows[0])
        writer.writeheader()
        writer.writerows(rule_rows)
    with products_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=product_rows[0])
        writer.writeheader()
        writer.writerows(product_rows)

    report = validate(rules_path=rules_path, products_path=products_path)
    errors = "\n".join(report["errors"])

    assert report["valid"] is False
    assert "RULE_SCOPE_MISMATCH" in errors
    assert "PRODUCT_NAME_MISMATCH" in errors


def test_check_cli_is_read_only() -> None:
    observed_paths = (SOURCE_SHORTLIST, TARGET_TRIAGE, RULES, PRODUCTS)
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in observed_paths
    }

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in observed_paths
    }
    assert result.returncode == 0, result.stderr
    assert "source_rows=33 target_rows=33 unique_ids=33" in result.stdout
    assert after == before
