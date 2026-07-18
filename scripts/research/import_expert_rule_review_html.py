from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

def load_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def import_result(result_path:Path,packet_path:Path,output_path:Path):
    raw=result_path.read_bytes(); data=json.loads(raw.decode("utf-8-sig")); decisions=data.get("decisions",{})
    if data.get("overall_status")!="completed" or len(decisions)!=6: raise ValueError("six completed decisions required")
    rows=load_csv(packet_path); by_rule={r["rule_id"]:r for r in rows}
    for rule_id,d in decisions.items():
        if rule_id not in by_rule: raise ValueError(f"unknown rule_id: {rule_id}")
        if d.get("review_kind")!="human_expert_rule_review" or d.get("decision") not in {"approve","revise","reject"}: raise ValueError(f"invalid decision provenance: {rule_id}")
        if not all(d.get(k) for k in ("reviewer_id","reviewer_role","reviewed_at")): raise ValueError(f"review identity/time missing: {rule_id}")
        row=by_rule[rule_id]; row.update({"overall_decision":d["decision"],"required_revision":d.get("note","") if d["decision"]!="approve" else "","reviewer_id":d["reviewer_id"],"reviewer_role":d["reviewer_role"],"reviewed_at":d["reviewed_at"],"notes":d.get("note","")})
        for field in ("threshold_correct","scope_correct","conditions_correct","exceptions_correct","message_safe","next_action_safe","source_locator_verified"):
            row[field]="true" if d.get(field) is True else "false" if d.get(field) is False else ""
        if d.get("evidence_quote"): row["evidence_quote"]=d["evidence_quote"]
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report={"schema_version":"1.0.0","source_sha256":hashlib.sha256(raw).hexdigest(),"imported":6,"approved":sum(d["decision"]=="approve" for d in decisions.values()),"release_promoted":0,"note":"Overall expert decisions imported. Release still requires item-level checks and exact evidence quotes."}
    report_path=output_path.with_name("expert_rule_review_html_import_report.json");report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--packet",type=Path,default=Path("research_v3/rules/expert_rule_review_packet.csv"));p.add_argument("--output",type=Path,default=Path("research_v3/rules/expert_rule_review_packet.csv"));a=p.parse_args();print(json.dumps(import_result(a.input,a.packet,a.output),ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
