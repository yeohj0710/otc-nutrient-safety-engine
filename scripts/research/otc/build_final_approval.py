from __future__ import annotations

import csv
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "review" / "OTC_최종결정권자_확인.html"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build() -> str:
    rules = rows(OTC / "rules" / "rules.csv")
    scenarios = rows(OTC / "validation" / "independent_scenarios.csv")
    products = {row["item_sequence"]: row["product_name"] for row in rows(OTC / "normalized" / "product_master.csv")}
    rule_decisions = {
        row["rule_id"]: {
            "decision": "revise" if row["rule_id"] == "OTC-RULE-015" else "approve",
            "comment": "Codex 근거·문구·binding 검토안 확인",
        }
        for row in rules
    }
    scenario_decisions = {
        row["scenario_id"]: {
            "decision": "0" if row["scenario_family"] in {"normal_use", "unsupported_product"} else "1",
            "comment": "Codex 예상 기준정답 확인",
        }
        for row in scenarios
    }
    bundle = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "reviewer_id": "FINAL-DECISION-001",
        "review_mode": "codex_recommendations_confirmed_by_human_not_blinded_independent_review",
        "rule_decisions": rule_decisions,
        "scenario_decisions": scenario_decisions,
        "approved_at": "",
    }
    rule_items = "".join(
        f'<li><b>{html.escape(row["rule_id"])} · {html.escape(row["rule_type"])}</b><span>{"수정 필요" if row["rule_id"] == "OTC-RULE-015" else "승인"}</span><p>{html.escape(row["message_ko"])}</p></li>'
        for row in rules
    )
    scenario_items_list = []
    for row in scenarios:
        case = json.loads((OTC / "validation" / row["case_payload_ref"]).read_text(encoding="utf-8"))
        product_names = []
        for item in case.get("productInputs", []):
            if item.get("inputType") == "product_search_query":
                product_names.append(f'검색어 “{item.get("productNameQuery", "") or "없음"}”')
            else:
                product_names.append(products.get(str(item.get("itemSequence", "")), "제품명 확인 필요"))
        profile = case.get("userProfile", {})
        conditions = []
        for key, label in (("liverDisease", "간질환"), ("kidneyDisease", "신장질환"), ("giBleedingOrUlcer", "위장관 출혈·궤양"), ("hypertensionOrCardiovascularDisease", "고혈압·심혈관질환"), ("willDrive", "운전 예정"), ("alcohol", "음주")):
            if profile.get(key):
                conditions.append(label)
        if profile.get("ageYears") is not None:
            conditions.append(f'{profile["ageYears"]}세')
        if profile.get("medications"):
            conditions.append("병용약 " + ", ".join(profile["medications"]))
        proposed = "위험 신호 없음" if row["scenario_family"] in {"normal_use", "unsupported_product"} else "위험 신호 있음"
        detail = f'제품: {", ".join(product_names) or "없음"} · 조건: {", ".join(conditions) or "특이사항 없음"}'
        scenario_items_list.append(f'<li><b>{html.escape(row["scenario_id"])} · {html.escape(row["scenario_family"])}</b><span>{proposed}</span><p>{html.escape(detail)}</p></li>')
    scenario_items = "".join(scenario_items_list)
    payload = json.dumps(bundle, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OTC 최종 일괄 승인</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f7f8fa;color:#191f28;font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif}}main{{max-width:800px;margin:auto;padding:48px 22px}}h1{{font-size:38px}}.notice{{padding:16px;border-radius:12px;background:#fff4e5;color:#8b5a00;line-height:1.6}}section{{margin:30px 0;padding:22px;border-radius:16px;background:white}}ul{{padding:0;list-style:none}}li{{padding:14px 0;border-bottom:1px solid #e5e8eb}}li span{{float:right;color:#1b64da;font-weight:700}}li p{{margin:8px 0 0;color:#6b7684}}button{{position:sticky;bottom:18px;width:100%;height:58px;border:0;border-radius:14px;background:#3182f6;color:white;font-size:18px;font-weight:800}}#done{{display:none;padding:18px;border-radius:12px;background:#e8f3ff;color:#1b64da;font-weight:700}}
</style></head><body><main><p style="color:#3182f6;font-weight:800">FINAL-DECISION-001 · 최종결정권자 확인</p><h1>작성된 최종안을 한 번에 확인하세요</h1><div class="notice">Codex가 규칙 16건과 시나리오 13건의 결정을 모두 작성했습니다. 최종결정권자는 목록을 보고 아래 버튼 한 번만 누르면 됩니다. 장기복용 규칙 15번은 정량 일수 근거가 없어 ‘수정 필요’로 두었습니다. 이 확인은 비맹검 최종결정 확인이며 약사 전문가 검토나 맹검 독립평가로 바꾸어 기록하지 않습니다.</div><section><h2>규칙 16건</h2><ul>{rule_items}</ul></section><section><h2>시나리오 13건</h2><ul>{scenario_items}</ul></section><p id="done">최종결정 확인 결과가 저장되었습니다. 이 파일을 Codex가 가져옵니다.</p><button id="approve">전체 최종안 확인</button><script id="payload" type="application/json">{payload}</script><script>
document.getElementById('approve').onclick=()=>{{const data=JSON.parse(document.getElementById('payload').textContent);data.approved_at=new Date().toISOString();const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='otc_final_decision_confirmation.json';a.click();URL.revokeObjectURL(a.href);document.getElementById('done').style.display='block';document.getElementById('approve').disabled=true;document.getElementById('approve').textContent='확인 완료';}};
</script></main></body></html>'''


def main() -> int:
    OUTPUT.write_text(build(), encoding="utf-8")
    print(json.dumps({"output": OUTPUT.relative_to(ROOT).as_posix(), "rules": len(rows(OTC / "rules" / "rules.csv")), "scenarios": len(rows(OTC / "validation" / "independent_scenarios.csv"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
