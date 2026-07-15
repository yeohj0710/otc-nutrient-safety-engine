from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "research_v3" / "otc" / "raw" / "nedrug"
NORMALIZED = ROOT / "research_v3" / "otc" / "normalized"

PRODUCTS = {
    # The former 199303108 authorization was withdrawn; 202106092 is the
    # current authorization held by the present distributor.
    "SAFE-OTC-01": "202106092",
    "SAFE-OTC-02": "199402278",
    "SAFE-OTC-03": "199303109",
    # The legacy 199603002 authorization was withdrawn. The same designated
    # product name is currently authorized under 202200525.
    "SAFE-OTC-04": "202200525",
    "SAFE-OTC-05": "198601920",
    "SAFE-OTC-06": "198700405",
    "SAFE-OTC-07": "200300406",
    "SAFE-OTC-08": "199900926",
    "SAFE-OTC-09": "199801026",
    "SAFE-OTC-10": "196800036",
    "SAFE-OTC-11": "199400202",
    "SAFE-OTC-12": "198400250",
    "SAFE-OTC-13": "200501321",
    # Rule-coverage expansion candidates. These are not members of the
    # Ministry of Health and Welfare convenience-store designation list.
    "EXP-OTC-01": "201110646",  # 덱스피드연질캡슐 (덱시부프로펜)
    "EXP-OTC-02": "197500016",  # 낙센정 (나프록센)
    "EXP-OTC-03": "200610765",  # 지르텍정 (세티리진염산염)
}

DETAIL_URL = "https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail?itemSeq={item_seq}"
PDF_URL = "https://nedrug.mfds.go.kr/dsie/pdf/drb/{item_seq}/{document_type}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, retries: int = 3) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "otc-safety-research/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


class RowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[tuple[str, str]] = []
        self.in_tr = False
        self.cell: str | None = None
        self.skip = 0
        self.th: list[str] = []
        self.td: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        elif not self.skip and tag == "tr":
            self.in_tr = True
            self.th, self.td = [], []
        elif not self.skip and self.in_tr and tag in {"th", "td"}:
            self.cell = tag

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        elif not self.skip and tag in {"th", "td"}:
            self.cell = None
        elif not self.skip and tag == "tr" and self.in_tr:
            key = clean(" ".join(self.th))
            value = clean(" ".join(self.td))
            if key and value:
                self.rows.append((key, value))
            self.in_tr = False

    def handle_data(self, data):
        if not self.skip and self.in_tr and self.cell:
            (self.th if self.cell == "th" else self.td).append(data)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def first(rows: list[tuple[str, str]], *labels: str) -> str | None:
    for label in labels:
        for key, value in rows:
            if clean(key) == label:
                return value
    return None


def embedded_ingredients(text: str) -> list[dict[str, str | None]]:
    ingredients = []
    seen = set()
    for match in re.finditer(r"var\s+aasda\s*=\s*(\{.*?\});", text, re.S):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("ingrName")
        quantity = obj.get("ingrTotqy")
        unit = obj.get("ingrUnitName")
        basis = obj.get("totqyCont")
        if not name or not quantity or not unit:
            continue
        key = (name, quantity, unit, basis)
        if key in seen:
            continue
        seen.add(key)
        ingredients.append({
            "source_name": name,
            "quantity": quantity,
            "unit": unit,
            "quantity_basis": basis,
            "ingredient_code": obj.get("ingrCode"),
            "source_locator": "의약품상세정보 > 원료약품 및 분량",
        })
    return ingredients


def normalize(candidate_id: str, item_seq: str, data: bytes, retrieved_at: str) -> dict:
    text = data.decode("utf-8")
    parser = RowParser()
    parser.feed(text)
    rows = parser.rows
    cancel_date = first(rows, "취소일자", "취하일자", "취소/취하일자")
    cancel_reason = first(rows, "취소사유", "취하사유", "취소/취하")
    otc = first(rows, "전문/일반")
    status = "withdrawn" if cancel_date or cancel_reason else "active"
    return {
        "candidate_id": candidate_id,
        "product_id": f"MFDS-{item_seq}",
        "item_seq": item_seq,
        "product_name": first(rows, "제품명"),
        "company_name": first(rows, "업체명"),
        "otc_classification": otc,
        "authorization_date": first(rows, "허가일"),
        "authorization_status": status,
        "cancellation_date": cancel_date,
        "cancellation_reason": cancel_reason,
        "dosage_form": first(rows, "성상"),
        "storage_method": first(rows, "저장방법"),
        "valid_term": first(rows, "사용기간"),
        "package_unit": first(rows, "포장정보"),
        "detail_url": DETAIL_URL.format(item_seq=item_seq),
        "efficacy_pdf_url": PDF_URL.format(item_seq=item_seq, document_type="EE"),
        "dosage_pdf_url": PDF_URL.format(item_seq=item_seq, document_type="UD"),
        "precautions_pdf_url": PDF_URL.format(item_seq=item_seq, document_type="NB"),
        "source_id": "MFDS-NEDRUG-DETAIL",
        "source_locator": "의약품상세정보 > 기본정보; 원료약품 및 분량",
        "retrieved_at_utc": retrieved_at,
        "raw_sha256": sha256(data),
        "ingredients": embedded_ingredients(text),
        "status": "verified_from_source" if otc == "일반의약품" and status == "active" else "excluded",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="append", choices=sorted(PRODUCTS))
    args = parser.parse_args()
    selected = args.candidate or list(PRODUCTS)
    retrieved_at = datetime.now(UTC).isoformat()
    products_path = NORMALIZED / "products.json"
    manifest_path = RAW / "manifest.json"
    products = json.loads(products_path.read_text(encoding="utf-8")) if products_path.exists() else []
    old_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"records": []}
    manifest = old_manifest.get("records", [])
    for candidate_id in selected:
        item_seq = PRODUCTS[candidate_id]
        product_dir = RAW / item_seq
        product_dir.mkdir(parents=True, exist_ok=True)
        detail = fetch(DETAIL_URL.format(item_seq=item_seq))
        detail_path = product_dir / "detail.html"
        detail_path.write_bytes(detail)
        files = [{"path": str(detail_path.relative_to(ROOT)), "sha256": sha256(detail), "bytes": len(detail)}]
        for document_type in ("EE", "UD", "NB"):
            pdf = fetch(PDF_URL.format(item_seq=item_seq, document_type=document_type))
            path = product_dir / f"{document_type}.pdf"
            path.write_bytes(pdf)
            files.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(pdf), "bytes": len(pdf)})
        product = normalize(candidate_id, item_seq, detail, retrieved_at)
        products = [row for row in products if row.get("candidate_id") != candidate_id]
        products.append(product)
        manifest = [row for row in manifest if row.get("candidate_id") != candidate_id]
        manifest.append({"candidate_id": candidate_id, "item_seq": item_seq, "files": files})
        print(f"{candidate_id} {item_seq} {product['status']} {len(product['ingredients'])} ingredients")
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    products.sort(key=lambda row: row["candidate_id"])
    manifest.sort(key=lambda row: row["candidate_id"])
    products_path.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps({"retrieved_at_utc": retrieved_at, "source": "MFDS NEDRUG", "records": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
