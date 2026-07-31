#!/usr/bin/env python3
"""Read-only v5.1 boundary and v5.0 baseline audit.

The trust anchor is pinned in this module, not delegated to the mutable JSON
manifest.  The pinned digest commits to the capture date used as the freshness
lower bound, baseline metadata, preservation boundary, core artifact byte/hash
records, external artifact byte/hash records, and verified counts.  This
self-contained audit cannot detect a coordinated change to both this source
file and its tests, or replacement of the repository and Git object database;
that requires an independently stored signed attestation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO / "research_v51" / "audit" / "baseline_manifest.json"
DOSE_OR_INTERVAL_RULES = {"max_daily_dose", "minimum_interval"}
EXPECTED_BASELINE_COMMIT = "6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9"
EXPECTED_RESEARCH_V3_TREE_OID = "325001631c37e6fe8749a021c13a2ccc75bdf5b9"
EXPECTED_PROTECTED_PATH = "research_v3"
EXPECTED_CAPTURED_AT = "2026-07-31"
# SHA-256 of canonical JSON containing baseline, boundary, core_artifacts,
# external_canonical_artifacts, verified_counts, and captured_at. The date is
# the lower timestamp bound consumed by downstream freshness checks. This
# independently pins every declared contract value without treating the
# manifest as its own root of trust.
EXPECTED_CONTRACT_SHA256 = (
    "d11ce5b21dce902d7778ecac18d640215352a5f777e66c020985a5e14582b64b"
)
CONTRACT_KEYS = (
    "captured_at",
    "baseline",
    "boundary",
    "core_artifacts",
    "external_canonical_artifacts",
    "verified_counts",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_contract_sha256(manifest: dict[str, Any]) -> str:
    contract = {key: manifest.get(key) for key in CONTRACT_KEYS}
    payload = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def manifest_contract_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    observed_captured_at = manifest.get("captured_at")
    if observed_captured_at != EXPECTED_CAPTURED_AT:
        errors.append(
            "MANIFEST_CAPTURED_AT_MISMATCH "
            f"expected={EXPECTED_CAPTURED_AT} observed={observed_captured_at}"
        )

    baseline = manifest.get("baseline")
    observed_commit = baseline.get("commit") if isinstance(baseline, dict) else None
    if observed_commit != EXPECTED_BASELINE_COMMIT:
        errors.append(
            "MANIFEST_BASELINE_COMMIT_MISMATCH "
            f"expected={EXPECTED_BASELINE_COMMIT} observed={observed_commit}"
        )

    boundary = manifest.get("boundary")
    protected_paths = (
        boundary.get("protected_paths") if isinstance(boundary, dict) else None
    )
    expected_protected_paths = [
        {
            "path": EXPECTED_PROTECTED_PATH,
            "baseline_tree_oid": EXPECTED_RESEARCH_V3_TREE_OID,
        }
    ]
    if protected_paths != expected_protected_paths:
        errors.append(
            "MANIFEST_PROTECTED_PATHS_MISMATCH "
            f"expected={expected_protected_paths!r} observed={protected_paths!r}"
        )

    observed_digest = canonical_contract_sha256(manifest)
    if observed_digest != EXPECTED_CONTRACT_SHA256:
        errors.append(
            "MANIFEST_CONTRACT_DIGEST_MISMATCH "
            f"expected={EXPECTED_CONTRACT_SHA256} observed={observed_digest}"
        )
    return errors


def pinned_boundary_manifest() -> dict[str, Any]:
    return {
        "baseline": {"commit": EXPECTED_BASELINE_COMMIT},
        "boundary": {
            "protected_paths": [
                {
                    "path": EXPECTED_PROTECTED_PATH,
                    "baseline_tree_oid": EXPECTED_RESEARCH_V3_TREE_OID,
                }
            ]
        },
    }


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_value(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_boundary_errors(repo: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    baseline = manifest["baseline"]["commit"]

    resolved = run_git(repo, "rev-parse", f"{baseline}^{{commit}}")
    if resolved.returncode != 0:
        return [f"BASELINE_COMMIT_UNAVAILABLE commit={baseline}"]
    if resolved.stdout.strip() != baseline:
        errors.append(
            f"BASELINE_COMMIT_MISMATCH expected={baseline} observed={resolved.stdout.strip()}"
        )

    ancestor = run_git(repo, "merge-base", "--is-ancestor", baseline, "HEAD")
    if ancestor.returncode != 0:
        errors.append(f"BASELINE_NOT_ANCESTOR_OF_HEAD commit={baseline}")

    for protected in manifest["boundary"]["protected_paths"]:
        relative = protected["path"]
        expected_tree = protected["baseline_tree_oid"]

        baseline_tree = run_git(repo, "rev-parse", f"{baseline}:{relative}")
        if baseline_tree.returncode != 0:
            errors.append(f"PROTECTED_BASELINE_PATH_MISSING path={relative}")
            continue
        if baseline_tree.stdout.strip() != expected_tree:
            errors.append(
                "PROTECTED_BASELINE_TREE_MISMATCH "
                f"path={relative} expected={expected_tree} observed={baseline_tree.stdout.strip()}"
            )

        head_tree = run_git(repo, "rev-parse", f"HEAD:{relative}")
        if head_tree.returncode != 0:
            errors.append(f"PROTECTED_HEAD_PATH_MISSING path={relative}")
        elif head_tree.stdout.strip() != expected_tree:
            errors.append(
                "PROTECTED_HEAD_DIVERGED "
                f"path={relative} baseline_tree={expected_tree} head_tree={head_tree.stdout.strip()}"
            )

        tracked_status = run_git(
            repo, "status", "--porcelain=v1", "--untracked-files=no", "--", relative
        )
        if tracked_status.returncode != 0:
            errors.append(f"PROTECTED_STATUS_CHECK_FAILED path={relative}")
        elif tracked_status.stdout.strip():
            changed = " | ".join(tracked_status.stdout.splitlines())
            errors.append(f"PROTECTED_WORKTREE_DIRTY path={relative} files={changed}")

        untracked = run_git(
            repo, "ls-files", "--others", "--exclude-standard", "--", relative
        )
        if untracked.returncode != 0:
            errors.append(f"PROTECTED_UNTRACKED_CHECK_FAILED path={relative}")
        elif untracked.stdout.strip():
            paths = " | ".join(untracked.stdout.splitlines())
            errors.append(f"PROTECTED_UNTRACKED_FILES path={relative} files={paths}")

    return errors


def artifact_errors(repo: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = repo.resolve()
    for artifact in manifest["core_artifacts"]:
        path = (repo / artifact["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"CORE_ARTIFACT_OUTSIDE_REPO path={artifact['path']}")
            continue
        if not path.is_file():
            errors.append(f"CORE_ARTIFACT_MISSING path={artifact['path']}")
            continue
        observed_bytes = path.stat().st_size
        if observed_bytes != artifact["bytes"]:
            errors.append(
                "CORE_ARTIFACT_BYTES_MISMATCH "
                f"path={artifact['path']} expected={artifact['bytes']} observed={observed_bytes}"
            )
        observed_hash = sha256(path)
        if observed_hash != artifact["sha256"]:
            errors.append(
                "CORE_ARTIFACT_HASH_MISMATCH "
                f"path={artifact['path']} expected={artifact['sha256']} observed={observed_hash}"
            )
    return errors


def external_artifact_results(
    manifest: dict[str, Any], *, check_external: bool
) -> tuple[list[str], list[str], bool, int]:
    errors: list[str] = []
    warnings: list[str] = []
    verified_artifacts = 0
    for artifact in manifest["external_canonical_artifacts"]:
        if not check_external:
            warnings.append(f"EXTERNAL_ARTIFACT_CHECK_SKIPPED path={artifact['path']}")
            continue
        path = Path(artifact["path"])
        drive_root = Path(artifact["drive_root"])
        if not path.is_file():
            if os.name == "nt" and drive_root.exists():
                errors.append(f"EXTERNAL_CANONICAL_MISSING path={artifact['path']}")
            else:
                warnings.append(f"EXTERNAL_ENVIRONMENT_UNAVAILABLE path={artifact['path']}")
            continue
        observed_bytes = path.stat().st_size
        if observed_bytes != artifact["bytes"]:
            errors.append(
                "EXTERNAL_CANONICAL_BYTES_MISMATCH "
                f"path={artifact['path']} expected={artifact['bytes']} observed={observed_bytes}"
            )
        observed_hash = sha256(path)
        if observed_hash != artifact["sha256"]:
            errors.append(
                "EXTERNAL_CANONICAL_HASH_MISMATCH "
                f"path={artifact['path']} expected={artifact['sha256']} observed={observed_hash}"
            )
        if (
            observed_bytes == artifact["bytes"]
            and observed_hash == artifact["sha256"]
        ):
            verified_artifacts += 1
    verification_complete = (
        check_external
        and not errors
        and not warnings
        and verified_artifacts == len(manifest["external_canonical_artifacts"])
    )
    return errors, warnings, verification_complete, verified_artifacts


def baseline_runtime(repo: Path, commit: str) -> dict[str, Any]:
    payload = git_value(repo, "show", f"{commit}:src/generated/otc-runtime.json")
    return json.loads(payload)


def collect_counts(repo: Path, baseline_commit: str) -> dict[str, Any]:
    normalized = repo / "research_v3" / "otc" / "normalized"
    rules_root = repo / "research_v3" / "otc" / "rules"
    logs = repo / "research_v3" / "logs"

    products = read_csv(normalized / "product_master.csv")
    ingredients = read_csv(normalized / "ingredient_master.csv")
    product_ingredients = read_csv(normalized / "product_ingredient.csv")
    constraints = read_csv(normalized / "administration_constraints.csv")
    rules = read_csv(rules_root / "rules.csv")
    shortlist = read_csv(rules_root / "rule_evidence_shortlist.csv")
    candidates = read_csv(rules_root / "official_evidence_candidates.csv")

    product_status = Counter(row["analysis_status"] for row in products)
    rule_status = Counter(row["status"] for row in rules)
    shortlist_status = Counter(row["review_status"] for row in shortlist)
    candidate_status = Counter(row["review_status"] for row in candidates)
    selected_bindings = [
        row for row in product_ingredients if row["selected_for_calculation"].lower() == "true"
    ]

    runtime = baseline_runtime(repo, baseline_commit)
    product_rule_bindings = sum(
        len(product["supportedRuleTypes"]) for product in runtime["products"]
    )
    dose_only = sum(
        set(product["supportedRuleTypes"]) <= DOSE_OR_INTERVAL_RULES
        for product in runtime["products"]
    )

    link_manifest = load_json(
        repo
        / "research_v3"
        / "otc"
        / "literature"
        / "v5"
        / "downstream"
        / "literature_link_manifest.json"
    )["results"]
    direct_links = read_csv(
        repo
        / "research_v3"
        / "otc"
        / "literature"
        / "v5"
        / "downstream"
        / "supporting_literature.csv"
    )
    run = load_json(logs / "v50_run_report.json")
    scoring = load_json(logs / "v50_scoring_report.json")

    phase_a = run["phases"]["A"]["full_record"]
    phase_b = run["phases"]["B"]["full_record"]
    phase_c = run["phases"]["C"]
    adjudication = phase_c["semantic_adjudication_layer"]
    final = phase_c["final_layer"]["decision_distribution"]
    weighted = scoring["layers"]["overall"]["weighted_metrics"]

    return {
        "authorization_layer": {
            "product_master_rows": len(products),
            "analysis_products": product_status["included"],
            "ineligible_products": product_status["ineligible"],
            "excluded_products": product_status["excluded"],
            "ingredient_master_rows": len(ingredients),
            "calculation_ingredients": len(
                {row["ingredient_id"] for row in selected_bindings}
            ),
            "product_ingredient_rows": len(product_ingredients),
            "selected_product_ingredient_bindings": len(selected_bindings),
            "administration_constraints": len(constraints),
            "rules_total": len(rules),
            "rules_released": rule_status["released"],
            "rules_draft": rule_status["draft"],
        },
        "runtime_baseline_snapshot": {
            "products": len(runtime["products"]),
            "rules_released": runtime["rulesReleased"],
            "product_rule_bindings": product_rule_bindings,
            "dose_or_interval_only_products": dose_only,
            "disease_or_medication_capable_products": len(runtime["products"])
            - dose_only,
        },
        "candidate_evidence": {
            "shortlist_rows": len(shortlist),
            "shortlist_human_expert_verified": shortlist_status[
                "human_expert_verified"
            ],
            "shortlist_not_expert_verified": shortlist_status[
                "codex_recommended_not_expert_verified"
            ],
            "official_candidate_rows": len(candidates),
            "official_candidates_not_expert_verified": candidate_status[
                "codex_candidate_not_expert_verified"
            ],
        },
        "v50_literature": {
            "rules_total": link_manifest["rule_count"],
            "rules_with_direct_links": link_manifest["resolved_rule_count"],
            "rules_without_direct_links": link_manifest["unresolved_rule_count"],
            "direct_links": len(direct_links),
            "unique_linked_pmids": len({row["pmid"] for row in direct_links}),
            "rejected_candidates": link_manifest["rejected_candidate_count"],
            "not_in_v5_corpus": link_manifest["rejection_counts"][
                "not_in_v5_corpus"
            ],
            "no_retain_decision_for_rule_question": link_manifest[
                "rejection_counts"
            ]["no_retain_decision_for_rule_question"],
        },
        "v50_screening": {
            "pubmed_hits": phase_a["totals"][
                "hit_count_before_cross_question_deduplication"
            ],
            "unique_papers": phase_b["totals"]["evidence_map_rows_unique_papers"],
            "screening_units": phase_b["totals"][
                "question_membership_units_after_bibliographic_deduplication"
            ],
            "semantic_adjudication_rows": adjudication["reviewed_rows"],
            "semantic_disagreements": adjudication["disagreement_count"],
            "semantic_disagreement_rate": adjudication["disagreement_rate"],
            "final_retain": final["retain"],
            "final_deprioritize": final["deprioritize"],
            "final_uncertain": final["uncertain"],
        },
        "v50_scoring_ai_reference": {
            "sample_rows": scoring["layers"]["overall"]["sample_n"],
            "agreement_vs_ai_reference": weighted["agreement_vs_ai_reference"],
            "sensitivity_vs_ai_reference": weighted[
                "sensitivity_vs_ai_reference"
            ],
            "specificity_vs_ai_reference": weighted[
                "specificity_vs_ai_reference"
            ],
            "cohen_kappa_vs_ai_reference_weighted": weighted[
                "cohen_kappa_vs_ai_reference_weighted"
            ],
        },
        "state": {
            "human_reference_rows": run["state_flags"]["human_reference_rows"],
            "independent_blinding": run["state_flags"]["independent_blinding"],
            "semantic_adjudication_independent_blinding_ai": run["state_flags"][
                "semantic_adjudication_independent_blinding_ai"
            ],
            "release_ready": run["state_flags"]["release_ready"],
            "overall_execution_status": run["overall_execution_status"],
        },
    }


def compare_expected(expected: Any, observed: Any, prefix: str = "counts") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return [f"COUNT_TYPE_MISMATCH path={prefix}"]
        for key, value in expected.items():
            if key not in observed:
                errors.append(f"COUNT_MISSING path={prefix}.{key}")
                continue
            errors.extend(compare_expected(value, observed[key], f"{prefix}.{key}"))
        return errors
    if observed != expected:
        errors.append(
            f"COUNT_MISMATCH path={prefix} expected={expected!r} observed={observed!r}"
        )
    return errors


def audit(
    *,
    repo: Path = REPO,
    manifest_path: Path = DEFAULT_MANIFEST,
    check_external: bool = True,
) -> dict[str, Any]:
    repo = repo.resolve()
    manifest = load_json(manifest_path)
    contract_errors = manifest_contract_errors(manifest)
    errors = list(contract_errors)
    errors.extend(git_boundary_errors(repo, pinned_boundary_manifest()))
    warnings: list[str] = []
    verification_complete = False
    verified_external_artifacts = 0

    # Artifact and count declarations are safe to consume only after the
    # independently pinned contract digest matches.
    if not contract_errors:
        errors.extend(artifact_errors(repo, manifest))
        (
            external_errors,
            warnings,
            verification_complete,
            verified_external_artifacts,
        ) = external_artifact_results(manifest, check_external=check_external)
        errors.extend(external_errors)
    else:
        warnings.append("MANIFEST_DECLARATIONS_NOT_CONSUMED_UNTRUSTED_CONTRACT")

    observed_counts: dict[str, Any] = {}
    if not contract_errors:
        try:
            observed_counts = collect_counts(repo, EXPECTED_BASELINE_COMMIT)
            errors.extend(
                compare_expected(manifest["verified_counts"], observed_counts)
            )
        except (KeyError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"COUNT_RECOMPUTE_FAILED detail={exc}")

    return {
        "schema_version": "1.1.0",
        "audit": "v5.1_boundary_and_v5.0_baseline",
        "baseline_commit": EXPECTED_BASELINE_COMMIT,
        "valid": not errors,
        "verification_complete": verification_complete,
        "external_verification": {
            "requested": check_external,
            "required_artifacts": (
                len(manifest.get("external_canonical_artifacts", []))
                if not contract_errors
                else 0
            ),
            "verified_artifacts": verified_external_artifacts,
        },
        "errors": errors,
        "warnings": warnings,
        "observed_counts": observed_counts,
        "trust_limit": (
            "This audit cannot detect coordinated modification of its pinned "
            "source contract and tests, or replacement of the Git object database; "
            "an independently stored signed attestation is required for that threat."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--skip-external",
        action="store_true",
        help="G 드라이브 논문 검증을 건너뛰고 환경 경고만 남깁니다.",
    )
    args = parser.parse_args()
    result = audit(
        manifest_path=args.manifest.resolve(), check_external=not args.skip_external
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
