import csv,json
from pathlib import Path
from scripts.research.import_independent_scenario_review import run
def test_imports_twelve_locked_labels(tmp_path:Path):
    fields=["scenario_id","scenario_type","input_json","gold_hazards_json","critical","adjudicator_id","adjudicated_at","locked_before_test","source_note","notes"]
    scaffold=tmp_path/"scaffold.csv"
    with scaffold.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({"scenario_id":f"IND-{i:03}","input_json":json.dumps({"ingredient":"zinc"})} for i in range(1,13))
    decisions={f"IND-{i:03}":{"label":"no_warning","adjudicator_id":"판정자","adjudicated_at":"2026-07-13T00:00:00Z","review_kind":"independent_human_scenario_adjudication","locked_before_test":True} for i in range(1,13)}
    result=tmp_path/"result.json";result.write_text(json.dumps({"overall_status":"completed","decisions":decisions},ensure_ascii=False),encoding="utf-8")
    out=tmp_path/"out.csv";r=run(result,scaffold,out);rows=list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert r=={"imported":12,"locked":12,"predictions_imported":0}
    assert all(x["locked_before_test"]=="true" and x["adjudicator_id"]=="판정자" for x in rows)
