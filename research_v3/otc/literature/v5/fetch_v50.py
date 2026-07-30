"""Fetch the complete v5 PubMed corpus and preserve every raw XML response.

Phase A must have completed before this program runs.  Queries over PubMed's
10,000 UID ceiling are split into non-overlapping publication-date intervals;
the interval counts must reconcile exactly to the contemporaneous base count.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parents[4]
V5 = Path(__file__).resolve().parent
QUERY_DEFINITIONS = V5 / "query_definitions.json"
PROBE_REPORT = V5 / "probe_report.json"
EVIDENCE_MAP = V5 / "evidence_map.csv"
CORPUS_MANIFEST = V5 / "corpus_manifest.json"
SEARCHES = V5 / "searches"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_EMAIL = "yeohj0710@yonsei.ac.kr"
QUESTION_ORDER = [
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
]
EVIDENCE_COLUMNS = [
    "record_id",
    "pmid",
    "all_pmids",
    "title",
    "abstract",
    "has_abstract",
    "journal",
    "publication_year",
    "doi",
    "publication_types",
    "mesh_terms",
    "question_ids",
    "search_run_ids",
    "source_database",
    "deduplication_key",
    "input_sha256",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def text_sha256(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def stable_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def normalize_doi(value: str) -> str:
    cleaned = normalize_space(value).strip().lower()
    cleaned = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", cleaned)
    cleaned = re.sub(r"^doi:\s*", "", cleaned)
    return cleaned.rstrip(". ")


def element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return normalize_space("".join(element.itertext()))


def child_text(element: ET.Element, path: str) -> str:
    found = element.find(path)
    return element_text(found)


def abstract_text(article: ET.Element) -> str:
    parts: list[str] = []
    for node in article.findall(".//Abstract/AbstractText"):
        value = element_text(node)
        if not value:
            continue
        label = normalize_space(node.attrib.get("Label", ""))
        parts.append(f"{label}: {value}" if label else value)
    return "\n".join(parts)


def article_id(article: ET.Element, id_type: str) -> str:
    for node in article.findall(".//ArticleIdList/ArticleId"):
        if node.attrib.get("IdType", "").lower() == id_type.lower():
            return element_text(node)
    return ""


def elocation_id(article: ET.Element, id_type: str) -> str:
    for node in article.findall(".//ELocationID"):
        if (
            node.attrib.get("EIdType", "").lower() == id_type.lower()
            and node.attrib.get("ValidYN", "Y").upper() != "N"
        ):
            return element_text(node)
    return ""


def publication_year(article: ET.Element) -> str:
    candidates = [
        child_text(article, ".//JournalIssue/PubDate/Year"),
        child_text(article, ".//ArticleDate/Year"),
        child_text(article, ".//PubMedPubDate[@PubStatus='pubmed']/Year"),
        child_text(article, ".//PubMedPubDate[@PubStatus='entrez']/Year"),
        child_text(article, ".//Book/PubDate/Year"),
        child_text(article, ".//ContributionDate/Year"),
    ]
    medline_date = child_text(article, ".//JournalIssue/PubDate/MedlineDate")
    match = re.search(r"(?:18|19|20|21)\d{2}", medline_date)
    if match:
        candidates.append(match.group(0))
    return next((value for value in candidates if value), "")


def parse_pubmed_xml(xml_bytes: bytes, question_id: str, run_id: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = child_text(article, ".//MedlineCitation/PMID")
        if not pmid:
            continue
        title = element_text(article.find(".//ArticleTitle"))
        abstract = abstract_text(article)
        journal = child_text(article, ".//Journal/Title") or child_text(
            article, ".//Journal/ISOAbbreviation"
        )
        doi = normalize_doi(article_id(article, "doi") or elocation_id(article, "doi"))
        publication_types = sorted(
            {
                element_text(node)
                for node in article.findall(".//PublicationTypeList/PublicationType")
                if element_text(node)
            }
        )
        mesh_terms = sorted(
            {
                element_text(node)
                for node in article.findall(".//MeshHeading/DescriptorName")
                if element_text(node)
            }
        )
        records.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "publication_year": publication_year(article),
                "doi": doi,
                "publication_types": publication_types,
                "mesh_terms": mesh_terms,
                "question_id": question_id,
                "search_run_id": run_id,
            }
        )
    for article in root.findall(".//PubmedBookArticle"):
        pmid = child_text(article, ".//BookDocument/PMID")
        if not pmid:
            continue
        title = element_text(article.find(".//BookDocument/ArticleTitle"))
        abstract = abstract_text(article)
        journal = element_text(article.find(".//BookDocument/Book/BookTitle"))
        doi = normalize_doi(article_id(article, "doi"))
        publication_types = sorted(
            {
                element_text(node)
                for node in article.findall(".//PublicationType")
                if element_text(node)
            }
        )
        mesh_terms = sorted(
            {
                element_text(node)
                for node in article.findall(".//MeshHeading/DescriptorName")
                if element_text(node)
            }
        )
        records.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "publication_year": publication_year(article),
                "doi": doi,
                "publication_types": publication_types,
                "mesh_terms": mesh_terms,
                "question_id": question_id,
                "search_run_id": run_id,
            }
        )
    return records


@dataclass
class ResponseRecord:
    request_type: str
    requested_at_utc: str
    completed_at_utc: str
    status_code: int
    response_bytes: int
    response_sha256: str
    relative_path: str
    parameters: dict[str, Any]


class EUtilsClient:
    def __init__(self, email: str, api_key: str, run_dir: Path) -> None:
        self.email = email
        self.api_key = api_key
        self.run_dir = run_dir
        self.session = requests.Session()
        self.last_request_started = 0.0
        self.responses: list[ResponseRecord] = []

    def request(self, url: str, params: dict[str, Any], output: Path, kind: str) -> bytes:
        payload: dict[str, Any] = {
            "tool": "otc_safety_v50",
            "email": self.email,
            **params,
        }
        if self.api_key:
            payload["api_key"] = self.api_key
        last_error: Exception | None = None
        for attempt in range(7):
            interval = 0.11 if self.api_key else 0.36
            delay = interval - (time.monotonic() - self.last_request_started)
            if delay > 0:
                time.sleep(delay)
            started = utc_now()
            self.last_request_started = time.monotonic()
            try:
                response = self.session.post(url, data=payload, timeout=180)
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After", "")
                    wait = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else min(60.0, 2**attempt)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                content = response.content
                ET.fromstring(content)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(content)
                redacted = {
                    key: value
                    for key, value in payload.items()
                    if key not in {"api_key", "email", "WebEnv"}
                }
                relative = output.relative_to(self.run_dir).as_posix()
                self.responses.append(
                    ResponseRecord(
                        request_type=kind,
                        requested_at_utc=started,
                        completed_at_utc=utc_now(),
                        status_code=response.status_code,
                        response_bytes=len(content),
                        response_sha256=sha256_bytes(content),
                        relative_path=relative,
                        parameters=redacted,
                    )
                )
                return content
            except (requests.RequestException, ET.ParseError) as error:
                last_error = error
                time.sleep(min(60.0, 2**attempt))
        raise RuntimeError(f"{kind} failed after retries: {last_error}")

    def esearch(self, query: str, output: Path, label: str) -> dict[str, Any]:
        content = self.request(
            ESEARCH_URL,
            {
                "db": "pubmed",
                "term": query,
                "retmode": "xml",
                "retmax": 0,
                "usehistory": "y",
            },
            output,
            f"esearch:{label}",
        )
        root = ET.fromstring(content)
        count = int(root.findtext(".//Count", "0"))
        query_key = root.findtext(".//QueryKey", "")
        webenv = root.findtext(".//WebEnv", "")
        errors = [element_text(node) for node in root.findall(".//ERROR")]
        warnings = [element_text(node) for node in root.findall(".//WarningList/*")]
        if errors:
            raise RuntimeError(f"ESearch error for {label}: {errors}")
        if count and (not query_key or not webenv):
            raise RuntimeError(f"ESearch history missing for {label}")
        return {
            "label": label,
            "query": query,
            "query_sha256": text_sha256(query),
            "count": count,
            "query_key": query_key,
            "webenv": webenv,
            "warnings": warnings,
            "raw_path": output.relative_to(self.run_dir).as_posix(),
            "raw_sha256": sha256_bytes(content),
        }

    def efetch(
        self,
        *,
        history: dict[str, Any],
        retstart: int,
        retmax: int,
        output: Path,
        label: str,
    ) -> bytes:
        return self.request(
            EFETCH_URL,
            {
                "db": "pubmed",
                "query_key": history["query_key"],
                "WebEnv": history["webenv"],
                "retstart": retstart,
                "retmax": retmax,
                "retmode": "xml",
            },
            output,
            f"efetch:{label}",
        )


def entrez_dated_query(query: str, start: str, end: str) -> str:
    """Partition a result set by its single-valued PubMed Entrez date.

    Publication-date intervals are not disjoint in PubMed because one citation
    can carry both electronic and print publication dates.  Entrez date is a
    technical retrieval key only; the frozen publication-date eligibility
    clause remains unchanged inside ``query``.
    """

    return f'({query}) AND ("{start}"[Date - Entrez] : "{end}"[Date - Entrez])'


def build_entrez_date_histories(
    client: EUtilsClient, query: str, run_dir: Path
) -> list[dict[str, Any]]:
    current_year = datetime.now(timezone.utc).year
    histories: list[dict[str, Any]] = []

    def visit(start_year: int, end_year: int) -> None:
        start = f"{start_year}/01/01"
        end = f"{end_year}/12/31"
        label = f"edat_{start_year}_{end_year}"
        history = client.esearch(
            entrez_dated_query(query, start, end),
            run_dir / "segments" / f"{label}_esearch.xml",
            label,
        )
        history["interval_start"] = start
        history["interval_end"] = end
        history["partition_field"] = "Date - Entrez"
        if history["count"] <= 9_999:
            histories.append(history)
            return
        if start_year == end_year:
            raise RuntimeError(
                f"single Entrez-date year exceeds 9,999: {label}; finer split required"
            )
        midpoint = (start_year + end_year) // 2
        visit(start_year, midpoint)
        visit(midpoint + 1, end_year)

    visit(1900, current_year)
    tail_start = f"{current_year + 1}/01/01"
    tail_label = f"edat_{current_year + 1}_3000"
    tail = client.esearch(
        entrez_dated_query(query, tail_start, "3000"),
        run_dir / "segments" / f"{tail_label}_esearch.xml",
        tail_label,
    )
    tail["interval_start"] = tail_start
    tail["interval_end"] = "3000"
    tail["partition_field"] = "Date - Entrez"
    if tail["count"] > 9_999:
        raise RuntimeError("future Entrez-date tail exceeds 9,999")
    histories.append(tail)
    return histories


def write_checksums(run_dir: Path) -> dict[str, str]:
    xml_files = sorted(run_dir.rglob("*.xml"))
    checksums = {
        path.relative_to(run_dir).as_posix(): file_sha256(path) for path in xml_files
    }
    lines = [f"{digest}  {relative}" for relative, digest in checksums.items()]
    (run_dir / "checksum.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums


def fetch_question(
    definition: dict[str, Any],
    probe_question: dict[str, Any],
    run_id: str,
    email: str,
    api_key: str,
    batch_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    qid = definition["question_id"]
    run_dir = SEARCHES / qid / run_id
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing raw run: {run_dir}")
    run_dir.mkdir(parents=True)
    client = EUtilsClient(email, api_key, run_dir)
    started = utc_now()
    query = definition["query"]
    if text_sha256(query) != definition["query_sha256"]:
        raise ValueError(f"frozen query hash mismatch: {qid}")
    base = client.esearch(query, run_dir / "base_esearch.xml", "base")

    histories: list[dict[str, Any]] = []
    segmentation = "none"
    if base["count"] <= 9_999:
        histories = [base]
    else:
        segmentation = "non_overlapping_entrez_date_binary_intervals"
        histories = build_entrez_date_histories(client, query, run_dir)
        segment_sum = sum(item["count"] for item in histories)
        if segment_sum != base["count"]:
            raise RuntimeError(
                f"segment reconciliation failed for {qid}: base={base['count']} segments={segment_sum}"
            )

    parsed: list[dict[str, Any]] = []
    for history_index, history in enumerate(histories, start=1):
        count = history["count"]
        if count == 0:
            continue
        safe_label = re.sub(r"[^0-9A-Za-z_.-]+", "_", history["label"])
        for batch_index, retstart in enumerate(range(0, count, batch_size), start=1):
            retmax = min(batch_size, count - retstart)
            output = run_dir / "efetch" / f"{history_index:03d}_{safe_label}_{batch_index:04d}.xml"
            content = client.efetch(
                history=history,
                retstart=retstart,
                retmax=retmax,
                output=output,
                label=f"{history['label']}:{batch_index}",
            )
            batch_records = parse_pubmed_xml(content, qid, run_id)
            if len(batch_records) != retmax:
                raise RuntimeError(
                    f"EFetch reconciliation failed for {qid} {history['label']} batch {batch_index}: "
                    f"requested={retmax} parsed={len(batch_records)}"
                )
            parsed.extend(batch_records)

    pmids = [row["pmid"] for row in parsed]
    unique_pmids = set(pmids)
    if len(parsed) != base["count"] or len(unique_pmids) != base["count"]:
        duplicate_pmids = sorted(pmid for pmid, count in Counter(pmids).items() if count > 1)
        raise RuntimeError(
            f"question reconciliation failed for {qid}: base={base['count']} parsed={len(parsed)} "
            f"unique_pmids={len(unique_pmids)} duplicate_sample={duplicate_pmids[:10]}"
        )

    checksums = write_checksums(run_dir)
    response_metadata = {
        "schema_version": "5.0.0",
        "question_id": qid,
        "run_id": run_id,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "phase_a_probe_count": probe_question["hit_count"],
        "phase_b_base_count": base["count"],
        "change_since_probe": base["count"] - probe_question["hit_count"],
        "query_sha256": definition["query_sha256"],
        "segmentation": segmentation,
        "segments": [
            {
                key: value
                for key, value in history.items()
                if key not in {"webenv", "query_key", "query"}
            }
            for history in histories
        ],
        "segment_count_sum": sum(item["count"] for item in histories),
        "parsed_records": len(parsed),
        "unique_pmids": len(unique_pmids),
        "efetch_batch_size": batch_size,
        "efetch_calls": sum(1 for item in client.responses if item.request_type.startswith("efetch:")),
        "esearch_calls": sum(1 for item in client.responses if item.request_type.startswith("esearch:")),
        "raw_xml_file_count": len(checksums),
        "raw_xml_checksums": checksums,
        "responses": [record.__dict__ for record in client.responses],
        "status": "complete",
    }
    metadata_path = run_dir / "response_metadata.json"
    metadata_path.write_text(
        json.dumps(response_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return parsed, {
        "question_id": qid,
        "run_id": run_id,
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "query_sha256": definition["query_sha256"],
        "phase_a_probe_count": probe_question["hit_count"],
        "phase_b_base_count": base["count"],
        "change_since_probe": base["count"] - probe_question["hit_count"],
        "segmentation": segmentation,
        "segment_count_sum": sum(item["count"] for item in histories),
        "raw_parsed_records": len(parsed),
        "unique_pmids": len(unique_pmids),
        "raw_xml_file_count": len(checksums),
        "checksum_manifest_sha256": file_sha256(run_dir / "checksum.sha256"),
        "response_metadata_sha256": file_sha256(metadata_path),
        "efetch_calls": response_metadata["efetch_calls"],
        "esearch_calls": response_metadata["esearch_calls"],
        "status": "complete",
    }


def load_completed_question(
    definition: dict[str, Any], probe_question: dict[str, Any], run_id: str
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Load and verify a completed question so an interrupted run can resume."""

    qid = definition["question_id"]
    run_dir = SEARCHES / qid / run_id
    metadata_path = run_dir / "response_metadata.json"
    checksum_path = run_dir / "checksum.sha256"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") != "complete":
        raise RuntimeError(f"existing run is not complete: {run_dir}")
    if metadata.get("question_id") != qid or metadata.get("query_sha256") != definition["query_sha256"]:
        raise RuntimeError(f"existing run identity or query hash mismatch: {run_dir}")
    if not checksum_path.exists():
        raise RuntimeError(f"missing checksum manifest: {run_dir}")
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    observed_xml = {
        path.relative_to(run_dir).as_posix(): file_sha256(path)
        for path in sorted(run_dir.rglob("*.xml"))
    }
    if expected != observed_xml:
        raise RuntimeError(f"raw XML checksum mismatch: {run_dir}")
    parsed: list[dict[str, Any]] = []
    for path in sorted((run_dir / "efetch").glob("*.xml")):
        parsed.extend(parse_pubmed_xml(path.read_bytes(), qid, run_id))
    expected_count = int(metadata["phase_b_base_count"])
    pmids = {row["pmid"] for row in parsed}
    if len(parsed) != expected_count or len(pmids) != expected_count:
        raise RuntimeError(
            f"resumed raw reconciliation failed for {qid}: expected={expected_count} "
            f"parsed={len(parsed)} unique_pmids={len(pmids)}"
        )
    return parsed, {
        "question_id": qid,
        "run_id": run_id,
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "query_sha256": definition["query_sha256"],
        "phase_a_probe_count": int(probe_question["hit_count"]),
        "phase_b_base_count": expected_count,
        "change_since_probe": expected_count - int(probe_question["hit_count"]),
        "segmentation": metadata["segmentation"],
        "segment_count_sum": int(metadata["segment_count_sum"]),
        "raw_parsed_records": len(parsed),
        "unique_pmids": len(pmids),
        "raw_xml_file_count": len(observed_xml),
        "checksum_manifest_sha256": file_sha256(checksum_path),
        "response_metadata_sha256": file_sha256(metadata_path),
        "efetch_calls": int(metadata["efetch_calls"]),
        "esearch_calls": int(metadata["esearch_calls"]),
        "status": "complete",
        "resumed_from_verified_raw": True,
    }


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    # Apply the protocol literally per citation: use DOI when present; only a
    # citation with no DOI may fall back to exact title.  A no-DOI citation is
    # therefore never inferred to be the same paper as a DOI-bearing citation.
    # This conservative boundary avoids merging generic translated titles.
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if row["doi"]:
            key = f"doi:{normalize_doi(row['doi'])}"
        elif row["title"]:
            key = f"title:{normalize_space(row['title'])}"
        else:
            key = f"pmid:{row['pmid']}"
        groups[key].append(row)

    output: list[dict[str, str]] = []
    for key, members in groups.items():
        sorted_members = sorted(
            members,
            key=lambda row: (
                0 if row["abstract"] else 1,
                -len(row["abstract"]),
                int(row["pmid"]) if row["pmid"].isdigit() else 10**20,
            ),
        )
        primary = sorted_members[0]
        all_pmids = sorted(
            {row["pmid"] for row in members},
            key=lambda value: int(value) if value.isdigit() else 10**20,
        )
        question_ids = sorted(
            {row["question_id"] for row in members}, key=QUESTION_ORDER.index
        )
        run_ids = sorted({row["search_run_id"] for row in members})
        publication_types = sorted(
            {value for row in members for value in row["publication_types"]}
        )
        mesh_terms = sorted({value for row in members for value in row["mesh_terms"]})
        doi = next((row["doi"] for row in sorted_members if row["doi"]), "")
        canonical_payload = {
            "pmids": all_pmids,
            "title": primary["title"],
            "abstract": primary["abstract"],
            "journal": primary["journal"],
            "publication_year": primary["publication_year"],
            "doi": doi,
            "publication_types": publication_types,
            "mesh_terms": mesh_terms,
            "question_ids": question_ids,
            "search_run_ids": run_ids,
        }
        output.append(
            {
                "record_id": f"PMID-{primary['pmid']}",
                "pmid": primary["pmid"],
                "all_pmids": ";".join(all_pmids),
                "title": primary["title"],
                "abstract": primary["abstract"],
                "has_abstract": "true" if bool(primary["abstract"]) else "false",
                "journal": primary["journal"],
                "publication_year": primary["publication_year"],
                "doi": doi,
                "publication_types": ";".join(publication_types),
                "mesh_terms": ";".join(mesh_terms),
                "question_ids": ";".join(question_ids),
                "search_run_ids": ";".join(run_ids),
                "source_database": "PubMed",
                "deduplication_key": key,
                "input_sha256": stable_json_sha256(canonical_payload),
            }
        )
    output.sort(
        key=lambda row: (
            int(row["pmid"]) if row["pmid"].isdigit() else 10**20,
            row["record_id"],
        )
    )
    duplicate_groups = [members for members in groups.values() if len(members) > 1]
    stats = {
        "input_membership_records": len(records),
        "unique_papers": len(output),
        "records_removed_by_cross_question_or_bibliographic_deduplication": len(records) - len(output),
        "multi_member_deduplication_groups": len(duplicate_groups),
        "doi_keyed_papers": sum(row["deduplication_key"].startswith("doi:") for row in output),
        "title_keyed_papers_without_doi": sum(row["deduplication_key"].startswith("title:") for row in output),
        "pmid_fallback_papers_without_doi_or_title": sum(row["deduplication_key"].startswith("pmid:") for row in output),
    }
    return output, stats


