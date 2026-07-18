import csv,json
from pathlib import Path
from scripts.research.import_expert_rule_review_html import import_result

def test_imports_six_expert_decisions_without_release(tmp_path:Path):
    checks=["threshold_correct","scope_correct","conditions_correct","exceptions_correct","message_safe","next_action_safe","source_locator_verified"]
    packet=tmp_path/"packet.csv"; fields=["rule_id","evidence_quote",*checks,"overall_decision","required_revision","reviewer_id","reviewer_role","reviewed_at","notes"]
    with packet.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({"rule_id":f"R{i}"} for i in range(6))
    decisions={f"R{i}":{"decision":"approve","reviewer_id":"검토자","reviewer_role":"약사","reviewed_at":"2026-07-13T00:00:00Z","review_kind":"human_expert_rule_review","evidence_quote":"공식 표 전사",**{k:True for k in checks}} for i in range(6)}
    result=tmp_path/"result.json";result.write_text(json.dumps({"overall_status":"completed","decisions":decisions},ensure_ascii=False),encoding="utf-8")
    out=tmp_path/"out.csv";report=import_result(result,packet,out)
    assert report["imported"]==6 and report["approved"]==6 and report["release_promoted"]==0
    rows=list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert all(r["reviewer_role"]=="약사" and r["evidence_quote"]=="공식 표 전사" for r in rows)
    assert all(r[k]=="true" for r in rows for k in checks)
