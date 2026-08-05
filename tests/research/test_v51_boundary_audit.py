from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import stat
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "otc" / "audit_v51_boundaries.py"
SPEC = importlib.util.spec_from_file_location("audit_v51_boundaries", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

LEGACY_LF_WORKTREE_INPUTS = (
    "research_v3/otc/normalized/administration_constraints.csv",
    "research_v3/otc/rules/evidence_text_overrides.csv",
    "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
    "research_v3/otc/literature/v5/downstream/supporting_literature.csv",
)
MIXED_EOL_BLOB_INPUTS = (
    "research_v3/otc/rules/rule_evidence_shortlist.csv",
    "research_v3/otc/rules/official_evidence_candidates.csv",
)


@pytest.mark.skipif(os.name != "nt", reason="Windows volume capability policy")
def test_zero_link_count_requires_a_volume_without_hardlink_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown_link_count = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=0)
    monkeypatch.setattr(
        MODULE, "_windows_volume_supports_hard_links", lambda _path: False
    )

    MODULE._validate_external_file_stat(
        unknown_link_count,
        source="test",
        path=tmp_path / "virtual-volume-file.pdf",
    )

    monkeypatch.setattr(
        MODULE, "_windows_volume_supports_hard_links", lambda _path: True
    )
    with pytest.raises(
        MODULE.ExternalSnapshotError,
        match="expected=1 observed=0",
    ):
        MODULE._validate_external_file_stat(
            unknown_link_count,
            source="test",
            path=tmp_path / "hardlink-capable-volume-file.pdf",
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows volume capability policy")
def test_zero_link_count_fails_closed_when_volume_policy_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown_link_count = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=0)

    def unavailable(_path: Path) -> bool:
        raise MODULE.ExternalSnapshotError(
            "EXTERNAL_CANONICAL_LINK_POLICY_UNAVAILABLE",
            "injected volume lookup failure",
        )

    monkeypatch.setattr(MODULE, "_windows_volume_supports_hard_links", unavailable)
    with pytest.raises(
        MODULE.ExternalSnapshotError,
        match="injected volume lookup failure",
    ):
        MODULE._validate_external_file_stat(
            unknown_link_count,
            source="test",
            path=tmp_path / "unknown-volume-file.pdf",
        )


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
            "protected_paths": [{"path": "research_v3", "baseline_tree_oid": tree}]
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
    assert (
        result["observed_counts"]["candidate_evidence"]["shortlist_not_expert_verified"]
        == 33
    )
    assert result["observed_counts"]["v50_literature"]["direct_links"] == 10


def test_only_legacy_lf_worktree_inputs_disable_checkout_conversion() -> None:
    inputs = (*LEGACY_LF_WORKTREE_INPUTS, *MIXED_EOL_BLOB_INPUTS)
    attributes = git(
        ROOT,
        "check-attr",
        "text",
        "--",
        *inputs,
    )
    observed = {
        path: value
        for path, attribute, value in (
            line.split(": ", maxsplit=2) for line in attributes.splitlines()
        )
        if attribute == "text"
    }

    assert observed == {
        **{path: "unset" for path in LEGACY_LF_WORKTREE_INPUTS},
        **{path: "unspecified" for path in MIXED_EOL_BLOB_INPUTS},
    }
    for path in LEGACY_LF_WORKTREE_INPUTS:
        filtered = git(ROOT, "hash-object", f"--path={path}", "--", path)
        raw = git(ROOT, "hash-object", "--no-filters", "--", path)
        assert filtered == raw, path


