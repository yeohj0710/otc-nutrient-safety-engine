from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


UA = "otc-nutrient-safety-engine/1.0 (research artifact; contact unavailable)"


def get(url: str, timeout: int = 40) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-review", type=Path, default=Path("research_v3/ai_review/priority_118_ai_review.csv"))
    parser.add_argument("--output-root", type=Path, default=Path("research_v3/full_text"))
    args = parser.parse_args()
    with args.ai_review.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [row for row in csv.DictReader(f) if row["full_text_retrieval_recommended"] == "true"]
    pmids = [row["pmid"] for row in rows]
    query = urllib.parse.urlencode({"ids": ",".join(pmids), "format": "json", "tool": "otc-nutrient-safety-engine"})
    idconv_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?{query}"
    converted = json.loads(get(idconv_url).decode("utf-8"))
    by_pmid = {str(record.get("pmid")): record for record in converted.get("records", [])}
    xml_dir = args.output_root / "oa_xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, row in enumerate(rows, start=1):
        pmid = row["pmid"]
        record = by_pmid.get(pmid, {})
        pmcid = record.get("pmcid", "")
        item = {
            "evidence_candidate_id": row["evidence_candidate_id"],
            "pmid": pmid,
            "pmcid": pmcid,
            "retrieval_status": "no_pmc_open_access_identifier" if not pmcid else "pending",
            "retrieval_url": "",
            "local_path": "",
            "bytes": "",
            "sha256": "",
            "retrieved_at_utc": "",
            "error": "",
            "review_status": "retrieved_not_human_reviewed",
        }
        if pmcid:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            item["retrieval_url"] = url
            try:
                payload = get(url)
                if not payload.lstrip().startswith(b"<"):
                    raise ValueError("response is not XML")
                path = xml_dir / f"{pmcid}.xml"
                path.write_bytes(payload)
                item.update(
                    {
                        "retrieval_status": "retrieved_open_access_xml",
                        "local_path": path.as_posix(),
                        "bytes": str(len(payload)),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                )
            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                fallback_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/?report=xml"
                try:
                    payload = get(fallback_url)
                    if b"<html" not in payload[:1000].lower():
                        raise ValueError("fallback response is not HTML")
                    path = xml_dir / f"{pmcid}.html"
                    path.write_bytes(payload)
                    item.update(
                        {
                            "retrieval_status": "retrieved_public_pmc_html",
                            "retrieval_url": fallback_url,
                            "local_path": path.as_posix(),
                            "bytes": str(len(payload)),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "error": f"Europe PMC XML unavailable: {error}",
                        }
                    )
                except (urllib.error.URLError, TimeoutError, ValueError) as fallback_error:
                    item["retrieval_status"] = "retrieval_failed"
                    item["error"] = f"Europe PMC: {error}; PMC fallback: {fallback_error}"
            time.sleep(0.08)
        manifest.append(item)
        if index % 20 == 0:
            print(f"processed {index}/{len(rows)}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    fields = list(manifest[0])
    with (args.output_root / "retrieval_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    summary = {
        "schema_version": "1.0.0",
        "requested": len(rows),
        "retrieved_open_access_xml": sum(row["retrieval_status"] == "retrieved_open_access_xml" for row in manifest),
        "retrieved_public_pmc_html": sum(row["retrieval_status"] == "retrieved_public_pmc_html" for row in manifest),
        "no_pmc_open_access_identifier": sum(row["retrieval_status"] == "no_pmc_open_access_identifier" for row in manifest),
        "retrieval_failed": sum(row["retrieval_status"] == "retrieval_failed" for row in manifest),
        "human_full_text_reviews": 0,
    }
    (args.output_root / "retrieval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
