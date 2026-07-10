#!/usr/bin/env python3
"""Fetch missed PubMed seeds and record which Boolean query blocks fail."""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research.pubmed_full_retrieval import EUtilsClient, resolve_email


MISSED = {
    "K2": ["6308447"],
    "K3": ["37010569"],
    "K4": ["29988705", "37487817", "39218658"],
    "K5": ["37736439", "38846187"],
}


def text(node: ET.Element | None) -> str:
    return "" if node is None else "".join(node.itertext()).strip()


def extract(xml: str) -> list[dict[str, object]]:
    root = ET.fromstring(xml)
    rows: list[dict[str, object]] = []
    for article in root.findall(".//PubmedArticle"):
        citation = article.find("MedlineCitation")
        if citation is None:
            continue
        pmid = text(citation.find("PMID"))
        article_node = citation.find("Article")
        rows.append(
            {
                "pmid": pmid,
                "title": text(article_node.find("ArticleTitle") if article_node is not None else None),
                "abstract": " ".join(
                    text(part) for part in citation.findall(".//Abstract/AbstractText") if text(part)
                ),
                "mesh_terms": [text(item) for item in citation.findall(".//MeshHeading/DescriptorName")],
                "publication_types": [text(item) for item in citation.findall(".//PublicationType")],
            }
        )
    return rows


def main() -> None:
    email, _ = resolve_email()
    client = EUtilsClient(email=email)
    reverse = {pmid: node for node, pmids in MISSED.items() for pmid in pmids}
    ids = list(reverse)
    rows = extract(client.fetch(ids))
    found = {str(row["pmid"]) for row in rows}
    if found != set(ids):
        raise RuntimeError(f"seed diagnostic reconciliation failed expected={set(ids)} found={found}")
    for row in rows:
        row["node_id"] = reverse[str(row["pmid"])]
    rows.sort(key=lambda row: (str(row["node_id"]), str(row["pmid"])))
    output = REPO_ROOT / "research_v2" / "search" / "seed_miss_diagnostics.json"
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"diagnosed": len(rows), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
