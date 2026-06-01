from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


SEARCH_RUN_COLUMNS = [
    "search_run_id",
    "source",
    "target_id",
    "query",
    "mapped_query",
    "filters",
    "search_date",
    "hit_count",
    "max_records",
    "export_method",
    "raw_path",
    "status",
    "notes",
]

RETRIEVED_RECORD_COLUMNS = [
    "record_id",
    "source",
    "target_id",
    "search_run_id",
    "title",
    "abstract_or_summary",
    "year",
    "journal_or_source",
    "doi",
    "pmid",
    "url",
    "raw_record_id",
    "dedup_key",
    "duplicate_of",
    "is_duplicate",
]

SCREENING_LOG_COLUMNS = [
    "record_id",
    "suggested_decision",
    "human_final_decision",
    "exclusion_reason",
    "reviewer",
    "review_date",
]

EVIDENCE_EXTRACTION_COLUMNS = [
    "record_id",
    "population",
    "supplement",
    "dose",
    "comparator",
    "outcome",
    "safety_signal",
    "locator",
    "linked_target",
]


class CsvModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def none_to_empty_string(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    def csv_row(self, columns: list[str]) -> dict[str, str]:
        data = self.model_dump()
        return {column: str(data.get(column, "")) for column in columns}


class SearchRun(CsvModel):
    search_run_id: str
    source: str
    target_id: str
    query: str
    mapped_query: str = ""
    filters: str = ""
    search_date: str = Field(default_factory=lambda: date.today().isoformat())
    hit_count: int = 0
    max_records: int = 0
    export_method: str = ""
    raw_path: str = ""
    status: str = "completed"
    notes: str = ""


class RetrievedRecord(CsvModel):
    record_id: str
    source: str
    target_id: str
    search_run_id: str
    title: str
    abstract_or_summary: str = ""
    year: str = ""
    journal_or_source: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    raw_record_id: str = ""
    dedup_key: str = ""
    duplicate_of: str = ""
    is_duplicate: str = "false"


class ScreeningLog(CsvModel):
    record_id: str
    suggested_decision: str = ""
    human_final_decision: str = ""
    exclusion_reason: str = ""
    reviewer: str = ""
    review_date: str = ""


class EvidenceExtraction(CsvModel):
    record_id: str
    population: str = ""
    supplement: str = ""
    dose: str = ""
    comparator: str = ""
    outcome: str = ""
    safety_signal: str = ""
    locator: str = ""
    linked_target: str = ""
