from __future__ import annotations
import argparse,csv
from pathlib import Path

QUOTES={
"V3-DRAFT-KDRI-VD-UL":"2025 한국인 영양소 섭취기준 - 지용성비타민, 비타민 D(μg/일): 남자 19-29세 평균필요량 10, 상한섭취량 100; 여자 19-29세 평균필요량 10, 상한섭취량 100; 임신부·수유부 상한섭취량 총량 100.",
"V3-DRAFT-KDRI-B6-UL":"2025 한국인 영양소 섭취기준 - 수용성비타민, 비타민 B6(mg/일): 남자 19-29세 평균필요량 1.3, 권장섭취량 1.5, 상한섭취량 50; 여자 19-29세 평균필요량 1.2, 권장섭취량 1.4, 상한섭취량 50; 임신부·수유부 상한섭취량 총량 50.",
"V3-DRAFT-KDRI-MG-UL":"2025 한국인 영양소 섭취기준 - 다량무기질, 마그네슘(mg/일): 남자 19-29세 평균필요량 300, 권장섭취량 360, 식품 외 급원 상한섭취량 350; 여자 19-29세 평균필요량 240, 권장섭취량 280, 식품 외 급원 상한섭취량 350.",
"V3-DRAFT-KDRI-FE-UL":"2025 한국인 영양소 섭취기준 - 미량무기질, 철(mg/일): 남자 19-29세 평균필요량 6, 권장섭취량 8, 상한섭취량 45; 여자 19-29세 평균필요량 7, 권장섭취량 12, 상한섭취량 45; 임신부·수유부 상한섭취량 총량 45.",
"V3-DRAFT-KDRI-ZN-UL":"2025 한국인 영양소 섭취기준 - 미량무기질, 아연(mg/일): 남자 19-29세 평균필요량 9, 권장섭취량 10, 상한섭취량 35; 여자 19-29세 평균필요량 7, 권장섭취량 8, 상한섭취량 35; 임신부·수유부 상한섭취량 총량 35.",
"V3-DRAFT-KDRI-CA-UL":"2025 한국인 영양소 섭취기준 - 다량무기질, 칼슘(mg/일): 남자 19-29세 상한섭취량 3,000, 남자 30-49세 2,500, 여자 19-29세 2,500, 여자 30-49세 2,000; 임신부·수유부는 해당 연령 여성 상한섭취량과 동일.",
}
def populate(path:Path):
    with path.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f));fields=list(rows[0])
    if {r["rule_id"] for r in rows}!=set(QUOTES):raise ValueError("rule set mismatch")
    for r in rows:r["evidence_quote"]=QUOTES[r["rule_id"]]
    with path.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return len(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument("--packet",type=Path,default=Path("research_v3/rules/expert_rule_review_packet.csv"));a=p.parse_args();print(populate(a.packet));return 0
if __name__=="__main__":raise SystemExit(main())
