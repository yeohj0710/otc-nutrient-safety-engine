from __future__ import annotations

import csv
import json
import os
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research.otc import audit_v51_source_freshness as audit


ROOT = Path(__file__).resolve().parents[2]
STABLE_NOW = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)


class FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type


class FakeResponse:
    def __init__(
        self,
        *,
        body: bytes = b"%PDF-1.7\nvalid",
        content_type: str = "application/pdf",
        final_url: str,
        status: int = 200,
    ) -> None:
        self.body = body
        self.headers = FakeHeaders(content_type)
        self.final_url = final_url
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.final_url

    def read(self) -> bytes:
        return self.body


def copy_evidence_links(tmp_path: Path) -> Path:
    target = tmp_path / audit.EVIDENCE_LINKS.relative_to(ROOT)
    target.parent.mkdir(parents=True)
    target.write_bytes(audit.EVIDENCE_LINKS.read_bytes())
    return target


def rewrite_csv(
    path: Path,
    mutate: Callable[[list[dict[str, str]]], None],
) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    mutate(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def local_pdf_bytes(url: str, _timeout: float, _retries: int) -> bytes:
    match = audit.MFDS_PDF_RE.fullmatch(url)
    assert match is not None
    return (
        ROOT
        / "research_v3"
        / "otc"
        / "raw"
        / "nedrug"
        / match.group("item_sequence")
        / f"{match.group('document_type')}.pdf"
    ).read_bytes()


def pinned_text(
    _pdf_bytes: bytes,
    source: audit.SourceRecord,
    _scratch: Path,
) -> str:
    return audit.pinned_text_path(ROOT, source).read_text(encoding="utf-8")


def test_semantic_normalization_ignores_layout_but_not_content() -> None:
    left = "임신 3기\n이부프로펜"
    right = "임신\t３기 이부프로펜"

    assert audit.normalize_semantic_text(left) == audit.normalize_semantic_text(right)
    assert audit.compare_texts(left, right)["semanticTextMatch"] is True
    assert audit.compare_texts(left, right + " 변경")["semanticTextMatch"] is False
    document = audit.normalize_excerpt("상위 지시문 중간 목록 대상 항목")
    assert audit.excerpt_matches_document("상위 지시문 … 대상 항목", document)
    assert not audit.excerpt_matches_document("대상 항목 … 상위 지시문", document)


@pytest.mark.parametrize(
    ("pinned", "changed"),
    [
        ("1일 최대 4그램", "1일 최대 8그램"),
        ("함께 복용하지 않는다.", "함께 복용한다."),
        ("임신 말기 3개월", "임신 초기 3개월"),
        ("의사·약사와 상의", "의사, 약사와 상의"),
    ],
)
def test_semantic_normalization_preserves_clinically_meaningful_changes(
    pinned: str,
    changed: str,
) -> None:
    assert audit.compare_texts(pinned, changed)["semanticTextMatch"] is False


def test_source_inventory_is_complete_and_official() -> None:
    sources = audit.load_sources(ROOT)

    assert len(sources) == 20
    assert sum(len(source.evidence_rows) for source in sources) == 360
    assert sum(
        row["evidence_status"] == "verified_primary"
        for source in sources
        for row in source.evidence_rows
    ) == 15
    assert all(audit.MFDS_PDF_RE.fullmatch(source.url) for source in sources)


def test_source_inventory_fails_closed_when_a_candidate_is_missing(
    tmp_path: Path,
) -> None:
    path = copy_evidence_links(tmp_path)
    rewrite_csv(path, lambda rows: rows.pop())

    with pytest.raises(ValueError, match="expected 360 evidence candidate links"):
        audit.load_sources(tmp_path)


def test_source_inventory_fails_closed_when_verified_membership_changes(
    tmp_path: Path,
) -> None:
    path = copy_evidence_links(tmp_path)

    def swap_verified_status(rows: list[dict[str, str]]) -> None:
        verified = next(row for row in rows if row["evidence_status"] == "verified_primary")
        provisional = next(row for row in rows if row["evidence_status"] == "provisional")
        verified["evidence_status"] = "provisional"
        provisional["evidence_status"] = "verified_primary"

    rewrite_csv(path, swap_verified_status)

    with pytest.raises(ValueError, match="verified-primary candidate IDs"):
        audit.load_sources(tmp_path)


def test_source_inventory_checks_document_and_product_identity(
    tmp_path: Path,
) -> None:
    path = copy_evidence_links(tmp_path)

    def change_document_type(rows: list[dict[str, str]]) -> None:
        rows[0]["document_type"] = "UD"

    rewrite_csv(path, change_document_type)

    with pytest.raises(ValueError, match="source URL/document type mismatch"):
        audit.load_sources(tmp_path)


def test_source_inventory_rejects_a_different_official_url_set(
    tmp_path: Path,
) -> None:
    path = copy_evidence_links(tmp_path)

    def substitute_source(rows: list[dict[str, str]]) -> None:
        for row in rows:
            if row["item_sequence"] == "200501321":
                row["item_sequence"] = "200501322"
                row["product_id"] = "MFDS-200501322"
                row["source_url"] = row["source_url"].replace("200501321", "200501322")

    rewrite_csv(path, substitute_source)

    with pytest.raises(ValueError, match="approved 20-URL source inventory"):
        audit.load_sources(tmp_path)


def test_source_inventory_rejects_changed_candidate_source_text(
    tmp_path: Path,
) -> None:
    path = copy_evidence_links(tmp_path)

    def change_excerpt(rows: list[dict[str, str]]) -> None:
        rows[0]["raw_candidate_evidence_text"] += "변경"

    rewrite_csv(path, change_excerpt)

    with pytest.raises(ValueError, match="candidate source inventory digest"):
        audit.load_sources(tmp_path)


def test_fetch_pdf_checks_status_content_type_magic_and_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://nedrug.mfds.go.kr/dsie/pdf/drb/202106092/NB"

    def install(response: FakeResponse) -> None:
        monkeypatch.setattr(audit, "urlopen", lambda *_args, **_kwargs: response)

    install(FakeResponse(final_url=url))
    assert audit.fetch_pdf(url, timeout_seconds=1, retries=0).startswith(b"%PDF-")

    install(FakeResponse(final_url=url, status=206))
    with pytest.raises(RuntimeError, match="HTTP 206"):
        audit.fetch_pdf(url, timeout_seconds=1, retries=0)

    install(FakeResponse(final_url=url, content_type="text/html"))
    with pytest.raises(RuntimeError, match="invalid PDF response"):
        audit.fetch_pdf(url, timeout_seconds=1, retries=0)

    install(FakeResponse(final_url=url, body=b"not a PDF"))
    with pytest.raises(RuntimeError, match="invalid PDF response"):
        audit.fetch_pdf(url, timeout_seconds=1, retries=0)

    redirected = "https://nedrug.mfds.go.kr/dsie/pdf/drb/198601920/NB"
    install(FakeResponse(final_url=redirected))
    with pytest.raises(RuntimeError, match="unexpected redirect target"):
        audit.fetch_pdf(url, timeout_seconds=1, retries=0)


def test_fetch_pdf_rejects_noncanonical_initial_url_without_requesting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = False

    def should_not_run(*_args: object, **_kwargs: object) -> FakeResponse:
        nonlocal requested
        requested = True
        raise AssertionError("request should not run")

    monkeypatch.setattr(audit, "urlopen", should_not_run)

    with pytest.raises(ValueError, match="unsupported MFDS PDF URL"):
        audit.fetch_pdf("https://example.com/not-official.pdf", 1, 0)
    assert requested is False


def test_offline_audit_matches_every_pinned_document_and_candidate_excerpt() -> None:
    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    assert snapshot["summary"] == {
        "officialSourceUrlCount": 20,
        "semantic_match": 20,
        "semantic_drift": 0,
        "unreachable": 0,
        "candidateLinkCount": 360,
        "candidateExcerptMatchCount": 360,
        "candidateExcerptMismatchCount": 0,
        "verifiedPrimaryLinkCount": 15,
        "verifiedPrimaryCandidateExcerptMatchCount": 15,
        "newRulesActivated": 0,
        "releaseReady": False,
    }
    assert snapshot["accessedAtUtc"] == "2026-07-31T14:00:00+00:00"
    assert snapshot["generator"] == (
        "scripts/research/otc/audit_v51_source_freshness.py"
    )
    assert len(snapshot["generatorSha256"]) == 64
    assert snapshot["inputs"]["evidenceRuleLinks"]["path"] == (
        "research_v51/evidence/evidence_rule_links.csv"
    )
    assert len(snapshot["inputs"]["evidenceRuleLinks"]["sha256"]) == 64
    assert all(source["snapshotPdfByteMatch"] for source in snapshot["sources"])
    assert snapshot["volatilityProbe"]["semanticTextStable"] is True
    assert audit.audit_passed(snapshot) is True


def test_audit_gate_fails_closed_for_every_integrity_dimension() -> None:
    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    page_drift = deepcopy(snapshot)
    page_drift["sources"][0]["semanticPageMatch"] = False
    page_drift["sources"][0]["mismatchedPages"] = [1]
    assert audit.audit_passed(page_drift) is False

    candidate_mismatch = deepcopy(snapshot)
    candidate_mismatch["sources"][0]["candidateExcerptMatchCount"] -= 1
    candidate_mismatch["sources"][0]["candidateExcerptMismatchIds"] = [
        "synthetic-candidate"
    ]
    candidate_mismatch["summary"]["candidateExcerptMatchCount"] -= 1
    candidate_mismatch["summary"]["candidateExcerptMismatchCount"] += 1
    assert audit.audit_passed(candidate_mismatch) is False

    verified_mismatch = deepcopy(snapshot)
    verified_source = next(
        source
        for source in verified_mismatch["sources"]
        if source["verifiedPrimaryLinkCount"]
    )
    verified_source["verifiedPrimaryCandidateExcerptMatchCount"] -= 1
    verified_source["verifiedPrimaryCandidateExcerptMismatchIds"] = [
        "synthetic-verified"
    ]
    verified_mismatch["summary"]["verifiedPrimaryCandidateExcerptMatchCount"] -= 1
    assert audit.audit_passed(verified_mismatch) is False

    unstable_probe = deepcopy(snapshot)
    unstable_probe["volatilityProbe"]["semanticTextStable"] = False
    unstable_probe["volatilityProbe"]["secondSemanticTextSha256"] = "0" * 64
    unstable_probe["volatilityProbe"]["interpretation"] = "semantic_difference_observed"
    assert audit.audit_passed(unstable_probe) is False

    unreachable_probe = deepcopy(snapshot)
    unreachable_probe["volatilityProbe"] = {"status": "unreachable"}
    assert audit.audit_passed(unreachable_probe) is False

    stale_generator = deepcopy(snapshot)
    stale_generator["generatorSha256"] = "0" * 64
    assert audit.audit_passed(stale_generator) is False

    stale_evidence_input = deepcopy(snapshot)
    stale_evidence_input["inputs"]["evidenceRuleLinks"]["sha256"] = "0" * 64
    assert audit.audit_passed(stale_evidence_input) is False

    invalid_access_time = deepcopy(snapshot)
    invalid_access_time["accessedAtUtc"] = "not-a-timestamp"
    assert audit.audit_passed(invalid_access_time) is False

    wrong_product = deepcopy(snapshot)
    wrong_product["sources"][0]["productName"] = "다른 제품"
    assert audit.audit_passed(wrong_product) is False

    wrong_pinned_text = deepcopy(snapshot)
    wrong_pinned_text["sources"][-1]["pinnedSemanticTextSha256"] = "0" * 64
    wrong_pinned_text["sources"][-1]["remoteSemanticTextSha256"] = "0" * 64
    assert audit.audit_passed(wrong_pinned_text) is False


def test_shared_snapshot_validator_rejects_forged_pdf_hash_and_time_window() -> None:
    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    forged_pdf = deepcopy(snapshot)
    source = next(
        item
        for item in forged_pdf["sources"]
        if item["url"] != forged_pdf["volatilityProbe"]["url"]
    )
    source["pinnedSnapshotPdfSha256"] = "0" * 64
    source["remotePdfSha256"] = "0" * 64
    source["snapshotPdfByteMatch"] = True
    assert audit.audit_passed(
        forged_pdf,
        root=ROOT,
        now_utc=STABLE_NOW,
    ) is False

    future = deepcopy(snapshot)
    future["accessedAtUtc"] = "2026-08-01T00:00:01+00:00"
    assert audit.audit_passed(
        future,
        root=ROOT,
        now_utc=STABLE_NOW,
    ) is False

    pre_baseline = deepcopy(snapshot)
    pre_baseline["accessedAtUtc"] = "2026-07-30T23:59:59+00:00"
    assert audit.audit_passed(
        pre_baseline,
        root=ROOT,
        now_utc=STABLE_NOW,
    ) is False


def test_volatility_probe_rejects_a_non_pdf_second_response() -> None:
    request_count = 0

    def non_pdf_on_probe(url: str, timeout: float, retries: int) -> bytes:
        nonlocal request_count
        request_count += 1
        if request_count == 21:
            return b"not a PDF"
        return local_pdf_bytes(url, timeout, retries)

    snapshot = audit.audit(
        ROOT,
        fetcher=non_pdf_on_probe,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    assert snapshot["summary"]["semantic_match"] == 20
    assert snapshot["volatilityProbe"]["status"] == "unreachable"
    assert audit.audit_passed(snapshot) is False


def test_main_returns_nonzero_when_non_source_summary_gate_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )
    snapshot["sources"][0]["candidateExcerptMatchCount"] -= 1
    snapshot["sources"][0]["candidateExcerptMismatchIds"] = [
        "synthetic-candidate"
    ]
    snapshot["summary"]["candidateExcerptMatchCount"] -= 1
    snapshot["summary"]["candidateExcerptMismatchCount"] += 1
    monkeypatch.setattr(audit, "audit", lambda **_kwargs: snapshot)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(
        audit,
        "parse_args",
        lambda: SimpleNamespace(
            output=tmp_path / audit.OUTPUT_RELATIVE,
            timeout_seconds=1,
            retries=0,
        ),
    )

    assert audit.main() == 1


def test_main_reloads_and_compares_persisted_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )
    output = tmp_path / audit.OUTPUT_RELATIVE
    real_write = audit.write_snapshot

    def write_then_corrupt(
        value: dict[str, object],
        *,
        output: Path,
        root: Path,
    ) -> None:
        real_write(value, output=output, root=root)
        output.write_bytes(b'{"corrupt": true}\n')

    monkeypatch.setattr(audit, "audit", lambda **_kwargs: snapshot)
    monkeypatch.setattr(audit, "write_snapshot", write_then_corrupt)
    monkeypatch.setattr(audit, "audit_passed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(
        audit,
        "parse_args",
        lambda: SimpleNamespace(
            output=output,
            timeout_seconds=1,
            retries=0,
        ),
    )

    with pytest.raises(ValueError, match="persisted freshness snapshot differs"):
        audit.main()


