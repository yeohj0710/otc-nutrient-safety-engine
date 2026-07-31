from __future__ import annotations

import copy
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.research.otc import build_v51_final_audit as builder
from scripts.research.otc import build_v51_review_packet as packet_builder


ROOT = Path(__file__).resolve().parents[2]
STABLE_NOW = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)


def output_paths(root: Path = ROOT) -> dict[str, Path]:
    return {
        "metrics_path": root / builder.METRICS_RELATIVE,
        "product_matrix_path": root / builder.PRODUCT_MATRIX_RELATIVE,
        "rule_matrix_path": root / builder.RULE_MATRIX_RELATIVE,
    }


def compute_from(inputs: dict) -> dict:
    return builder.compute(inputs, **output_paths(inputs["root"]))


def minimal_write_package(tmp_path: Path) -> tuple[dict, Path]:
    audit_root = tmp_path / builder.AUDIT_ROOT_RELATIVE
    audit_root.mkdir(parents=True)
    input_path = tmp_path / "research_v51" / "evidence" / "protected.txt"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(b"protected-input")
    snapshot = builder.safely_read_input(input_path, tmp_path)
    relative = input_path.relative_to(tmp_path).as_posix()
    paths = output_paths(tmp_path)
    package = {
        "root": tmp_path.resolve(),
        "input_paths": (input_path,),
        "input_snapshots": {relative: snapshot},
        "output_paths": {
            "final_metrics": paths["metrics_path"],
            "product_support_matrix": paths["product_matrix_path"],
            "active_rule_matrix": paths["rule_matrix_path"],
        },
        "metrics_bytes": b'{"valid":true}\n',
        "product_matrix_bytes": b"product_id\n",
        "rule_matrix_bytes": b"rule_id\n",
    }
    return package, input_path


def test_compute_reports_required_baseline_and_v51_metrics() -> None:
    package = builder.build(ROOT)
    metrics = package["metrics"]
    current = metrics["v51"]

    assert len(package["product_matrix_rows"]) == 13
    assert len(package["rule_matrix_rows"]) == 15
    assert current["runtime"]["historical_support_type_labels"] == 26
    assert current["runtime"]["direct_product_rule_bindings"] == 13
    assert current["runtime"]["administration_derived_type_associations"] == 13
    assert current["runtime"]["cross_product_or_global_rules"] == 2
    assert current["runtime"]["cross_product_or_global_rule_ids"] == [
        "OTC-RULE-001",
        "OTC-RULE-002",
    ]
    assert current["runtime"]["structured_runtime_binding_rows"] == 13
    assert current["runtime"]["administration_constraints"] == 32
    assert current["runtime"]["support_tier_counts"] == {
        "broader_safety_support": 3,
        "dose_or_interval_only": 10,
    }
    assert current["evidence"]["evidence_units"] == 328
    assert current["evidence"]["evidence_rule_links"] == 360
    assert current["evidence"]["evidence_status_counts"] == {
        "needs_expert_review": 33,
        "provisional": 308,
        "rejected": 4,
        "verified_primary": 15,
    }
    assert current["evidence"]["candidate_operational_status_counts"] == {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }
    assert current["evidence"]["operational_evidence_rows"] == 15
    assert current["evidence"]["inactive_candidate_rows"] == 345
    assert current["evidence"]["triage_recommended_status_counts"] == {
        "needs_expert_review": 17,
        "provisional": 2,
        "rejected": 14,
    }
    assert current["evidence"]["triage_semantic_relation_counts"] == {
        "direct_same_scope": 3,
        "duplicate_context": 5,
        "potential_product_extension": 16,
        "wrong_scope": 9,
    }
    assert current["literature"]["v50_emitted_links"] == 10
    assert current["literature"]["v50_emitted_rules"] == 9
    assert current["literature"]["direct_capable_links"] == 5
    assert current["literature"]["direct_match_links"] == 1
    assert current["literature"]["scope_qualified_direct_links"] == 4
    assert current["literature"]["background_only_links"] == 5
    assert current["literature"]["excluded_legacy_links"] == 10
    assert current["literature"]["human_expert_reviewed"] == 0
    assert current["expert_review_packet"]["packet_items"] == 33
    assert current["expert_review_packet"]["new_human_expert_reviews"] == 0
    assert current["expert_review_packet"]["activated_items"] == 0
    assert current["expert_review_packet"]["required_human_review_fields"] == [
        "review_decision",
        "review_comment",
        "reviewer_id",
        "reviewer_role",
        "reviewed_at",
    ]
    assert current["official_source_freshness"]["official_source_urls"] == 20
    assert current["official_source_freshness"]["semantic_match_source_urls"] == 20
    assert current["official_source_freshness"]["semantic_drift_source_urls"] == 0
    assert current["official_source_freshness"]["unreachable_source_urls"] == 0
    assert current["official_source_freshness"]["candidate_excerpt_matches"] == 360
    assert (
        current["official_source_freshness"][
            "verified_primary_candidate_excerpt_matches"
        ]
        == 15
    )
    assert (
        current["official_source_freshness"][
            "remote_pdf_byte_mismatch_is_semantic_drift"
        ]
        is False
    )
    assert current["official_source_freshness"]["new_rules_activated"] == 0
    assert current["runtime"]["release_ready"] is False
    assert all(
        comparison["unchanged"]
        for comparison in metrics["baseline_vs_v51"].values()
    )


