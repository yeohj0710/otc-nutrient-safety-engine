from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "v40_literature_pipeline.py"
SPEC = importlib.util.spec_from_file_location("v40_literature_pipeline", MODULE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def test_picos_questions_cover_all_active_inputs() -> None:
    snapshot = pipeline.input_snapshot()
    pipeline.validate_question_coverage(snapshot, pipeline.QUESTION_SPECS)

    assert len(snapshot["products"]) == 13
    assert len(snapshot["ingredients"]) == 28
    assert len(snapshot["rules"]) == 16
    assert len(pipeline.QUESTION_SPECS) == 5


def test_parse_esearch_extracts_history_values() -> None:
    result = pipeline.parse_esearch(
        b"<eSearchResult><Count>12</Count><QueryKey>1</QueryKey>"
        b"<WebEnv>NCID_1</WebEnv><QueryTranslation>term</QueryTranslation></eSearchResult>"
    )
    assert result == {
        "count": 12,
        "query_key": "1",
        "webenv": "NCID_1",
        "translated_query": "term",
    }


def test_parse_and_normalize_pubmed_xml_merges_question_membership() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
    <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue><Title>Journal</Title></Journal>
    <ArticleTitle>Safety title</ArticleTitle><Abstract><AbstractText Label='RESULTS'>Safety result.</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
    </Article><MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList>
    </MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType='doi'>10.1/test</ArticleId></ArticleIdList></PubmedData>
    </PubmedArticle></PubmedArticleSet>"""
    first = pipeline.parse_pubmed_xml(xml, "Q1")
    second = pipeline.parse_pubmed_xml(xml, "Q2")
    result = pipeline.normalize_records([*first, *second])

    assert len(result) == 1
    assert result[0]["pmid"] == "123"
    assert result[0]["abstract"] == "RESULTS: Safety result."
    assert result[0]["question_ids"] == ["Q1", "Q2"]
    assert result[0]["doi"] == "10.1/test"


def test_picos_prompt_hash_is_stable() -> None:
    assert pipeline.sha256_bytes(pipeline.PICOS_PROMPT.encode("utf-8")) == pipeline.sha256_bytes(
        pipeline.PICOS_PROMPT.encode("utf-8")
    )
