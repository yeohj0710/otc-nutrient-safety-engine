from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research.otc import build_v51_review_packet as builder
from scripts.research.otc import validate_v51_shortlist_triage as triage_validator


ROOT = Path(__file__).resolve().parents[2]


def copy_review_packet_input_set(tmp_path: Path) -> None:
    for relative in (
        builder.QUEUE_RELATIVE,
        builder.TRIAGE_RELATIVE,
        builder.EVIDENCE_INVENTORY_RELATIVE,
        builder.GENERATOR_RELATIVE,
        builder.TRIAGE_VALIDATOR_RELATIVE,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def rewrite_csv_row(
    path: Path,
    required_fields: tuple[str, ...],
    field: str,
    value: str,
) -> None:
    fields, rows = builder.read_csv(path, required_fields)
    rows[0][field] = value
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixture_rows(count: int = 33) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    queue_rows: list[dict[str, str]] = []
    triage_rows: list[dict[str, str]] = []
    for index in range(count):
        candidate_id = f"CAND-{index:02d}"
        rule_id = f"RULE-{index:02d}"
        product_name = f"검토 제품 {index:02d}"
        item_sequence = f"{index:09d}"
        current_scope = f"scope_{index:02d}"
        queue_rows.append(
            {
                "evidence_candidate_id": candidate_id,
                "rule_id": rule_id,
                "rule_type": "maximum_duration",
                "referenced_rule_status": "released",
                "candidate_operational_status": "inactive_candidate",
                "product_name": product_name,
                "item_sequence": item_sequence,
                "current_rule_scope": current_scope,
                "referenced_runtime_condition": f"item_sequence={item_sequence}",
                "proposed_message_ko": "현재 후보 사용자 문구",
                "proposed_next_action_ko": "약사에게 문의하세요.",
                "source_id": "MFDS-NEDRUG-DETAIL",
                "source_url": (
                    "https://nedrug.mfds.go.kr/dsie/pdf/drb/"
                    f"{item_sequence}/NB"
                ),
                "source_version": f"sha256:{index:064x}",
                "raw_candidate_source_locator": "사용상의주의사항 PDF p.1, 문단 1",
                "raw_candidate_evidence_text": "공식 원문 후보 문장",
                "proposed_review_source_locator": (
                    "사용상의주의사항 PDF p.1, 문단 1"
                ),
                "proposed_review_evidence_text": "검토할 공식 원문 후보 문장",
                "reviewed_source_locator": "",
                "reviewed_evidence_text": "",
                "operational_source_locator": "",
                "operational_evidence_text": "",
                "referenced_code_link": "src/lib/otc/engine.ts:100",
                "review_status": "needs_expert_review",
                "required_regression_tests": (
                    "normal|boundary|non_target|false_positive"
                ),
                "review_decision": "",
                "review_comment": "",
                "reviewer_id": "",
                "reviewer_role": "",
                "reviewed_at": "",
            }
        )
        triage_rows.append(
            {
                "evidence_candidate_id": candidate_id,
                "rule_id": rule_id,
                "rule_type": "maximum_duration",
                "product_name": product_name,
                "item_sequence": item_sequence,
                "current_scope": current_scope,
                "semantic_relation": "potential_product_extension",
                "recommended_status": "needs_expert_review",
                "proposed_trigger": f"item_sequence={item_sequence} AND duration>3",
                "expected_decision_ko": "3일을 넘기기 전에 상담하도록 안내한다.",
                "decision_reason_ko": "제품별 적용 범위를 확인해야 한다.",
                "expert_question_ko": "이 제품에 3일 기준을 적용할 수 있는가?",
            }
        )
    return queue_rows, triage_rows


def test_packet_joins_every_queue_item_once_and_stays_inactive() -> None:
    queue_rows, triage_rows = fixture_rows()

    package = builder.build_from_rows(queue_rows, triage_rows)

    assert package["summary"]["packet_items"] == 33
    assert package["summary"]["unique_candidate_ids"] == 33
    assert package["summary"]["activated_items"] == 0
    assert package["summary"]["inactive_candidate_items"] == 33
    assert package["summary"]["candidate_operational_status_counts"] == {
        "inactive_candidate": 33
    }
    assert package["summary"]["recommended_status_counts"] == {
        "needs_expert_review": 33
    }
    for row in queue_rows:
        heading = f". {builder.markdown_text(row['evidence_candidate_id'])}\n"
        assert package["markdown"].count(heading) == 1
    assert "사람 전문가가 검증하기 전까지 비활성" in package["markdown"]
    assert "공식 허가 원문" in package["markdown"]
    assert "참조 규칙 범위" in package["markdown"]
    assert "후보 운영 상태" in package["markdown"]
    assert "참조 규칙 상태" in package["markdown"]
    assert "참조 규칙 실행 조건" in package["markdown"]
    assert "참조 코드 위치" in package["markdown"]
    assert "원시 후보 원문 위치" in package["markdown"]
    assert "검토 제안 원문 위치" in package["markdown"]
    assert "제안 적용 범위·판정 조건" in package["markdown"]
    assert "후보 판정문" in package["markdown"]
    assert "판단 근거" in package["markdown"]
    assert "전문가 확인 질문" in package["markdown"]
    required_tests = "- 채택 시 필수 회귀 테스트: 정상·경계·비대상·오탐 방지"
    assert package["markdown"].count(required_tests) == 33
    assert package["markdown"].count("- 검토자 ID:") == 33
    assert package["markdown"].count("- 검토자 역할:") == 33
    assert package["markdown"].count("- 검토일:") == 33
    assert package["markdown"].count("- 검토 의견:") == 33
    assert package["summary"]["items_with_required_regression_tests"] == 33


def test_packet_order_is_deterministic() -> None:
    queue_rows, triage_rows = fixture_rows()

    forward = builder.build_from_rows(queue_rows, triage_rows)
    reverse = builder.build_from_rows(
        list(reversed(queue_rows)),
        list(reversed(triage_rows)),
    )

    assert forward["markdown"] == reverse["markdown"]
    assert forward["summary"] == reverse["summary"]


def test_duplicate_and_unmatched_candidates_fail() -> None:
    queue_rows, triage_rows = fixture_rows()
    duplicate_queue = [*queue_rows, copy.deepcopy(queue_rows[0])]

    with pytest.raises(ValueError, match="duplicate queue candidate IDs"):
        builder.build_from_rows(duplicate_queue, triage_rows)

    duplicate_triage = [*triage_rows, copy.deepcopy(triage_rows[0])]
    with pytest.raises(ValueError, match="duplicate triage candidate IDs"):
        builder.build_from_rows(queue_rows, duplicate_triage)

    unmatched_triage = copy.deepcopy(triage_rows)
    unmatched_triage[0]["evidence_candidate_id"] = "NOT-IN-QUEUE"
    with pytest.raises(ValueError, match="queue/triage candidate mismatch"):
        builder.build_from_rows(queue_rows, unmatched_triage)


def test_identity_mismatch_and_unverified_activation_fail() -> None:
    queue_rows, triage_rows = fixture_rows()
    mismatched = copy.deepcopy(triage_rows)
    mismatched[0]["product_name"] = "다른 제품"

    with pytest.raises(ValueError, match="identity mismatch"):
        builder.build_from_rows(queue_rows, mismatched)

    active = copy.deepcopy(triage_rows)
    active[0]["recommended_status"] = "verified_primary"
    with pytest.raises(ValueError, match="invalid recommended status"):
        builder.build_from_rows(queue_rows, active)

    operationally_active = copy.deepcopy(queue_rows)
    operationally_active[0]["candidate_operational_status"] = (
        "active_existing_released_primary_evidence"
    )
    with pytest.raises(ValueError, match="queue item is operationally active"):
        builder.build_from_rows(operationally_active, triage_rows)

    reviewed = copy.deepcopy(queue_rows)
    reviewed[0]["reviewed_source_locator"] = (
        "사용상의주의사항 PDF p.1, 문단 1"
    )
    with pytest.raises(
        ValueError, match="inactive queue item carries reviewed or operational evidence"
    ):
        builder.build_from_rows(reviewed, triage_rows)


@pytest.mark.parametrize(
    "claim",
    (
        "human_expert_verified",
        "release_ready=true",
    ),
)
def test_inactive_triage_rejects_forbidden_approval_or_activation_claims(
    claim: str,
) -> None:
    assert builder.TRIAGE_FORBIDDEN_CLAIMS is triage_validator.FORBIDDEN_CLAIMS
    queue_rows, triage_rows = fixture_rows()
    mutated = copy.deepcopy(triage_rows)
    mutated[0]["decision_reason_ko"] = f"제품별 적용 범위를 확인해야 한다. {claim}"

    with pytest.raises(
        ValueError,
        match="FORBIDDEN_REVIEW_OR_ACTIVATION_CLAIM",
    ):
        builder.build_from_rows(queue_rows, mutated)


def test_rendered_packet_claim_scan_allows_warning_but_rejects_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder.validate_rendered_packet_claims(
        "사람 전문가가 검증하기 전까지 모든 후보는 비활성이다.\n"
        "경고: `release_ready=true`로 간주하지 않는다.\n"
        "경고: `human_expert_verified`가 아니다.\n"
        "경고: 전문가 검토 완료로 간주하지 않는다.\n"
    )

    queue_rows, triage_rows = fixture_rows()
    monkeypatch.setattr(
        builder,
        "render_markdown",
        lambda *_args: "검토 결과: release_ready=true\n",
    )
    with pytest.raises(ValueError, match="rendered packet contains prohibited"):
        builder.build_from_rows(queue_rows, triage_rows)


@pytest.mark.parametrize(
    "claim",
    (
        "release_ready=true is not false",
        "human_expert_verified is not false",
        "release_ready=true not false",
        "human_expert_verified not false",
        "release_ready=true is not prohibited",
        "human_expert_verified is not untrue",
        "경고: `release_ready=true`로 간주하지 않는다. 추가",
        "경고: `human_expert_verified`가 아니다. ",
    ),
)
def test_rendered_packet_claim_scan_rejects_double_negatives_and_modified_disclaimers(
    claim: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_rows, triage_rows = fixture_rows()
    monkeypatch.setattr(builder, "render_markdown", lambda *_args: f"{claim}\n")

    with pytest.raises(ValueError, match="rendered packet contains prohibited"):
        builder.build_from_rows(queue_rows, triage_rows)


def test_prefilled_human_review_and_nonofficial_source_fail() -> None:
    queue_rows, triage_rows = fixture_rows()
    prefilled = copy.deepcopy(queue_rows)
    prefilled[0]["review_decision"] = "adopt"

    with pytest.raises(ValueError, match="human review fields are prefilled"):
        builder.build_from_rows(prefilled, triage_rows)

    prefilled_role = copy.deepcopy(queue_rows)
    prefilled_role[0]["reviewer_role"] = "pharmacist_expert"
    with pytest.raises(ValueError, match="human review fields are prefilled"):
        builder.build_from_rows(prefilled_role, triage_rows)

    missing_role = copy.deepcopy(queue_rows)
    missing_role[0].pop("reviewer_role")
    with pytest.raises(ValueError, match="missing required fields.*reviewer_role"):
        builder.build_from_rows(missing_role, triage_rows)

    nonofficial = copy.deepcopy(queue_rows)
    nonofficial[0]["source_url"] = "https://example.com/not-official"
    with pytest.raises(ValueError, match="non-official source URL"):
        builder.build_from_rows(nonofficial, triage_rows)

    wrong_product = copy.deepcopy(queue_rows)
    wrong_product[0]["source_url"] = (
        "https://nedrug.mfds.go.kr/dsie/pdf/drb/999999999/NB"
    )
    with pytest.raises(ValueError, match="source product mismatch"):
        builder.build_from_rows(wrong_product, triage_rows)

    unpinned = copy.deepcopy(queue_rows)
    unpinned[0]["source_version"] = "latest"
    with pytest.raises(ValueError, match="source version is not SHA-256 pinned"):
        builder.build_from_rows(unpinned, triage_rows)


def test_korean_decision_reason_and_question_are_required() -> None:
    queue_rows, triage_rows = fixture_rows()
    english_only = copy.deepcopy(triage_rows)
    english_only[0]["decision_reason_ko"] = "TBD"
    english_only[0]["expert_question_ko"] = "Is this supported?"

    with pytest.raises(ValueError, match="contain no Hangul"):
        builder.build_from_rows(queue_rows, english_only)


def test_all_required_regression_test_categories_are_required() -> None:
    queue_rows, triage_rows = fixture_rows()
    incomplete = copy.deepcopy(queue_rows)
    incomplete[0]["required_regression_tests"] = "normal|boundary"

    with pytest.raises(ValueError, match="missing regression test tokens"):
        builder.build_from_rows(incomplete, triage_rows)


def test_expert_queue_must_match_evidence_inventory() -> None:
    queue_path = ROOT / "research_v51" / "review" / "expert_review_queue.csv"
    inventory_path = (
        ROOT / "research_v51" / "audit" / "evidence_inventory.json"
    )
    queue_fields, queue_rows = builder.read_csv(
        queue_path, builder.QUEUE_REQUIRED_FIELDS
    )
    inventory = builder.read_json(inventory_path)
    tampered = copy.deepcopy(inventory)
    relative = builder.relative_path(queue_path, ROOT)
    tampered["artifacts"][relative]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="does not match evidence inventory"):
        builder.validate_queue_inventory(
            root=ROOT,
            queue_path=queue_path,
            queue_fields=queue_fields,
            queue_rows=queue_rows,
            inventory=tampered,
        )


def test_build_rejects_coordinated_queue_inventory_swap_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copy_review_packet_input_set(tmp_path)
    queue_path = tmp_path / builder.QUEUE_RELATIVE
    inventory_path = tmp_path / builder.EVIDENCE_INVENTORY_RELATIVE
    real_validate = builder.validate_queue_inventory
    attacked = False

    def validate_then_swap(**kwargs: object) -> None:
        nonlocal attacked
        real_validate(**kwargs)  # type: ignore[arg-type]
        rewrite_csv_row(
            queue_path,
            builder.QUEUE_REQUIRED_FIELDS,
            "product_name",
            "교체된 제품명",
        )
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        queue_payload = queue_path.read_bytes()
        queue_record = inventory["artifacts"][builder.QUEUE_RELATIVE.as_posix()]
        queue_record["bytes"] = len(queue_payload)
        queue_record["sha256"] = hashlib.sha256(queue_payload).hexdigest()
        inventory_path.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        attacked = True

    monkeypatch.setattr(builder, "validate_queue_inventory", validate_then_swap)

    with pytest.raises(ValueError, match="review packet input.*changed"):
        builder.build(tmp_path)

    assert attacked is True
    assert not (tmp_path / builder.PACKET_RELATIVE).exists()
    assert not (tmp_path / builder.AUDIT_RELATIVE).exists()


def test_build_executes_forbidden_patterns_from_validator_snapshot(
    tmp_path: Path,
) -> None:
    copy_review_packet_input_set(tmp_path)
    validator_path = tmp_path / builder.TRIAGE_VALIDATOR_RELATIVE
    validator_source = validator_path.read_text(encoding="utf-8")
    marker = "FORBIDDEN_CLAIMS = (\n"
    assert marker in validator_source
    validator_path.write_text(
        validator_source.replace(
            marker,
            marker + '    re.compile(r"SNAPSHOT_ONLY_FORBIDDEN"),\n',
            1,
        ),
        encoding="utf-8",
    )
    triage_path = tmp_path / builder.TRIAGE_RELATIVE
    rewrite_csv_row(
        triage_path,
        builder.TRIAGE_REQUIRED_FIELDS,
        "decision_reason_ko",
        "제품별 범위를 확인해야 한다. SNAPSHOT_ONLY_FORBIDDEN",
    )

    with pytest.raises(
        ValueError,
        match="FORBIDDEN_REVIEW_OR_ACTIVATION_CLAIM",
    ):
        builder.build(tmp_path)


def test_validator_change_between_output_replacements_rolls_back_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copy_review_packet_input_set(tmp_path)
    package = builder.build(tmp_path)
    packet_path = tmp_path / builder.PACKET_RELATIVE
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    old_packet = b"old-packet\n"
    old_audit = b'{"old": true}\n'
    packet_path.write_bytes(old_packet)
    audit_path.write_bytes(old_audit)
    validator_path = tmp_path / builder.TRIAGE_VALIDATOR_RELATIVE
    real_replace = builder._replace_staged_output
    attacked = False

    def replace_then_change_validator(
        staged: builder._StagedOutput,
        destination: Path,
        *,
        keep_open: bool = False,
    ) -> None:
        nonlocal attacked
        real_replace(staged, destination, keep_open=keep_open)
        if destination == packet_path and not attacked:
            validator_path.write_bytes(
                validator_path.read_bytes() + b"\n# lineage changed\n"
            )
            attacked = True

    monkeypatch.setattr(
        builder,
        "_replace_staged_output",
        replace_then_change_validator,
    )

    with pytest.raises(ValueError, match="review packet input.*changed"):
        builder.write(
            package,
            packet_path=packet_path,
            audit_path=audit_path,
            root=tmp_path,
        )

    assert attacked is True
    assert packet_path.read_bytes() == old_packet
    assert audit_path.read_bytes() == old_audit


def test_checked_in_packet_and_audit_match_generator() -> None:
    package = builder.build(ROOT)
    packet_path = ROOT / "research_v51" / "review" / "expert_review_packet.md"
    audit_path = ROOT / "research_v51" / "audit" / "review_packet_audit.json"
    inventory_path = ROOT / "research_v51" / "audit" / "evidence_inventory.json"

    assert packet_path.read_text(encoding="utf-8") == package["markdown"]
    assert json.loads(audit_path.read_text(encoding="utf-8")) == package["audit"]
    assert package["audit"]["checks"]["all_queue_items_joined_exactly_once"]
    assert package["audit"]["checks"][
        "expert_queue_matches_evidence_inventory"
    ]
    assert package["audit"]["checks"][
        "all_items_include_required_regression_tests"
    ]
    assert package["audit"]["counts"][
        "items_with_required_regression_tests"
    ] == 33
    assert package["audit"]["activation_boundary"]["activated_items"] == 0
    assert package["audit"]["activation_boundary"][
        "inactive_candidate_items"
    ] == 33
    assert package["audit"]["activation_boundary"][
        "candidate_operational_status_counts"
    ] == {"inactive_candidate": 33}
    assert package["audit"]["checks"]["all_source_versions_sha256_pinned"]
    assert package["audit"]["checks"]["triage_forbidden_claim_validator_shared"]
    assert package["audit"]["checks"]["rendered_packet_forbidden_claim_scan"]
    assert package["audit"]["checks"]["all_human_review_fields_blank"]
    assert package["audit"]["activation_boundary"][
        "required_human_review_fields"
    ] == list(builder.HUMAN_REVIEW_FIELDS)
    assert "reviewer_role" in package["audit"]["activation_boundary"][
        "required_human_review_fields"
    ]
    validator_path = ROOT / builder.TRIAGE_VALIDATOR_RELATIVE
    validator_record = package["audit"]["inputs"][
        builder.TRIAGE_VALIDATOR_RELATIVE.as_posix()
    ]
    assert validator_record["sha256"] == hashlib.sha256(
        validator_path.read_bytes()
    ).hexdigest()
    inventory_record = package["audit"]["inputs"][
        "research_v51/audit/evidence_inventory.json"
    ]
    assert inventory_record["sha256"] == hashlib.sha256(
        inventory_path.read_bytes()
    ).hexdigest()
    assert package["audit"]["generator_sha256"] == hashlib.sha256(
        (ROOT / package["audit"]["generator"]).read_bytes()
    ).hexdigest()
    packet_bytes = packet_path.read_bytes()
    assert package["audit"]["artifact"]["bytes"] == len(packet_bytes)
    assert package["audit"]["artifact"]["sha256"] == hashlib.sha256(
        packet_bytes
    ).hexdigest()


def test_review_packet_write_uses_only_canonical_atomic_outputs(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / builder.PACKET_RELATIVE
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    package = {"markdown": "검토 패킷\n", "audit": {"valid": True}}

    builder.write(
        package,
        packet_path=packet_path,
        audit_path=audit_path,
        root=tmp_path,
    )

    assert packet_path.read_bytes() == "검토 패킷\n".encode()
    assert json.loads(audit_path.read_text(encoding="utf-8")) == {"valid": True}
    assert list(packet_path.parent.glob(f".{packet_path.name}.*.tmp")) == []
    assert list(audit_path.parent.glob(f".{audit_path.name}.*.tmp")) == []


def test_review_packet_staged_hardlink_swap_rolls_back_both_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet_path = tmp_path / builder.PACKET_RELATIVE
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    old_packet = b"old-packet\n"
    old_audit = b'{"old": true}\n'
    packet_path.write_bytes(old_packet)
    audit_path.write_bytes(old_audit)
    protected = tmp_path / "research_v3" / "protected-input.txt"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"ATTACK")

    real_replace = os.replace
    attacked = False

    def swap_second_stage(
        source: str | Path,
        destination: str | Path,
    ) -> None:
        nonlocal attacked
        source_path = Path(source)
        destination_path = Path(destination)
        if not attacked and destination_path == audit_path:
            source_path.unlink()
            os.link(protected, source_path)
            attacked = True
        real_replace(source_path, destination_path)

    monkeypatch.setattr(builder.os, "replace", swap_second_stage)

    with pytest.raises(ValueError, match="staged|post-replace"):
        builder.write(
            {"markdown": "new-packet\n", "audit": {"new": True}},
            packet_path=packet_path,
            audit_path=audit_path,
            root=tmp_path,
        )

    assert attacked is True
    assert packet_path.read_bytes() == old_packet
    assert audit_path.read_bytes() == old_audit
    assert protected.read_bytes() == b"ATTACK"
    assert protected.stat().st_nlink == 1
    assert list(packet_path.parent.glob(f".{packet_path.name}.*.tmp")) == []
    assert list(audit_path.parent.glob(f".{audit_path.name}.*.tmp")) == []


def test_review_packet_holds_output_pair_through_final_recheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet_path = tmp_path / builder.PACKET_RELATIVE
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    old_payloads = {
        packet_path: b"old-packet\n",
        audit_path: b'{"old": true}\n',
    }
    for path, payload in old_payloads.items():
        path.write_bytes(payload)
    protected = tmp_path / "research_v3" / "protected-input.txt"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"ATTACK")
    package = {"markdown": "new-packet\n", "audit": {"new": True}}
    expected_audit = b'{\n  "new": true\n}\n'

    real_read = builder._read_regular_output
    audit_new_reads = 0
    attacked = False

    def swap_packet_during_last_audit_read(path: Path) -> dict[str, object]:
        nonlocal audit_new_reads, attacked
        snapshot = real_read(path)
        if path == audit_path and snapshot["payload"] == expected_audit:
            audit_new_reads += 1
            if audit_new_reads == 2:
                packet_path.unlink()
                os.link(protected, packet_path)
                attacked = True
        return snapshot

    monkeypatch.setattr(builder, "_read_regular_output", swap_packet_during_last_audit_read)

    with pytest.raises(ValueError, match="hard link|identity|post-commit"):
        builder.write(
            package,
            packet_path=packet_path,
            audit_path=audit_path,
            root=tmp_path,
        )

    assert audit_new_reads == 2
    assert attacked is True
    assert {path: path.read_bytes() for path in old_payloads} == old_payloads
    assert protected.read_bytes() == b"ATTACK"
    assert protected.stat().st_nlink == 1