def test_released_rules_and_admin_constraints_stay_separate() -> None:
    package = builder.build(ROOT)
    runtime = package["metrics"]["v51"]["runtime"]
    rule_rows = package["rule_matrix_rows"]
    product_rows = package["product_matrix_rows"]

    assert len(runtime["released_rules_explicit"]) == 15
    assert all(
        rule["ruleId"].startswith("OTC-RULE-")
        and rule["applicability"]
        and rule["evidence"]
        and rule["evidence"][0]["sourceVersion"].startswith("sha256:")
        and rule["evidence"][0]["url"]
        and rule["evidence"][0]["locator"]
        for rule in runtime["released_rules_explicit"]
    )
    assert not set(runtime["released_rule_ids"]) & set(
        runtime["administration_constraint_ids"]
    )
    assert runtime["admin_ids_in_released_rules"] == []
    assert runtime["rule_003_004_scope_contract"] == {
        "OTC-RULE-003": {
            "scope": "acetaminophen_tylenol500_age_12_plus",
            "source_item_sequence": "202106092",
        },
        "OTC-RULE-004": {
            "scope": "tylenol500_age_12_plus",
            "source_item_sequence": "202106092",
        },
    }
    assert all(row["status"] == "released" for row in rule_rows)
    assert all(row["source_evidence_json"] for row in rule_rows)
    assert Counter(row["binding_category"] for row in rule_rows) == {
        "direct_product": 13,
        "cross_product_or_global": 2,
    }
    assert sum(
        int(row["historical_support_type_label_count"]) for row in product_rows
    ) == 26
    assert sum(
        int(row["direct_released_rule_binding_count"]) for row in product_rows
    ) == 13
    assert sum(
        int(row["admin_derived_support_type_association_count"])
        for row in product_rows
    ) == 13
    assert sum(int(row["administration_constraint_count"]) for row in product_rows) == 32
    assert Counter(row["numeric_finding_decision_bases"] for row in product_rows) == {
        "administration_constraint": 12,
        "administration_constraint;released_rule": 1,
    }
    assert Counter(row["support_tier"] for row in product_rows) == {
        "dose_or_interval_only": 10,
        "broader_safety_support": 3,
    }


def test_duplicate_identity_and_missing_source_fail() -> None:
    inputs = builder.load_inputs(ROOT)
    duplicated = copy.deepcopy(inputs)
    duplicated["json"]["runtime"]["products"].append(
        copy.deepcopy(duplicated["json"]["runtime"]["products"][0])
    )
    with pytest.raises(ValueError, match="duplicate itemSequence"):
        compute_from(duplicated)

    missing_source = copy.deepcopy(inputs)
    runtime_rule = missing_source["json"]["runtime"]["releasedRules"][0]
    runtime_rule["evidence"][0]["locator"] = ""
    source_rule = runtime_rule["ruleId"]
    shortlist_row = next(
        row
        for row in missing_source["csv"]["rule_shortlist"]
        if row["rule_id"] == source_rule
        and row["review_status"] == "human_expert_verified"
    )
    shortlist_row["source_locator"] = ""
    active_link = next(
        row
        for row in missing_source["csv"]["evidence_links"]
        if row["rule_id"] == source_rule
        and row["candidate_operational_status"]
        == "active_existing_released_primary_evidence"
    )
    active_link["reviewed_source_locator"] = ""
    active_link["operational_source_locator"] = ""
    with pytest.raises(ValueError, match="blank fields"):
        compute_from(missing_source)


