from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path


NODE_INGREDIENT = {
    "K1": "vitamin D/calcium",
    "K2": "vitamin B6",
    "K3": "iron",
    "K4": "magnesium",
    "K5": "zinc",
}
NODE_TERMS = {
    "K1": ("hypercalcemia", "hypercalciuria", "nephrolithiasis", "kidney stone", "toxicity"),
    "K2": ("neuropathy", "neurotoxicity", "sensory", "paresthesia", "toxicity"),
    "K3": ("gastrointestinal", "nausea", "constipation", "diarrhea", "abdominal", "iron overload", "toxicity"),
    "K4": ("diarrhea", "hypermagnesemia", "gastrointestinal", "toxicity"),
    "K5": ("nausea", "gastrointestinal", "copper deficiency", "anemia", "toxicity"),
}
GENERAL_TERMS = ("adverse event", "adverse effect", "side effect", "safety", "tolerability", "risk", "harm")
DOSE_RE = re.compile(
    r"(?<![\d,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s?(?:mg|µg|ug|mcg|IU|g)(?:\s*/\s*day|\s+per day|\s+daily)?\b(?!\s*/\s*(?:dL|L|mL)\b)",
    re.I,
)
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:day|week|month|year)s?\b", re.I)
POP_RE = re.compile(r"\b(?:adult|women|woman|men|man|pregnan\w*|postmenopausal|child\w*|infant\w*|elderly|older\s+(?:adult|women|men))\b", re.I)
DESIGN_TERMS = ("randomized", "double-blind", "placebo", "cohort", "case-control", "cross-sectional", "systematic review", "meta-analysis", "trial")
CANDIDATE_FIELDS = [
    "evidence_candidate_id", "parent_candidate_id", "pmid", "pmcid", "clinical_node_id", "ingredient", "title",
    "source_path", "source_sha256", "section_title", "locator", "evidence_text", "signal_types", "dose_mentions",
    "population_mentions", "duration_mentions", "design_signals", "ai_relevance_score", "reviewer_id", "review_status",
    "human_verification_required",
]
ARTICLE_FIELDS = [
    "pmcid", "source_path", "source_sha256", "linked_candidate_records", "paragraphs_parsed",
    "ai_evidence_candidates", "review_status",
]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading = ""
        self.in_p = False
        self.in_heading = False
        self.buf: list[str] = []
        self.paragraphs: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4"}:
            self.in_heading, self.buf = True, []
        elif tag == "p":
            self.in_p, self.buf = True, []

    def handle_endtag(self, tag: str) -> None:
        if self.in_heading and tag in {"h1", "h2", "h3", "h4"}:
            self.heading = clean("".join(self.buf))
            self.in_heading, self.buf = False, []
        elif self.in_p and tag == "p":
            text = clean("".join(self.buf))
            if len(text) >= 80:
                self.paragraphs.append((self.heading or "Body", f"html-p{len(self.paragraphs)+1}", text))
            self.in_p, self.buf = False, []

    def handle_data(self, data: str) -> None:
        if self.in_p or self.in_heading:
            self.buf.append(data)


def xml_paragraphs(path: Path) -> tuple[str, list[tuple[str, str, str]]]:
    root = ET.parse(path).getroot()
    title_node = root.find(".//article-title")
    title = clean("".join(title_node.itertext())) if title_node is not None else ""
    rows: list[tuple[str, str, str]] = []
    body = root.find(".//body")
    paragraph_index = 0

    def walk(element: ET.Element, section_path: list[str]) -> None:
        nonlocal paragraph_index
        if element.tag.rsplit("}", 1)[-1] == "sec":
            title_element = next((child for child in element if child.tag.rsplit("}", 1)[-1] == "title"), None)
            section_title = clean("".join(title_element.itertext())) if title_element is not None else ""
            if section_title:
                section_path = [*section_path, section_title]
        for child in element:
            local = child.tag.rsplit("}", 1)[-1]
            if local == "p":
                paragraph_index += 1
                text = clean("".join(child.itertext()))
                if len(text) >= 80:
                    rows.append((" > ".join(section_path) or "Body", child.get("id", f"p{paragraph_index}"), text))
            elif local not in {"title", "table-wrap", "fig", "ref-list"}:
                walk(child, section_path)

    if body is not None:
        walk(body, [])
    return title, rows


def html_paragraphs(path: Path) -> tuple[str, list[tuple[str, str, str]]]:
    parser = ParagraphParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return "", parser.paragraphs


