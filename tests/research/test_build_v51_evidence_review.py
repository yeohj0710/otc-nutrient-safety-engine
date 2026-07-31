from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.research.otc import build_v51_evidence_review as builder


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "research_v51"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_preserves_all_candidates_and_status_boundaries() -> None:
    package = builder.build(ROOT)
    units = package["evidence_units"]
    links = package["evidence_rule_links"]
    queue = package["expert_review_queue"]

    assert len(units) == 328
    assert len(links) == 360
    assert len({row["evidence_candidate_id"] for row in links}) == 360
    assert sum(int(row["candidate_link_count"]) for row in units) == 360
    assert sum(row["duplicate_location"] == "true" for row in units) == 28
    assert len(queue) == 33
    assert {row["evidence_candidate_id"] for row in queue} == {
        row["evidence_candidate_id"]
        for row in links
        if row["evidence_status"] == "needs_expert_review"
    }
    assert Counter(row["evidence_status"] for row in links) == {
        "verified_primary": 15,
        "needs_expert_review": 33,
        "rejected": 4,
        "provisional": 308,
    }
    assert Counter(row["candidate_operational_status"] for row in links) == {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }
    assert Counter(
        row["evidence_status"]
        for row in links
        if row["candidate_operational_status"] == "inactive_candidate"
    ) == {
        "needs_expert_review": 33,
        "provisional": 308,
        "rejected": 4,
    }


def test_build_keeps_human_review_and_source_provenance_honest() -> None:
    links = builder.build(ROOT)["evidence_rule_links"]
    verified = [row for row in links if row["evidence_status"] == "verified_primary"]
    unverified = [row for row in links if row["evidence_status"] != "verified_primary"]
    rejected = [row for row in links if row["evidence_status"] == "rejected"]

    assert all(
        row["reviewer_id"] == "EXT-PHARM-001"
        and row["reviewer_role"] == "pharmacist_expert"
        and row["reviewed_at"]
        and row["recommendation"] == "recommended_primary"
        and row["referenced_rule_status"] == "released"
        and row["candidate_operational_status"]
        == "active_existing_released_primary_evidence"
        and row["reviewed_source_locator"]
        and row["reviewed_evidence_text"]
        and row["operational_source_locator"] == row["reviewed_source_locator"]
        and row["operational_evidence_text"] == row["reviewed_evidence_text"]
        for row in verified
    )
    assert all(
        not row["reviewer_id"]
        and not row["reviewer_role"]
        and not row["reviewed_at"]
        and row["candidate_operational_status"] == "inactive_candidate"
        and not row["reviewed_source_locator"]
        and not row["reviewed_evidence_text"]
        and not row["operational_source_locator"]
        and not row["operational_evidence_text"]
        for row in unverified
    )
    assert len(rejected) == 4
    assert all(
        row["candidate_id"] == "SAFE-OTC-13"
        and row["status_reason"] == "analysis_excluded_product"
        and row["analysis_exclusion_reason"] == "ambiguous_authorized_package_size"
        for row in rejected
    )
    assert all(
        row["source_url"].startswith("https://nedrug.mfds.go.kr/")
        and row["raw_candidate_source_locator"]
        and row["raw_candidate_evidence_text"]
        and row["source_version"] == f"sha256:{row['source_pdf_sha256']}"
        and len(row["source_pdf_sha256"]) == 64
        and len(row["source_page_text_sha256"]) == 64
        and row["retrieved_at"]
        and row["retrieved_at_utc"]
        and row["ingredient_names"]
        and row["ingredient_scope"]
        == "product_authorized_ingredient_set_not_excerpt_attribution"
        and row["rule_scope"]
        and row["referenced_runtime_condition"]
        and row["rule_message_ko"]
        and row["next_action_ko"]
        and row["referenced_code_link"].startswith("src/lib/otc/engine.ts:")
        for row in links
    )
    assert all(
        "rule_status" not in row
        and "runtime_condition" not in row
        and "current_code_link" not in row
        for row in links
    )
    overridden = [row for row in links if row["evidence_text_override"] == "true"]
    assert len(overridden) == 7
    assert all(row["evidence_text_override_reason"] for row in overridden)
    changed = [
        row for row in links if row["shortlist_changed_from_candidate"] == "true"
    ]
    assert [row["evidence_candidate_id"] for row in changed] == [
        "SAFE-OTC-01-NB-P2-B12-urgent_referral"
    ]
    rule_016 = next(
        row
        for row in verified
        if row["evidence_candidate_id"] == "SAFE-OTC-01-NB-P2-B12-urgent_referral"
    )
    assert rule_016["raw_candidate_source_locator"] == (
        "사용상의주의사항 PDF p.2, 문단 12"
    )
    assert rule_016["reviewed_source_locator"] == (
        "사용상의주의사항 PDF p.2, 문단 12-19"
    )
    assert rule_016["operational_source_locator"] == (
        "사용상의주의사항 PDF p.2, 문단 12-19"
    )
    assert rule_016["operational_evidence_text"] == rule_016["shortlist_evidence_text"]
    assert (
        rule_016["operational_evidence_text"] != rule_016["raw_candidate_evidence_text"]
    )


