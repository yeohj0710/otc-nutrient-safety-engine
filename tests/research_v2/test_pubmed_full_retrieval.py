from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from tools.search_pipeline.pubmed_adapter import parse_pubmed_xml


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "research" / "pubmed_full_retrieval.py"
SPEC = importlib.util.spec_from_file_location("pubmed_full_retrieval", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def count(self, query: str) -> int:
        return self.counts[query]


def test_small_query_is_one_segment() -> None:
    query = "vitamin d"
    start = date(2020, 1, 1)
    end = date(2020, 1, 2)
    scoped = MODULE.dated_query(query, start, end)
    segments = MODULE.plan_segments(FakeClient({scoped: 12}), query, start, end)
    assert len(segments) == 1
    assert segments[0].count == 12


def test_large_query_splits_without_overlap() -> None:
    query = "iron"
    start = date(2020, 1, 1)
    end = date(2020, 1, 4)
    whole = MODULE.dated_query(query, start, end)
    left = MODULE.dated_query(query, date(2020, 1, 1), date(2020, 1, 2))
    right = MODULE.dated_query(query, date(2020, 1, 3), date(2020, 1, 4))
    segments = MODULE.plan_segments(
        FakeClient({whole: 12_000, left: 6_000, right: 6_000}), query, start, end
    )
    assert [(item.start, item.end, item.count) for item in segments] == [
        ("2020-01-01", "2020-01-02", 6_000),
        ("2020-01-03", "2020-01-04", 6_000),
    ]


def test_single_day_above_limit_fails_closed() -> None:
    query = "zinc"
    day = date(2020, 1, 1)
    scoped = MODULE.dated_query(query, day, day)
    with pytest.raises(RuntimeError, match="single publication day"):
        MODULE.plan_segments(FakeClient({scoped: 10_001}), query, day, day)


def test_file_manifest_excludes_its_own_manifest(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "raw_manifest.json").write_text("{}", encoding="utf-8")
    result = MODULE.file_manifest(tmp_path)
    assert [item["path"] for item in result] == ["a.txt"]
    assert len(result[0]["sha256"]) == 64
    assert MODULE.raw_files_sha256(result) == MODULE.raw_files_sha256(result)
    assert len(MODULE.raw_files_sha256(result)) == 64


def test_pubmed_parser_keeps_pubmed_book_articles() -> None:
    xml = """<?xml version="1.0"?>
    <PubmedArticleSet>
      <PubmedBookArticle>
        <BookDocument>
          <PMID>25905352</PMID>
          <ArticleTitle>Hypercalcemia</ArticleTitle>
          <Abstract><AbstractText>Book chapter abstract.</AbstractText></Abstract>
          <Book><BookTitle>Endotext</BookTitle><PubDate><Year>2000</Year></PubDate></Book>
          <ArticleIdList><ArticleId IdType="bookaccession">NBK279129</ArticleId></ArticleIdList>
        </BookDocument>
      </PubmedBookArticle>
    </PubmedArticleSet>"""
    records = parse_pubmed_xml(xml, target_id="K1", search_run_id="run")
    assert len(records) == 1
    assert records[0].pmid == "25905352"
    assert records[0].title == "Hypercalcemia"
    assert records[0].journal_or_source == "Endotext"