@pytest.mark.parametrize(
    "relative_target",
    (
        Path("research_v3/otc/rules/rules.csv"),
        Path("research_v51/evidence/evidence_rule_links.csv"),
        Path("research_v51/review/not-the-packet.md"),
    ),
)
def test_review_packet_rejects_noncanonical_outputs_without_overwrite(
    tmp_path: Path,
    relative_target: Path,
) -> None:
    protected = tmp_path / relative_target
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected-input")
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    package = {"markdown": "replacement\n", "audit": {"valid": True}}

    with pytest.raises(ValueError, match="canonical"):
        builder.write(
            package,
            packet_path=protected,
            audit_path=audit_path,
            root=tmp_path,
        )

    assert protected.read_bytes() == b"protected-input"
    assert not audit_path.exists()


def test_review_packet_rejects_hardlink_and_samefile_aliases(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / builder.PACKET_RELATIVE
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    protected = tmp_path / "research_v3" / "protected.md"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected")
    try:
        os.link(protected, packet_path)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")
    audit_path = tmp_path / builder.AUDIT_RELATIVE
    package = {"markdown": "replacement\n", "audit": {"valid": True}}

    with pytest.raises(ValueError, match="hardlink"):
        builder.write(
            package,
            packet_path=packet_path,
            audit_path=audit_path,
            root=tmp_path,
        )

    alias_path = tmp_path / "research_v3" / "packet-alias.md"
    os.link(packet_path, alias_path)
    with pytest.raises(ValueError, match="canonical"):
        builder.validate_review_output_paths(
            packet_path=alias_path,
            audit_path=audit_path,
            root=tmp_path,
        )
    assert protected.read_bytes() == b"protected"
    assert packet_path.read_bytes() == b"protected"
    assert not audit_path.exists()


def test_review_packet_rejects_canonical_symlink_output(tmp_path: Path) -> None:
    packet_path = tmp_path / builder.PACKET_RELATIVE
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    protected = tmp_path / "research_v3" / "protected.md"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected")
    try:
        packet_path.symlink_to(protected)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    with pytest.raises(ValueError, match="symlink"):
        builder.write(
            {"markdown": "replacement\n", "audit": {"valid": True}},
            packet_path=packet_path,
            audit_path=tmp_path / builder.AUDIT_RELATIVE,
            root=tmp_path,
        )

    assert protected.read_bytes() == b"protected"


def test_review_packet_main_validates_outputs_before_building(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protected = tmp_path / "research_v51" / "evidence" / "input.csv"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"source-data")
    build_called = False

    def should_not_build(**_kwargs: object) -> dict[str, object]:
        nonlocal build_called
        build_called = True
        raise AssertionError("build should not run")

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "build", should_not_build)
    monkeypatch.setattr(
        builder,
        "parse_args",
        lambda: SimpleNamespace(
            queue=tmp_path / "queue.csv",
            triage=tmp_path / "triage.csv",
            packet=protected,
            audit=tmp_path / builder.AUDIT_RELATIVE,
            evidence_inventory=tmp_path / "inventory.json",
        ),
    )

    with pytest.raises(SystemExit, match="canonical"):
        builder.main()

    assert build_called is False
    assert protected.read_bytes() == b"source-data"
