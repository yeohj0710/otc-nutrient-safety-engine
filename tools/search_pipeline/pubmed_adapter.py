from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import requests

from .schemas import RETRIEVED_RECORD_COLUMNS, SEARCH_RUN_COLUMNS, RetrievedRecord, SearchRun
from .storage import (
    SYSTEMATIC_SEARCH_DIR,
    append_csv_rows,
    ensure_layout,
    stable_hash,
    timestamp_id,
    to_repo_relative,
    upsert_csv_rows,
    write_json,
)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_TOOL_NAME = "nutrition_safety_engine"


@dataclass(frozen=True)
class PubMedResult:
    search_run: SearchRun
    records: list[RetrievedRecord]


class PubMedAdapter:
    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        output_root: Path = SYSTEMATIC_SEARCH_DIR,
        session: requests.Session | None = None,
    ) -> None:
        self.email = email or os.getenv("NCBI_EMAIL", "")
        self.api_key = api_key or os.getenv("NCBI_API_KEY", "")
        self.output_root = output_root
        self.session = session or requests.Session()

        if not self.email:
            raise ValueError("NCBI_EMAIL is required for PubMed E-utilities requests.")

    def run(
        self,
        *,
        target_id: str,
        query: str,
        filters: str = "",
        max_records: int = 500,
        search_date: str | None = None,
    ) -> PubMedResult:
        ensure_layout(self.output_root)
        run_id = f"pubmed_{target_id}_{timestamp_id()}_{stable_hash(query, 8)}"
        run_dir = self.output_root / "raw" / "pubmed" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        esearch_payload = self._esearch(query=query, max_records=max_records)
        write_json(run_dir / "esearch.json", esearch_payload)

        id_list = esearch_payload.get("esearchresult", {}).get("idlist", [])
        hit_count = int(esearch_payload.get("esearchresult", {}).get("count", 0))
        records: list[RetrievedRecord] = []

        for batch_index, pmids in enumerate(_chunks(id_list, 200), start=1):
            xml_text = self._efetch(pmids)
            raw_path = run_dir / f"efetch_{batch_index:03}.xml"
            raw_path.write_text(xml_text, encoding="utf-8")
            records.extend(
                parse_pubmed_xml(
                    xml_text,
                    target_id=target_id,
                    search_run_id=run_id,
                )
            )
            time.sleep(0.12 if self.api_key else 0.34)

        search_run = SearchRun(
            search_run_id=run_id,
            source="pubmed",
            target_id=target_id,
            query=query,
            mapped_query=query,
            filters=filters,
            search_date=search_date or date.today().isoformat(),
            hit_count=hit_count,
            max_records=max_records,
            export_method="ncbi_eutils_esearch_efetch",
            raw_path=to_repo_relative(run_dir),
            status="completed",
            notes=f"retrieved_pmids={len(id_list)}",
        )

        append_csv_rows(
            self.output_root / "search_runs.csv",
            [search_run.csv_row(SEARCH_RUN_COLUMNS)],
            SEARCH_RUN_COLUMNS,
        )
        upsert_csv_rows(
            self.output_root / "retrieved_records.csv",
            [record.csv_row(RETRIEVED_RECORD_COLUMNS) for record in records],
            RETRIEVED_RECORD_COLUMNS,
            key_column="record_id",
        )

        return PubMedResult(search_run=search_run, records=records)

    def _request(self, path: str, params: dict[str, object]) -> requests.Response:
        request_params = {
            "tool": PUBMED_TOOL_NAME,
            "email": self.email,
            **params,
        }
        if self.api_key:
            request_params["api_key"] = self.api_key

        last_response: requests.Response | None = None
        for attempt in range(5):
            response = self.session.get(
                f"{EUTILS_BASE}/{path}",
                params=request_params,
                timeout=30,
            )
            last_response = response
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response

            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = (2**attempt) * (0.34 if self.api_key else 1.0)
            time.sleep(delay)

        assert last_response is not None
        last_response.raise_for_status()
        return last_response

    def _esearch(self, *, query: str, max_records: int) -> dict[str, object]:
        response = self._request(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_records,
            },
        )
        return response.json()

    def _efetch(self, pmids: list[str]) -> str:
        response = self._request(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            },
        )
        return response.text


def parse_pubmed_xml(
    xml_text: str,
    *,
    target_id: str,
    search_run_id: str,
) -> list[RetrievedRecord]:
    root = ET.fromstring(xml_text)
    records: list[RetrievedRecord] = []

    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//MedlineCitation/PMID"))
        if not pmid:
            continue

        title = _iter_text(article.find(".//ArticleTitle"))
        abstract = _abstract_text(article)
        journal = (
            _text(article.find(".//Journal/Title"))
            or _text(article.find(".//Journal/ISOAbbreviation"))
        )
        year = _publication_year(article)
        doi = _article_id(article, "doi") or _elocation_id(article, "doi")

        records.append(
            RetrievedRecord(
                record_id=f"pubmed:{pmid}:{search_run_id}",
                source="pubmed",
                target_id=target_id,
                search_run_id=search_run_id,
                title=title,
                abstract_or_summary=abstract,
                year=year,
                journal_or_source=journal,
                doi=doi,
                pmid=pmid,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                raw_record_id=pmid,
            )
        )

    return records


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _text(element: ET.Element | None) -> str:
    return "" if element is None or element.text is None else element.text.strip()


def _iter_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _abstract_text(article: ET.Element) -> str:
    parts: list[str] = []
    for abstract in article.findall(".//Abstract/AbstractText"):
        text = _iter_text(abstract)
        if not text:
            continue
        label = abstract.attrib.get("Label", "").strip()
        parts.append(f"{label}: {text}" if label else text)
    return "\n".join(parts)


def _publication_year(article: ET.Element) -> str:
    candidates = [
        _text(article.find(".//JournalIssue/PubDate/Year")),
        _text(article.find(".//ArticleDate/Year")),
        _text(article.find(".//PubMedPubDate[@PubStatus='pubmed']/Year")),
    ]
    medline_date = _text(article.find(".//JournalIssue/PubDate/MedlineDate"))
    if medline_date[:4].isdigit():
        candidates.append(medline_date[:4])
    return next((candidate for candidate in candidates if candidate), "")


def _article_id(article: ET.Element, id_type: str) -> str:
    for element in article.findall(".//ArticleIdList/ArticleId"):
        if element.attrib.get("IdType", "").lower() == id_type.lower():
            return _text(element)
    return ""


def _elocation_id(article: ET.Element, id_type: str) -> str:
    for element in article.findall(".//ELocationID"):
        if element.attrib.get("EIdType", "").lower() == id_type.lower():
            return _text(element)
    return ""