def test_expert_queue_never_prefills_human_decisions() -> None:
    queue = builder.build(ROOT)["expert_review_queue"]
    assert all(row["review_status"] == "needs_expert_review" for row in queue)
    assert all(
        row["candidate_operational_status"] == "inactive_candidate"
        and row["referenced_rule_status"]
        and row["referenced_runtime_condition"]
        and row["referenced_code_link"].startswith("src/lib/otc/engine.ts:")
        and row["raw_candidate_source_locator"]
        and row["raw_candidate_evidence_text"]
        and row["proposed_review_source_locator"]
        and row["proposed_review_evidence_text"]
        and not row["reviewed_source_locator"]
        and not row["reviewed_evidence_text"]
        and not row["operational_source_locator"]
        and not row["operational_evidence_text"]
        for row in queue
    )
    assert all(
        "rule_status" not in row
        and "current_runtime_condition" not in row
        and "current_code_link" not in row
        and "source_locator" not in row
        and "evidence_text" not in row
        for row in queue
    )
    assert all(
        not row["review_decision"]
        and not row["review_comment"]
        and not row["reviewer_id"]
        and not row["reviewer_role"]
        and not row["reviewed_at"]
        for row in queue
    )
    assert "reviewer_role" in builder.QUEUE_FIELDS
    primary = [row for row in queue if row["recommendation"] == "recommended_primary"]
    assert len(primary) == 1
    assert primary[0]["rule_id"] == "OTC-RULE-015"
    assert primary[0]["status_reason"] == "pharmacist_requested_revision"


def test_build_rejects_candidate_text_that_does_not_match_extracted_paragraph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_csv = builder.read_protected_csv

    def read_csv_with_tampered_candidate(
        root: Path, relative: str
    ) -> list[dict[str, str]]:
        rows = original_read_csv(root, relative)
        if Path(relative).name == "official_evidence_candidates.csv":
            rows[0]["evidence_text"] += " tampered"
        return rows

    monkeypatch.setattr(builder, "read_protected_csv", read_csv_with_tampered_candidate)
    with pytest.raises(
        ValueError, match="evidence text mismatch with extracted paragraph"
    ):
        builder.build(ROOT)


def test_build_rejects_candidate_locator_that_disagrees_with_candidate_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_csv = builder.read_protected_csv

    def read_csv_with_tampered_locator(
        root: Path, relative: str
    ) -> list[dict[str, str]]:
        rows = original_read_csv(root, relative)
        if Path(relative).name == "official_evidence_candidates.csv":
            prefix, _ = rows[0]["source_locator"].rsplit(" ", 1)
            rows[0]["source_locator"] = f"{prefix} 999"
        return rows

    monkeypatch.setattr(builder, "read_protected_csv", read_csv_with_tampered_locator)
    with pytest.raises(ValueError, match="candidate ID/source locator mismatch"):
        builder.build(ROOT)


def test_build_validates_product_and_source_url_on_every_candidate_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_csv = builder.read_protected_csv
    replacement = next(
        row
        for row in original_read_csv(
            ROOT, "research_v3/otc/normalized/product_master.csv"
        )
        if row["candidate_id"] == "SAFE-OTC-05"
    )

    def read_csv_with_cross_product_source(
        root: Path, relative: str
    ) -> list[dict[str, str]]:
        rows = original_read_csv(root, relative)
        if Path(relative).name == "official_evidence_candidates.csv":
            target = next(
                row
                for row in rows
                if row["evidence_candidate_id"] == "EXP-OTC-02-NB-P1-B3-alcohol"
            )
            target["candidate_id"] = replacement["candidate_id"]
            target["item_sequence"] = replacement["item_sequence"]
            target["product_name"] = replacement["product_name"]
        return rows

    monkeypatch.setattr(
        builder, "read_protected_csv", read_csv_with_cross_product_source
    )
    with pytest.raises(ValueError, match="candidate/source URL mismatch"):
        builder.build(ROOT)


