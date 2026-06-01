from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.search_pipeline.dedup import dedup_retrieved_records
from tools.search_pipeline.pubmed_adapter import parse_pubmed_xml
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


if __name__ == "__main__":
    unittest.main()