def test_expert_queue_requires_blank_reviewer_role() -> None:
    inputs = builder.load_inputs(ROOT)
    missing_field = copy.deepcopy(inputs)
    missing_field["csv"]["expert_queue"][0].pop("reviewer_role", None)
    with pytest.raises(ValueError, match="missing fields.*reviewer_role"):
        builder.analyze_evidence(missing_field)

    prefilled = copy.deepcopy(inputs)
    prefilled["csv"]["expert_queue"][0]["reviewer_role"] = (
        "pharmacist_expert"
    )
    with pytest.raises(ValueError, match="expert queue has prefilled review"):
        builder.analyze_evidence(prefilled)

    missing_audit_role = copy.deepcopy(inputs)
    required_fields = missing_audit_role["json"]["review_audit"][
        "activation_boundary"
    ]["required_human_review_fields"]
    required_fields.remove("reviewer_role")
    with pytest.raises(ValueError, match="required human review fields"):
        builder.analyze_review_packet(missing_audit_role)


def test_mismatched_applicability_and_protected_output_fail() -> None:
    inputs = builder.load_inputs(ROOT)
    mismatched = copy.deepcopy(inputs)
    mismatched["json"]["runtime"]["releasedRules"][0]["applicability"] = {
        "ingredientIds": ["ING-not-the-source"]
    }
    with pytest.raises(ValueError, match="applicability mismatch"):
        compute_from(mismatched)

    with pytest.raises(ValueError, match="must stay under"):
        builder.compute(
            inputs,
            metrics_path=ROOT / "research_v3" / "forbidden.json",
            product_matrix_path=ROOT / builder.PRODUCT_MATRIX_RELATIVE,
            rule_matrix_path=ROOT / builder.RULE_MATRIX_RELATIVE,
        )
    with pytest.raises(ValueError, match="canonical paths"):
        builder.compute(
            inputs,
            metrics_path=ROOT / "research_v51" / "audit" / "baseline_manifest.json",
            product_matrix_path=ROOT / builder.PRODUCT_MATRIX_RELATIVE,
            rule_matrix_path=ROOT / builder.RULE_MATRIX_RELATIVE,
        )


def test_output_hardlink_to_input_is_rejected(tmp_path: Path) -> None:
    audit_root = tmp_path / "research_v51" / "audit"
    audit_root.mkdir(parents=True)
    protected_input = audit_root / "baseline_manifest.json"
    protected_input.write_text("protected", encoding="utf-8")
    metrics_path = tmp_path / builder.METRICS_RELATIVE
    metrics_path.hardlink_to(protected_input)

    with pytest.raises(ValueError, match="must not be a hard link"):
        builder.require_output_paths(
            tmp_path,
            metrics_path,
            tmp_path / builder.PRODUCT_MATRIX_RELATIVE,
            tmp_path / builder.RULE_MATRIX_RELATIVE,
            input_paths=(protected_input,),
        )


def test_support_decomposition_and_freshness_lineage_mismatch_fail() -> None:
    inputs = builder.load_inputs(ROOT)
    mismatched_binding = copy.deepcopy(inputs)
    product = next(
        product
        for product in mismatched_binding["json"]["runtime"]["products"]
        if not product["supportedReleasedRuleIds"]
    )
    product["supportedReleasedRuleIds"] = ["OTC-RULE-003"]
    with pytest.raises(ValueError, match="direct released-rule bindings"):
        compute_from(mismatched_binding)

    mismatched_freshness = copy.deepcopy(inputs)
    mismatched_freshness["json"]["source_freshness"]["inputs"][
        "evidenceRuleLinks"
    ]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="freshness evidence input sha256"):
        compute_from(mismatched_freshness)

    invalid_version = copy.deepcopy(inputs)
    runtime_rule = invalid_version["json"]["runtime"]["releasedRules"][0]
    active_link = next(
        row
        for row in invalid_version["csv"]["evidence_links"]
        if row["rule_id"] == runtime_rule["ruleId"]
        and row["candidate_operational_status"]
        == "active_existing_released_primary_evidence"
    )
    runtime_rule["evidence"][0]["sourceVersion"] = "sha256:not-a-complete-hash"
    active_link["source_version"] = "sha256:not-a-complete-hash"
    with pytest.raises(ValueError, match="exact SHA-256 pin"):
        compute_from(invalid_version)


def test_freshness_recomputes_pinned_text_and_validates_utc_timestamp() -> None:
    inputs = builder.load_inputs(ROOT)
    generator_path = builder.STATIC_INPUTS["source_freshness_generator"]
    inputs["json"]["source_freshness"]["generatorSha256"] = inputs["lineage"][
        generator_path
    ]["sha256"]
    forged = copy.deepcopy(inputs)
    source = next(
        row
        for row in forged["json"]["source_freshness"]["sources"]
        if row["url"]
        != forged["json"]["source_freshness"]["volatilityProbe"]["url"]
    )
    source["pinnedSemanticTextSha256"] = "0" * 64
    source["remoteSemanticTextSha256"] = "0" * 64
    with pytest.raises(ValueError, match="recomputed pinned semantic hash"):
        builder.analyze_source_freshness(forged)

    invalid_timestamp = copy.deepcopy(inputs)
    invalid_timestamp["json"]["source_freshness"]["accessedAtUtc"] = (
        "2026-07-31T14:54:40"
    )
    with pytest.raises(ValueError, match="explicit UTC offset"):
        builder.analyze_source_freshness(invalid_timestamp)