def sentence_excerpt(text: str, terms: tuple[str, ...]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chosen = [s for s in sentences if any(term in s.lower() for term in terms) or DOSE_RE.search(s)]
    excerpt = clean(" ".join(chosen[:2]) or text)
    return excerpt[:500].rstrip()


def run(root: Path) -> dict[str, object]:
    manifest_path = root / "full_text" / "retrieval_manifest.csv"
    queue_path = root / "human_review_minimal" / "03_우선문헌_118건_검토.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        queue = {row["evidence_candidate_id"]: row for row in csv.DictReader(handle)}

    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    hash_mismatches: list[str] = []
    for row in manifest:
        if row["retrieval_status"] not in {"retrieved_open_access_xml", "retrieved_public_pmc_html"}:
            continue
        path = root.parent / row["local_path"]
        if sha256(path) != row["sha256"]:
            hash_mismatches.append(row["evidence_candidate_id"])
            continue
        by_source[str(path)].append(row)

    candidates: list[dict[str, object]] = []
    article_rows: list[dict[str, object]] = []
    for source_name, source_manifest in sorted(by_source.items()):
        path = Path(source_name)
        title_from_source, paragraphs = xml_paragraphs(path) if path.suffix.lower() == ".xml" else html_paragraphs(path)
        source_candidate_count = 0
        for manifest_row in source_manifest:
            metadata = queue.get(manifest_row["evidence_candidate_id"], {})
            node = metadata.get("clinical_node_id", manifest_row["evidence_candidate_id"].split("-")[1])
            terms = NODE_TERMS.get(node, ()) + GENERAL_TERMS
            scored: list[tuple[int, str, str, str, list[str]]] = []
            for section, locator, text in paragraphs:
                lower = text.lower()
                signals = [term for term in terms if term in lower]
                if not signals:
                    continue
                score = len(signals) * 3 + bool(DOSE_RE.search(text)) * 2 + bool(DURATION_RE.search(text)) + bool(POP_RE.search(text))
                scored.append((score, section, locator, text, signals))
            for rank, (score, section, locator, text, signals) in enumerate(sorted(scored, reverse=True)[:5], 1):
                source_candidate_count += 1
                candidates.append({
                    "evidence_candidate_id": f"AI-FT-{manifest_row['evidence_candidate_id']}-{rank:02d}",
                    "parent_candidate_id": manifest_row["evidence_candidate_id"],
                    "pmid": manifest_row["pmid"], "pmcid": manifest_row["pmcid"],
                    "clinical_node_id": node, "ingredient": NODE_INGREDIENT.get(node, ""),
                    "title": metadata.get("title") or title_from_source,
                    "source_path": manifest_row["local_path"], "source_sha256": manifest_row["sha256"],
                    "section_title": section, "locator": f"{manifest_row['pmcid']}, {section}, {locator}",
                    "evidence_text": sentence_excerpt(text, terms), "signal_types": ";".join(signals),
                    "dose_mentions": ";".join(dict.fromkeys(DOSE_RE.findall(text))),
                    "population_mentions": ";".join(dict.fromkeys(m.group(0) for m in POP_RE.finditer(text))),
                    "duration_mentions": ";".join(dict.fromkeys(DURATION_RE.findall(text))),
                    "design_signals": ";".join(term for term in DESIGN_TERMS if term in text.lower()),
                    "ai_relevance_score": score, "reviewer_id": "codex_ai",
                    "review_status": "ai_extracted_not_human_verified", "human_verification_required": "true",
                })
        article_rows.append({
            "pmcid": source_manifest[0]["pmcid"], "source_path": source_manifest[0]["local_path"],
            "source_sha256": source_manifest[0]["sha256"], "linked_candidate_records": len(source_manifest),
            "paragraphs_parsed": len(paragraphs), "ai_evidence_candidates": source_candidate_count,
            "review_status": "ai_extracted_not_human_verified",
        })

    out = root / "extraction"
    out.mkdir(parents=True, exist_ok=True)
    candidate_path = out / "ai_full_text_evidence_candidates.csv"
    article_path = out / "ai_full_text_article_summary.csv"
    with candidate_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS); writer.writeheader(); writer.writerows(candidates)
    with article_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ARTICLE_FIELDS); writer.writeheader(); writer.writerows(article_rows)
    report = {
        "schema_version": "1.0.0", "method": "deterministic_keyword_candidate_extraction_by_codex_ai",
        "unique_sources_verified": len(by_source), "manifest_records_processed": sum(map(len, by_source.values())),
        "articles_with_candidates": sum(row["ai_evidence_candidates"] > 0 for row in article_rows),
        "ai_evidence_candidates": len(candidates), "by_clinical_node": dict(sorted(Counter(str(row["clinical_node_id"]) for row in candidates).items())),
        "source_hash_mismatches": hash_mismatches, "human_verified_candidates": 0,
        "claim_boundary": "Candidate passages only; no causal, clinical, threshold, or expert conclusion is established.",
    }
    (out / "ai_full_text_extraction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("research_v3"))
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
