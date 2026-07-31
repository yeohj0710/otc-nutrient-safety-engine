from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "otc" / "audit_v51_boundaries.py"
SPEC = importlib.util.spec_from_file_location("audit_v51_boundaries", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def make_boundary_repo(tmp_path: Path) -> tuple[Path, dict]:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Boundary Test")
    protected = tmp_path / "research_v3"
    protected.mkdir()
    (protected / "canonical.txt").write_text("frozen\n", encoding="utf-8")
    git(tmp_path, "add", "research_v3/canonical.txt")
    git(tmp_path, "commit", "-q", "-m", "baseline")
    commit = git(tmp_path, "rev-parse", "HEAD")
    tree = git(tmp_path, "rev-parse", "HEAD:research_v3")
    manifest = {
        "baseline": {"commit": commit},
        "boundary": {
            "protected_paths": [
                {"path": "research_v3", "baseline_tree_oid": tree}
            ]
        },
    }
    return tmp_path, manifest


def test_current_v50_boundary_and_manifest_counts_match() -> None:
    result = MODULE.audit(check_external=False)

    assert result["valid"] is True, result["errors"]
    assert result["verification_complete"] is False
    assert result["external_verification"] == {
        "requested": False,
        "required_artifacts": 2,
        "verified_artifacts": 0,
    }
    assert result["errors"] == []
    assert result["baseline_commit"] == "6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9"
    assert result["observed_counts"]["authorization_layer"]["analysis_products"] == 13
    assert result["observed_counts"]["candidate_evidence"][
        "shortlist_not_expert_verified"
    ] == 33
    assert result["observed_counts"]["v50_literature"]["direct_links"] == 10


def test_manifest_cannot_retarget_pinned_commit_tree_and_artifact_hashes(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    retargeted = deepcopy(manifest)
    different_commit = "cd63925b7b5fdec3ce1e7708ef5be89e992e3ed4"
    retargeted["baseline"]["commit"] = different_commit
    retargeted["baseline"]["short_commit"] = different_commit[:7]
    retargeted["boundary"]["protected_paths"][0]["baseline_tree_oid"] = (
        git(ROOT, "rev-parse", f"{different_commit}:research_v3")
    )
    for artifact in retargeted["core_artifacts"]:
        content = git_blob(ROOT, different_commit, artifact["path"])
        artifact["bytes"] = len(content)
        artifact["sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path = tmp_path / "retargeted-manifest.json"
    manifest_path.write_text(
        json.dumps(retargeted, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result = MODULE.audit(manifest_path=manifest_path, check_external=False)

    assert result["valid"] is False
    assert result["verification_complete"] is False
    assert result["baseline_commit"] == MODULE.EXPECTED_BASELINE_COMMIT
    assert any(
        error.startswith("MANIFEST_BASELINE_COMMIT_MISMATCH")
        for error in result["errors"]
    )
    assert any(
        error.startswith("MANIFEST_PROTECTED_PATHS_MISMATCH")
        for error in result["errors"]
    )
    assert any(
        error.startswith("MANIFEST_CONTRACT_DIGEST_MISMATCH")
        for error in result["errors"]
    )
    assert result["observed_counts"] == {}
    assert result["warnings"] == [
        "MANIFEST_DECLARATIONS_NOT_CONSUMED_UNTRUSTED_CONTRACT"
    ]


def test_manifest_captured_at_is_a_pinned_freshness_lower_bound(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["captured_at"] == "2026-07-31"
    assert MODULE.manifest_contract_errors(manifest) == []
    manifest["captured_at"] = "2026-08-01"
    manifest_path = tmp_path / "changed-captured-at.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    contract_errors = MODULE.manifest_contract_errors(manifest)
    result = MODULE.audit(manifest_path=manifest_path, check_external=False)

    assert any(
        error.startswith("MANIFEST_CAPTURED_AT_MISMATCH")
        for error in contract_errors
    )
    assert any(
        error.startswith("MANIFEST_CONTRACT_DIGEST_MISMATCH")
        for error in contract_errors
    )
    assert result["valid"] is False
    assert result["verification_complete"] is False
    assert result["observed_counts"] == {}


def test_missing_external_files_keep_local_audit_valid_but_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    missing_path = tmp_path / "unavailable-drive" / "thesis.pdf"
    missing_external = [
        {
            "path": str(missing_path),
            "drive_root": str(tmp_path / "unavailable-drive"),
            "bytes": 1,
            "sha256": "0" * 64,
        }
    ]
    manifest["external_canonical_artifacts"] = missing_external
    manifest_path = tmp_path / "missing-external-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.setattr(
        MODULE,
        "EXPECTED_CONTRACT_SHA256",
        MODULE.canonical_contract_sha256(manifest),
    )

    result = MODULE.audit(manifest_path=manifest_path, check_external=True)

    assert result["valid"] is True, result["errors"]
    assert result["verification_complete"] is False
    assert result["external_verification"] == {
        "requested": True,
        "required_artifacts": 1,
        "verified_artifacts": 0,
    }
    assert result["errors"] == []
    assert result["warnings"] == [
        f"EXTERNAL_ENVIRONMENT_UNAVAILABLE path={missing_path}"
    ]


def test_matching_external_file_marks_verification_complete(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    artifact_path = tmp_path / "thesis.pdf"
    artifact_path.write_bytes(b"canonical thesis")
    matching_external = [
        {
            "path": str(artifact_path),
            "drive_root": str(tmp_path),
            "bytes": artifact_path.stat().st_size,
            "sha256": MODULE.sha256(artifact_path),
        }
    ]
    manifest["external_canonical_artifacts"] = matching_external
    manifest_path = tmp_path / "matching-external-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    monkeypatch.setattr(
        MODULE,
        "EXPECTED_CONTRACT_SHA256",
        MODULE.canonical_contract_sha256(manifest),
    )

    result = MODULE.audit(manifest_path=manifest_path, check_external=True)

    assert result["valid"] is True, result["errors"]
    assert result["verification_complete"] is True
    assert result["external_verification"] == {
        "requested": True,
        "required_artifacts": 1,
        "verified_artifacts": 1,
    }
    assert result["errors"] == []
    assert result["warnings"] == []


def test_protected_worktree_change_fails(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "canonical.txt").write_text(
        "changed\n", encoding="utf-8"
    )

    errors = MODULE.git_boundary_errors(repo, manifest)

    assert any(error.startswith("PROTECTED_WORKTREE_DIRTY") for error in errors)


def test_protected_untracked_file_fails(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "new.txt").write_text("new\n", encoding="utf-8")

    errors = MODULE.git_boundary_errors(repo, manifest)

    assert any(error.startswith("PROTECTED_UNTRACKED_FILES") for error in errors)


def test_committed_protected_change_fails_against_baseline(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "canonical.txt").write_text(
        "changed\n", encoding="utf-8"
    )
    git(repo, "add", "research_v3/canonical.txt")
    git(repo, "commit", "-q", "-m", "change protected file")

    errors = MODULE.git_boundary_errors(repo, manifest)

    assert any(error.startswith("PROTECTED_HEAD_DIVERGED") for error in errors)


def test_contract_keeps_only_inherited_reviewed_evidence_operational() -> None:
    contract = (ROOT / "research_v51" / "protocol" / "README.md").read_text(
        encoding="utf-8"
    )
    normalized_contract = " ".join(contract.split())
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    inventory = json.loads(
        (ROOT / "research_v51" / "audit" / "evidence_inventory.json").read_text(
            encoding="utf-8"
        )
    )

    assert (
        "현재 `verified_primary` 15건은 v5.0에서 상속한 운영 근거다."
        in normalized_contract
    )
    assert "비활성 후보는 345건(33+308+4)이다." in normalized_contract
    assert (
        "v5.1에서 새로 수행한 사람 전문가 검토나 새로 활성화한 규칙·후보는 없다."
        in normalized_contract
    )
    assert (
        "`verified_primary`라는 일반적인 근거 라벨만으로 미래 후보의 사람 승인까지 "
        "증명할 수는 없다."
        in normalized_contract
    )
    assert "허가원문은 판정하고 문헌은 설명한다" in contract
    assert "`git push`, PR 생성, production 배포" in contract
    assert manifest["boundary"]["allowed_research_output_root"] == "research_v51"
    assert manifest["verified_counts"]["state"]["release_ready"] is False
    assert inventory["counts"]["status_counts"] == {
        "verified_primary": 15,
        "needs_expert_review": 33,
        "rejected": 4,
        "provisional": 308,
    }
    assert inventory["counts"]["candidate_operational_status_counts"] == {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }
    assert inventory["review_boundary"]["new_human_expert_reviews"] == 0
