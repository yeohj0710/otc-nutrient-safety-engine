import json

from scripts.research.otc.build_supporting_literature import TARGET, build, write


def test_supporting_literature_is_traceable_and_not_rule_release_evidence() -> None:
    papers = build()
    assert len(papers) >= 13
    assert len({paper["pmid"] for paper in papers}) == len(papers)
    assert all(paper["doi"] for paper in papers)
    assert all(paper["url"] == f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/" for paper in papers)
    assert all(paper["supportsRuleRelease"] is False for paper in papers)
    assert all(
        paper["evidenceRelation"]
        in {"supports_caution", "contextualizes_uncertainty", "supports_mechanism"}
        for paper in papers
    )
    assert all(
        paper["reviewStatus"] == "codex_curated_supporting_not_rule_release_evidence"
        for paper in papers
    )


def test_priority_condition_rules_have_directly_mapped_literature() -> None:
    papers = build()
    by_pmid = {paper["pmid"]: paper for paper in papers}
    assert "alcohol" in by_pmid["22851428"]["ruleTypes"]
    assert by_pmid["22851428"]["evidenceRelation"] == "contextualizes_uncertainty"
    assert "hepatic_disease" in by_pmid["31206302"]["ruleTypes"]
    assert "decongestant_hypertension" in by_pmid["17264159"]["ruleTypes"]
    assert "pregnancy_lactation" in by_pmid["16638921"]["ruleTypes"]
    assert by_pmid["16638921"]["profileConditions"] == ["pregnant"]
    assert "gi_bleeding_ulcer" in by_pmid["1834002"]["ruleTypes"]


def test_written_supporting_literature_matches_build(tmp_path) -> None:
    target = tmp_path / "otc-supporting-literature.json"
    write(target)
    assert json.loads(target.read_text(encoding="utf-8")) == build()


def test_canonical_supporting_literature_matches_the_validated_csv() -> None:
    assert json.loads(TARGET.read_text(encoding="utf-8")) == build()