def test_final_audit_shared_freshness_validator_rejects_pdf_hash_and_time() -> None:
    inputs = builder.load_inputs(ROOT)
    generator_path = builder.STATIC_INPUTS["source_freshness_generator"]
    inputs["json"]["source_freshness"]["generatorSha256"] = inputs["lineage"][
        generator_path
    ]["sha256"]
    observed = builder.analyze_source_freshness(inputs, now_utc=STABLE_NOW)
    assert observed["official_source_urls"] == 20
    assert observed["candidate_excerpt_matches"] == 360
    assert observed["release_ready"] is False

    forged_pdf = copy.deepcopy(inputs)
    snapshot = forged_pdf["json"]["source_freshness"]
    source = next(
        item
        for item in snapshot["sources"]
        if item["url"] != snapshot["volatilityProbe"]["url"]
    )
    source["pinnedSnapshotPdfSha256"] = "0" * 64
    source["remotePdfSha256"] = "0" * 64
    source["snapshotPdfByteMatch"] = True
    with pytest.raises(ValueError, match="pinned PDF hash"):
        builder.analyze_source_freshness(forged_pdf, now_utc=STABLE_NOW)

    future = copy.deepcopy(inputs)
    future["json"]["source_freshness"]["accessedAtUtc"] = (
        "2026-08-01T00:00:01+00:00"
    )
    with pytest.raises(ValueError, match="valid audit window"):
        builder.analyze_source_freshness(future, now_utc=STABLE_NOW)

    pre_baseline = copy.deepcopy(inputs)
    pre_baseline["json"]["source_freshness"]["accessedAtUtc"] = (
        "2026-07-30T23:59:59+00:00"
    )
    with pytest.raises(ValueError, match="valid audit window"):
        builder.analyze_source_freshness(pre_baseline, now_utc=STABLE_NOW)


@pytest.mark.parametrize("claim", ("human_expert_verified", "release_ready=true"))
def test_final_audit_rejects_consistently_rehashed_packet_claims(claim: str) -> None:
    inputs = builder.load_inputs(ROOT)
    mutated = copy.deepcopy(inputs)

    triage_relative = builder.STATIC_INPUTS["triage"]
    triage_rows = mutated["csv"]["triage"]
    triage_rows[0]["decision_reason_ko"] += f" {claim}"
    triage_payload = builder.csv_payload(
        tuple(mutated["fields"]["triage"]),
        triage_rows,
    )
    triage_sha = builder.sha256_bytes(triage_payload)
    mutated["lineage"][triage_relative]["bytes"] = len(triage_payload)
    mutated["lineage"][triage_relative]["sha256"] = triage_sha
    mutated["input_snapshots"][triage_relative]["bytes"] = triage_payload
    mutated["input_snapshots"][triage_relative]["sha256"] = triage_sha
    review_audit = mutated["json"]["review_audit"]
    review_audit["inputs"][triage_relative]["bytes"] = len(triage_payload)
    review_audit["inputs"][triage_relative]["sha256"] = triage_sha

    packet_relative = review_audit["artifact"]["path"]
    packet_payload = mutated["packet_bytes"] + f"\n{claim}\n".encode()
    packet_sha = builder.sha256_bytes(packet_payload)
    mutated["packet_bytes"] = packet_payload
    mutated["lineage"][packet_relative]["bytes"] = len(packet_payload)
    mutated["lineage"][packet_relative]["sha256"] = packet_sha
    mutated["input_snapshots"][packet_relative]["bytes"] = packet_payload
    mutated["input_snapshots"][packet_relative]["sha256"] = packet_sha
    review_audit["artifact"]["bytes"] = len(packet_payload)
    review_audit["artifact"]["sha256"] = packet_sha

    with pytest.raises(ValueError, match="FORBIDDEN|prohibited"):
        builder.analyze_review_packet(mutated)


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
def test_final_audit_shared_packet_scanner_rejects_modified_disclaimers(
    claim: str,
) -> None:
    inputs = builder.load_inputs(ROOT)
    mutated = copy.deepcopy(inputs)
    review_audit = mutated["json"]["review_audit"]
    packet_relative = review_audit["artifact"]["path"]
    packet_payload = mutated["packet_bytes"] + f"\n{claim}\n".encode()
    packet_sha = builder.sha256_bytes(packet_payload)
    mutated["packet_bytes"] = packet_payload
    mutated["lineage"][packet_relative]["bytes"] = len(packet_payload)
    mutated["lineage"][packet_relative]["sha256"] = packet_sha
    mutated["input_snapshots"][packet_relative]["bytes"] = packet_payload
    mutated["input_snapshots"][packet_relative]["sha256"] = packet_sha
    review_audit["artifact"]["bytes"] = len(packet_payload)
    review_audit["artifact"]["sha256"] = packet_sha

    with pytest.raises(ValueError, match="rendered packet contains prohibited"):
        compute_from(mutated)


