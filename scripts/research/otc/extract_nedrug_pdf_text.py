from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "research_v3" / "otc" / "raw" / "nedrug"
OUT = ROOT / "research_v3" / "otc" / "extracted" / "nedrug"
PRODUCTS = ROOT / "research_v3" / "otc" / "normalized" / "products.json"
DOCUMENT_LABEL = {"EE": "효능효과", "UD": "용법용량", "NB": "사용상의주의사항"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract(executable: str, pdf: Path) -> str:
    result = subprocess.run(
        [executable, "-layout", "-enc", "UTF-8", str(pdf), "-"],
        check=True, capture_output=True,
    )
    return result.stdout.decode("utf-8")


def main() -> int:
    executable = shutil.which("pdftotext")
    if not executable:
        raise SystemExit("pdftotext not found")
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    rows = []
    for product in products:
        item_seq = product["item_seq"]
        target = OUT / item_seq
        target.mkdir(parents=True, exist_ok=True)
        for doc_type, label in DOCUMENT_LABEL.items():
            pdf = RAW / item_seq / f"{doc_type}.pdf"
            text = extract(executable, pdf)
            text_path = target / f"{doc_type}.txt"
            text_path.write_text(text, encoding="utf-8")
            pages = text.split("\f")
            if pages and not pages[-1].strip():
                pages.pop()
            for page_number, page in enumerate(pages, 1):
                normalized = page.strip()
                rows.append({
                    "candidate_id": product["candidate_id"], "item_sequence": item_seq,
                    "document_type": doc_type, "document_label": label, "page": page_number,
                    "source_locator": f"{label} PDF p.{page_number}",
                    "pdf_path": str(pdf.relative_to(ROOT)).replace("\\", "/"),
                    "text_path": str(text_path.relative_to(ROOT)).replace("\\", "/"),
                    "pdf_sha256": sha256(pdf.read_bytes()),
                    "page_text_sha256": sha256(normalized.encode("utf-8")),
                    "character_count": len(normalized),
                })
    manifest = OUT / "page_manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"documents={len(products) * 3} pages={len(rows)} manifest={manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
