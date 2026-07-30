"""Build v5 rule-to-literature links from retained v5 screening decisions.

This script deliberately treats the v4 supporting-literature table as a set of
candidate links, not as evidence that a link is valid in v5.  A candidate is
emitted only when all of the following are true:

* the cited paper can be resolved to one v5 evidence-map record;
* that record has a ``retain`` decision for a question allowed for the rule;
* the question is part of the paper's v5 corpus membership; and
* the cited locator resolves to a v5 abstract sentence that exactly equals the
  candidate quotation.

The only generated artifacts are ``downstream/supporting_literature.csv`` and
``downstream/literature_link_manifest.json``.  Authorization-layer and v4
files are read-only inputs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.literature_locator import parse_locator, sentence_at  # noqa: E402


V5_DIR = ROOT / "research_v3" / "otc" / "literature" / "v5"
EVIDENCE_MAP = V5_DIR / "evidence_map.csv"
DECISIONS = V5_DIR / "screening" / "decisions.csv"
ADJUDICATION_MANIFEST = V5_DIR / "screening" / "adjudication_manifest.json"
CANDIDATES = ROOT / "research_v3" / "otc" / "rules" / "supporting_literature.csv"
RULES = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
QUERY_DEFINITIONS = V5_DIR / "query_definitions.json"
OUTPUT_DIR = V5_DIR / "downstream"
OUTPUT_CSV = OUTPUT_DIR / "supporting_literature.csv"
OUTPUT_MANIFEST = OUTPUT_DIR / "literature_link_manifest.json"

REVIEW_STATUS = "agent_curated_from_v50_final_screening_layer"
EVIDENCE_AUTHORITY = "literature_explanatory_only"
VALID_EVIDENCE_RELATIONS = {
    "supports_caution",
    "contextualizes_uncertainty",
    "supports_mechanism",
}
VALID_AUTHORIZATION_ALIGNMENTS = {"consistent", "conflict"}
QUESTION_ID_PATTERN = re.compile(r"OTC-LIT-Q\d{2}-[A-Z0-9-]+")
LOCATOR_PATTERN = re.compile(r"abstract:sentence:[1-9][0-9]*\Z")
VALID_SCREENING_LABELS = {"retain", "deprioritize", "uncertain"}
EXPECTED_FINAL_ROWS = 43_207
EXPECTED_ADJUDICATED_ROWS = 5_000
EXPECTED_CANDIDATE_ROWS = 20
EXPECTED_CANDIDATES_SHA256 = "a09a98590f60d6edc8312878843c3dd2b14c63ca35eecf9ef33f9b16c068734d"


@dataclass(frozen=True)
class EvidenceRecord:
    row: dict[str, str]
    record_id: str
    pmid: str
    doi: str
    title_key: str
    question_ids: frozenset[str]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def _require_fields(path: Path, fieldnames: Iterable[str], required: set[str]) -> None:
    missing = sorted(required - set(fieldnames))
    if missing:
        raise ValueError(f"{path}: missing required columns {missing}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _normalise_doi(value: str) -> str:
    doi = (value or "").strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    return re.sub(r"^doi:\s*", "", doi).strip()


def _title_key(value: str) -> str:
    # Evidence-map construction normalises XML whitespace before deduplication.
    # Preserve case so this remains an exact-title fallback rather than a fuzzy
    # match.
    return " ".join((value or "").split())


def _split_values(value: str) -> set[str]:
    text = (value or "").strip()
    if not text:
        return set()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return {str(item).strip() for item in parsed if str(item).strip()}
    return {part.strip() for part in re.split(r"[;|,]", text) if part.strip()}


def _question_ids(row: dict[str, str]) -> frozenset[str]:
    values: set[str] = set()
    for field in ("question_ids", "question_id", "corpus_question_ids"):
        values.update(_split_values(row.get(field, "")))
    if not values:
        # Last-resort extraction supports manifests such as
        # ``v5_search_corpus:OTC-LIT-Q01-ACETAMINOPHEN`` without accepting
        # arbitrary words as question identifiers.
        values.update(QUESTION_ID_PATTERN.findall(row.get("corpus_membership", "")))
    return frozenset(values)


def _pmid_aliases(row: dict[str, str]) -> set[str]:
    aliases: set[str] = set()
    for field in ("pmid", "all_pmids", "pmids", "duplicate_pmids", "source_pmids"):
        aliases.update(_split_values(row.get(field, "")))
    return {value for value in aliases if value.isdigit()}


def _build_evidence_indexes(
    rows: list[dict[str, str]],
) -> tuple[
    list[EvidenceRecord],
    dict[str, list[EvidenceRecord]],
    dict[str, list[EvidenceRecord]],
    dict[str, list[EvidenceRecord]],
    dict[str, list[EvidenceRecord]],
]:
    records: list[EvidenceRecord] = []
    by_record_id: dict[str, list[EvidenceRecord]] = defaultdict(list)
    by_pmid: dict[str, list[EvidenceRecord]] = defaultdict(list)
    by_doi: dict[str, list[EvidenceRecord]] = defaultdict(list)
    by_title: dict[str, list[EvidenceRecord]] = defaultdict(list)

    seen_record_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        record_id = row.get("record_id", "").strip()
        if not record_id:
            raise ValueError(f"{EVIDENCE_MAP}:{row_number}: blank record_id")
        if record_id in seen_record_ids:
            raise ValueError(f"{EVIDENCE_MAP}:{row_number}: duplicate record_id {record_id!r}")
        seen_record_ids.add(record_id)

        pmid = row.get("pmid", "").strip()
        doi = _normalise_doi(row.get("doi", ""))
        title = _title_key(row.get("title", ""))
        record = EvidenceRecord(
            row=row,
            record_id=record_id,
            pmid=pmid,
            doi=doi,
            title_key=title,
            question_ids=_question_ids(row),
        )
        records.append(record)
        by_record_id[record_id].append(record)
        for alias in _pmid_aliases(row):
            by_pmid[alias].append(record)
        if doi:
            by_doi[doi].append(record)
        if title:
            by_title[title].append(record)

    return records, by_record_id, by_pmid, by_doi, by_title


def _resolve_candidate(
    row: dict[str, str],
    by_record_id: dict[str, list[EvidenceRecord]],
    by_pmid: dict[str, list[EvidenceRecord]],
    by_doi: dict[str, list[EvidenceRecord]],
    by_title: dict[str, list[EvidenceRecord]],
) -> tuple[EvidenceRecord | None, str]:
    probes = (
        ("record_id", row.get("record_id", "").strip(), by_record_id),
        ("pmid", row.get("pmid", "").strip(), by_pmid),
        ("normalized_doi", _normalise_doi(row.get("doi", "")), by_doi),
        ("exact_title", _title_key(row.get("title", "")), by_title),
    )
    resolved: list[tuple[str, EvidenceRecord]] = []
    unresolved_methods: list[str] = []
    for method, key, index in probes:
        if not key:
            continue
        matches = index.get(key, [])
        if len(matches) == 1:
            resolved.append((method, matches[0]))
            continue
        if len(matches) > 1:
            return None, f"ambiguous_{method}"
        unresolved_methods.append(method)

    if not resolved:
        return None, "not_in_v5_corpus"
    if unresolved_methods:
        return None, "supplied_identifier_not_in_v5_corpus"

    resolved_record_ids = {record.record_id for _, record in resolved}
    if len(resolved_record_ids) != 1:
        return None, "conflicting_supplied_identifiers"
    return resolved[0][1], "+".join(method for method, _ in resolved)


def _load_rule_questions() -> dict[str, set[str]]:
    with QUERY_DEFINITIONS.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if payload.get("query_authority") != "final query strings in this file":
        raise ValueError(f"{QUERY_DEFINITIONS}: not marked as the final v5 query authority")
    mapping: dict[str, set[str]] = defaultdict(set)
    seen_question_ids: set[str] = set()
    for question in payload.get("questions", []):
        question_id = str(question.get("question_id", "")).strip()
        if not question_id:
            raise ValueError(f"{QUERY_DEFINITIONS}: blank question_id")
        if question_id in seen_question_ids:
            raise ValueError(f"{QUERY_DEFINITIONS}: duplicate question_id {question_id!r}")
        seen_question_ids.add(question_id)
        rule_types = question.get("rule_types")
        if not isinstance(rule_types, list) or not rule_types:
            raise ValueError(f"{QUERY_DEFINITIONS}: {question_id} has no rule_types")
        for rule_type in rule_types:
            normalized_rule_type = str(rule_type).strip()
            if not normalized_rule_type:
                raise ValueError(f"{QUERY_DEFINITIONS}: {question_id} has a blank rule_type")
            mapping[normalized_rule_type].add(question_id)
    if not seen_question_ids:
        raise ValueError(f"{QUERY_DEFINITIONS}: no questions")
    return dict(mapping)


def _load_retain_decisions() -> tuple[set[tuple[str, str]], int, Counter[str]]:
    fieldnames, rows = _read_csv(DECISIONS)
    _require_fields(DECISIONS, fieldnames, {"record_id", "question_id"})
    decision_field = next(
        (name for name in ("decision", "label", "screening_decision") if name in fieldnames),
        None,
    )
    if decision_field is None:
        raise ValueError(
            f"{DECISIONS}: expected one of decision, label, screening_decision"
        )

    if len(rows) != EXPECTED_FINAL_ROWS:
        raise ValueError(
            f"{DECISIONS}: expected {EXPECTED_FINAL_ROWS} physical rows, found {len(rows)}"
        )

    labels: Counter[str] = Counter()
    decisions_by_key: dict[tuple[str, str], str] = {}
    for row_number, row in enumerate(rows, start=2):
        key = (row["record_id"].strip(), row["question_id"].strip())
        label = row[decision_field].strip().lower()
        if not all(key) or not label:
            raise ValueError(f"{DECISIONS}:{row_number}: incomplete screening decision")
        if label not in VALID_SCREENING_LABELS:
            raise ValueError(f"{DECISIONS}:{row_number}: invalid decision {label!r}")
        prior = decisions_by_key.get(key)
        if prior is not None:
            raise ValueError(f"{DECISIONS}:{row_number}: duplicate decision key {key}")
        decisions_by_key[key] = label
        labels[label] += 1

    retain = {key for key, label in decisions_by_key.items() if label == "retain"}
    return retain, len(decisions_by_key), labels


def _require_final_adjudication_manifest() -> dict[str, object]:
    if not ADJUDICATION_MANIFEST.is_file():
        raise FileNotFoundError(ADJUDICATION_MANIFEST)
    with ADJUDICATION_MANIFEST.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    compiled = payload.get("layers", {}).get("compiled_decisions", {})
    counts = payload.get("counts", {})
    if not all(
        (
            payload.get("run_complete") is True,
            compiled.get("path") == DECISIONS.relative_to(ROOT).as_posix(),
            compiled.get("sha256") == _sha256(DECISIONS),
            compiled.get("row_count") == EXPECTED_FINAL_ROWS,
            counts.get("classifier_rows") == EXPECTED_FINAL_ROWS,
            counts.get("compiled_decision_rows") == EXPECTED_FINAL_ROWS,
            counts.get("selected_rows") == EXPECTED_ADJUDICATED_ROWS,
            counts.get("adjudicated_rows") == EXPECTED_ADJUDICATED_ROWS,
            compiled.get("adjudication_labels_applied") is True,
            payload.get("hashes", {}).get("evidence_map_sha256") == _sha256(EVIDENCE_MAP),
            payload.get("classifier_decisions_unchanged") is True,
            payload.get("adjudication_input_blinded_to_classifier_labels") is True,
            payload.get("agent_identity_recorded") is False,
            payload.get("specific_agent_attribution_supported") is False,
            payload.get("execution_receipts_recorded") is False,
            payload.get("independent_blinding_ai") is False,
            payload.get("independent_blinding") is False,
            payload.get("release_ready") is False,
        )
    ):
        raise ValueError("adjudication manifest does not prove a complete 43,207-row final layer")
    return payload


def _candidate_error(row: dict[str, str], reason: str, **details: object) -> dict[str, object]:
    return {
        "source_link_id": row.get("link_id", ""),
        "rule_id": row.get("rule_id", ""),
        "candidate_pmid": row.get("pmid", ""),
        "reason": reason,
        **details,
    }


def _copy_evidence_metadata(output: dict[str, str], evidence: EvidenceRecord) -> None:
    row = evidence.row
    output["record_id"] = evidence.record_id
    for field in ("pmid", "doi", "title", "journal", "publication_year", "publication_types"):
        if row.get(field, "").strip():
            output[field] = row[field].strip()
    output["corpus_membership"] = "v5_search_corpus"
    output["screening_decision"] = "retain"
    output["review_status"] = REVIEW_STATUS
    output["supports_rule_release"] = "false"
    pmid = output.get("pmid", "").strip()
    output["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""


def _validate_candidate_constants(row: dict[str, str]) -> str | None:
    if row.get("evidence_authority", "") != EVIDENCE_AUTHORITY:
        return "invalid_evidence_authority"
    if row.get("supports_rule_release", "").strip().lower() != "false":
        return "candidate_claims_release_authority"
    if row.get("evidence_relation", "") not in VALID_EVIDENCE_RELATIONS:
        return "invalid_evidence_relation"
    if row.get("authorization_alignment", "") not in VALID_AUTHORIZATION_ALIGNMENTS:
        return "invalid_authorization_alignment"
    return None


def _build() -> tuple[list[str], list[dict[str, str]], dict[str, object]]:
    evidence_fields, evidence_rows = _read_csv(EVIDENCE_MAP)
    _require_fields(
        EVIDENCE_MAP,
        evidence_fields,
        {"record_id", "pmid", "all_pmids", "title", "abstract", "doi"},
    )
    candidate_fields, candidate_rows = _read_csv(CANDIDATES)
    _require_fields(
        CANDIDATES,
        candidate_fields,
        {
            "link_id",
            "rule_id",
            "rule_type",
            "pmid",
            "record_id",
            "doi",
            "title",
            "journal",
            "publication_year",
            "publication_types",
            "study_design",
            "corpus_membership",
            "screening_decision",
            "locator",
            "locator_quote_en",
            "ingredient_ids",
            "profile_conditions",
            "key_finding_ko",
            "selection_reason_ko",
            "limitation_ko",
            "evidence_relation",
            "evidence_authority",
            "authorization_alignment",
            "authorization_note_ko",
            "review_status",
            "supports_rule_release",
            "url",
        },
    )
    if len(candidate_rows) != EXPECTED_CANDIDATE_ROWS:
        raise ValueError(
            f"{CANDIDATES}: expected {EXPECTED_CANDIDATE_ROWS} frozen candidates, "
            f"found {len(candidate_rows)}"
        )
    candidate_sha256 = _sha256(CANDIDATES)
    if candidate_sha256 != EXPECTED_CANDIDATES_SHA256:
        raise ValueError(
            f"{CANDIDATES}: frozen SHA-256 mismatch: {candidate_sha256}"
        )
    rule_fields, rule_rows = _read_csv(RULES)
    _require_fields(RULES, rule_fields, {"rule_id", "rule_type"})

    rule_types = {row["rule_id"].strip(): row["rule_type"].strip() for row in rule_rows}
    if len(rule_types) != len(rule_rows):
        raise ValueError(f"{RULES}: duplicate rule_id")
    if len(rule_types) != 16:
        raise ValueError(f"{RULES}: expected 16 rules, found {len(rule_types)}")

    rule_questions = _load_rule_questions()
    missing_question_maps = sorted(
        rule_id for rule_id, rule_type in rule_types.items() if not rule_questions.get(rule_type)
    )
    if missing_question_maps:
        raise ValueError(f"rules lack v5 query question mapping: {missing_question_maps}")

    records, by_record_id, by_pmid, by_doi, by_title = _build_evidence_indexes(evidence_rows)
    adjudication_manifest = _require_final_adjudication_manifest()
    retain_decisions, distinct_decisions, label_counts = _load_retain_decisions()
    if distinct_decisions != adjudication_manifest["counts"]["compiled_decision_rows"]:  # type: ignore[index]
        raise ValueError("decisions.csv row count differs from adjudication manifest")

    accepted: list[dict[str, str]] = []
    accepted_metadata: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    source_link_ids: set[str] = set()

    for candidate in candidate_rows:
        source_link_id = candidate.get("link_id", "").strip()
        if not source_link_id or source_link_id in source_link_ids:
            raise ValueError(f"{CANDIDATES}: blank or duplicate link_id {source_link_id!r}")
        source_link_ids.add(source_link_id)

        rule_id = candidate.get("rule_id", "").strip()
        rule_type = candidate.get("rule_type", "").strip()
        if rule_types.get(rule_id) != rule_type:
            rejected.append(_candidate_error(candidate, "rule_id_rule_type_mismatch"))
            continue
        invalid_constant = _validate_candidate_constants(candidate)
        if invalid_constant:
            rejected.append(_candidate_error(candidate, invalid_constant))
            continue

        evidence, resolution = _resolve_candidate(
            candidate,
            by_record_id,
            by_pmid,
            by_doi,
            by_title,
        )
        if evidence is None:
            rejected.append(_candidate_error(candidate, resolution))
            continue

        allowed_questions = rule_questions[rule_type]
        eligible_questions = sorted(
            question_id
            for question_id in evidence.question_ids & allowed_questions
            if (evidence.record_id, question_id) in retain_decisions
        )
        if not eligible_questions:
            retained_elsewhere = sorted(
                question_id
                for record_id, question_id in retain_decisions
                if record_id == evidence.record_id
            )
            rejected.append(
                _candidate_error(
                    candidate,
                    "no_retain_decision_for_rule_question",
                    record_id=evidence.record_id,
                    corpus_question_ids=sorted(evidence.question_ids),
                    allowed_question_ids=sorted(allowed_questions),
                    retained_question_ids=retained_elsewhere,
                )
            )
            continue

        locator = candidate.get("locator", "")
        if LOCATOR_PATTERN.fullmatch(locator) is None:
            rejected.append(
                _candidate_error(
                    candidate,
                    "noncanonical_locator",
                    record_id=evidence.record_id,
                    locator=locator,
                )
            )
            continue
        try:
            sentence_index = parse_locator(locator)
            actual_quote = sentence_at(evidence.row.get("abstract", ""), sentence_index)
        except (ValueError, IndexError) as exc:
            rejected.append(
                _candidate_error(
                    candidate,
                    "invalid_or_out_of_range_locator",
                    record_id=evidence.record_id,
                    error=str(exc),
                )
            )
            continue

        candidate_quote = candidate.get("locator_quote_en", "")
        if actual_quote != candidate_quote:
            rejected.append(
                _candidate_error(
                    candidate,
                    "locator_quote_mismatch",
                    record_id=evidence.record_id,
                    locator=locator,
                    candidate_quote=candidate_quote,
                    actual_quote=actual_quote,
                )
            )
            continue

        output = dict(candidate)
        _copy_evidence_metadata(output, evidence)
        output["locator"] = f"abstract:sentence:{sentence_index}"
        # The quote comes from the v5 abstract, even though equality with the
        # v4 candidate was required above.
        output["locator_quote_en"] = actual_quote
        accepted.append(output)
        accepted_metadata.append(
            {
                "source_link_id": source_link_id,
                "rule_id": rule_id,
                "record_id": evidence.record_id,
                "pmid": output.get("pmid", ""),
                "resolution_method": resolution,
                "resolution_identifiers": resolution.split("+"),
                "screening_question_ids": eligible_questions,
                "locator": locator,
                "quote_exact_match": True,
            }
        )

    if len(accepted) + len(rejected) != EXPECTED_CANDIDATE_ROWS:
        raise RuntimeError(
            "candidate accounting mismatch: "
            f"accepted={len(accepted)} rejected={len(rejected)} "
            f"expected={EXPECTED_CANDIDATE_ROWS}"
        )
    if not accepted:
        raise ValueError("no candidate passed v5 downstream validation")

    accepted.sort(
        key=lambda row: (
            row.get("rule_id", ""),
            row.get("pmid", ""),
            row.get("locator", ""),
            row.get("link_id", ""),
        )
    )
    accepted_by_source = {
        item["source_link_id"]: item for item in accepted_metadata
    }
    accepted_metadata = [
        accepted_by_source[row["link_id"]]
        for row in accepted
    ]
    for index, row in enumerate(accepted, start=1):
        source_link_id = row["link_id"]
        row["link_id"] = f"OTC-LIT-V50-LINK-{index:03d}"
        accepted_by_source[source_link_id]["link_id"] = row["link_id"]

    links_by_rule: dict[str, list[dict[str, object]]] = defaultdict(list)
    for metadata in accepted_metadata:
        links_by_rule[str(metadata["rule_id"])].append(metadata)
    candidates_by_rule = Counter(row.get("rule_id", "").strip() for row in candidate_rows)
    rejected_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for rejection in rejected:
        rejected_by_rule[str(rejection["rule_id"])][str(rejection["reason"])] += 1

    rule_results: list[dict[str, object]] = []
    unresolved_rule_ids: list[str] = []
    for rule_id in sorted(rule_types):
        links = links_by_rule.get(rule_id, [])
        status = "resolved" if links else "unresolved"
        if not links:
            unresolved_rule_ids.append(rule_id)
        rule_results.append(
            {
                "rule_id": rule_id,
                "rule_type": rule_types[rule_id],
                "status": status,
                "unresolved_reason": (
                    None
                    if links
                    else (
                        "no_v4_candidate"
                        if candidates_by_rule[rule_id] == 0
                        else "no_candidate_passed_v5_validation"
                    )
                ),
                "candidate_count": candidates_by_rule[rule_id],
                "link_count": len(links),
                "link_ids": [str(link["link_id"]) for link in links],
                "rejection_counts": dict(sorted(rejected_by_rule[rule_id].items())),
                "allowed_question_ids": sorted(rule_questions[rule_types[rule_id]]),
            }
        )

    rejection_counts = Counter(str(item["reason"]) for item in rejected)
    manifest: dict[str, object] = {
        "schema_version": "1.1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "v4_candidate_links_checked_against_v5_retain_decisions",
        "authority": {
            "evidence_authority": EVIDENCE_AUTHORITY,
            "supports_rule_release": False,
            "independent_blinding": False,
            "release_ready": False,
        },
        "inputs": {
            "evidence_map": {
                "path": EVIDENCE_MAP.relative_to(ROOT).as_posix(),
                "sha256": _sha256(EVIDENCE_MAP),
                "record_count": len(records),
            },
            "screening_decisions": {
                "path": DECISIONS.relative_to(ROOT).as_posix(),
                "sha256": _sha256(DECISIONS),
                "distinct_decision_count": distinct_decisions,
                "label_counts": dict(sorted(label_counts.items())),
            },
            "adjudication_manifest": {
                "path": ADJUDICATION_MANIFEST.relative_to(ROOT).as_posix(),
                "sha256": _sha256(ADJUDICATION_MANIFEST),
                "run_complete": True,
                "adjudicated_rows": adjudication_manifest["counts"]["adjudicated_rows"],  # type: ignore[index]
                "compiled_decision_rows": adjudication_manifest["counts"]["compiled_decision_rows"],  # type: ignore[index]
            },
            "v4_candidate_links": {
                "path": CANDIDATES.relative_to(ROOT).as_posix(),
                "sha256": _sha256(CANDIDATES),
                "candidate_count": len(candidate_rows),
                "expected_candidate_count": EXPECTED_CANDIDATE_ROWS,
                "frozen_sha256": EXPECTED_CANDIDATES_SHA256,
                "read_only": True,
            },
            "rules": {
                "path": RULES.relative_to(ROOT).as_posix(),
                "sha256": _sha256(RULES),
                "rule_count": len(rule_types),
                "read_only": True,
            },
            "query_definitions": {
                "path": QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
                "sha256": _sha256(QUERY_DEFINITIONS),
                "mapping_field": "questions[].rule_types",
                "question_count": len(
                    {question_id for values in rule_questions.values() for question_id in values}
                ),
                "read_only": True,
            },
        },
        "validation_policy": {
            "candidate_resolution_identifiers": [
                "record_id",
                "pmid_including_all_pmids",
                "normalized_doi",
                "exact_title",
            ],
            "candidate_resolution_requirement": (
                "every_supplied_identifier_resolves_uniquely_to_the_same_v5_record"
            ),
            "rule_question_mapping_source": QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
            "screening_requirement": "retain_for_corpus_question_allowed_for_rule_type",
            "locator_requirement": "abstract:sentence:N",
            "quote_requirement": "exact_string_equality_with_v5_abstract_sentence",
            "unresolved_policy": "do_not_invent_or_substitute_links",
        },
        "results": {
            "rule_count": len(rule_types),
            "resolved_rule_count": len(rule_types) - len(unresolved_rule_ids),
            "unresolved_rule_count": len(unresolved_rule_ids),
            "unresolved_rule_ids": unresolved_rule_ids,
            "emitted_link_count": len(accepted),
            "rejected_candidate_count": len(rejected),
            "rejection_counts": dict(sorted(rejection_counts.items())),
            "rules": rule_results,
            "links": accepted_metadata,
            "rejected_candidates": rejected,
        },
    }
    return candidate_fields, accepted, manifest


def _render_csv(fieldnames: list[str], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _validate_rendered_csv(content: bytes, expected_rows: int) -> None:
    text = content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) != expected_rows:
        raise ValueError(
            f"rendered output row count mismatch: expected {expected_rows}, found {len(rows)}"
        )
    seen_links: set[str] = set()
    for row in rows:
        link_id = row["link_id"]
        if link_id in seen_links:
            raise ValueError(f"rendered output has duplicate link_id: {link_id}")
        seen_links.add(link_id)
        if row["screening_decision"] != "retain":
            raise ValueError(f"{link_id}: non-retain decision reached output")
        if row["supports_rule_release"].lower() != "false":
            raise ValueError(f"{link_id}: output grants release authority")
        if LOCATOR_PATTERN.fullmatch(row["locator"]) is None:
            raise ValueError(f"{link_id}: output has noncanonical locator {row['locator']!r}")
        parse_locator(row["locator"])


def main() -> int:
    fieldnames, rows, manifest = _build()
    csv_content = _render_csv(fieldnames, rows)
    _validate_rendered_csv(csv_content, len(rows))
    manifest["outputs"] = {
        "supporting_literature": {
            "path": OUTPUT_CSV.relative_to(ROOT).as_posix(),
            "sha256": _sha256_bytes(csv_content),
            "row_count": len(rows),
        },
        "manifest": {
            "path": OUTPUT_MANIFEST.relative_to(ROOT).as_posix(),
        },
    }
    manifest_content = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")

    _atomic_write(OUTPUT_CSV, csv_content)
    _atomic_write(OUTPUT_MANIFEST, manifest_content)
    unresolved = manifest["results"]["unresolved_rule_count"]  # type: ignore[index]
    print(
        f"v50 downstream links={len(rows)} unresolved_rules={unresolved} "
        f"csv={OUTPUT_CSV} manifest={OUTPUT_MANIFEST}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