def test_main_holds_persisted_snapshot_through_audit_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    protected = tmp_path / "research_v3" / "protected-input.json"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"ATTACK")
    snapshot = {
        "summary": {
            "officialSourceUrlCount": 20,
            "semantic_match": 20,
            "semantic_drift": 0,
            "unreachable": 0,
            "candidateExcerptMatchCount": 360,
            "candidateLinkCount": 360,
        }
    }
    attacked = False

    def swap_during_audit_gate(*_args: object, **_kwargs: object) -> bool:
        nonlocal attacked
        output.unlink()
        os.link(protected, output)
        attacked = True
        return True

    monkeypatch.setattr(audit, "audit", lambda **_kwargs: snapshot)
    monkeypatch.setattr(audit, "audit_passed", swap_during_audit_gate)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(
        audit,
        "parse_args",
        lambda: SimpleNamespace(
            output=output,
            timeout_seconds=1,
            retries=0,
        ),
    )

    with pytest.raises(ValueError, match="hard link|identity|pathname"):
        audit.main()

    assert attacked is True
    assert protected.read_bytes() == b"ATTACK"
    assert output.read_bytes() == b"ATTACK"


def test_freshness_snapshot_write_uses_only_canonical_atomic_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    snapshot = {"summary": {"officialSourceUrlCount": 20}}

    audit.write_snapshot(snapshot, output=output, root=tmp_path)

    assert json.loads(output.read_text(encoding="utf-8")) == snapshot
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


