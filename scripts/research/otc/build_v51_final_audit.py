from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    from scripts.research.otc import audit_v51_boundaries as boundary_audit
    from scripts.research.otc.audit_v51_source_freshness import (
        validate_freshness_snapshot,
    )
    from scripts.research.otc.build_v51_review_packet import (
        HUMAN_REVIEW_FIELDS as REVIEW_PACKET_HUMAN_REVIEW_FIELDS,
        build_from_rows as build_review_packet_from_rows,
        forbidden_claims_from_validator_bytes,
        validate_inactive_triage_claims,
        validate_rendered_packet_claims,
    )
except ModuleNotFoundError:  # Direct `python path/to/script.py` execution.
    import audit_v51_boundaries as boundary_audit
    from audit_v51_source_freshness import validate_freshness_snapshot
    from build_v51_review_packet import (
        HUMAN_REVIEW_FIELDS as REVIEW_PACKET_HUMAN_REVIEW_FIELDS,
        build_from_rows as build_review_packet_from_rows,
        forbidden_claims_from_validator_bytes,
        validate_inactive_triage_claims,
        validate_rendered_packet_claims,
    )


ROOT = Path(__file__).resolve().parents[3]
AUDIT_ROOT_RELATIVE = Path("research_v51/audit")
METRICS_RELATIVE = AUDIT_ROOT_RELATIVE / "final_metrics.json"
PRODUCT_MATRIX_RELATIVE = AUDIT_ROOT_RELATIVE / "product_support_matrix.csv"
RULE_MATRIX_RELATIVE = AUDIT_ROOT_RELATIVE / "active_rule_matrix.csv"
PROTECTED_INPUT_PREFIX = "research_v3/"
PORTABLE_VERIFICATION_SCOPE = "portable_repository"
EXTERNAL_VERIFICATION_SCOPE = "portable_repository_and_external_canonical_artifacts"

STATIC_INPUTS = {
    "baseline": "research_v51/audit/baseline_manifest.json",
    "evidence_inventory": "research_v51/audit/evidence_inventory.json",
    "triage": "research_v51/review/shortlist_semantic_triage.csv",
    "literature": "research_v51/literature/link_classification.csv",
    "literature_audit": (
        "research_v51/audit/literature_link_classification_audit.json"
    ),
    "review_audit": "research_v51/audit/review_packet_audit.json",
    "expert_packet": "research_v51/review/expert_review_packet.md",
    "review_packet_generator": ("scripts/research/otc/build_v51_review_packet.py"),
    "review_triage_validator": (
        "scripts/research/otc/validate_v51_shortlist_triage.py"
    ),
    "source_freshness": "research_v51/audit/source_freshness_snapshot.json",
    "source_freshness_generator": (
        "scripts/research/otc/audit_v51_source_freshness.py"
    ),
    "boundary_audit_generator": ("scripts/research/otc/audit_v51_boundaries.py"),
    "final_audit_generator": ("scripts/research/otc/build_v51_final_audit.py"),
    "runtime": "src/generated/otc-runtime.json",
    "rules": "research_v3/otc/rules/rules.csv",
    "runtime_bindings": "research_v3/otc/rules/runtime_rule_bindings.csv",
    "rule_shortlist": "research_v3/otc/rules/rule_evidence_shortlist.csv",
    "constraints": ("research_v3/otc/normalized/administration_constraints.csv"),
    "product_master": "research_v3/otc/normalized/product_master.csv",
}

PRODUCT_MATRIX_FIELDS = (
    "product_id",
    "item_sequence",
    "product_name",
    "authorization_status",
    "therapeutic_class",
    "support_tier",
    "historical_support_type_label_count",
    "historical_support_type_labels",
    "direct_released_rule_binding_count",
    "direct_released_rule_ids",
    "direct_released_rule_type_count",
    "direct_released_rule_types",
    "admin_derived_support_type_association_count",
    "admin_derived_support_type_labels",
    "dose_or_interval_label_count",
    "broader_safety_label_count",
    "administration_constraint_count",
    "administration_constraint_ids",
    "numeric_finding_decision_bases",
    "ingredient_count",
    "product_source_id",
    "product_source_url",
    "product_source_locator",
)

RULE_MATRIX_FIELDS = (
    "rule_id",
    "rule_type",
    "status",
    "severity",
    "scope",
    "lineage_status",
    "binding_category",
    "direct_product_binding_count",
    "direct_product_item_sequences",
    "applicability_json",
    "applicability_field_count",
    "source_evidence_count",
    "source_item_sequences",
    "source_ids",
    "source_versions",
    "source_urls",
    "source_locators_json",
    "source_evidence_json",
)

DOSE_OR_INTERVAL_TYPES = {"max_daily_dose", "minimum_interval"}
ADMIN_CONSTRAINT_TO_SUPPORT_TYPE = {
    "maximum_units_per_dose": "max_daily_dose",
    "maximum_doses_per_day": "max_daily_dose",
    "maximum_daily_ingredient_amount": "max_daily_dose",
    "minimum_interval_hours": "minimum_interval",
}
MFDS_PDF_PATTERN = re.compile(
    r"https://nedrug\.mfds\.go\.kr/dsie/pdf/drb/"
    r"(?P<item_sequence>[0-9]+)/(?:NB|UD)"
)
MFDS_PRODUCT_PATTERN = re.compile(
    r"https://nedrug\.mfds\.go\.kr/pbp/CCBBB01/getItemDetail\?"
    r"itemSeq=(?P<item_sequence>[0-9]+)"
)

APPLICABILITY_FIELDS = (
    ("product_item_sequences", "productItemSequences", "text_list"),
    ("ingredient_ids", "ingredientIds", "text_list"),
    ("pharmacologic_classes", "pharmacologicClasses", "text_list"),
    (
        "required_anchor_ingredient_ids",
        "requiredAnchorIngredientIds",
        "text_list",
    ),
    (
        "administration_constraint_types",
        "administrationConstraintTypes",
        "text_list",
    ),
    ("medication_terms", "medicationTerms", "text_list"),
    ("minimum_age_years", "minimumAgeYears", "integer"),
    ("pregnancy_trimesters", "pregnancyTrimesters", "integer_list"),
    ("lactation_supported", "lactationSupported", "boolean"),
    ("urgent_terms", "urgentTerms", "text_list"),
)


def parse_json(payload: bytes, path: Path) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def parse_csv(payload: bytes, path: Path) -> tuple[list[str], list[dict[str, str]]]:
    handle = io.StringIO(payload.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(handle)
    fields = reader.fieldnames or []
    if not fields:
        raise ValueError(f"CSV has no header: {path}")
    if len(fields) != len(set(fields)):
        raise ValueError(f"CSV has duplicate columns: {path}")
    return fields, list(reader)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def json_payload(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_json_payload(value: Any) -> bytes:
    return compact_json(value).encode("utf-8")


def csv_payload(fields: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def repo_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"input path leaves repository: {relative}") from exc
    return path


def file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def safely_read_input(
    path: Path,
    root: Path,
    *,
    require_single_link: bool = False,
    role: str = "input",
    hold_descriptor: bool = False,
) -> dict[str, Any]:
    """Read and identify one regular repository file through a single handle."""

    root = root.resolve()
    lexical = path.parent.resolve() / path.name
    try:
        lexical.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"input path leaves repository: {path}") from exc
    before = os.lstat(lexical)
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"final audit {role} must not be a symbolic link: {lexical}")
    if require_single_link and before.st_nlink != 1:
        raise ValueError(f"final audit {role} must not be a hard link: {lexical}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = (
        _open_delete_shared_read(lexical)
        if hold_descriptor
        else os.open(lexical, flags)
    )
    close_descriptor = True
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError(f"final audit {role} must be a regular file: {lexical}")
        if require_single_link and opened.st_nlink != 1:
            raise ValueError(f"final audit {role} must not be a hard link: {lexical}")
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError(f"final audit {role} changed while opening: {lexical}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read()
        after = os.fstat(descriptor)
        if require_single_link and after.st_nlink != 1:
            raise ValueError(f"final audit {role} must not be a hard link: {lexical}")
        if (
            file_identity(opened) != file_identity(after)
            or len(payload) != after.st_size
        ):
            raise ValueError(f"final audit {role} changed while reading: {lexical}")
        snapshot = {
            "path": lexical,
            "identity": file_identity(after),
            "bytes": payload,
            "sha256": sha256_bytes(payload),
        }
        if hold_descriptor:
            snapshot["descriptor"] = descriptor
            close_descriptor = False
        return snapshot
    finally:
        if close_descriptor:
            os.close(descriptor)


def revalidate_input_snapshots(package: dict[str, Any]) -> None:
    for relative, expected in package["input_snapshots"].items():
        observed = safely_read_input(expected["path"], package["root"])
        if (
            observed["identity"] != expected["identity"]
            or observed["sha256"] != expected["sha256"]
            or observed["bytes"] != expected["bytes"]
        ):
            raise ValueError(f"final audit input changed after compute: {relative}")


def require_output_paths(
    root: Path,
    metrics_path: Path,
    product_matrix_path: Path,
    rule_matrix_path: Path,
    *,
    input_paths: tuple[Path, ...] = (),
) -> None:
    root = root.resolve()
    allowed = root / AUDIT_ROOT_RELATIVE
    if allowed.resolve() != allowed or allowed.is_symlink():
        raise ValueError(f"final audit output directory must not be a link: {allowed}")
    paths = (metrics_path, product_matrix_path, rule_matrix_path)
    canonical = [
        root / METRICS_RELATIVE,
        root / PRODUCT_MATRIX_RELATIVE,
        root / RULE_MATRIX_RELATIVE,
    ]
    lexical = [path.parent.resolve() / path.name for path in paths]
    for path in lexical:
        try:
            path.relative_to(allowed)
        except ValueError as exc:
            raise ValueError(
                f"final audit output must stay under {allowed}: {path}"
            ) from exc
    if lexical != canonical:
        raise ValueError(
            "final audit outputs must use canonical paths and must not collide "
            f"with audit inputs: expected={canonical}, observed={lexical}"
        )
    for path in paths:
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"final audit output must not be a symbolic link: {path}")
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"final audit output must be a regular file: {path}")
        if metadata.st_nlink != 1:
            raise ValueError(f"final audit output must not be a hard link: {path}")
    existing_outputs = [path for path in paths if path.exists()]
    for index, path in enumerate(existing_outputs):
        for other in existing_outputs[index + 1 :]:
            if path.samefile(other):
                raise ValueError(f"final audit output aliases another output: {path}")
        for input_path in input_paths:
            if input_path.exists() and path.samefile(input_path):
                raise ValueError(f"final audit output aliases an input: {path}")


def file_lineage(
    snapshot: dict[str, Any],
    root: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": relative_path(snapshot["path"], root),
        "bytes": len(snapshot["bytes"]),
        "sha256": snapshot["sha256"],
    }
    if rows is not None:
        record["rows"] = len(rows)
    if fields is not None:
        record["fields"] = fields
    for field in ("basis", "baseline_commit", "git_blob_oid"):
        if field in snapshot:
            record[field] = snapshot[field]
    return record


