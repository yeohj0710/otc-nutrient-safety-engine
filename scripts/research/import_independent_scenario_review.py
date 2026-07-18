from __future__ import annotations
import argparse,csv,json
from pathlib import Path
RULES={"vitamin_d":"V3-DRAFT-KDRI-VD-UL","calcium":"V3-DRAFT-KDRI-CA-UL","vitamin_b6":"V3-DRAFT-KDRI-B6-UL","iron":"V3-DRAFT-KDRI-FE-UL","magnesium":"V3-DRAFT-KDRI-MG-UL","zinc":"V3-DRAFT-KDRI-ZN-UL"}
def run(result:Path,scaffold:Path,output:Path):
    data=json.loads(result.read_text(encoding="utf-8-sig"));d=data.get("decisions",{})
    if data.get("overall_status")!="completed" or len(d)!=12:raise ValueError("12 completed decisions required")
    with scaffold.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f));fields=list(rows[0])
    for r in rows:
        x=d.get(r["scenario_id"],{})
        if x.get("review_kind")!="independent_human_scenario_adjudication" or x.get("locked_before_test") is not True:raise ValueError(f"invalid lock provenance: {r['scenario_id']}")
        if x.get("label") not in {"warning","no_warning"}:raise ValueError(f"invalid label: {r['scenario_id']}")
        ingredient=json.loads(r["input_json"])["ingredient"]
        gold=[RULES[ingredient]] if x["label"]=="warning" else []
        r.update({"gold_hazards_json":json.dumps(gold,ensure_ascii=False),"adjudicator_id":x["adjudicator_id"],"adjudicated_at":x["adjudicated_at"],"locked_before_test":"true","notes":x.get("note","")})
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return {"imported":len(rows),"locked":len(rows),"predictions_imported":0}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--scaffold",type=Path,default=Path("research_v3/human_review_minimal/05_독립시나리오_12건_확정.csv"));p.add_argument("--output",type=Path,default=Path("research_v3/validation/independent_scenarios.csv"));a=p.parse_args();print(json.dumps(run(a.input,a.scaffold,a.output),ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