def test_freshness_staged_hardlink_swap_is_rejected_and_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    old_payload = b'{"old": true}\n'
    output.write_bytes(old_payload)
    protected = tmp_path / "research_v3" / "protected-input.json"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"ATTACK")

    real_replace = os.replace
    attacked = False

    def swap_stage(source: str | Path, destination: str | Path) -> None:
        nonlocal attacked
        source_path = Path(source)
        destination_path = Path(destination)
        if not attacked and destination_path == output:
            source_path.unlink()
            os.link(protected, source_path)
            attacked = True
        real_replace(source_path, destination_path)

    monkeypatch.setattr(audit.os, "replace", swap_stage)

    with pytest.raises(ValueError, match="staged|post-replace"):
        audit.write_snapshot(
            {"summary": {"officialSourceUrlCount": 20}},
            output=output,
            root=tmp_path,
        )

    assert attacked is True
    assert output.read_bytes() == old_payload
    assert protected.read_bytes() == b"ATTACK"
    assert protected.stat().st_nlink == 1
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


def test_freshness_post_replace_path_swap_is_rejected_and_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    old_payload = b'{"old": true}\n'
    output.write_bytes(old_payload)
    protected = tmp_path / "research_v3" / "protected-input.json"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"ATTACK")

    real_replace = os.replace
    attacked = False

    def swap_persisted_path(source: str | Path, destination: str | Path) -> None:
        nonlocal attacked
        destination_path = Path(destination)
        real_replace(source, destination_path)
        if not attacked and destination_path == output:
            destination_path.unlink()
            os.link(protected, destination_path)
            attacked = True

    monkeypatch.setattr(audit.os, "replace", swap_persisted_path)

    with pytest.raises(ValueError, match="post-replace"):
        audit.write_snapshot(
            {"summary": {"officialSourceUrlCount": 20}},
            output=output,
            root=tmp_path,
        )

    assert attacked is True
    assert output.read_bytes() == old_payload
    assert protected.read_bytes() == b"ATTACK"
    assert protected.stat().st_nlink == 1


