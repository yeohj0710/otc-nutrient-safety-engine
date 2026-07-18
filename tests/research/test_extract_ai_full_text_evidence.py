from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from scripts.research.extract_ai_full_text_evidence import run


def test_extracts_located_candidates_without_misreading_lab_units(tmp_path: Path) -> None:
    root = tmp_path / "research_v3"
    source = root / "full_text" / "oa_xml" / "PMC1.xml"
    source.parent.mkdir(parents=True)
    source.write_text(
        """<article><front><article-title>Iron trial</article-title></front><body><sec><title>Safety</title>
        <p id="P1">Adults received 45 mg daily for 12 weeks. Gastrointestinal adverse events included nausea and constipation.</p>
        <p id="P2">Hemoglobin was 13 g/dL in adult men and this paragraph describes risk without a supplement dose.</p>
        <p id="P3">A safety arm received 10,000 IU daily for supplementation, and investigators reported an adverse event during follow-up.</p>
        </sec></body></article>""",
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = root / "full_text" / "retrieval_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "evidence_candidate_id", "pmid", "pmcid", "retrieval_status", "retrieval_url", "local_path",
            "bytes", "sha256", "retrieved_at_utc", "error", "review_status",
        ])
        writer.writeheader()
        writer.writerow({"evidence_candidate_id": "EV-K3-1", "pmid": "1", "pmcid": "PMC1",
                         "retrieval_status": "retrieved_open_access_xml", "local_path": "research_v3/full_text/oa_xml/PMC1.xml",
                         "sha256": digest})
    queue = root / "human_review_minimal" / "03_우선문헌_118건_검토.csv"
    queue.parent.mkdir(parents=True)
    with queue.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["evidence_candidate_id", "clinical_node_id", "title"])
        writer.writeheader(); writer.writerow({"evidence_candidate_id": "EV-K3-1", "clinical_node_id": "K3", "title": "Iron trial"})

    report = run(root)
    rows = list(csv.DictReader((root / "extraction" / "ai_full_text_evidence_candidates.csv").open(encoding="utf-8-sig")))
    assert report["source_hash_mismatches"] == []
    assert report["human_verified_candidates"] == 0
    assert rows[0]["section_title"] == "Safety"
    assert "45 mg daily" in rows[0]["dose_mentions"]
    lab_row = next(row for row in rows if row["locator"].endswith("P2"))
    assert "13 g" not in lab_row["dose_mentions"]
    comma_row = next(row for row in rows if row["locator"].endswith("P3"))
    assert "10,000 IU daily" in comma_row["dose_mentions"]
    assert "000 IU" not in comma_row["dose_mentions"].split(";")
    assert all(row["review_status"] == "ai_extracted_not_human_verified" for row in rows)


def test_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "research_v3"
    source = root / "full_text" / "oa_xml" / "PMC1.xml"
    source.parent.mkdir(parents=True)
    source.write_text("<article><body/></article>", encoding="utf-8")
    manifest = root / "full_text" / "retrieval_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["evidence_candidate_id", "pmid", "pmcid", "retrieval_status", "retrieval_url", "local_path", "bytes", "sha256", "retrieved_at_utc", "error", "review_status"])
        writer.writeheader(); writer.writerow({"evidence_candidate_id": "EV-K1-1", "pmid": "1", "pmcid": "PMC1", "retrieval_status": "retrieved_open_access_xml", "local_path": "research_v3/full_text/oa_xml/PMC1.xml", "sha256": "bad"})
    queue = root / "human_review_minimal" / "03_우선문헌_118건_검토.csv"
    queue.parent.mkdir(parents=True)
    queue.write_text("evidence_candidate_id,clinical_node_id,title\nEV-K1-1,K1,T\n", encoding="utf-8")
    report = run(root)
    assert report["source_hash_mismatches"] == ["EV-K1-1"]
    assert report["ai_evidence_candidates"] == 0
