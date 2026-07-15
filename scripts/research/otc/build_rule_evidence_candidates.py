from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
EXTRACTED = OTC / "extracted" / "nedrug"

PATTERNS = {
    "duplicate_ingredient": r"다른\s*(?:제품|의약품).{0,80}(?:함께|동시).{0,40}(?:복용|사용).{0,30}(?:안|말)",
    "duplicate_pharmacologic_class": r"다른\s*(?:해열.?진통제|소염.?진통제|비스테로이드성).{0,100}(?:함께|복용)",
    "max_daily_dose": r"(?:1일|일일)\s*최대|최대\s*(?:1일|일일)\s*(?:용량|용법)",
    "minimum_interval": r"\d+\s*[-~～]\s*\d+\s*시간\s*(?:마다|간격)|\d+\s*시간\s*(?:마다|간격)",
    "age_restriction": r"(?:만\s*)?\d+\s*세\s*(?:이상|미만|이하)|소아|고령자|노인",
    "pregnancy_lactation": r"임부|임신|수유부|수유\s*중",
    "hepatic_disease": r"간(?:장애|질환|손상)|간장.{0,8}(?:장애|질환)",
    "renal_disease": r"신장.{0,8}(?:장애|질환)|콩팥.{0,8}(?:장애|질환)",
    "gi_bleeding_ulcer": r"위장.{0,12}(?:출혈|궤양)|소화성\s*궤양|위궤양|십이지장궤양",
    "sedation_driving": r"졸음|운전|기계\s*조작",
    "alcohol": r"알코올|술을\s*마시|음주",
    "anticoagulant_antiplatelet": r"와파린|항응고|항혈소판",
    "sedative_medication": r"바르비탈|진정제|수면제|삼환계\s*항우울제",
    "decongestant_hypertension": r"고혈압|심혈관|심장.{0,8}(?:질환|기능)",
    "maximum_duration": r"장기(?:간)?.{0,12}복용|연속\s*\d+\s*일|\d+\s*일간.{0,40}(?:복용|사용)",
    "urgent_referral": r"즉각\s*중지|즉시\s*(?:복용을\s*)?중단|즉시.{0,20}(?:의사|진료|상담)",
}


def paragraphs(page: str) -> list[str]:
    return [re.sub(r"\s+", " ", value).strip() for value in re.split(r"(?:\r?\n){2,}", page) if value.strip()]


def build() -> list[dict[str, str | int]]:
    products = json.loads((OTC / "normalized" / "products.json").read_text(encoding="utf-8"))
    output = []
    for product in products:
        if product["status"] != "verified_from_source":
            continue
        for doc_type in ("UD", "NB"):
            text_path = EXTRACTED / product["item_seq"] / f"{doc_type}.txt"
            pages = text_path.read_text(encoding="utf-8").split("\f")
            for page_number, page in enumerate(pages, 1):
                for paragraph_number, paragraph in enumerate(paragraphs(page), 1):
                    for rule_type, pattern in PATTERNS.items():
                        if re.search(pattern, paragraph, re.I | re.S):
                            output.append({
                                "evidence_candidate_id": f"{product['candidate_id']}-{doc_type}-P{page_number}-B{paragraph_number}-{rule_type}",
                                "rule_type": rule_type, "candidate_id": product["candidate_id"],
                                "item_sequence": product["item_seq"], "product_name": product["product_name"],
                                "document_type": doc_type, "source_id": "MFDS-NEDRUG-DETAIL",
                                "source_url": product[f"{'dosage' if doc_type == 'UD' else 'precautions'}_pdf_url"],
                                "source_locator": f"{'용법용량' if doc_type == 'UD' else '사용상의주의사항'} PDF p.{page_number}, 문단 {paragraph_number}",
                                "evidence_text": paragraph[:1200],
                                "review_status": "codex_candidate_not_expert_verified",
                                "supports_release": "false",
                            })
    return output


def main() -> int:
    output = build()
    target = OTC / "rules" / "official_evidence_candidates.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"candidates={len(output)} rule_types={len({row['rule_type'] for row in output})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