@pytest.mark.parametrize(
    "relative_target",
    (
        Path("research_v3/otc/rules/rules.csv"),
        Path("research_v51/evidence/evidence_rule_links.csv"),
        Path("research_v51/audit/not-the-snapshot.json"),
    ),
)
def test_freshness_snapshot_rejects_noncanonical_output_without_overwrite(
    tmp_path: Path,
    relative_target: Path,
) -> None:
    protected = tmp_path / relative_target
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected-input")

    with pytest.raises(ValueError, match="canonical"):
        audit.write_snapshot({"replacement": True}, output=protected, root=tmp_path)

    assert protected.read_bytes() == b"protected-input"


def test_freshness_snapshot_rejects_hardlink_and_samefile_aliases(
    tmp_path: Path,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    protected = tmp_path / "research_v3" / "protected.json"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected")
    try:
        os.link(protected, output)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")

    with pytest.raises(ValueError, match="hardlink"):
        audit.write_snapshot({"replacement": True}, output=output, root=tmp_path)

    alias_path = tmp_path / "research_v3" / "snapshot-alias.json"
    os.link(output, alias_path)
    with pytest.raises(ValueError, match="canonical"):
        audit.validate_snapshot_output(alias_path, root=tmp_path)
    assert protected.read_bytes() == b"protected"
    assert output.read_bytes() == b"protected"


def test_freshness_snapshot_rejects_canonical_symlink_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / audit.OUTPUT_RELATIVE
    output.parent.mkdir(parents=True, exist_ok=True)
    protected = tmp_path / "research_v3" / "protected.json"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"protected")
    try:
        output.symlink_to(protected)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    with pytest.raises(ValueError, match="symlink"):
        audit.write_snapshot({"replacement": True}, output=output, root=tmp_path)

    assert protected.read_bytes() == b"protected"