def test_core_artifact_contract_uses_pinned_git_blob_bytes() -> None:
    manifest = json.loads(
        (ROOT / "research_v51" / "audit" / "baseline_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    commit = manifest["baseline"]["commit"]

    for artifact in manifest["core_artifacts"]:
        payload = MODULE.git_blob_bytes(ROOT, commit, artifact["path"])
        assert len(payload) == artifact["bytes"]
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
        assert MODULE.git_blob_oid(ROOT, commit, artifact["path"]) == git(
            ROOT, "rev-parse", f"{commit}:{artifact['path']}"
        )


@pytest.mark.parametrize(
    ("commit", "relative"),
    [
        ("6dbdad5", "research_v3/otc/rules/rules.csv"),
        ("6DBDAD518E2FA7B2ED7B9A8048E0C47DBA5B6AE9", "research_v3/otc/rules/rules.csv"),
        (MODULE.EXPECTED_BASELINE_COMMIT, "../research_v3/otc/rules/rules.csv"),
        (MODULE.EXPECTED_BASELINE_COMMIT, "/research_v3/otc/rules/rules.csv"),
        (MODULE.EXPECTED_BASELINE_COMMIT, "research_v3\\otc\\rules\\rules.csv"),
        (MODULE.EXPECTED_BASELINE_COMMIT, "HEAD:research_v3/otc/rules/rules.csv"),
    ],
)
def test_git_blob_helpers_reject_ambiguous_revision_inputs(
    commit: str, relative: str
) -> None:
    with pytest.raises(ValueError):
        MODULE.git_blob_oid(ROOT, commit, relative)


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
    retargeted["boundary"]["protected_paths"][0]["baseline_tree_oid"] = git(
        ROOT, "rev-parse", f"{different_commit}:research_v3"
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
        error.startswith("MANIFEST_CAPTURED_AT_MISMATCH") for error in contract_errors
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


def test_external_directory_fails_regular_file_gate(tmp_path: Path) -> None:
    artifact_path = tmp_path / "thesis.pdf"
    artifact_path.mkdir()
    manifest = {
        "external_canonical_artifacts": [
            {
                "path": str(artifact_path),
                "drive_root": str(tmp_path),
                "bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            }
        ]
    }

    errors, warnings, complete, verified = MODULE.external_artifact_results(
        manifest, check_external=True
    )

    assert any(error.startswith("EXTERNAL_CANONICAL_NOT_REGULAR") for error in errors)
    assert warnings == []
    assert complete is False
    assert verified == 0


def test_external_hard_link_fails_single_link_gate(tmp_path: Path) -> None:
    artifact_path = tmp_path / "thesis.pdf"
    artifact_path.write_bytes(b"canonical thesis")
    os.link(artifact_path, tmp_path / "second-name.pdf")
    manifest = {
        "external_canonical_artifacts": [
            {
                "path": str(artifact_path),
                "drive_root": str(tmp_path),
                "bytes": artifact_path.stat().st_size,
                "sha256": MODULE.sha256(artifact_path),
            }
        ]
    }

    errors, warnings, complete, verified = MODULE.external_artifact_results(
        manifest, check_external=True
    )

    assert any(
        error.startswith("EXTERNAL_CANONICAL_LINK_COUNT_MISMATCH") for error in errors
    )
    assert warnings == []
    assert complete is False
    assert verified == 0


def test_windows_zero_native_link_count_requires_hard_link_unsupported_volume() -> None:
    MODULE._validate_windows_link_policy(
        native_count=0,
        hard_links_supported=False,
        stat_counts=(0, 0, 0, 0),
    )

    with pytest.raises(
        MODULE.ExternalSnapshotError,
        match="native link count is unavailable on a hard-link-capable volume",
    ):
        MODULE._validate_windows_link_policy(
            native_count=0,
            hard_links_supported=True,
            stat_counts=(0, 0, 0, 0),
        )


def test_windows_native_metadata_failure_fails_external_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    if os.name != "nt":
        pytest.skip("Windows native handle metadata is Windows-only")
    artifact_path = tmp_path / "thesis.pdf"
    canonical = b"canonical thesis"
    artifact_path.write_bytes(canonical)
    manifest = {
        "external_canonical_artifacts": [
            {
                "path": str(artifact_path),
                "drive_root": str(tmp_path),
                "bytes": len(canonical),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            }
        ]
    }

    def fail_native_metadata(*_args, **_kwargs):
        raise MODULE.ExternalSnapshotError(
            "EXTERNAL_CANONICAL_SNAPSHOT_FAILED",
            "phase=windows_native_metadata detail=simulated failure",
        )

    monkeypatch.setattr(MODULE, "_windows_external_handle_info", fail_native_metadata)

    errors, warnings, complete, verified = MODULE.external_artifact_results(
        manifest, check_external=True
    )

    assert errors == [
        "EXTERNAL_CANONICAL_SNAPSHOT_FAILED "
        f"path={artifact_path} "
        "detail=phase=windows_native_metadata detail=simulated failure"
    ]
    assert warnings == []
    assert complete is False
    assert verified == 0


def test_external_content_change_during_snapshot_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    artifact_path = tmp_path / "thesis.pdf"
    canonical = b"canonical thesis"
    artifact_path.write_bytes(canonical)
    manifest = {
        "external_canonical_artifacts": [
            {
                "path": str(artifact_path),
                "drive_root": str(tmp_path),
                "bytes": len(canonical),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            }
        ]
    }
    original_open = Path.open
    mutated = False

    class MutateAtEof:
        def __init__(self, stream) -> None:
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name: str):
            return getattr(self.stream, name)

        def read(self, *args):
            nonlocal mutated
            chunk = self.stream.read(*args)
            if chunk == b"" and not mutated:
                mutated = True
                artifact_path.write_bytes(b"tampered canonical thesis")
            return chunk

    def racing_open(self: Path, mode: str = "r", *args, **kwargs):
        stream = original_open(self, mode, *args, **kwargs)
        if self == artifact_path and mode == "rb" and not mutated:
            return MutateAtEof(stream)
        return stream

    monkeypatch.setattr(Path, "open", racing_open)

    errors, warnings, complete, verified = MODULE.external_artifact_results(
        manifest, check_external=True
    )

    assert mutated is True
    assert any(
        error.startswith("EXTERNAL_CANONICAL_SNAPSHOT_UNSTABLE") for error in errors
    )
    assert warnings == []
    assert complete is False
    assert verified == 0


def test_external_path_replacement_after_snapshot_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    artifact_path = tmp_path / "thesis.pdf"
    replacement_path = tmp_path / "replacement.pdf"
    canonical = b"canonical thesis"
    artifact_path.write_bytes(canonical)
    replacement_path.write_bytes(canonical)
    manifest = {
        "external_canonical_artifacts": [
            {
                "path": str(artifact_path),
                "drive_root": str(tmp_path),
                "bytes": len(canonical),
                "sha256": hashlib.sha256(canonical).hexdigest(),
            }
        ]
    }
    original_open = Path.open
    replaced = False

    class ReplaceAfterClose:
        def __init__(self, stream) -> None:
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            nonlocal replaced
            result = self.stream.__exit__(*args)
            os.replace(replacement_path, artifact_path)
            replaced = True
            return result

        def __getattr__(self, name: str):
            return getattr(self.stream, name)

    def racing_open(self: Path, mode: str = "r", *args, **kwargs):
        stream = original_open(self, mode, *args, **kwargs)
        if self == artifact_path and mode == "rb" and not replaced:
            return ReplaceAfterClose(stream)
        return stream

    monkeypatch.setattr(Path, "open", racing_open)

    errors, warnings, complete, verified = MODULE.external_artifact_results(
        manifest, check_external=True
    )

    assert replaced is True
    assert any(
        error.startswith("EXTERNAL_CANONICAL_IDENTITY_CHANGED") for error in errors
    )
    assert warnings == []
    assert complete is False
    assert verified == 0


def test_protected_worktree_change_fails(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "canonical.txt").write_text("changed\n", encoding="utf-8")

    errors = MODULE.git_boundary_errors(repo, manifest)

    assert any(error.startswith("PROTECTED_WORKTREE_DIRTY") for error in errors)


def test_protected_untracked_file_fails(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "new.txt").write_text("new\n", encoding="utf-8")

    errors = MODULE.git_boundary_errors(repo, manifest)

    assert any(error.startswith("PROTECTED_UNTRACKED_FILES") for error in errors)


def test_committed_protected_change_fails_against_baseline(tmp_path: Path) -> None:
    repo, manifest = make_boundary_repo(tmp_path)
    (repo / "research_v3" / "canonical.txt").write_text("changed\n", encoding="utf-8")
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
        "증명할 수는 없다." in normalized_contract
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
