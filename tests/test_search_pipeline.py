from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tools.search_pipeline.curation import _matched_terms
from tools.search_pipeline.dedup import dedup_retrieved_records
from tools.search_pipeline.pubmed_adapter import (
    PubMedAdapter,
    PubMedRetrievalLimitError,
    parse_pubmed_xml,
)
from tools.search_pipeline.ris_parser import parse_ris_file
from tools.search_pipeline.schemas import RETRIEVED_RECORD_COLUMNS
from tools.search_pipeline.storage import write_csv_rows


class PubMedParserTest(unittest.TestCase):
    def test_parse_pubmed_xml_extracts_core_fields(self) -> None:
        xml = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal>
          <Title>Test Journal</Title>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Omega-3 and bleeding risk</ArticleTitle>
        <Abstract>
          <AbstractText Label="Background">Warfarin users were studied.</AbstractText>
          <AbstractText>Bleeding outcome was assessed.</AbstractText>
        </Abstract>
        <ELocationID EIdType="doi">10.1000/example</ELocationID>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/example</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""
        records = parse_pubmed_xml(xml, target_id="anticoag", search_run_id="run-1")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].record_id, "pubmed:12345:run-1")
        self.assertEqual(records[0].doi, "10.1000/example")
        self.assertEqual(records[0].year, "2024")
        self.assertIn("Warfarin users", records[0].abstract_or_summary)


class PubMedFullRetrievalTest(unittest.TestCase):
    def test_full_retrieval_rejects_result_over_10000(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = PubMedAdapter(email="test@example.com", output_root=Path(tmp))
            adapter._esearch = Mock(
                return_value={"esearchresult": {"count": "10001", "idlist": []}}
            )

            with self.assertRaisesRegex(
                PubMedRetrievalLimitError, "segment the query"
            ):
                adapter.run(target_id="K1", query="vitamin D", max_records=None)

    def test_full_retrieval_requests_and_imports_every_uid_under_limit(self) -> None:
        count_payload = {"esearchresult": {"count": "3", "idlist": []}}
        uid_payload = {
            "esearchresult": {"count": "3", "idlist": ["1", "2", "3"]}
        }
        xml = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>One</ArticleTitle></Article></MedlineCitation></PubmedArticle>
  <PubmedArticle><MedlineCitation><PMID>2</PMID><Article><ArticleTitle>Two</ArticleTitle></Article></MedlineCitation></PubmedArticle>
  <PubmedArticle><MedlineCitation><PMID>3</PMID><Article><ArticleTitle>Three</ArticleTitle></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>
"""
        with tempfile.TemporaryDirectory() as tmp:
            adapter = PubMedAdapter(email="test@example.com", output_root=Path(tmp))
            adapter._esearch = Mock(side_effect=[count_payload, uid_payload])
            adapter._efetch = Mock(return_value=xml)

            result = adapter.run(
                target_id="K1", query="vitamin D", max_records=None
            )

        self.assertEqual(result.search_run.hit_count, 3)
        self.assertEqual(result.search_run.exported_count, 3)
        self.assertEqual(result.search_run.imported_count, 3)
        self.assertEqual(result.search_run.retrieval_mode, "full")
        self.assertEqual(len(result.records), 3)
        self.assertEqual(adapter._esearch.call_args_list[0].kwargs["max_records"], 0)
        self.assertEqual(adapter._esearch.call_args_list[1].kwargs["max_records"], 3)


class RisParserTest(unittest.TestCase):
    def test_parse_ris_file_extracts_core_fields(self) -> None:
        ris = """TY  - JOUR
TI  - Warfarin and dietary supplement interactions
AB  - Abstract text.
PY  - 2021
JF  - British Journal of Clinical Pharmacology
DO  - 10.1111/example
UR  - https://example.org/article
AN  - L2005415619
ER  -
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ris"
            path.write_text(ris, encoding="utf-8")
            records = parse_ris_file(path, source="embase", target_id="anticoag", search_run_id="run-2")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].record_id, "embase:L2005415619:run-2")
        self.assertEqual(records[0].doi, "10.1111/example")
        self.assertEqual(records[0].journal_or_source, "British Journal of Clinical Pharmacology")


class DedupTest(unittest.TestCase):
    def test_dedup_marks_later_duplicate_by_doi(self) -> None:
        rows = [
            {
                "record_id": "pubmed:1",
                "source": "pubmed",
                "title": "Same paper",
                "doi": "10.1000/ABC",
            },
            {
                "record_id": "embase:L1",
                "source": "embase",
                "title": "Same paper",
                "doi": "https://doi.org/10.1000/abc",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_csv_rows(root / "retrieved_records.csv", rows, RETRIEVED_RECORD_COLUMNS)
            result = dedup_retrieved_records(root)

        self.assertEqual(result.total_records, 2)
        self.assertEqual(result.duplicate_records, 1)


class CurationTermMatchTest(unittest.TestCase):
    def test_short_terms_match_word_boundaries_only(self) -> None:
        text = "atrial stratification in anticoagulant users"

        self.assertEqual(_matched_terms(text, ("rat", "cat")), [])
        self.assertEqual(_matched_terms("rat model and cat study", ("rat", "cat")), ["rat", "cat"])


if __name__ == "__main__":
    unittest.main()