def test_freshness_main_validates_output_before_network_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protected = tmp_path / "research_v51" / "evidence" / "input.csv"
    protected.parent.mkdir(parents=True, exist_ok=True)
    protected.write_bytes(b"source-data")
    audit_called = False

    def should_not_audit(**_kwargs: object) -> dict[str, object]:
        nonlocal audit_called
        audit_called = True
        raise AssertionError("audit should not run")

    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "audit", should_not_audit)
    monkeypatch.setattr(
        audit,
        "parse_args",
        lambda: SimpleNamespace(
            output=protected,
            timeout_seconds=1,
            retries=0,
        ),
    )

    with pytest.raises(SystemExit, match="canonical"):
        audit.main()

    assert audit_called is False
    assert protected.read_bytes() == b"source-data"


def test_offline_audit_marks_semantic_drift_without_activating_a_rule() -> None:
    def changed_text(
        pdf_bytes: bytes,
        source: audit.SourceRecord,
        scratch: Path,
    ) -> str:
        text = pinned_text(pdf_bytes, source, scratch)
        return text + ("의미 변경" if source.item_sequence == "196800036" else "")

    snapshot = audit.audit(
        ROOT,
        fetcher=local_pdf_bytes,
        extractor=changed_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    assert snapshot["summary"]["semantic_drift"] == 1
    assert snapshot["summary"]["semantic_match"] == 19
    assert snapshot["summary"]["newRulesActivated"] == 0
    changed = [
        source
        for source in snapshot["sources"]
        if source["status"] == "semantic_drift"
    ]
    assert [(source["itemSequence"], source["documentType"]) for source in changed] == [
        ("196800036", "NB")
    ]


def test_audit_rejects_non_pdf_fetches_as_unreachable() -> None:
    def html_fetch(_url: str, _timeout: float, _retries: int) -> bytes:
        return b"<html>blocked</html>"

    snapshot = audit.audit(
        ROOT,
        fetcher=html_fetch,
        extractor=pinned_text,
        accessed_at_utc="2026-07-31T14:00:00+00:00",
    )

    assert snapshot["summary"]["unreachable"] == 20
    assert snapshot["summary"]["semantic_match"] == 0
    assert snapshot["volatilityProbe"] == {"status": "not_run"}