def write_evidence_map(rows: list[dict[str, str]]) -> None:
    temporary = EVIDENCE_MAP.with_name(f".{EVIDENCE_MAP.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, EVIDENCE_MAP)


def write_json_atomic(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("NCBI_EMAIL", DEFAULT_EMAIL))
    parser.add_argument("--api-key", default=os.getenv("NCBI_API_KEY", ""))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--run-id",
        help="Resume this run ID by verifying and loading completed question directories.",
    )
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1_000:
        raise ValueError("batch size must be between 1 and 1,000")

    started = utc_now()
    definitions = json.loads(QUERY_DEFINITIONS.read_text(encoding="utf-8"))
    probe = json.loads(PROBE_REPORT.read_text(encoding="utf-8"))
    if probe.get("status") != "complete" or probe.get("totals", {}).get("efetch_calls") != 0:
        raise ValueError("Phase A probe is not a complete count-only run")
    if probe.get("query_definitions_sha256") != file_sha256(QUERY_DEFINITIONS):
        raise ValueError("Phase A probe does not match the current frozen query definitions")
    questions = {row["question_id"]: row for row in definitions["questions"]}
    probe_questions = {row["question_id"]: row for row in probe["questions"]}
    if list(questions) != QUESTION_ORDER or set(probe_questions) != set(QUESTION_ORDER):
        raise ValueError("question order or coverage mismatch")
    for qid in QUESTION_ORDER:
        if probe_questions[qid].get("query_sha256") != questions[qid].get("query_sha256"):
            raise ValueError(f"Phase A query hash mismatch: {qid}")
    run_id = args.run_id or f"v50_{compact_utc_now()}"
    if not re.fullmatch(r"v50_[0-9]{8}T[0-9]{6}Z", run_id):
        raise ValueError("run ID must match v50_YYYYMMDDTHHMMSSZ")
    all_records: list[dict[str, Any]] = []
    per_question: list[dict[str, Any]] = []
    for qid in QUESTION_ORDER:
        completed = load_completed_question(questions[qid], probe_questions[qid], run_id)
        if completed is not None:
            rows, summary = completed
            print(json.dumps({"event": "verified_raw_resume", **summary}, ensure_ascii=False))
        else:
            print(json.dumps({"event": "fetch_start", "question_id": qid, "run_id": run_id}))
            rows, summary = fetch_question(
                questions[qid], probe_questions[qid], run_id, args.email, args.api_key, args.batch_size
            )
        all_records.extend(rows)
        per_question.append(summary)
        print(json.dumps({"event": "fetch_complete", **summary}, ensure_ascii=False))

    evidence_rows, deduplication = deduplicate(all_records)
    write_evidence_map(evidence_rows)
    per_question_membership = {
        qid: sum(qid in row["question_ids"].split(";") for row in evidence_rows)
        for qid in QUESTION_ORDER
    }
    overlaps = Counter(
        tuple(row["question_ids"].split(";"))
        for row in evidence_rows
        if ";" in row["question_ids"]
    )
    manifest = {
        "schema_version": "5.0.0",
        "phase": "B",
        "status": "complete",
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "run_id": run_id,
        "source_database": "PubMed",
        "retrieval_method": "NCBI ESearch history plus EFetch; publication-date segmentation above 9,999 results",
        "deduplication_rule": "normalized DOI; when DOI is absent, whitespace-normalized exact title; PMID only when DOI and title are both absent",
        "query_definitions_path": QUERY_DEFINITIONS.relative_to(ROOT).as_posix(),
        "query_definitions_sha256": file_sha256(QUERY_DEFINITIONS),
        "probe_report_path": PROBE_REPORT.relative_to(ROOT).as_posix(),
        "probe_report_sha256": file_sha256(PROBE_REPORT),
        "questions": [
            {
                **summary,
                "canonical_membership_rows": per_question_membership[summary["question_id"]],
            }
            for summary in per_question
        ],
        "totals": {
            "phase_a_probe_hits_before_cross_question_deduplication": sum(
                row["phase_a_probe_count"] for row in per_question
            ),
            "phase_b_hits_before_cross_question_deduplication": len(all_records),
            "question_membership_units_after_bibliographic_deduplication": sum(per_question_membership.values()),
            "evidence_map_rows_unique_papers": len(evidence_rows),
            "unique_pmids": len({row["pmid"] for row in all_records}),
            "esearch_calls": sum(row["esearch_calls"] for row in per_question),
            "efetch_calls": sum(row["efetch_calls"] for row in per_question),
            "raw_xml_files": sum(row["raw_xml_file_count"] for row in per_question),
        },
        "per_question_membership_rows": per_question_membership,
        "cross_question_overlap_patterns": [
            {"question_ids": list(key), "paper_count": count}
            for key, count in sorted(overlaps.items())
        ],
        "deduplication": deduplication,
        "evidence_map": {
            "path": EVIDENCE_MAP.relative_to(ROOT).as_posix(),
            "sha256": file_sha256(EVIDENCE_MAP),
            "rows": len(evidence_rows),
            "columns": EVIDENCE_COLUMNS,
        },
        "independent_blinding": False,
        "release_ready": False,
    }
    with EVIDENCE_MAP.open(encoding="utf-8", newline="") as handle:
        written_rows = sum(1 for _ in csv.DictReader(handle))
    if written_rows != len(evidence_rows):
        raise RuntimeError(
            f"written evidence map row reconciliation failed: {written_rows} != {len(evidence_rows)}"
        )
    write_json_atomic(CORPUS_MANIFEST, manifest)
    print(
        json.dumps(
            {
                "status": "complete",
                "run_id": run_id,
                "raw_records": len(all_records),
                "unique_papers": len(evidence_rows),
                "question_membership_units": sum(per_question_membership.values()),
                "evidence_map_sha256": manifest["evidence_map"]["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