def content_snapshot(
    raw_snapshot: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    """Select immutable baseline bytes for protected research_v3 content.

    The raw worktree snapshot remains the TOCTOU and aliasing view.  This
    second view makes parsing and lineage independent of checkout EOL policy.
    """

    relative = relative_path(raw_snapshot["path"], root)
    if not relative.startswith(PROTECTED_INPUT_PREFIX):
        return raw_snapshot
    baseline_commit = boundary_audit.EXPECTED_BASELINE_COMMIT
    payload = boundary_audit.git_blob_bytes(root, baseline_commit, relative)
    return {
        "path": raw_snapshot["path"],
        "bytes": payload,
        "sha256": sha256_bytes(payload),
        "basis": "baseline_git_blob",
        "baseline_commit": baseline_commit,
        "git_blob_oid": boundary_audit.git_blob_oid(
            root,
            baseline_commit,
            relative,
        ),
    }


def load_inputs(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    paths = {name: repo_path(root, value) for name, value in STATIC_INPUTS.items()}
    snapshots: dict[str, dict[str, Any]] = {}
    content_snapshots: dict[str, dict[str, Any]] = {}

    def capture(name: str, path: Path) -> None:
        raw_snapshot = safely_read_input(path, root)
        snapshots[name] = raw_snapshot
        content_snapshots[name] = content_snapshot(raw_snapshot, root)

    for name, path in paths.items():
        capture(name, path)

    baseline = parse_json(content_snapshots["baseline"]["bytes"], paths["baseline"])
    inventory = parse_json(
        content_snapshots["evidence_inventory"]["bytes"],
        paths["evidence_inventory"],
    )
    runtime = parse_json(content_snapshots["runtime"]["bytes"], paths["runtime"])
    literature_audit = parse_json(
        content_snapshots["literature_audit"]["bytes"],
        paths["literature_audit"],
    )
    review_audit = parse_json(
        content_snapshots["review_audit"]["bytes"], paths["review_audit"]
    )
    source_freshness = parse_json(
        content_snapshots["source_freshness"]["bytes"],
        paths["source_freshness"],
    )

    inventory_artifacts = inventory.get("artifacts", {})
    for name, relative in (
        ("evidence_units", "research_v51/evidence/evidence_units.csv"),
        ("evidence_links", "research_v51/evidence/evidence_rule_links.csv"),
        ("expert_queue", "research_v51/review/expert_review_queue.csv"),
    ):
        if relative not in inventory_artifacts:
            raise ValueError(f"evidence inventory artifact missing: {relative}")
        paths[name] = repo_path(root, relative)
        capture(name, paths[name])

    applicability = runtime.get("ruleApplicabilityProvenance", {})
    applicability_relative = applicability.get("path", "")
    if not applicability_relative:
        raise ValueError("runtime ruleApplicabilityProvenance.path is missing")
    paths["active_applicability"] = repo_path(root, applicability_relative)
    capture("active_applicability", paths["active_applicability"])

    freshness_pinned_texts: dict[str, bytes] = {}
    sources = source_freshness.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source freshness sources must be a list")
    for index, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            raise ValueError(f"source freshness row must be an object: {index}")
        relative = str(source.get("pinnedExtractedTextPath", ""))
        if not relative:
            raise ValueError(f"source freshness pinned text path is blank: {index}")
        path = repo_path(root, relative)
        name = f"freshness_pinned_text_{index:02d}"
        if relative in freshness_pinned_texts:
            raise ValueError(f"duplicate freshness pinned text path: {relative}")
        paths[name] = path
        capture(name, path)
        freshness_pinned_texts[relative] = content_snapshots[name]["bytes"]

    json_data = {
        "baseline": baseline,
        "evidence_inventory": inventory,
        "literature_audit": literature_audit,
        "review_audit": review_audit,
        "source_freshness": source_freshness,
        "runtime": runtime,
    }
    csv_names = (
        "triage",
        "literature",
        "rules",
        "runtime_bindings",
        "rule_shortlist",
        "constraints",
        "product_master",
        "evidence_units",
        "evidence_links",
        "expert_queue",
        "active_applicability",
    )
    csv_data: dict[str, list[dict[str, str]]] = {}
    csv_fields: dict[str, list[str]] = {}
    for name in csv_names:
        fields, rows = parse_csv(content_snapshots[name]["bytes"], paths[name])
        csv_fields[name] = fields
        csv_data[name] = rows

    lineage: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if name in csv_data:
            record = file_lineage(
                content_snapshots[name],
                root,
                rows=csv_data[name],
                fields=csv_fields[name],
            )
        else:
            record = file_lineage(content_snapshots[name], root)
        lineage[record["path"]] = record

    input_snapshots = {
        relative_path(snapshot["path"], root): snapshot
        for snapshot in snapshots.values()
    }
    if len(input_snapshots) != len(snapshots):
        raise ValueError("final audit input paths must be unique")

    return {
        "root": root,
        "paths": paths,
        "json": json_data,
        "csv": csv_data,
        "fields": csv_fields,
        "packet_bytes": content_snapshots["expert_packet"]["bytes"],
        "freshness_pinned_texts": freshness_pinned_texts,
        "input_snapshots": dict(sorted(input_snapshots.items())),
        "lineage": dict(sorted(lineage.items())),
    }


def require_fields(row: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        raise ValueError(f"missing fields for {label}: {missing}")


def require_nonblank(row: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    require_fields(row, fields, label)
    blank = [field for field in fields if not str(row[field]).strip()]
    if blank:
        raise ValueError(f"blank fields for {label}: {blank}")


def unique_by_key(
    rows: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, 1):
        value = str(row.get(key, "")).strip()
        if not value:
            raise ValueError(f"blank {key} in {label} row {index}")
        if value in output:
            raise ValueError(f"duplicate {key} in {label}: {value}")
        output[value] = row
    return output


def require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise ValueError(
            f"{label} mismatch: expected={expected!r}, observed={observed!r}"
        )


def require_mfds_pdf_source(
    row: dict[str, Any],
    label: str,
    *,
    item_key: str,
    url_key: str,
    locator_key: str,
) -> None:
    require_nonblank(row, (item_key, url_key, locator_key), label)
    match = MFDS_PDF_PATTERN.fullmatch(str(row[url_key]))
    if match is None:
        raise ValueError(f"invalid MFDS source URL for {label}: {row[url_key]}")
    if match.group("item_sequence") != str(row[item_key]):
        raise ValueError(
            f"MFDS source product mismatch for {label}: "
            f"item={row[item_key]}, url={row[url_key]}"
        )


def require_mfds_product_source(
    row: dict[str, Any],
    label: str,
    *,
    item_key: str,
    url_key: str,
    locator_key: str,
) -> None:
    require_nonblank(row, (item_key, url_key, locator_key), label)
    match = MFDS_PRODUCT_PATTERN.fullmatch(str(row[url_key]))
    if match is None:
        raise ValueError(f"invalid MFDS product URL for {label}: {row[url_key]}")
    if match.group("item_sequence") != str(row[item_key]):
        raise ValueError(
            f"MFDS product source mismatch for {label}: "
            f"item={row[item_key]}, url={row[url_key]}"
        )


def split_values(value: str) -> list[str]:
    return [item for item in value.split(";") if item]


def applicability_from_row(row: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source_field, runtime_field, value_type in APPLICABILITY_FIELDS:
        raw = row.get(source_field, "")
        if not raw:
            continue
        if value_type == "text_list":
            values = split_values(raw)
            if len(values) != len(set(values)):
                raise ValueError(
                    f"duplicate applicability values {source_field}: {raw}"
                )
            result[runtime_field] = values
        elif value_type == "integer_list":
            values = split_values(raw)
            if len(values) != len(set(values)):
                raise ValueError(
                    f"duplicate applicability values {source_field}: {raw}"
                )
            result[runtime_field] = [int(value) for value in values]
        elif value_type == "integer":
            result[runtime_field] = int(raw)
        elif value_type == "boolean":
            if raw not in {"true", "false"}:
                raise ValueError(f"invalid boolean applicability {source_field}: {raw}")
            result[runtime_field] = raw == "true"
        else:
            raise ValueError(f"unknown applicability value type: {value_type}")
    return result


def verify_inventory_artifact(
    inputs: dict[str, Any],
    name: str,
    relative: str,
) -> None:
    inventory = inputs["json"]["evidence_inventory"]
    expected = inventory["artifacts"].get(relative)
    if expected is None:
        raise ValueError(f"inventory artifact missing: {relative}")
    actual = inputs["lineage"][relative]
    for field in ("rows", "bytes", "sha256", "fields"):
        require_equal(actual.get(field), expected.get(field), f"{name}.{field}")


def analyze_evidence(inputs: dict[str, Any]) -> dict[str, Any]:
    csv_data = inputs["csv"]
    inventory = inputs["json"]["evidence_inventory"]
    units = csv_data["evidence_units"]
    links = csv_data["evidence_links"]
    queue = csv_data["expert_queue"]
    triage = csv_data["triage"]

    verify_inventory_artifact(
        inputs,
        "evidence_units",
        "research_v51/evidence/evidence_units.csv",
    )
    verify_inventory_artifact(
        inputs,
        "evidence_links",
        "research_v51/evidence/evidence_rule_links.csv",
    )
    verify_inventory_artifact(
        inputs,
        "expert_queue",
        "research_v51/review/expert_review_queue.csv",
    )

    unit_by_id = unique_by_key(units, "evidence_unit_id", "evidence units")
    link_by_id = unique_by_key(
        links,
        "evidence_candidate_id",
        "evidence rule links",
    )
    queue_by_id = unique_by_key(queue, "evidence_candidate_id", "expert queue")
    triage_by_id = unique_by_key(triage, "evidence_candidate_id", "triage")

    unit_locations: set[tuple[str, str]] = set()
    for unit_id, row in unit_by_id.items():
        require_mfds_pdf_source(
            row,
            f"evidence unit {unit_id}",
            item_key="item_sequence",
            url_key="source_url",
            locator_key="source_locator",
        )
        location = (row["source_url"], row["source_locator"])
        if location in unit_locations:
            raise ValueError(f"duplicate evidence unit source location: {location}")
        unit_locations.add(location)

    links_per_unit: Counter[str] = Counter()
    for candidate_id, row in link_by_id.items():
        require_mfds_pdf_source(
            row,
            f"evidence link {candidate_id}",
            item_key="item_sequence",
            url_key="source_url",
            locator_key="raw_candidate_source_locator",
        )
        require_nonblank(
            row,
            (
                "raw_candidate_evidence_text",
                "source_version",
                "source_pdf_sha256",
                "source_page_text_sha256",
                "candidate_operational_status",
            ),
            f"evidence link {candidate_id}",
        )
        require_equal(
            row["source_version"],
            f"sha256:{row['source_pdf_sha256']}",
            f"evidence link {candidate_id} source version",
        )
        unit_id = row["evidence_unit_id"]
        if unit_id not in unit_by_id:
            raise ValueError(
                f"evidence link references missing unit: {candidate_id} -> {unit_id}"
            )
        unit = unit_by_id[unit_id]
        for link_field, unit_field in (
            ("source_version", "source_version"),
            ("source_pdf_sha256", "source_pdf_sha256"),
            ("source_page_text_sha256", "source_page_text_sha256"),
            ("raw_candidate_source_locator", "source_locator"),
        ):
            require_equal(
                row[link_field],
                unit[unit_field],
                f"evidence link {candidate_id} unit provenance {link_field}",
            )
        links_per_unit[unit_id] += 1

    for unit_id, row in unit_by_id.items():
        require_equal(
            int(row["candidate_link_count"]),
            links_per_unit[unit_id],
            f"evidence unit {unit_id} candidate_link_count",
        )

    status_counts = Counter(row["evidence_status"] for row in links)
    operational_status_counts = Counter(
        row["candidate_operational_status"] for row in links
    )
    expected_counts = inventory["counts"]
    require_equal(len(units), expected_counts["evidence_units"], "evidence units")
    require_equal(len(links), expected_counts["evidence_rule_links"], "evidence links")
    require_equal(len(queue), expected_counts["expert_review_queue"], "expert queue")
    require_equal(
        dict(status_counts),
        expected_counts["status_counts"],
        "evidence status counts",
    )
    require_equal(
        dict(operational_status_counts),
        expected_counts["candidate_operational_status_counts"],
        "candidate operational status counts",
    )
    require_equal(
        inventory["review_boundary"]["human_decisions_prefilled"],
        0,
        "evidence inventory prefilled human decisions",
    )
    require_equal(
        inventory["review_boundary"].get("expert_review_queue_human_fields"),
        list(REVIEW_PACKET_HUMAN_REVIEW_FIELDS),
        "evidence inventory expert review human fields",
    )
    operational_contract = inventory["candidate_operational_status_contract"]
    require_equal(
        operational_status_counts["active_existing_released_primary_evidence"],
        operational_contract["active_count"],
        "inventory active candidate count",
    )
    require_equal(
        operational_status_counts["inactive_candidate"],
        operational_contract["inactive_count"],
        "inventory inactive candidate count",
    )
    require_equal(
        expected_counts["reviewed_primary_evidence_rows"],
        status_counts["verified_primary"],
        "reviewed primary evidence rows",
    )
    require_equal(
        expected_counts["operational_evidence_rows"],
        operational_status_counts["active_existing_released_primary_evidence"],
        "operational evidence rows",
    )

    needs_review_ids = {
        row["evidence_candidate_id"]
        for row in links
        if row["evidence_status"] == "needs_expert_review"
    }
    require_equal(set(queue_by_id), needs_review_ids, "expert queue IDs")
    require_equal(set(triage_by_id), needs_review_ids, "triage IDs")

    active_operational_ids: set[str] = set()
    for candidate_id, row in link_by_id.items():
        active = (
            row["candidate_operational_status"]
            == "active_existing_released_primary_evidence"
        )
        if active:
            active_operational_ids.add(candidate_id)
            require_equal(
                row["evidence_status"],
                "verified_primary",
                f"active evidence {candidate_id} review status",
            )
            require_equal(
                row["referenced_rule_status"],
                "released",
                f"active evidence {candidate_id} referenced rule status",
            )
            require_nonblank(
                row,
                (
                    "reviewed_source_locator",
                    "reviewed_evidence_text",
                    "operational_source_locator",
                    "operational_evidence_text",
                    "reviewer_id",
                    "reviewer_role",
                    "reviewed_at",
                ),
                f"active evidence {candidate_id}",
            )
            require_equal(
                row["operational_source_locator"],
                row["reviewed_source_locator"],
                f"active evidence {candidate_id} locator",
            )
            require_equal(
                row["operational_evidence_text"],
                row["reviewed_evidence_text"],
                f"active evidence {candidate_id} text",
            )
        else:
            require_equal(
                row["candidate_operational_status"],
                "inactive_candidate",
                f"inactive evidence {candidate_id} operational status",
            )
            if row["evidence_status"] == "verified_primary":
                raise ValueError(
                    f"verified primary evidence is operationally inactive: {candidate_id}"
                )
            inactive_values = [
                field
                for field in (
                    "reviewed_source_locator",
                    "reviewed_evidence_text",
                    "operational_source_locator",
                    "operational_evidence_text",
                    "reviewer_id",
                    "reviewer_role",
                    "reviewed_at",
                )
                if row[field]
            ]
            if inactive_values:
                raise ValueError(
                    f"inactive evidence has operational/reviewer fields: "
                    f"{candidate_id}={inactive_values}"
                )

    verified_primary_ids = {
        row["evidence_candidate_id"]
        for row in links
        if row["evidence_status"] == "verified_primary"
    }
    require_equal(
        active_operational_ids,
        verified_primary_ids,
        "active operational evidence IDs",
    )

    for candidate_id, row in queue_by_id.items():
        require_mfds_pdf_source(
            row,
            f"expert queue {candidate_id}",
            item_key="item_sequence",
            url_key="source_url",
            locator_key="proposed_review_source_locator",
        )
        require_nonblank(
            row,
            (
                "raw_candidate_source_locator",
                "raw_candidate_evidence_text",
                "proposed_review_source_locator",
                "proposed_review_evidence_text",
            ),
            f"expert queue {candidate_id}",
        )
        require_equal(
            row["review_status"],
            "needs_expert_review",
            f"expert queue {candidate_id} status",
        )
        require_equal(
            row["candidate_operational_status"],
            "inactive_candidate",
            f"expert queue {candidate_id} operational status",
        )
        require_fields(
            row,
            REVIEW_PACKET_HUMAN_REVIEW_FIELDS,
            f"expert queue {candidate_id}",
        )
        if any(
            row[field]
            for field in (
                "reviewed_source_locator",
                "reviewed_evidence_text",
                "operational_source_locator",
                "operational_evidence_text",
                *REVIEW_PACKET_HUMAN_REVIEW_FIELDS,
            )
        ):
            raise ValueError(f"expert queue has prefilled review: {candidate_id}")
        link = link_by_id[candidate_id]
        for queue_field, link_field in (
            ("evidence_unit_id", "evidence_unit_id"),
            ("rule_id", "rule_id"),
            ("rule_type", "rule_type"),
            ("referenced_rule_status", "referenced_rule_status"),
            ("referenced_runtime_condition", "referenced_runtime_condition"),
            ("referenced_code_link", "referenced_code_link"),
            ("candidate_operational_status", "candidate_operational_status"),
            ("raw_candidate_source_locator", "raw_candidate_source_locator"),
            ("raw_candidate_evidence_text", "raw_candidate_evidence_text"),
            ("current_rule_scope", "rule_scope"),
            ("source_id", "source_id"),
            ("source_url", "source_url"),
            ("source_version", "source_version"),
        ):
            require_equal(
                row[queue_field],
                link[link_field],
                f"expert queue {candidate_id} projection {queue_field}",
            )
        expected_review_locator = (
            link["shortlist_source_locator"] or link["raw_candidate_source_locator"]
        )
        expected_review_text = (
            link["shortlist_evidence_text"] or link["raw_candidate_evidence_text"]
        )
        require_equal(
            row["proposed_review_source_locator"],
            expected_review_locator,
            f"expert queue {candidate_id} proposed locator",
        )
        require_equal(
            row["proposed_review_evidence_text"],
            expected_review_text,
            f"expert queue {candidate_id} proposed text",
        )

    for candidate_id, row in triage_by_id.items():
        link = link_by_id[candidate_id]
        for triage_field, link_field in (
            ("rule_id", "rule_id"),
            ("rule_type", "rule_type"),
            ("product_name", "product_name"),
            ("item_sequence", "item_sequence"),
            ("current_scope", "rule_scope"),
        ):
            require_equal(
                row[triage_field],
                link[link_field],
                f"triage {candidate_id} {triage_field}",
            )

    triage_status = Counter(row["recommended_status"] for row in triage)
    semantic_relations = Counter(row["semantic_relation"] for row in triage)
    return {
        "evidence_units": len(units),
        "evidence_rule_links": len(links),
        "evidence_status_counts": dict(sorted(status_counts.items())),
        "candidate_operational_status_counts": dict(
            sorted(operational_status_counts.items())
        ),
        "operational_evidence_rows": len(active_operational_ids),
        "inactive_candidate_rows": len(links) - len(active_operational_ids),
        "legacy_human_expert_verified_links": status_counts["verified_primary"],
        "unique_products_including_excluded": len(
            {row["item_sequence"] for row in links}
        ),
        "triage_items": len(triage),
        "triage_recommended_status_counts": dict(sorted(triage_status.items())),
        "triage_semantic_relation_counts": dict(sorted(semantic_relations.items())),
        "evidence_source_urls_complete": True,
        "evidence_source_locators_complete": True,
    }


def analyze_literature(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = inputs["csv"]["literature"]
    audit = inputs["json"]["literature_audit"]
    by_id = unique_by_key(rows, "classification_id", "literature classifications")
    unique_by_key(rows, "source_link_id", "literature source links")

    seen_v50_links: set[str] = set()
    for classification_id, row in by_id.items():
        require_nonblank(
            row,
            ("pmid", "locator"),
            f"literature classification {classification_id}",
        )
        if not row["pmid"].isdigit():
            raise ValueError(
                f"invalid PubMed ID for {classification_id}: {row['pmid']}"
            )
        if row["lineage_status"] == "v50_emitted":
            v50_link_id = row["v50_link_id"]
            if not v50_link_id:
                raise ValueError(
                    f"emitted literature link has no v50 ID: {classification_id}"
                )
            if v50_link_id in seen_v50_links:
                raise ValueError(f"duplicate v50 literature link ID: {v50_link_id}")
            seen_v50_links.add(v50_link_id)
        require_equal(
            row["supports_rule_release"],
            "false",
            f"literature {classification_id} supports_rule_release",
        )
        require_equal(
            row["human_expert_reviewed"],
            "false",
            f"literature {classification_id} human_expert_reviewed",
        )
        expected_policy: tuple[str, str] | None = None
        if row["lineage_status"] == "v50_emitted":
            expected_policy = {
                "direct_match": ("direct", "true"),
                "mixed_scope": (
                    "direct_when_scope_matches_else_background",
                    "true",
                ),
                "background_context": ("background_only", "false"),
            }.get(row["semantic_classification"])
            if expected_policy is None:
                raise ValueError(
                    "unknown emitted literature semantic classification: "
                    f"{classification_id}={row['semantic_classification']}"
                )
        else:
            expected_policy = ("exclude_from_result_ui", "false")
            require_equal(
                row["semantic_classification"],
                "",
                f"excluded literature {classification_id} semantic classification",
            )
        require_equal(
            (row["ui_policy"], row["ui_direct_label_allowed"]),
            expected_policy,
            f"literature {classification_id} UI policy",
        )

    emitted = [row for row in rows if row["lineage_status"] == "v50_emitted"]
    excluded = [row for row in rows if row["ui_policy"] == "exclude_from_result_ui"]
    semantic = Counter(row["semantic_classification"] for row in emitted)
    direct_capable = [
        row for row in emitted if row["ui_direct_label_allowed"] == "true"
    ]
    counts = audit["counts"]
    require_equal(len(rows), counts["v4_candidate_rows"], "literature rows")
    require_equal(len(emitted), counts["v50_emitted_rows"], "emitted literature")
    require_equal(len(excluded), counts["v50_rejected_rows"], "excluded literature")
    require_equal(
        len({row["rule_id"] for row in emitted}),
        counts["v50_emitted_rule_count"],
        "emitted literature rules",
    )
    require_equal(
        dict(semantic),
        counts["semantic_classifications"],
        "literature semantic counts",
    )
    require_equal(audit["valid"], True, "literature audit valid")
    require_equal(
        audit["authority"]["human_expert_reviewed"],
        False,
        "literature audit human expert review",
    )
    require_equal(
        audit["authority"]["supports_rule_release"],
        False,
        "literature audit release authority",
    )
    output = audit["outputs"]["classification_csv"]
    literature_path = relative_path(inputs["paths"]["literature"], inputs["root"])
    require_equal(output["path"], literature_path, "literature output path")
    actual = inputs["lineage"][literature_path]
    require_equal(output["rows"], actual["rows"], "literature output rows")
    require_equal(output["sha256"], actual["sha256"], "literature output hash")

    pubmed_source_urls = sorted(
        {f"https://pubmed.ncbi.nlm.nih.gov/{row['pmid']}/" for row in rows}
    )
    return {
        "v50_emitted_links": len(emitted),
        "v50_emitted_rules": len({row["rule_id"] for row in emitted}),
        "direct_capable_links": len(direct_capable),
        "direct_match_links": semantic["direct_match"],
        "scope_qualified_direct_links": semantic["mixed_scope"],
        "background_only_links": semantic["background_context"],
        "excluded_legacy_links": len(excluded),
        "rejection_reason_counts": dict(
            sorted(counts["v50_rejection_reasons"].items())
        ),
        "human_expert_reviewed": sum(
            row["human_expert_reviewed"] == "true" for row in rows
        ),
        "supports_rule_release": sum(
            row["supports_rule_release"] == "true" for row in rows
        ),
        "source_locators_complete": True,
        "pubmed_source_urls_complete": True,
        "pubmed_source_url_template": "https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "pubmed_source_urls": pubmed_source_urls,
    }


def analyze_review_packet(inputs: dict[str, Any]) -> dict[str, Any]:
    validator_path = STATIC_INPUTS["review_triage_validator"]
    forbidden_claims = forbidden_claims_from_validator_bytes(
        inputs["input_snapshots"][validator_path]["bytes"]
    )
    for row in inputs["csv"]["triage"]:
        validate_inactive_triage_claims(
            row,
            forbidden_claims=forbidden_claims,
        )
    try:
        packet_text = inputs["packet_bytes"].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("review packet must be UTF-8") from error
    validate_rendered_packet_claims(
        packet_text,
        forbidden_claims=forbidden_claims,
    )

    expected_packet = build_review_packet_from_rows(
        inputs["csv"]["expert_queue"],
        inputs["csv"]["triage"],
        forbidden_claims=forbidden_claims,
    )
    expected_packet_bytes = expected_packet["markdown"].encode("utf-8")
    require_equal(
        inputs["packet_bytes"],
        expected_packet_bytes,
        "review packet canonical render",
    )

    audit = inputs["json"]["review_audit"]
    counts = audit["counts"]
    activation = audit["activation_boundary"]
    artifact = audit["artifact"]
    packet_path = relative_path(inputs["paths"]["expert_packet"], inputs["root"])
    require_equal(artifact["path"], packet_path, "review packet path")
    generator_path = STATIC_INPUTS["review_packet_generator"]
    require_equal(
        audit.get("generator"),
        generator_path,
        "review packet generator path",
    )
    require_equal(
        audit.get("generator_sha256"),
        inputs["lineage"][generator_path]["sha256"],
        "review packet generator sha256",
    )
    require_equal(
        artifact["bytes"],
        len(inputs["packet_bytes"]),
        "review packet bytes",
    )
    require_equal(
        artifact["sha256"],
        sha256_bytes(inputs["packet_bytes"]),
        "review packet hash",
    )
    require_equal(
        counts,
        expected_packet["summary"],
        "review packet canonical counts",
    )

    for source_name in ("triage", "expert_queue"):
        path = relative_path(inputs["paths"][source_name], inputs["root"])
        expected = audit["inputs"].get(path)
        if expected is None:
            raise ValueError(f"review audit input missing: {path}")
        actual = inputs["lineage"][path]
        require_equal(expected["bytes"], actual["bytes"], f"{source_name} bytes")
        require_equal(expected["sha256"], actual["sha256"], f"{source_name} hash")
        require_equal(expected["rows"], actual["rows"], f"{source_name} rows")
        require_equal(
            expected["fields"],
            actual["fields"],
            f"{source_name} fields",
        )

    inventory_path = STATIC_INPUTS["evidence_inventory"]
    expected_inventory = audit["inputs"].get(inventory_path)
    if expected_inventory is None:
        raise ValueError(f"review audit input missing: {inventory_path}")
    actual_inventory = inputs["lineage"][inventory_path]
    require_equal(
        expected_inventory.get("bytes"),
        actual_inventory["bytes"],
        "review evidence inventory bytes",
    )
    require_equal(
        expected_inventory.get("sha256"),
        actual_inventory["sha256"],
        "review evidence inventory sha256",
    )

    expected_generator = audit["inputs"].get(generator_path)
    if expected_generator is None:
        raise ValueError(f"review audit input missing: {generator_path}")
    actual_generator = inputs["lineage"][generator_path]
    require_equal(
        expected_generator.get("bytes"),
        actual_generator["bytes"],
        "review packet generator bytes",
    )
    require_equal(
        expected_generator.get("sha256"),
        actual_generator["sha256"],
        "review packet generator input sha256",
    )

    expected_validator = audit["inputs"].get(validator_path)
    if expected_validator is None:
        raise ValueError(f"review audit input missing: {validator_path}")
    actual_validator = inputs["lineage"][validator_path]
    require_equal(
        expected_validator.get("bytes"),
        actual_validator["bytes"],
        "review triage validator bytes",
    )
    require_equal(
        expected_validator.get("sha256"),
        actual_validator["sha256"],
        "review triage validator sha256",
    )

    require_equal(counts["packet_items"], 33, "review packet items")
    require_equal(counts["unique_candidate_ids"], 33, "review packet unique IDs")
    require_equal(counts["human_review_prefilled"], 0, "prefilled reviews")
    require_equal(counts["activated_items"], 0, "activated review items")
    require_equal(activation["activated_items"], 0, "activation boundary")
    require_equal(
        activation["human_expert_verification_required"],
        True,
        "human expert verification boundary",
    )
    require_equal(
        audit["checks"].get("all_human_review_fields_blank"),
        True,
        "review packet blank human review fields",
    )
    require_equal(
        activation.get("required_human_review_fields"),
        list(REVIEW_PACKET_HUMAN_REVIEW_FIELDS),
        "review packet required human review fields",
    )
    queue = inputs["csv"]["expert_queue"]
    queue_operational_counts = Counter(
        row["candidate_operational_status"] for row in queue
    )
    activated_items = sum(
        row["candidate_operational_status"] != "inactive_candidate" for row in queue
    )
    inactive_candidate_items = queue_operational_counts["inactive_candidate"]
    human_review_prefilled = sum(
        any(row[field] for field in REVIEW_PACKET_HUMAN_REVIEW_FIELDS) for row in queue
    )
    require_equal(counts["queue_rows"], len(queue), "review packet queue rows")
    require_equal(
        counts["candidate_operational_status_counts"],
        dict(sorted(queue_operational_counts.items())),
        "review packet operational status counts",
    )
    require_equal(
        activation["candidate_operational_status_counts"],
        dict(sorted(queue_operational_counts.items())),
        "review activation operational status counts",
    )
    require_equal(
        counts["activated_items"], activated_items, "review packet activated items"
    )
    require_equal(
        activation["activated_items"],
        activated_items,
        "review activation activated items",
    )
    require_equal(
        counts["inactive_candidate_items"],
        inactive_candidate_items,
        "review packet inactive candidate items",
    )
    require_equal(
        activation["inactive_candidate_items"],
        inactive_candidate_items,
        "review activation inactive candidate items",
    )
    require_equal(
        counts["human_review_prefilled"],
        human_review_prefilled,
        "review packet human review prefill",
    )
    require_equal(
        counts["recommended_status_counts"],
        dict(
            sorted(
                Counter(
                    row["recommended_status"] for row in inputs["csv"]["triage"]
                ).items()
            )
        ),
        "review packet recommended status counts",
    )
    require_equal(
        counts["semantic_relation_counts"],
        dict(
            sorted(
                Counter(
                    row["semantic_relation"] for row in inputs["csv"]["triage"]
                ).items()
            )
        ),
        "review packet semantic relation counts",
    )
    return {
        "packet_items": counts["packet_items"],
        "unique_candidate_ids": counts["unique_candidate_ids"],
        "new_human_expert_reviews": counts["human_review_prefilled"],
        "activated_items": counts["activated_items"],
        "candidate_operational_status_counts": dict(
            sorted(queue_operational_counts.items())
        ),
        "human_expert_verification_required": True,
        "required_human_review_fields": list(REVIEW_PACKET_HUMAN_REVIEW_FIELDS),
        "items_with_required_regression_tests": counts[
            "items_with_required_regression_tests"
        ],
    }


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def validate_baseline_hashes(inputs: dict[str, Any]) -> dict[str, Any]:
    baseline = inputs["json"]["baseline"]
    by_path = {record["path"]: record for record in baseline["core_artifacts"]}
    root = inputs["root"]
    baseline_commit = boundary_audit.EXPECTED_BASELINE_COMMIT
    require_equal(
        baseline["baseline"]["commit"],
        baseline_commit,
        "manifest/pinned baseline commit",
    )
    if re.fullmatch(r"[0-9a-f]{40}", baseline_commit) is None:
        raise ValueError(f"invalid baseline commit: {baseline_commit}")

    protected_records = {
        record["path"]: record for record in baseline["boundary"]["protected_paths"]
    }
    require_equal(
        set(protected_records),
        {"research_v3"},
        "baseline protected path set",
    )
    recorded_tree_oid = protected_records["research_v3"]["baseline_tree_oid"]
    baseline_tree_oid = git_output(root, "rev-parse", f"{baseline_commit}:research_v3")
    require_equal(
        baseline_tree_oid,
        recorded_tree_oid,
        "baseline research_v3 tree OID",
    )
    head_tree_oid = git_output(root, "rev-parse", "HEAD:research_v3")
    require_equal(
        head_tree_oid,
        baseline_tree_oid,
        "HEAD/baseline research_v3 tree OID",
    )
    protected_status = git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "research_v3",
    )
    require_equal(protected_status, "", "research_v3 worktree status")

    consumed: dict[str, dict[str, Any]] = {}
    for name in (
        "rules",
        "rule_shortlist",
        "constraints",
        "product_master",
        "runtime_bindings",
    ):
        path = relative_path(inputs["paths"][name], inputs["root"])
        actual = inputs["lineage"][path]
        require_equal(
            actual.get("basis"),
            "baseline_git_blob",
            f"baseline blob basis {path}",
        )
        require_equal(
            actual.get("baseline_commit"),
            baseline_commit,
            f"baseline blob commit {path}",
        )
        if name != "runtime_bindings":
            expected = by_path.get(path)
            if expected is None:
                raise ValueError(f"baseline core artifact missing: {path}")
            require_equal(actual["bytes"], expected["bytes"], f"baseline {path} bytes")
            require_equal(actual["sha256"], expected["sha256"], f"baseline {path} hash")

        baseline_blob_oid = boundary_audit.git_blob_oid(
            root,
            baseline_commit,
            path,
        )
        baseline_blob = boundary_audit.git_blob_bytes(
            root,
            baseline_commit,
            path,
        )
        require_equal(
            actual.get("git_blob_oid"),
            baseline_blob_oid,
            f"baseline blob OID {path}",
        )
        require_equal(
            actual["bytes"],
            len(baseline_blob),
            f"baseline blob bytes {path}",
        )
        require_equal(
            actual["sha256"],
            sha256_bytes(baseline_blob),
            f"baseline blob hash {path}",
        )
        consumed[path] = {
            "bytes": actual["bytes"],
            "sha256": actual["sha256"],
            "basis": actual["basis"],
            "baseline_commit": actual["baseline_commit"],
            "git_blob_oid": baseline_blob_oid,
        }

    return {
        "path": "research_v3",
        "baseline_commit": baseline_commit,
        "baseline_tree_oid": baseline_tree_oid,
        "head_tree_oid": head_tree_oid,
        "worktree_clean": True,
        "consumed_inputs": dict(sorted(consumed.items())),
    }


def declared_external_paths(inputs: dict[str, Any]) -> tuple[str, ...]:
    artifacts = inputs["json"]["baseline"].get("external_canonical_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("baseline external_canonical_artifacts must be a list")
    paths: list[str] = []
    for index, artifact in enumerate(artifacts, 1):
        if not isinstance(artifact, dict) or not str(artifact.get("path", "")):
            raise ValueError(f"invalid external artifact declaration: {index}")
        paths.append(str(artifact["path"]))
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate external artifact declaration")
    return tuple(paths)


def require_boundary_result(
    result: dict[str, Any],
    *,
    require_external: bool,
    external_paths: tuple[str, ...],
) -> dict[str, Any]:
    require_equal(result.get("valid"), True, "boundary audit valid")
    require_equal(result.get("errors"), [], "boundary errors")
    external = result.get("external_verification")
    if not isinstance(external, dict):
        raise ValueError("boundary audit external_verification must be an object")
    require_equal(
        external.get("required_artifacts"),
        len(external_paths),
        "boundary external required artifacts",
    )

    if require_external:
        require_equal(
            result.get("verification_complete"),
            True,
            "boundary audit verification_complete",
        )
        require_equal(external.get("requested"), True, "boundary external requested")
        require_equal(
            external.get("verified_artifacts"),
            len(external_paths),
            "boundary external verified artifacts",
        )
        require_equal(result.get("warnings"), [], "boundary warnings")
    else:
        require_equal(
            result.get("verification_complete"),
            False,
            "boundary audit portable verification_complete",
        )
        require_equal(
            external.get("requested"),
            False,
            "boundary external requested",
        )
        require_equal(
            external.get("verified_artifacts"),
            0,
            "boundary external verified artifacts",
        )
        expected_warnings = [
            f"EXTERNAL_ARTIFACT_CHECK_SKIPPED path={path}" for path in external_paths
        ]
        require_equal(result.get("warnings"), expected_warnings, "boundary warnings")

    # This record is embedded in final_metrics.json, so it deliberately states
    # the portable invariant and policy rather than the invocation's live mode.
    return {
        "valid": True,
        "verification_scope": PORTABLE_VERIFICATION_SCOPE,
        "portable_repository_verified": True,
        "external_artifacts_declared": len(external_paths),
        "external_artifacts_required_for_final_local_report": True,
    }


def validate_boundary_verification(
    inputs: dict[str, Any],
    *,
    require_external: bool,
) -> dict[str, Any]:
    external_paths = declared_external_paths(inputs)
    result = boundary_audit.audit(
        repo=inputs["root"],
        manifest_path=inputs["paths"]["baseline"],
        check_external=require_external,
    )
    return require_boundary_result(
        result,
        require_external=require_external,
        external_paths=external_paths,
    )


def require_complete_boundary_result(result: dict[str, Any]) -> dict[str, Any]:
    external = result.get("external_verification")
    if not isinstance(external, dict):
        raise ValueError("boundary audit external_verification must be an object")
    required_artifacts = external.get("required_artifacts")
    if not isinstance(required_artifacts, int) or required_artifacts < 0:
        raise ValueError("boundary external required_artifacts must be nonnegative")
    return require_boundary_result(
        result,
        require_external=True,
        external_paths=tuple(str(index) for index in range(required_artifacts)),
    )


def validate_complete_boundary_verification(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compatibility entry point for the explicit full external gate."""

    return validate_boundary_verification(inputs, require_external=True)


def revalidate_package_boundary(package: dict[str, Any]) -> None:
    manifest_path = package.get("boundary_manifest_path")
    if manifest_path is None:
        return
    result = boundary_audit.audit(
        repo=package["root"],
        manifest_path=manifest_path,
        check_external=package["require_external"],
    )
    require_boundary_result(
        result,
        require_external=package["require_external"],
        external_paths=package["external_artifact_paths"],
    )


def analyze_source_freshness(
    inputs: dict[str, Any],
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate freshness only from the final audit's captured input bytes."""

    root = inputs["root"]
    evidence_relative = relative_path(inputs["paths"]["evidence_links"], root)
    generator_relative = relative_path(
        inputs["paths"]["source_freshness_generator"], root
    )
    baseline_relative = relative_path(inputs["paths"]["baseline"], root)
    return validate_freshness_snapshot(
        inputs["json"]["source_freshness"],
        evidence_links_bytes=inputs["input_snapshots"][evidence_relative]["bytes"],
        pinned_text_bytes=inputs["freshness_pinned_texts"],
        generator_bytes=inputs["input_snapshots"][generator_relative]["bytes"],
        baseline_manifest_bytes=inputs["input_snapshots"][baseline_relative]["bytes"],
        now_utc=now_utc,
    )


def analyze_runtime(
    inputs: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    runtime = inputs["json"]["runtime"]
    csv_data = inputs["csv"]
    rules = csv_data["rules"]
    shortlist = csv_data["rule_shortlist"]
    products_source = csv_data["product_master"]
    constraints_source = csv_data["constraints"]
    runtime_bindings = csv_data["runtime_bindings"]
    applicability_rows = csv_data["active_applicability"]

    require_equal(runtime.get("schemaVersion"), "2.1.0", "runtime schemaVersion")
    require_equal(runtime.get("releaseReady"), False, "runtime releaseReady")

    rule_source_by_id = unique_by_key(rules, "rule_id", "rule source")
    released_source = {
        key: row
        for key, row in rule_source_by_id.items()
        if row["status"] == "released"
    }
    runtime_rules = runtime.get("releasedRules")
    if not isinstance(runtime_rules, list):
        raise ValueError("runtime releasedRules must be a list")
    runtime_rule_by_id = unique_by_key(
        runtime_rules, "ruleId", "runtime released rules"
    )
    require_equal(set(runtime_rule_by_id), set(released_source), "released rule IDs")
    require_equal(runtime["rulesReleased"], len(runtime_rules), "rulesReleased")
    require_equal(
        set(runtime["releasedRuleTypes"]),
        {row["rule_type"] for row in released_source.values()},
        "released rule types",
    )
    require_equal(
        set(runtime["ruleEvidenceByType"]),
        set(runtime["releasedRuleTypes"]),
        "ruleEvidenceByType keys",
    )
    require_equal(
        len(runtime["releasedRuleTypes"]),
        len(set(runtime["releasedRuleTypes"])),
        "released rule type uniqueness",
    )

    verified_shortlist = [
        row
        for row in shortlist
        if row["review_status"] == "human_expert_verified"
        and row["supports_release"] == "true"
    ]
    shortlist_by_rule = unique_by_key(
        verified_shortlist,
        "rule_id",
        "verified rule shortlist",
    )
    require_equal(set(shortlist_by_rule), set(released_source), "rule evidence IDs")
    operational_links = [
        row
        for row in csv_data["evidence_links"]
        if row["candidate_operational_status"]
        == "active_existing_released_primary_evidence"
    ]
    operational_link_by_rule = unique_by_key(
        operational_links,
        "rule_id",
        "operational rule evidence links",
    )
    require_equal(
        set(operational_link_by_rule),
        set(released_source),
        "operational rule evidence IDs",
    )

    applicability_by_rule = unique_by_key(
        applicability_rows,
        "rule_id",
        "active rule applicability",
    )
    require_equal(
        set(applicability_by_rule),
        set(released_source),
        "applicability rule IDs",
    )
    provenance = runtime["ruleApplicabilityProvenance"]
    applicability_path = relative_path(
        inputs["paths"]["active_applicability"], inputs["root"]
    )
    require_equal(provenance["path"], applicability_path, "applicability path")
    require_equal(
        provenance["sha256"],
        inputs["lineage"][applicability_path]["sha256"],
        "applicability hash",
    )

    rule_matrix: list[dict[str, str]] = []
    explicit_rules: list[dict[str, Any]] = []
    for rule_id in sorted(runtime_rule_by_id):
        runtime_rule = runtime_rule_by_id[rule_id]
        source = released_source[rule_id]
        shortlist_row = shortlist_by_rule[rule_id]
        operational_link = operational_link_by_rule[rule_id]
        require_equal(runtime_rule["ruleType"], source["rule_type"], f"{rule_id} type")
        require_equal(runtime_rule["scope"], source["scope"], f"{rule_id} scope")
        require_equal(
            runtime_rule["lineageStatus"],
            applicability_by_rule[rule_id]["lineage_status"],
            f"{rule_id} lineage",
        )
        expected_applicability = applicability_from_row(applicability_by_rule[rule_id])
        if not expected_applicability:
            raise ValueError(f"released rule has no applicability: {rule_id}")
        require_equal(
            runtime_rule["applicability"],
            expected_applicability,
            f"{rule_id} applicability",
        )

        require_equal(
            operational_link["evidence_candidate_id"],
            shortlist_row["evidence_candidate_id"],
            f"{rule_id} operational/shortlist candidate ID",
        )
        require_equal(
            operational_link["operational_source_locator"],
            shortlist_row["source_locator"],
            f"{rule_id} operational/shortlist locator",
        )
        require_equal(
            operational_link["operational_evidence_text"],
            shortlist_row["evidence_text"],
            f"{rule_id} operational/shortlist text",
        )
        expected_evidence = {
            "ruleId": rule_id,
            "productName": operational_link["product_name"],
            "itemSequence": operational_link["item_sequence"],
            "sourceId": operational_link["source_id"],
            "sourceVersion": operational_link["source_version"],
            "locator": operational_link["operational_source_locator"],
            "url": operational_link["source_url"],
            "excerptKo": operational_link["operational_evidence_text"],
        }
        require_equal(
            runtime_rule["evidence"],
            [expected_evidence],
            f"{rule_id} evidence",
        )
        for evidence in runtime_rule["evidence"]:
            require_mfds_pdf_source(
                evidence,
                f"released rule {rule_id} evidence",
                item_key="itemSequence",
                url_key="url",
                locator_key="locator",
            )
            require_nonblank(
                evidence,
                ("sourceId", "sourceVersion", "excerptKo"),
                f"released rule {rule_id} evidence",
            )
            if (
                re.fullmatch(r"sha256:[0-9a-f]{64}", str(evidence["sourceVersion"]))
                is None
            ):
                raise ValueError(
                    f"released rule {rule_id} sourceVersion is not an exact SHA-256 pin"
                )

        enriched = [
            {
                **evidence,
                "ruleType": runtime_rule["ruleType"],
                "scope": runtime_rule["scope"],
                "lineageStatus": runtime_rule["lineageStatus"],
                "applicability": runtime_rule["applicability"],
            }
            for evidence in runtime_rule["evidence"]
        ]
        require_equal(
            runtime["ruleEvidenceByType"].get(runtime_rule["ruleType"]),
            enriched,
            f"{rule_id} ruleEvidenceByType",
        )

        evidence = sorted(
            runtime_rule["evidence"],
            key=lambda row: (row["itemSequence"], row["url"], row["locator"]),
        )
        rule_matrix.append(
            {
                "rule_id": rule_id,
                "rule_type": runtime_rule["ruleType"],
                "status": source["status"],
                "severity": source["severity"],
                "scope": runtime_rule["scope"],
                "lineage_status": runtime_rule["lineageStatus"],
                "applicability_json": compact_json(runtime_rule["applicability"]),
                "applicability_field_count": str(len(runtime_rule["applicability"])),
                "source_evidence_count": str(len(evidence)),
                "source_item_sequences": ";".join(
                    row["itemSequence"] for row in evidence
                ),
                "source_ids": ";".join(row["sourceId"] for row in evidence),
                "source_versions": ";".join(row["sourceVersion"] for row in evidence),
                "source_urls": ";".join(row["url"] for row in evidence),
                "source_locators_json": compact_json(
                    [row["locator"] for row in evidence]
                ),
                "source_evidence_json": compact_json(evidence),
            }
        )
        explicit_rules.append(
            {
                "ruleId": rule_id,
                "ruleType": runtime_rule["ruleType"],
                "scope": runtime_rule["scope"],
                "lineageStatus": runtime_rule["lineageStatus"],
                "applicability": runtime_rule["applicability"],
                "evidence": evidence,
            }
        )

    for rule_id, expected_scope in {
        "OTC-RULE-003": "acetaminophen_tylenol500_age_12_plus",
        "OTC-RULE-004": "tylenol500_age_12_plus",
    }.items():
        require_equal(
            runtime_rule_by_id[rule_id]["scope"],
            expected_scope,
            f"{rule_id} fixed scope",
        )
        require_equal(
            runtime_rule_by_id[rule_id]["evidence"][0]["itemSequence"],
            "202106092",
            f"{rule_id} Tylenol evidence",
        )

    product_source_by_item = unique_by_key(
        [row for row in products_source if row["analysis_status"] == "included"],
        "item_sequence",
        "included product source",
    )
    runtime_products = runtime.get("products")
    if not isinstance(runtime_products, list):
        raise ValueError("runtime products must be a list")
    runtime_product_by_item = unique_by_key(
        runtime_products,
        "itemSequence",
        "runtime products",
    )
    unique_by_key(runtime_products, "productId", "runtime products")
    require_equal(
        set(runtime_product_by_item),
        set(product_source_by_item),
        "runtime product membership",
    )

    constraint_source_by_id = unique_by_key(
        constraints_source,
        "constraint_id",
        "administration constraints",
    )
    if any(
        row["record_status"] != "verified_from_authorization_source"
        for row in constraints_source
    ):
        raise ValueError("administration constraint is not authorization-verified")

    runtime_constraints: dict[str, dict[str, Any]] = {}
    product_matrix: list[dict[str, str]] = []
    historical_support_pairs: set[tuple[str, str]] = set()
    direct_binding_pairs: set[tuple[str, str]] = set()
    direct_support_type_pairs: set[tuple[str, str]] = set()
    admin_derived_support_pairs: set[tuple[str, str]] = set()
    direct_items_by_rule: dict[str, set[str]] = {}
    support_tiers: Counter[str] = Counter()
    for item_sequence in sorted(runtime_product_by_item):
        product = runtime_product_by_item[item_sequence]
        source = product_source_by_item[item_sequence]
        require_equal(product["productId"], source["product_id"], f"{item_sequence} ID")
        require_equal(
            product["productName"], source["product_name"], f"{item_sequence} name"
        )
        require_equal(
            product["authorizationStatus"],
            source["authorization_status"],
            f"{item_sequence} authorization",
        )
        require_mfds_product_source(
            product["evidence"] | {"itemSequence": item_sequence},
            f"product {item_sequence}",
            item_key="itemSequence",
            url_key="url",
            locator_key="locator",
        )
        require_equal(
            product["evidence"]["sourceId"],
            source["source_id"],
            f"{item_sequence} source ID",
        )
        require_equal(
            product["evidence"]["url"],
            source["authorization_document_url"],
            f"{item_sequence} source URL",
        )
        require_equal(
            product["evidence"]["locator"],
            source["source_locator"],
            f"{item_sequence} source locator",
        )
        for ingredient in product["ingredients"]:
            require_mfds_product_source(
                ingredient["evidence"] | {"itemSequence": item_sequence},
                f"product {item_sequence} ingredient {ingredient['ingredientId']}",
                item_key="itemSequence",
                url_key="url",
                locator_key="locator",
            )

        supported = product["supportedRuleTypes"]
        require_equal(
            supported,
            sorted(set(supported)),
            f"{item_sequence} canonical support labels",
        )
        if not supported:
            raise ValueError(f"product has no support labels: {item_sequence}")
        unknown = set(supported) - set(runtime["releasedRuleTypes"])
        if unknown:
            raise ValueError(
                f"product {item_sequence} has unknown support labels: {sorted(unknown)}"
            )

        direct_rule_ids = product.get("supportedReleasedRuleIds")
        if not isinstance(direct_rule_ids, list):
            raise ValueError(
                f"product {item_sequence} supportedReleasedRuleIds must be a list"
            )
        require_equal(
            direct_rule_ids,
            sorted(set(direct_rule_ids)),
            f"{item_sequence} canonical direct released rule IDs",
        )
        unknown_direct_ids = set(direct_rule_ids) - set(runtime_rule_by_id)
        if unknown_direct_ids:
            raise ValueError(
                f"product {item_sequence} has unknown direct rule IDs: "
                f"{sorted(unknown_direct_ids)}"
            )
        direct_rule_types = sorted(
            {runtime_rule_by_id[rule_id]["ruleType"] for rule_id in direct_rule_ids}
        )
        require_equal(
            len(direct_rule_types),
            len(direct_rule_ids),
            f"{item_sequence} one-to-one direct rule/type labels",
        )
        for rule_id in direct_rule_ids:
            direct_binding_pairs.add((item_sequence, rule_id))
            direct_items_by_rule.setdefault(rule_id, set()).add(item_sequence)
        direct_support_type_pairs.update(
            (item_sequence, rule_type) for rule_type in direct_rule_types
        )

        constraints = product["administrationConstraints"]
        constraint_ids: list[str] = []
        admin_support_types: set[str] = set()
        for constraint in constraints:
            constraint_id = constraint["constraintId"]
            if constraint_id in runtime_constraints:
                raise ValueError(f"duplicate runtime ADMIN ID: {constraint_id}")
            runtime_constraints[constraint_id] = constraint
            constraint_ids.append(constraint_id)
            source_constraint = constraint_source_by_id.get(constraint_id)
            if source_constraint is None:
                raise ValueError(
                    f"runtime ADMIN ID missing from source: {constraint_id}"
                )
            require_equal(
                source_constraint["item_sequence"],
                item_sequence,
                f"{constraint_id} item",
            )
            require_equal(
                constraint["type"],
                source_constraint["constraint_type"],
                f"{constraint_id} type",
            )
            if constraint["type"] not in ADMIN_CONSTRAINT_TO_SUPPORT_TYPE:
                raise ValueError(
                    f"unsupported ADMIN constraint type: {constraint['type']}"
                )
            admin_support_types.add(
                ADMIN_CONSTRAINT_TO_SUPPORT_TYPE[constraint["type"]]
            )
            require_equal(
                Decimal(str(constraint["value"])),
                Decimal(source_constraint["value"]),
                f"{constraint_id} value",
            )
            require_equal(
                constraint["valueUnit"],
                source_constraint["value_unit"],
                f"{constraint_id} value unit",
            )
            require_equal(
                constraint.get("ingredientId", ""),
                source_constraint["ingredient_id"],
                f"{constraint_id} ingredient",
            )
            require_equal(
                constraint["derivationMethod"],
                source_constraint["derivation_method"],
                f"{constraint_id} derivation",
            )
            require_mfds_pdf_source(
                constraint["evidence"] | {"itemSequence": item_sequence},
                f"constraint {constraint_id}",
                item_key="itemSequence",
                url_key="url",
                locator_key="locator",
            )
            for runtime_field, source_field in (
                ("sourceId", "source_id"),
                ("url", "source_url"),
                ("locator", "source_locator"),
            ):
                require_equal(
                    constraint["evidence"][runtime_field],
                    source_constraint[source_field],
                    f"{constraint_id} evidence {runtime_field}",
                )
            require_equal(
                constraint["evidence"]["sourceVersion"],
                f"sha256:{source_constraint['source_sha256']}",
                f"{constraint_id} evidence sourceVersion",
            )

        expected_supported = set(direct_rule_types) | admin_support_types
        require_equal(
            set(supported),
            expected_supported,
            f"{item_sequence} support-label union",
        )
        admin_derived_types = sorted(admin_support_types - set(direct_rule_types))
        historical_support_pairs.update(
            (item_sequence, rule_type) for rule_type in supported
        )
        admin_derived_support_pairs.update(
            (item_sequence, rule_type) for rule_type in admin_derived_types
        )

        dose_count = sum(value in DOSE_OR_INTERVAL_TYPES for value in supported)
        broader_count = len(supported) - dose_count
        support_tier = (
            "dose_or_interval_only"
            if set(supported) <= DOSE_OR_INTERVAL_TYPES
            else "broader_safety_support"
        )
        support_tiers[support_tier] += 1
        numeric_released_rule_ids = sorted(
            rule_id
            for rule_id in direct_rule_ids
            if runtime_rule_by_id[rule_id]["ruleType"] in DOSE_OR_INTERVAL_TYPES
        )
        numeric_finding_decision_bases = ["administration_constraint"]
        if numeric_released_rule_ids:
            numeric_finding_decision_bases.append("released_rule")

        product_matrix.append(
            {
                "product_id": product["productId"],
                "item_sequence": item_sequence,
                "product_name": product["productName"],
                "authorization_status": product["authorizationStatus"],
                "therapeutic_class": product["therapeuticClass"],
                "support_tier": support_tier,
                "historical_support_type_label_count": str(len(supported)),
                "historical_support_type_labels": ";".join(supported),
                "direct_released_rule_binding_count": str(len(direct_rule_ids)),
                "direct_released_rule_ids": ";".join(direct_rule_ids),
                "direct_released_rule_type_count": str(len(direct_rule_types)),
                "direct_released_rule_types": ";".join(direct_rule_types),
                "admin_derived_support_type_association_count": str(
                    len(admin_derived_types)
                ),
                "admin_derived_support_type_labels": ";".join(admin_derived_types),
                "dose_or_interval_label_count": str(dose_count),
                "broader_safety_label_count": str(broader_count),
                "administration_constraint_count": str(len(constraints)),
                "administration_constraint_ids": ";".join(sorted(constraint_ids)),
                "numeric_finding_decision_bases": ";".join(
                    numeric_finding_decision_bases
                ),
                "ingredient_count": str(len(product["ingredients"])),
                "product_source_id": product["evidence"]["sourceId"],
                "product_source_url": product["evidence"]["url"],
                "product_source_locator": product["evidence"]["locator"],
            }
        )

    require_equal(
        set(runtime_constraints),
        set(constraint_source_by_id),
        "runtime/source ADMIN IDs",
    )
    require_equal(
        runtime.get("authorizationConstraintsCount"),
        len(runtime_constraints),
        "runtime authorizationConstraintsCount",
    )
    released_ids = set(runtime_rule_by_id)
    admin_ids = set(runtime_constraints)
    if released_ids & admin_ids:
        raise ValueError(
            f"ADMIN IDs leaked into releasedRules: {sorted(released_ids & admin_ids)}"
        )
    if any(rule_id.startswith("ADMIN-") for rule_id in released_ids):
        raise ValueError("releasedRules contains an ADMIN ID")

    binding_keys: set[tuple[str, ...]] = set()
    source_binding_pairs: set[tuple[str, str]] = set()
    for row in runtime_bindings:
        key = tuple(row[field] for field in inputs["fields"]["runtime_bindings"])
        if key in binding_keys:
            raise ValueError(f"duplicate runtime binding row: {key}")
        binding_keys.add(key)
        pair = (row["item_sequence"], row["rule_id"])
        if pair in source_binding_pairs:
            raise ValueError(f"duplicate product/rule binding: {pair}")
        source_binding_pairs.add(pair)
        if row["rule_id"] not in released_ids:
            raise ValueError(
                f"runtime binding references inactive rule: {row['rule_id']}"
            )
        require_equal(
            row["binding_status"],
            "human_expert_verified",
            f"runtime binding {row['rule_id']} status",
        )
        require_equal(
            row["supports_release"],
            "true",
            f"runtime binding {row['rule_id']} release support",
        )

    require_equal(
        direct_binding_pairs,
        source_binding_pairs,
        "runtime product/source direct released-rule bindings",
    )
    for rule_id, item_sequences in sorted(direct_items_by_rule.items()):
        require_equal(
            set(
                runtime_rule_by_id[rule_id]["applicability"].get(
                    "productItemSequences", []
                )
            ),
            item_sequences,
            f"{rule_id} direct product applicability",
        )
    require_equal(
        historical_support_pairs,
        direct_support_type_pairs | admin_derived_support_pairs,
        "historical support-label decomposition",
    )
    if direct_support_type_pairs & admin_derived_support_pairs:
        raise ValueError("direct and ADMIN-derived support-label partitions overlap")

    direct_bound_rule_ids = set(direct_items_by_rule)
    cross_product_or_global_rule_ids = released_ids - direct_bound_rule_ids
    require_equal(
        cross_product_or_global_rule_ids,
        {"OTC-RULE-001", "OTC-RULE-002"},
        "cross-product/global released rules",
    )
    require_equal(
        runtime_rule_by_id["OTC-RULE-001"]["applicability"],
        {"ingredientIds": ["ING-acetaminophen"]},
        "OTC-RULE-001 cross-product applicability",
    )
    require_equal(
        runtime_rule_by_id["OTC-RULE-002"]["applicability"],
        {
            "pharmacologicClasses": ["NSAID"],
            "requiredAnchorIngredientIds": ["ING-ibuprofen"],
        },
        "OTC-RULE-002 cross-product applicability",
    )

    for row in rule_matrix:
        item_sequences = sorted(direct_items_by_rule.get(row["rule_id"], set()))
        row["binding_category"] = (
            "direct_product" if item_sequences else "cross_product_or_global"
        )
        row["direct_product_binding_count"] = str(len(item_sequences))
        row["direct_product_item_sequences"] = ";".join(item_sequences)

    metrics = {
        "schema_version": runtime["schemaVersion"],
        "source_generated_at": runtime.get("generatedAt"),
        "products": len(runtime_products),
        "released_rules": len(runtime_rules),
        "released_rule_types": len(runtime["releasedRuleTypes"]),
        "historical_support_type_labels": len(historical_support_pairs),
        "historical_support_type_label_definition": (
            "unique (itemSequence, supportedRuleType) pairs from runtime products; "
            "the v5.0 baseline called these product_rule_bindings"
        ),
        "direct_product_rule_bindings": len(direct_binding_pairs),
        "direct_product_rule_binding_definition": (
            "unique products[].supportedReleasedRuleIds pairs, exactly matching "
            "runtime_rule_bindings.csv"
        ),
        "administration_derived_type_associations": len(admin_derived_support_pairs),
        "administration_derived_type_association_definition": (
            "supportedRuleTypes pairs attributable to mapped ADMIN constraints "
            "after subtracting types already supplied by direct released rules"
        ),
        "cross_product_or_global_rules": len(cross_product_or_global_rule_ids),
        "cross_product_or_global_rule_ids": sorted(cross_product_or_global_rule_ids),
        "structured_runtime_binding_rows": len(runtime_bindings),
        "administration_constraints": len(runtime_constraints),
        "authorization_constraints_count": runtime["authorizationConstraintsCount"],
        "support_tier_counts": dict(sorted(support_tiers.items())),
        "administration_constraint_type_counts": dict(
            sorted(
                Counter(row["constraint_type"] for row in constraints_source).items()
            )
        ),
        "released_rule_ids": sorted(released_ids),
        "administration_constraint_ids": sorted(admin_ids),
        "admin_ids_in_released_rules": [],
        "release_ready": runtime["releaseReady"],
        "released_rules_explicit": explicit_rules,
        "rule_003_004_scope_contract": {
            "OTC-RULE-003": {
                "scope": runtime_rule_by_id["OTC-RULE-003"]["scope"],
                "source_item_sequence": "202106092",
            },
            "OTC-RULE-004": {
                "scope": runtime_rule_by_id["OTC-RULE-004"]["scope"],
                "source_item_sequence": "202106092",
            },
        },
        "decision_basis_contract": {
            "released_rule_ids": "released_rule",
            "administration_constraint_ids": "administration_constraint",
            "historical_support_type_labels_are_not_rule_ids": True,
            "admin_derived_support_types_are_not_released_rule_bindings": True,
        },
    }
    return metrics, product_matrix, rule_matrix


def count_comparison(
    baseline: int,
    current: int,
    *,
    definition: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "baseline": baseline,
        "v51": current,
        "delta": current - baseline,
        "unchanged": baseline == current,
    }
    if definition:
        record["definition"] = definition
    return record


def state_comparison(baseline: Any, current: Any) -> dict[str, Any]:
    return {
        "baseline": baseline,
        "v51": current,
        "unchanged": baseline == current,
    }


def compute(
    inputs: dict[str, Any],
    *,
    metrics_path: Path,
    product_matrix_path: Path,
    rule_matrix_path: Path,
    require_external: bool = False,
) -> dict[str, Any]:
    root = inputs["root"]
    require_output_paths(
        root,
        metrics_path,
        product_matrix_path,
        rule_matrix_path,
        input_paths=tuple(inputs["paths"].values()),
    )
    baseline_protection = validate_baseline_hashes(inputs)
    boundary_verification = validate_boundary_verification(
        inputs,
        require_external=require_external,
    )
    runtime, product_rows, rule_rows = analyze_runtime(inputs)
    evidence = analyze_evidence(inputs)
    literature = analyze_literature(inputs)
    review = analyze_review_packet(inputs)
    freshness = analyze_source_freshness(inputs)
    baseline = inputs["json"]["baseline"]["verified_counts"]

    runtime_baseline = baseline["runtime_baseline_snapshot"]
    authorization_baseline = baseline["authorization_layer"]
    candidate_baseline = baseline["candidate_evidence"]
    literature_baseline = baseline["v50_literature"]
    state_baseline = baseline["state"]
    comparisons = {
        "products": count_comparison(runtime_baseline["products"], runtime["products"]),
        "released_rules": count_comparison(
            runtime_baseline["rules_released"], runtime["released_rules"]
        ),
        "historical_support_type_labels": count_comparison(
            runtime_baseline["product_rule_bindings"],
            runtime["historical_support_type_labels"],
            definition=(
                "the v5.0 field product_rule_bindings counted flattened "
                "products[].supportedRuleTypes labels, not released-rule IDs"
            ),
        ),
        "administration_constraints": count_comparison(
            authorization_baseline["administration_constraints"],
            runtime["administration_constraints"],
        ),
        "dose_or_interval_only_products": count_comparison(
            runtime_baseline["dose_or_interval_only_products"],
            runtime["support_tier_counts"].get("dose_or_interval_only", 0),
        ),
        "broader_safety_support_products": count_comparison(
            runtime_baseline["disease_or_medication_capable_products"],
            runtime["support_tier_counts"].get("broader_safety_support", 0),
        ),
        "official_evidence_rule_links": count_comparison(
            candidate_baseline["official_candidate_rows"],
            evidence["evidence_rule_links"],
            definition="candidate-to-rule links; statuses apply at this 360-row level",
        ),
        "unverified_shortlist_to_expert_packet": count_comparison(
            candidate_baseline["shortlist_not_expert_verified"],
            review["packet_items"],
        ),
        "v50_emitted_literature_links": count_comparison(
            literature_baseline["direct_links"],
            literature["v50_emitted_links"],
            definition=(
                "v5.0 emitted links, not semantic direct matches; v5.1 classifies "
                "them as 1 direct, 4 scope-qualified, and 5 background-only"
            ),
        ),
        "v50_emitted_literature_rules": count_comparison(
            literature_baseline["rules_with_direct_links"],
            literature["v50_emitted_rules"],
        ),
        "release_ready": state_comparison(
            state_baseline["release_ready"], runtime["release_ready"]
        ),
    }

    required_unchanged = (
        "products",
        "released_rules",
        "historical_support_type_labels",
        "administration_constraints",
        "dose_or_interval_only_products",
        "broader_safety_support_products",
        "official_evidence_rule_links",
        "unverified_shortlist_to_expert_packet",
        "v50_emitted_literature_links",
        "v50_emitted_literature_rules",
        "release_ready",
    )
    changed = [key for key in required_unchanged if not comparisons[key]["unchanged"]]
    if changed:
        raise ValueError(f"baseline/v5.1 count mismatch: {changed}")

    require_equal(runtime["products"], 13, "v5.1 products")
    require_equal(runtime["released_rules"], 15, "v5.1 released rules")
    require_equal(
        runtime["historical_support_type_labels"],
        26,
        "historical product support-type labels",
    )
    require_equal(
        runtime["direct_product_rule_bindings"],
        13,
        "direct product/released-rule bindings",
    )
    require_equal(
        runtime["administration_derived_type_associations"],
        13,
        "ADMIN-derived support-type associations",
    )
    require_equal(
        runtime["cross_product_or_global_rules"],
        2,
        "cross-product/global rules",
    )
    require_equal(runtime["administration_constraints"], 32, "ADMIN constraints")
    require_equal(evidence["evidence_units"], 328, "v5.1 evidence units")
    require_equal(evidence["evidence_rule_links"], 360, "v5.1 evidence links")
    require_equal(literature["v50_emitted_links"], 10, "literature emitted")
    require_equal(literature["v50_emitted_rules"], 9, "literature rules")
    require_equal(literature["direct_capable_links"], 5, "direct-capable literature")
    require_equal(literature["direct_match_links"], 1, "direct literature")
    require_equal(
        literature["scope_qualified_direct_links"], 4, "scope-qualified literature"
    )
    require_equal(literature["background_only_links"], 5, "background literature")
    require_equal(literature["excluded_legacy_links"], 10, "excluded literature")
    require_equal(literature["human_expert_reviewed"], 0, "literature expert review")
    require_equal(review["new_human_expert_reviews"], 0, "new expert reviews")
    require_equal(review["activated_items"], 0, "activated expert packet items")
    require_equal(freshness["official_source_urls"], 20, "fresh official sources")
    require_equal(
        freshness["semantic_match_source_urls"], 20, "semantic source matches"
    )
    require_equal(freshness["semantic_drift_source_urls"], 0, "semantic drift")
    require_equal(freshness["unreachable_source_urls"], 0, "unreachable sources")
    require_equal(freshness["candidate_links"], 360, "freshness candidate links")
    require_equal(
        freshness["candidate_excerpt_matches"], 360, "candidate excerpt matches"
    )
    require_equal(
        freshness["verified_primary_links"], 15, "freshness verified-primary links"
    )
    require_equal(
        freshness["verified_primary_candidate_excerpt_matches"],
        15,
        "verified-primary candidate excerpt matches",
    )
    require_equal(freshness["new_rules_activated"], 0, "freshness new rules")
    require_equal(
        freshness["release_ready"], runtime["release_ready"], "freshness/runtime state"
    )
    require_equal(runtime["release_ready"], False, "release readiness")

    product_bytes = csv_payload(PRODUCT_MATRIX_FIELDS, product_rows)
    rule_bytes = csv_payload(RULE_MATRIX_FIELDS, rule_rows)
    metrics: dict[str, Any] = {
        "schema_version": "1.0.0",
        "track": "v5.1-final-mechanical-audit",
        "baseline_commit": inputs["json"]["baseline"]["baseline"]["commit"],
        "generator": "scripts/research/otc/build_v51_final_audit.py",
        "generator_sha256": inputs["lineage"][STATIC_INPUTS["final_audit_generator"]][
            "sha256"
        ],
        "computation_policy": {
            "mechanical_sources_only": True,
            "ui_code_used": False,
            "historical_support_type_label_definition": (
                "one unique (itemSequence, supportedRuleType) pair from runtime products"
            ),
            "direct_released_rule_binding_source": (
                "products[].supportedReleasedRuleIds, cross-checked against "
                "runtime_rule_bindings.csv"
            ),
            "admin_derived_support_type_source": (
                "mapped administrationConstraints[].type minus direct released-rule types"
            ),
            "evidence_status_assignment_level": "360 evidence_rule_links",
            "evidence_units_are_status_free": True,
            "literature_authority": "explanatory_only",
            "release_ready_requires_human_review": True,
            "portable_repository_verification": True,
            "external_artifacts_required_for_final_local_report": True,
        },
        "inputs": inputs["lineage"],
        "protected_baseline": baseline_protection,
        "boundary_verification": boundary_verification,
        "baseline_vs_v51": comparisons,
        "v51": {
            "runtime": runtime,
            "evidence": evidence,
            "literature": literature,
            "expert_review_packet": review,
            "official_source_freshness": freshness,
        },
        "checks": {
            "runtime_schema_is_2_1_0": True,
            "protected_research_v3_tree_matches_baseline": True,
            "protected_research_v3_worktree_is_clean": True,
            "portable_repository_verification_is_complete": True,
            "external_verification_is_required_for_final_local_report": True,
            "all_consumed_protected_inputs_match_baseline": True,
            "released_rules_match_v50_released_ids": True,
            "released_rules_have_applicability": True,
            "released_rules_have_authorization_source_evidence": True,
            "rule_003_004_remain_tylenol_scoped": True,
            "admin_ids_are_unique": True,
            "admin_ids_are_not_released_rule_ids": True,
            "historical_support_labels_split_into_13_direct_and_13_admin": True,
            "cross_product_or_global_rules_are_001_and_002": True,
            "product_membership_matches_13_included_source_products": True,
            "all_product_sources_have_url_and_locator": True,
            "all_rule_sources_have_url_and_locator": True,
            "all_constraint_sources_have_url_and_locator": True,
            "all_evidence_sources_have_url_and_locator": True,
            "all_literature_sources_have_pubmed_id_and_locator": True,
            "triage_joins_all_33_unverified_links_once": True,
            "expert_packet_activation_is_zero": True,
            "literature_human_expert_review_is_zero": True,
            "official_sources_are_20_of_20_semantic_matches": True,
            "remote_pdf_byte_mismatch_is_not_treated_as_semantic_drift": True,
            "release_ready_is_false": True,
            "outputs_stay_under_research_v51_audit": True,
        },
        "outputs": {
            "product_support_matrix": {
                "path": relative_path(product_matrix_path, root),
                "rows": len(product_rows),
                "fields": list(PRODUCT_MATRIX_FIELDS),
                "bytes": len(product_bytes),
                "sha256": sha256_bytes(product_bytes),
            },
            "active_rule_matrix": {
                "path": relative_path(rule_matrix_path, root),
                "rows": len(rule_rows),
                "fields": list(RULE_MATRIX_FIELDS),
                "bytes": len(rule_bytes),
                "sha256": sha256_bytes(rule_bytes),
            },
            "final_metrics": {
                "path": relative_path(metrics_path, root),
                "hash_scope": (
                    "canonical JSON with outputs.final_metrics.semantic_sha256 empty"
                ),
                "semantic_sha256": "",
            },
        },
        "valid": True,
    }
    semantic_hash = sha256_bytes(canonical_json_payload(metrics))
    metrics["outputs"]["final_metrics"]["semantic_sha256"] = semantic_hash
    metrics_bytes = json_payload(metrics)
    return {
        "metrics": metrics,
        "metrics_bytes": metrics_bytes,
        "product_matrix_rows": product_rows,
        "product_matrix_bytes": product_bytes,
        "rule_matrix_rows": rule_rows,
        "rule_matrix_bytes": rule_bytes,
        "root": root,
        "input_paths": tuple(inputs["paths"].values()),
        "input_snapshots": inputs["input_snapshots"],
        "boundary_manifest_path": inputs["paths"]["baseline"],
        "external_artifact_paths": declared_external_paths(inputs),
        "require_external": require_external,
        "verification_scope": (
            EXTERNAL_VERIFICATION_SCOPE
            if require_external
            else PORTABLE_VERIFICATION_SCOPE
        ),
        "final_local_report_ready": require_external,
        "output_paths": {
            "final_metrics": metrics_path,
            "product_support_matrix": product_matrix_path,
            "active_rule_matrix": rule_matrix_path,
        },
    }


def build(
    root: Path = ROOT,
    *,
    metrics_path: Path | None = None,
    product_matrix_path: Path | None = None,
    rule_matrix_path: Path | None = None,
    require_external: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    metrics_path = metrics_path or root / METRICS_RELATIVE
    product_matrix_path = product_matrix_path or root / PRODUCT_MATRIX_RELATIVE
    rule_matrix_path = rule_matrix_path or root / RULE_MATRIX_RELATIVE
    inputs = load_inputs(root)
    return compute(
        inputs,
        metrics_path=metrics_path,
        product_matrix_path=product_matrix_path,
        rule_matrix_path=rule_matrix_path,
        require_external=require_external,
    )


def expected_outputs(package: dict[str, Any]) -> dict[Path, bytes]:
    paths = package["output_paths"]
    return {
        paths["final_metrics"]: package["metrics_bytes"],
        paths["product_support_matrix"]: package["product_matrix_bytes"],
        paths["active_rule_matrix"]: package["rule_matrix_bytes"],
    }


@dataclass
class StagedOutput:
    path: Path
    descriptor: int
    payload: bytes
    device: int
    inode: int


def _open_delete_shared_read(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if os.name != "nt":
        return os.open(path, flags)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path.resolve()),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(int(handle), flags)
    except BaseException:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _revalidate_held_output_set(
    snapshots: list[dict[str, Any]],
    missing_paths: set[Path],
    package: dict[str, Any],
) -> None:
    output_identities: set[tuple[int, int]] = set()
    protected_identities = {
        tuple(snapshot["identity"][:2])
        for snapshot in package["input_snapshots"].values()
    }
    for snapshot in snapshots:
        descriptor = snapshot["descriptor"]
        opened = os.fstat(descriptor)
        path = snapshot["path"]
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError(f"final audit output must not be a hard link: {path}")
        if file_identity(opened) != snapshot["identity"]:
            raise ValueError(f"final audit output identity changed: {path}")
        if _read_descriptor(descriptor) != snapshot["bytes"]:
            raise ValueError(f"final audit output payload changed: {path}")

        metadata = os.lstat(path)
        identity = (metadata.st_dev, metadata.st_ino)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or identity != tuple(snapshot["identity"][:2])
        ):
            raise ValueError(f"final audit output pathname identity changed: {path}")
        if identity in output_identities:
            raise ValueError(f"final audit output aliases another output: {path}")
        if identity in protected_identities:
            raise ValueError(f"final audit output aliases an input: {path}")
        output_identities.add(identity)

    appeared = [path for path in missing_paths if path.exists()]
    if appeared:
        raise ValueError(
            f"missing final audit outputs appeared during check: {appeared}"
        )

    paths = package["output_paths"]
    require_output_paths(
        package["root"],
        paths["final_metrics"],
        paths["product_support_matrix"],
        paths["active_rule_matrix"],
        input_paths=package["input_paths"],
    )


def _validate_staged_path(staged: StagedOutput) -> None:
    opened = os.fstat(staged.descriptor)
    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
        raise ValueError(f"unsafe staged final audit descriptor: {staged.path}")
    if (opened.st_dev, opened.st_ino) != (staged.device, staged.inode):
        raise ValueError(
            f"staged final audit descriptor identity changed: {staged.path}"
        )
    if (
        opened.st_size != len(staged.payload)
        or _read_descriptor(staged.descriptor) != staged.payload
    ):
        raise ValueError(f"staged final audit payload changed: {staged.path}")
    metadata = os.lstat(staged.path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"staged final audit pathname identity changed: {staged.path}")


def _verify_published_payload(
    staged: StagedOutput,
    destination: Path,
    root: Path,
) -> None:
    opened = os.fstat(staged.descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(
            f"post-replace staged descriptor identity changed: {destination}"
        )
    metadata = os.lstat(destination)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != (staged.device, staged.inode)
    ):
        raise ValueError(f"post-replace output identity mismatch: {destination}")
    if _read_descriptor(staged.descriptor) != staged.payload:
        raise ValueError(f"post-replace staged payload mismatch: {destination}")
    observed = safely_read_input(
        destination,
        root,
        require_single_link=True,
        role="output",
    )
    if (
        observed["identity"][:2] != (staged.device, staged.inode)
        or observed["bytes"] != staged.payload
        or observed["sha256"] != sha256_bytes(staged.payload)
    ):
        raise ValueError(f"post-replace output payload mismatch: {destination}")


def _replace_staged_output(
    staged: StagedOutput,
    destination: Path,
    root: Path,
    *,
    published_paths: set[Path] | None = None,
) -> None:
    _validate_staged_path(staged)
    os.replace(staged.path, destination)
    if published_paths is not None:
        published_paths.add(destination)
    try:
        _verify_published_payload(staged, destination, root)
    finally:
        os.close(staged.descriptor)
        staged.descriptor = -1


def _close_staged(staged: StagedOutput) -> None:
    """Release a staged handle without deleting an uncertain pathname."""

    if staged.descriptor >= 0:
        os.close(staged.descriptor)
        staged.descriptor = -1


def stage_output(path: Path, payload: bytes, audit_root: Path) -> StagedOutput:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=audit_root
    )
    temporary = Path(temporary_name)
    if temporary.parent.resolve() != audit_root.resolve():
        os.close(descriptor)
        raise ValueError(f"staged output left canonical audit directory: {temporary}")
    held_descriptor: int | None = None
    staged: StagedOutput | None = None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        metadata = os.lstat(temporary)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError(f"unsafe staged final audit output: {temporary}")
        held_descriptor = _open_delete_shared_read(temporary)
        staged = StagedOutput(
            path=temporary,
            descriptor=held_descriptor,
            payload=payload,
            device=metadata.st_dev,
            inode=metadata.st_ino,
        )
        _validate_staged_path(staged)
        return staged
    except BaseException as error:
        if staged is not None:
            _close_staged(staged)
        elif held_descriptor is not None:
            os.close(held_descriptor)
        raise RuntimeError(
            "staged final audit output failed; automatic temp deletion is "
            f"disabled, retained={temporary}"
        ) from error


def write(package: dict[str, Any]) -> None:
    paths = package["output_paths"]
    root = package["root"]
    require_output_paths(
        root,
        paths["final_metrics"],
        paths["product_support_matrix"],
        paths["active_rule_matrix"],
        input_paths=package["input_paths"],
    )
    audit_root = root / AUDIT_ROOT_RELATIVE
    audit_root.mkdir(parents=True, exist_ok=True)
    outputs = expected_outputs(package)
    publish_order = [
        paths["product_support_matrix"],
        paths["active_rule_matrix"],
        paths["final_metrics"],
    ]
    staged: dict[Path, StagedOutput] = {}
    published_paths: set[Path] = set()
    published_snapshots: list[dict[str, Any]] = []
    try:
        for path, payload in outputs.items():
            staged[path] = stage_output(path, payload, audit_root)

        # This is the commit boundary: every parsed input must still be the same
        # file identity and the same bytes immediately before any replacement.
        revalidate_input_snapshots(package)
        revalidate_package_boundary(package)
        require_output_paths(
            root,
            paths["final_metrics"],
            paths["product_support_matrix"],
            paths["active_rule_matrix"],
            input_paths=package["input_paths"],
        )
        for path in publish_order:
            # Recheck each destination directly before the atomic directory-entry
            # replacement. os.replace never writes through an existing inode.
            revalidate_input_snapshots(package)
            revalidate_package_boundary(package)
            require_output_paths(
                root,
                paths["final_metrics"],
                paths["product_support_matrix"],
                paths["active_rule_matrix"],
                input_paths=package["input_paths"],
            )
            _replace_staged_output(
                staged[path],
                path,
                root,
                published_paths=published_paths,
            )

        revalidate_input_snapshots(package)
        revalidate_package_boundary(package)
        require_output_paths(
            root,
            paths["final_metrics"],
            paths["product_support_matrix"],
            paths["active_rule_matrix"],
            input_paths=package["input_paths"],
        )
        for path, payload in outputs.items():
            observed = safely_read_input(
                path,
                root,
                require_single_link=True,
                role="output",
                hold_descriptor=True,
            )
            published_snapshots.append(observed)
            if observed["bytes"] != payload:
                raise ValueError(f"post-commit output payload mismatch: {path}")
        revalidate_input_snapshots(package)
        revalidate_package_boundary(package)
        _revalidate_held_output_set(
            published_snapshots,
            set(),
            package,
        )
    except BaseException as error:
        for snapshot in published_snapshots:
            descriptor = snapshot["descriptor"]
            if descriptor >= 0:
                os.close(descriptor)
                snapshot["descriptor"] = -1
        retained_staged = sorted(
            str(staged.path)
            for staged in staged.values()
            if staged.descriptor >= 0 and staged.path.exists()
        )
        if published_paths:
            raise RuntimeError(
                "final audit publish failed after partial publication; automatic "
                "rollback and temp deletion are disabled to preserve concurrent "
                "writer data. Run --check, resolve the failed input or path, and "
                "rerun the writer. "
                f"published={sorted(str(path) for path in published_paths)} "
                f"retained_staged={retained_staged}"
            ) from error
        if retained_staged:
            raise RuntimeError(
                "final audit staging failed; automatic temp deletion is disabled. "
                f"retained_staged={retained_staged}"
            ) from error
        raise
    finally:
        for snapshot in published_snapshots:
            if snapshot["descriptor"] >= 0:
                os.close(snapshot["descriptor"])
        for temporary in staged.values():
            _close_staged(temporary)


def check(package: dict[str, Any]) -> list[dict[str, Any]]:
    paths = package["output_paths"]
    require_output_paths(
        package["root"],
        paths["final_metrics"],
        paths["product_support_matrix"],
        paths["active_rule_matrix"],
        input_paths=package["input_paths"],
    )
    revalidate_input_snapshots(package)
    revalidate_package_boundary(package)
    mismatches: list[dict[str, Any]] = []
    held_snapshots: list[dict[str, Any]] = []
    missing_paths: set[Path] = set()
    try:
        for path, expected in expected_outputs(package).items():
            try:
                snapshot = safely_read_input(
                    path,
                    package["root"],
                    require_single_link=True,
                    role="output",
                    hold_descriptor=True,
                )
            except FileNotFoundError:
                missing_paths.add(path)
                mismatches.append({"path": str(path), "reason": "missing"})
                continue
            held_snapshots.append(snapshot)
            observed = snapshot["bytes"]
            if observed != expected:
                mismatches.append(
                    {
                        "path": str(path),
                        "reason": "content_mismatch",
                        "expected_sha256": sha256_bytes(expected),
                        "observed_sha256": sha256_bytes(observed),
                    }
                )
        _revalidate_held_output_set(held_snapshots, missing_paths, package)
        revalidate_input_snapshots(package)
        revalidate_package_boundary(package)
        # This must remain the final operation before success. Input and
        # boundary validation can execute arbitrary filesystem reads, so the
        # held output set is checked once more after those calls return.
        _revalidate_held_output_set(held_snapshots, missing_paths, package)
        return mismatches
    finally:
        for snapshot in held_snapshots:
            os.close(snapshot["descriptor"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--require-external",
        action="store_true",
        help=(
            "Require both declared external canonical artifacts before marking "
            "the final local report ready."
        ),
    )
    parser.add_argument("--metrics", type=Path, default=ROOT / METRICS_RELATIVE)
    parser.add_argument(
        "--product-matrix",
        type=Path,
        default=ROOT / PRODUCT_MATRIX_RELATIVE,
    )
    parser.add_argument(
        "--rule-matrix",
        type=Path,
        default=ROOT / RULE_MATRIX_RELATIVE,
    )
    args = parser.parse_args()
    package = build(
        metrics_path=args.metrics.resolve(),
        product_matrix_path=args.product_matrix.resolve(),
        rule_matrix_path=args.rule_matrix.resolve(),
        require_external=args.require_external,
    )
    mismatches = check(package) if args.check else []
    if not args.check:
        write(package)
    result = {
        "valid": not mismatches,
        "mode": "check" if args.check else "write",
        "verification_scope": package["verification_scope"],
        "final_local_report_ready": (
            package["final_local_report_ready"] and not mismatches
        ),
        "counts": {
            "products": len(package["product_matrix_rows"]),
            "released_rules": len(package["rule_matrix_rows"]),
            "evidence_units": package["metrics"]["v51"]["evidence"]["evidence_units"],
            "evidence_rule_links": package["metrics"]["v51"]["evidence"][
                "evidence_rule_links"
            ],
        },
        "mismatches": mismatches,
        "output_sha256": {
            path.name: sha256_bytes(payload)
            for path, payload in expected_outputs(package).items()
        },
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
