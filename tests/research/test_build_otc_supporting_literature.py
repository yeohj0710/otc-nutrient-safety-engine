import csv
import json
import re

from scripts.research.otc.build_supporting_literature import (
    DISCLAIMER_KO,
    RULES,
    TARGET,
    build,
    write,
)


def _rule_rows() -> list[dict[str, str]]:
    with RULES.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_supporting_literature_is_traceable_and_not_rule_release_evidence() -> None:
    papers = build()
    assert len(papers) >= 13
    assert len({paper["pmid"] for paper in papers}) == len(papers)
    assert all(paper["doi"] for paper in papers)
    assert all(paper["journal"] for paper in papers)
    assert all(paper["url"] == f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/" for paper in papers)
    assert all(paper["supportsRuleRelease"] is False for paper in papers)
    assert all(paper["evidenceAuthority"] == "literature_explanatory_only" for paper in papers)
    assert all(paper["disclaimerKo"] == DISCLAIMER_KO for paper in papers)
    assert all(
        paper["evidenceRelation"]
        in {"supports_caution", "contextualizes_uncertainty", "supports_mechanism"}
        for paper in papers
    )
    assert all(
        paper["reviewStatus"] == "agent_curated_from_v40_retained_corpus"
        for paper in papers
    )


def test_every_rule_has_a_sentence_level_literature_locator() -> None:
    """규칙 16개 전부에 문헌이 붙어야 하고, 모든 연결은 초록 문장 locator 를 가진다."""
    papers = build()
    links = [link for paper in papers for link in paper["ruleLinks"]]
    assert {row["rule_id"] for row in _rule_rows()} == {link["ruleId"] for link in links}
    for link in links:
        assert re.fullmatch(r"abstract:sentence:\d+", link["locator"]), link
        assert link["locatorQuoteEn"].strip()
        assert link["keyFindingKo"].strip()
        assert link["limitationKo"].strip()


def test_authorization_conflicts_are_preserved_not_dropped() -> None:
    """허가원문과 어긋나는 문헌을 지우지 않고 conflict 로 보존한다."""
    links = [link for paper in build() for link in paper["ruleLinks"]]
    conflicts = [link for link in links if link["authorizationAlignment"] == "conflict"]
    assert conflicts, "conflict 가 하나도 없으면 충돌을 지웠는지 의심해야 한다"
    for link in conflicts:
        assert link["authorizationNoteKo"].strip()
    assert all(
        link["authorizationAlignment"] in {"consistent", "conflict"} for link in links
    )


def test_draft_rule_literature_is_marked_as_unreleased() -> None:
    """maximum_duration 은 draft 라서 문헌이 붙어도 배포 규칙으로 보이면 안 된다."""
    links = [link for paper in build() for link in paper["ruleLinks"]]
    draft_links = [link for link in links if link["ruleType"] == "maximum_duration"]
    assert draft_links
    assert all(link["ruleReleased"] is False for link in draft_links)


def test_personalization_axis_uses_observed_values_only() -> None:
    papers = build()
    profile_keys = {
        "pregnant",
        "lactating",
        "liverDisease",
        "kidneyDisease",
        "giBleedingOrUlcer",
        "hypertensionOrCardiovascularDisease",
        "willDrive",
        "alcohol",
        "medications",
        "ageYears",
        "redFlagSymptoms",
    }
    for paper in papers:
        assert set(paper["profileConditions"]) <= profile_keys
        assert set(paper["doseInputConditions"]) <= {"hoursSincePreviousDose", "continuousDays"}
        assert all(value.startswith("ING-") for value in paper["ingredientIds"])


def test_written_supporting_literature_matches_build(tmp_path) -> None:
    target = tmp_path / "otc-supporting-literature.json"
    write(target)
    assert json.loads(target.read_text(encoding="utf-8")) == build()


def test_canonical_supporting_literature_matches_the_validated_csv() -> None:
    assert json.loads(TARGET.read_text(encoding="utf-8")) == build()