def test_final_audit_rebuilds_packet_from_captured_canonical_rows() -> None:
    inputs = builder.load_inputs(ROOT)
    mutated = copy.deepcopy(inputs)
    altered_triage = copy.deepcopy(mutated["csv"]["triage"])
    altered_triage[0]["expert_question_ko"] += " 재작성된 안전한 질문"
    packet_payload = packet_builder.build_from_rows(
        mutated["csv"]["expert_queue"],
        altered_triage,
    )["markdown"].encode("utf-8")
    assert packet_payload != mutated["packet_bytes"]

    review_audit = mutated["json"]["review_audit"]
    packet_relative = review_audit["artifact"]["path"]
    packet_sha = builder.sha256_bytes(packet_payload)
    mutated["packet_bytes"] = packet_payload
    mutated["lineage"][packet_relative]["bytes"] = len(packet_payload)
    mutated["lineage"][packet_relative]["sha256"] = packet_sha
    mutated["input_snapshots"][packet_relative]["bytes"] = packet_payload
    mutated["input_snapshots"][packet_relative]["sha256"] = packet_sha
    review_audit["artifact"]["bytes"] = len(packet_payload)
    review_audit["artifact"]["sha256"] = packet_sha

    with pytest.raises(ValueError, match="canonical render"):
        builder.analyze_review_packet(mutated)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("generator", "scripts/research/otc/not-the-review-generator.py"),
        ("generator_sha256", "0" * 64),
    ),
)
def test_final_audit_validates_review_packet_generator_lineage(
    field: str,
    value: str,
) -> None:
    inputs = builder.load_inputs(ROOT)
    inputs["json"]["review_audit"][field] = value

    with pytest.raises(ValueError, match="review packet generator"):
        builder.analyze_review_packet(inputs)


def test_final_audit_validates_review_triage_validator_lineage() -> None:
    inputs = builder.load_inputs(ROOT)
    packet_generator = builder.STATIC_INPUTS["review_packet_generator"]
    inputs["json"]["review_audit"]["generator_sha256"] = inputs["lineage"][
        packet_generator
    ]["sha256"]
    validator_path = "scripts/research/otc/validate_v51_shortlist_triage.py"
    inputs["json"]["review_audit"]["inputs"][validator_path]["sha256"] = (
        "0" * 64
    )

    with pytest.raises(ValueError, match="review triage validator"):
        builder.analyze_review_packet(inputs)


def test_final_audit_pins_canonical_review_packet_path() -> None:
    inputs = builder.load_inputs(ROOT)
    inputs["json"]["review_audit"]["artifact"]["path"] = (
        "research_v51/review/alternate_packet.md"
    )

    with pytest.raises(ValueError, match="review packet path"):
        builder.analyze_review_packet(inputs)


def test_boundary_verification_must_be_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = builder.load_inputs(ROOT)
    monkeypatch.setattr(
        builder.boundary_audit,
        "audit",
        lambda **_kwargs: {
            "valid": True,
            "verification_complete": False,
            "external_verification": {
                "requested": True,
                "required_artifacts": 2,
                "verified_artifacts": 0,
            },
        },
    )
    with pytest.raises(ValueError, match="verification_complete"):
        builder.validate_complete_boundary_verification(inputs)


def test_input_swap_after_compute_aborts_before_output_commit(tmp_path: Path) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    assert len(builder.check(package)) == 3

    protected_input.write_bytes(b"swapped-after-compute")
    with pytest.raises(ValueError, match="input changed after compute"):
        builder.write(package)

    assert protected_input.read_bytes() == b"swapped-after-compute"
    assert all(not path.exists() for path in builder.expected_outputs(package))
    assert list((tmp_path / builder.AUDIT_ROOT_RELATIVE).glob("*.tmp")) == []


def test_input_identity_change_with_same_bytes_aborts(tmp_path: Path) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    metadata = protected_input.stat()
    os.utime(
        protected_input,
        ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 2_000_000_000),
    )

    with pytest.raises(ValueError, match="input changed after compute"):
        builder.write(package)

    assert all(not path.exists() for path in builder.expected_outputs(package))