def test_checked_in_v51_artifacts_match_builder() -> None:
    package = builder.build(ROOT)
    units_path = OUTPUT / "evidence" / "evidence_units.csv"
    links_path = OUTPUT / "evidence" / "evidence_rule_links.csv"
    queue_path = OUTPUT / "review" / "expert_review_queue.csv"
    inventory_path = OUTPUT / "audit" / "evidence_inventory.json"

    assert csv_rows(units_path) == package["evidence_units"]
    assert csv_rows(links_path) == package["evidence_rule_links"]
    assert csv_rows(queue_path) == package["expert_review_queue"]

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    expected_inventory = dict(package["manifest"])
    expected_inventory["artifacts"] = {
        str(path.relative_to(ROOT)).replace("\\", "/"): {
            "rows": len(package[name]),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "fields": fields,
        }
        for name, path, fields in (
            ("evidence_units", units_path, builder.UNIT_FIELDS),
            ("evidence_rule_links", links_path, builder.LINK_FIELDS),
            ("expert_review_queue", queue_path, builder.QUEUE_FIELDS),
        )
    }
    assert inventory == expected_inventory
    assert inventory["review_boundary"]["human_decisions_prefilled"] == 0
    assert inventory["review_boundary"]["expert_review_queue_human_fields"] == (
        builder.QUEUE_HUMAN_REVIEW_FIELDS
    )
    assert "reviewer_role" in inventory["review_boundary"]["reviewer_metadata_policy"]
    assert inventory["counts"]["shortlist_source_overlay_changes"] == 1
    assert inventory["counts"]["candidate_operational_status_counts"] == {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }
    assert inventory["counts"]["reviewed_primary_evidence_rows"] == 15
    assert inventory["counts"]["operational_evidence_rows"] == 15
    assert (
        inventory["review_boundary"]["expert_review_queue_operational_status"]
        == "inactive_candidate"
    )
    assert (
        inventory["review_boundary"]["existing_human_expert_verified_primary_rows"]
        == 15
    )
    assert inventory["review_boundary"]["new_human_expert_reviews"] == 0
    assert inventory["source_version_contract"]["source_version"].startswith(
        "SHA-256 identity of the archived local MFDS PDF bytes"
    )
    assert (
        "normalized extracted text"
        in inventory["source_version_contract"]["freshness_policy"]
    )
    assert inventory["generator_sha256"] == sha256(ROOT / inventory["generator"])
    assert inventory["schema_version"] == "1.1.0"
    assert inventory["source_lineage"] == "v5.0_pinned_baseline_git_blobs"
    helper = inventory["inputs"]["scripts/research/otc/audit_v51_boundaries.py"]
    assert helper == {
        "basis": "worktree_bytes",
        "bytes": (ROOT / "scripts/research/otc/audit_v51_boundaries.py").stat().st_size,
        "sha256": sha256(ROOT / "scripts/research/otc/audit_v51_boundaries.py"),
    }
    protected = inventory["inputs"][
        "research_v3/otc/rules/official_evidence_candidates.csv"
    ]
    assert protected["basis"] == "baseline_git_blob"
    assert protected["baseline_commit"] == builder.BASELINE_COMMIT
    assert protected["git_blob_oid"] == builder.boundary_audit.git_blob_oid(
        ROOT,
        builder.BASELINE_COMMIT,
        "research_v3/otc/rules/official_evidence_candidates.csv",
    )
    assert protected["bytes"] == 140382
    assert protected["sha256"] == (
        "28b152300b07f373e78786b9981994b5a1a7b23967e533e2f1219a568912ea7b"
    )
    assert inventory["provenance_verification"] == {
        "raw_pdf_bytes_rehashed": True,
        "extracted_page_text_rehashed": True,
        "candidate_product_identity_cross_checked": True,
        "candidate_document_url_cross_checked": True,
        "candidate_locator_id_cross_checked": True,
        "candidate_paragraphs_revalidated": True,
        "evidence_text_overrides_hash_checked": True,
    }