def test_output_swap_to_input_hardlink_aborts_without_overwrite(tmp_path: Path) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    assert len(builder.check(package)) == 3
    metrics_path = package["output_paths"]["final_metrics"]
    metrics_path.hardlink_to(protected_input)

    with pytest.raises(ValueError, match="must not be a hard link"):
        builder.write(package)

    assert protected_input.read_bytes() == b"protected-input"
    assert metrics_path.read_bytes() == b"protected-input"
    assert not package["output_paths"]["product_support_matrix"].exists()
    assert not package["output_paths"]["active_rule_matrix"].exists()


def test_write_atomically_replaces_existing_output_inodes(tmp_path: Path) -> None:
    package, _protected_input = minimal_write_package(tmp_path)
    prior_identities = {}
    for path in builder.expected_outputs(package):
        path.write_bytes(b"old-output")
        prior_identities[path] = (path.stat().st_dev, path.stat().st_ino)

    builder.write(package)

    for path, expected in builder.expected_outputs(package).items():
        assert path.read_bytes() == expected
        assert (path.stat().st_dev, path.stat().st_ino) != prior_identities[path]
    assert list((tmp_path / builder.AUDIT_ROOT_RELATIVE).glob("*.tmp")) == []


def test_write_holds_output_set_through_final_post_commit_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    old_payloads = {
        path: f"old-{index}".encode()
        for index, path in enumerate(builder.expected_outputs(package), 1)
    }
    for path, payload in old_payloads.items():
        path.write_bytes(payload)

    metrics_path = package["output_paths"]["final_metrics"]
    rule_path = package["output_paths"]["active_rule_matrix"]
    real_read = builder.safely_read_input
    rule_output_reads = 0
    attacked = False

    def swap_metrics_during_last_output_read(
        path: Path,
        root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal attacked, rule_output_reads
        snapshot = real_read(path, root, **kwargs)
        if (
            kwargs.get("role") == "output"
            and path == rule_path
            and snapshot["bytes"] == package["rule_matrix_bytes"]
        ):
            rule_output_reads += 1
            if not attacked and rule_output_reads == 2:
                metrics_path.unlink()
                os.link(protected_input, metrics_path)
                attacked = True
        return snapshot

    monkeypatch.setattr(builder, "safely_read_input", swap_metrics_during_last_output_read)

    with pytest.raises(
        ValueError,
        match="hard link|identity|aliases an input|input changed after compute",
    ):
        builder.write(package)

    assert attacked is True
    assert rule_output_reads == 2
    assert {path: path.read_bytes() for path in old_payloads} == old_payloads
    assert protected_input.read_bytes() == b"protected-input"


def test_write_revalidates_inputs_while_all_output_handles_are_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    old_payloads = {
        path: f"old-{index}".encode()
        for index, path in enumerate(builder.expected_outputs(package), 1)
    }
    for path, payload in old_payloads.items():
        path.write_bytes(payload)

    rule_path = package["output_paths"]["active_rule_matrix"]
    real_read = builder.safely_read_input
    rule_output_reads = 0
    attacked = False

    def mutate_input_during_second_rule_read(
        path: Path,
        root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal attacked, rule_output_reads
        snapshot = real_read(path, root, **kwargs)
        if (
            kwargs.get("role") == "output"
            and path == rule_path
            and snapshot["bytes"] == package["rule_matrix_bytes"]
        ):
            rule_output_reads += 1
            if not attacked and rule_output_reads == 2:
                protected_input.write_bytes(b"changed-during-post-commit-read")
                attacked = True
        return snapshot

    monkeypatch.setattr(builder, "safely_read_input", mutate_input_during_second_rule_read)

    with pytest.raises(ValueError, match="input changed after compute"):
        builder.write(package)

    assert attacked is True
    assert rule_output_reads == 2
    assert protected_input.read_bytes() == b"changed-during-post-commit-read"
    assert {path: path.read_bytes() for path in old_payloads} == old_payloads


def test_staged_path_swap_to_input_hardlink_is_detected_and_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    real_replace = os.replace
    attacked = False

    def swap_before_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal attacked
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not attacked
            and destination_path
            == package["output_paths"]["product_support_matrix"]
        ):
            source_path.unlink()
            os.link(protected_input, source_path)
            attacked = True
        real_replace(source_path, destination_path)

    monkeypatch.setattr(builder.os, "replace", swap_before_replace)

    with pytest.raises(ValueError, match="staged|post-replace"):
        builder.write(package)

    assert attacked is True
    assert protected_input.read_bytes() == b"protected-input"
    assert all(not path.exists() for path in builder.expected_outputs(package))
    assert list((tmp_path / builder.AUDIT_ROOT_RELATIVE).glob("*.tmp")) == []


def test_second_publish_failure_rolls_back_all_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, _protected_input = minimal_write_package(tmp_path)
    old_payloads = {
        path: f"old-{index}".encode()
        for index, path in enumerate(builder.expected_outputs(package), 1)
    }
    for path, payload in old_payloads.items():
        path.write_bytes(payload)

    real_replace = os.replace
    replace_count = 0

    def fail_second_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("injected second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(builder.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="injected second replace failure"):
        builder.write(package)

    assert replace_count >= 3
    assert {
        path: path.read_bytes() for path in old_payloads
    } == old_payloads
    assert list((tmp_path / builder.AUDIT_ROOT_RELATIVE).glob("*.tmp")) == []


def test_final_metrics_is_published_after_both_matrices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, _protected_input = minimal_write_package(tmp_path)
    real_replace = os.replace
    published: list[Path] = []

    def record_replace(source: str | Path, destination: str | Path) -> None:
        destination_path = Path(destination)
        real_replace(source, destination_path)
        if destination_path in builder.expected_outputs(package):
            published.append(destination_path)

    monkeypatch.setattr(builder.os, "replace", record_replace)
    builder.write(package)

    assert published == [
        package["output_paths"]["product_support_matrix"],
        package["output_paths"]["active_rule_matrix"],
        package["output_paths"]["final_metrics"],
    ]


def test_check_rejects_output_swapped_to_input_hardlink(tmp_path: Path) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    for path, payload in builder.expected_outputs(package).items():
        path.write_bytes(payload)
    metrics_path = package["output_paths"]["final_metrics"]
    metrics_path.unlink()
    os.link(protected_input, metrics_path)

    with pytest.raises(ValueError, match="hard link"):
        builder.check(package)

    assert protected_input.read_bytes() == b"protected-input"
    assert metrics_path.read_bytes() == b"protected-input"


def test_check_holds_all_outputs_through_coordinated_hardlink_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    for path, payload in builder.expected_outputs(package).items():
        path.write_bytes(payload)

    metrics_path = package["output_paths"]["final_metrics"]
    real_read = builder.safely_read_input
    attacked = False

    def swap_after_metrics_read(
        path: Path,
        root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal attacked
        snapshot = real_read(path, root, **kwargs)
        if (
            not attacked
            and kwargs.get("role") == "output"
            and path == metrics_path
        ):
            path.unlink()
            os.link(protected_input, path)
            attacked = True
        return snapshot

    monkeypatch.setattr(builder, "safely_read_input", swap_after_metrics_read)

    with pytest.raises(ValueError, match="hard link|identity|aliases an input"):
        builder.check(package)

    assert attacked is True
    assert protected_input.read_bytes() == b"protected-input"
    assert metrics_path.read_bytes() == b"protected-input"


def test_check_revalidates_outputs_after_final_boundary_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, protected_input = minimal_write_package(tmp_path)
    for path, payload in builder.expected_outputs(package).items():
        path.write_bytes(payload)

    metrics_path = package["output_paths"]["final_metrics"]
    real_boundary_check = builder.revalidate_package_boundary
    boundary_checks = 0
    attacked = False

    def swap_during_late_boundary_check(value: dict[str, object]) -> None:
        nonlocal boundary_checks, attacked
        boundary_checks += 1
        real_boundary_check(value)
        if boundary_checks == 2:
            metrics_path.unlink()
            os.link(protected_input, metrics_path)
            attacked = True

    monkeypatch.setattr(
        builder,
        "revalidate_package_boundary",
        swap_during_late_boundary_check,
    )

    with pytest.raises(ValueError, match="hard link|identity|aliases an input"):
        builder.check(package)

    assert boundary_checks == 2
    assert attacked is True
    assert protected_input.read_bytes() == b"protected-input"
    assert metrics_path.read_bytes() == b"protected-input"


def test_all_consumed_research_v3_inputs_are_protected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = builder.load_inputs(ROOT)
    product_path = "research_v3/otc/normalized/product_master.csv"
    mismatched_product = copy.deepcopy(inputs)
    mismatched_product["lineage"][product_path]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match=f"baseline {product_path} hash"):
        compute_from(mismatched_product)

    real_git_output = builder.git_output

    def mismatched_runtime_binding_blob(root: Path, *args: str) -> str:
        if (
            args[0] == "hash-object"
            and args[-1]
            == "research_v3/otc/rules/runtime_rule_bindings.csv"
        ):
            return "0" * 40
        return real_git_output(root, *args)

    monkeypatch.setattr(builder, "git_output", mismatched_runtime_binding_blob)
    with pytest.raises(ValueError, match="protected baseline blob"):
        compute_from(inputs)


def test_source_freshness_volatility_probe_is_fail_closed() -> None:
    inputs = builder.load_inputs(ROOT)
    observed = builder.analyze_source_freshness(inputs)
    assert observed["volatility_probe"] == {
        "pdf_bytes_stable": False,
        "semantic_text_stable": True,
        "interpretation": "volatile_pdf_bytes_same_extracted_text",
    }

    stable = copy.deepcopy(inputs)
    stable_probe = stable["json"]["source_freshness"]["volatilityProbe"]
    stable_probe["secondPdfSha256"] = stable_probe["firstPdfSha256"]
    stable_probe["pdfBytesStable"] = True
    stable_probe["interpretation"] = "no_byte_volatility_observed"
    assert builder.analyze_source_freshness(stable)["volatility_probe"][
        "pdf_bytes_stable"
    ] is True

    mutations = (
        ("url", "https://nedrug.mfds.go.kr/dsie/pdf/drb/999999999/NB"),
        ("interpretation", "contradicts_the_hashes"),
        ("pdfBytesStable", 0),
        ("semanticTextStable", 1),
        ("firstPdfSha256", "0" * 64),
        ("firstSemanticTextSha256", "0" * 64),
    )
    for field, value in mutations:
        invalid = copy.deepcopy(inputs)
        invalid["json"]["source_freshness"]["volatilityProbe"][field] = value
        with pytest.raises(ValueError):
            builder.analyze_source_freshness(invalid)


def test_output_payloads_are_deterministic_and_self_describing() -> None:
    first = builder.build(ROOT)
    second = builder.build(ROOT)

    assert first["metrics_bytes"] == second["metrics_bytes"]
    assert first["product_matrix_bytes"] == second["product_matrix_bytes"]
    assert first["rule_matrix_bytes"] == second["rule_matrix_bytes"]
    metrics = copy.deepcopy(first["metrics"])
    expected_hash = metrics["outputs"]["final_metrics"]["semantic_sha256"]
    metrics["outputs"]["final_metrics"]["semantic_sha256"] = ""
    assert builder.sha256_bytes(builder.canonical_json_payload(metrics)) == expected_hash
    assert metrics["computation_policy"]["ui_code_used"] is False
    protected = metrics["protected_baseline"]
    assert protected["worktree_clean"] is True
    assert protected["baseline_tree_oid"] == protected["head_tree_oid"]
    assert len(protected["consumed_inputs"]) == 5
    assert (
        "research_v3/otc/rules/runtime_rule_bindings.csv"
        in protected["consumed_inputs"]
    )
    freshness_path = "research_v51/audit/source_freshness_snapshot.json"
    freshness_generator_path = "scripts/research/otc/audit_v51_source_freshness.py"
    triage_validator_path = (
        "scripts/research/otc/validate_v51_shortlist_triage.py"
    )
    assert freshness_path in first["metrics"]["inputs"]
    assert freshness_generator_path in first["metrics"]["inputs"]
    assert triage_validator_path in first["metrics"]["inputs"]
    assert (
        first["metrics"]["v51"]["official_source_freshness"]["input_artifacts"]
        ["evidenceRuleLinks"]["sha256"]
        == first["metrics"]["inputs"][
            "research_v51/evidence/evidence_rule_links.csv"
        ]["sha256"]
    )
    assert not any(
        path.startswith("app/") or path.startswith("src/lib/")
        for path in first["metrics"]["inputs"]
    )


def test_check_detects_missing_and_changed_outputs(tmp_path: Path) -> None:
    package, _protected_input = minimal_write_package(tmp_path)
    assert len(builder.check(package)) == 3
    for path, payload in builder.expected_outputs(package).items():
        path.write_bytes(payload)
    assert builder.check(package) == []
    package["output_paths"]["final_metrics"].write_text("changed", encoding="utf-8")
    mismatches = builder.check(package)
    assert mismatches == [
        {
            "path": str(package["output_paths"]["final_metrics"]),
            "reason": "content_mismatch",
            "expected_sha256": builder.sha256_bytes(package["metrics_bytes"]),
            "observed_sha256": builder.sha256_bytes(b"changed"),
        }
    ]


def test_checked_in_outputs_match_generator() -> None:
    package = builder.build(ROOT)
    assert builder.check(package) == []
    metrics_path = ROOT / builder.METRICS_RELATIVE
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics == package["metrics"]
    assert metrics["valid"] is True
