from __future__ import annotations

import csv
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "review" / "OTC_통합검토.html"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_payload() -> dict:
    scenarios = rows(OTC / "validation" / "independent_scenarios.csv")
    products = {row["item_sequence"]: row["product_name"] for row in rows(OTC / "normalized" / "product_master.csv")}
    for scenario in scenarios:
        case_path = OTC / "validation" / scenario["case_payload_ref"]
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case.pop("referenceLabel", None)
        case.pop("prediction", None)
        for product in case.get("productInputs", []):
            product["productName"] = products.get(str(product.get("itemSequence", "")), "지원하지 않는 제품")
        scenario["case_payload"] = case
    return {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "reviewer": {"reviewer_id": "", "reviewer_role": "", "reviewed_at": ""},
        "sections": {
            "official_candidates": rows(OTC / "selection" / "official_designation_candidates.csv"),
            "normalization_exceptions": rows(OTC / "normalized" / "rejected_rows.csv") if (OTC / "normalized" / "rejected_rows.csv").exists() else [],
            "normalization_reference": rows(OTC / "validation" / "normalization_reference.csv"),
            "draft_rules": rows(OTC / "rules" / "rules.csv"),
            "official_evidence_candidates": rows(OTC / "rules" / "official_evidence_candidates.csv"),
            "rule_evidence_shortlist": rows(OTC / "rules" / "rule_evidence_shortlist.csv"),
            "runtime_rule_bindings": rows(OTC / "rules" / "runtime_rule_bindings.csv"),
            "independent_scenarios": scenarios,
        },
        "human_decisions": {},
    }


def card(item_id: str, title: str, detail: str, section: str, options: list[tuple[str, str]], recommended_value: str = "", precheck: bool = False) -> str:
    radios = "".join(
        f'<label><input type="radio" name="{html.escape(section)}:{html.escape(item_id)}" value="{html.escape(value)}"{" checked" if precheck and value == recommended_value else ""}> {html.escape(label)}</label>'
        for value, label in options
    )
    recommendation = next((label for value, label in options if value == recommended_value), "")
    recommendation_html = f'<p class="recommendation">Codex 추천안: {html.escape(recommendation)}</p>' if recommendation else '<p class="recommendation independent">독립 평가: Codex 기준정답을 표시하지 않음</p>'
    return f'''<article class="review-card" data-section="{html.escape(section)}" data-item-id="{html.escape(item_id)}" data-recommended-value="{html.escape(recommended_value)}">
      <h3>{html.escape(title)}</h3><p>{html.escape(detail)}</p>{recommendation_html}<div class="choices">{radios}</div>
      <label class="comment">검토 메모<textarea rows="2" data-comment-for="{html.escape(section)}:{html.escape(item_id)}"></textarea></label>
    </article>'''


def rule_card(row: dict[str, str], evidence: list[dict[str, str]], bindings: list[dict[str, str]]) -> str:
    base = card(
        row["rule_id"], f'{row["rule_type"]} · {row["severity"]}', row["message_ko"], "draft_rules",
        [("approve", "근거·문구·binding 승인"), ("revise", "수정 필요"), ("reject", "제외")],
        "revise" if row["rule_id"] == "OTC-RULE-015" else "approve",
    )
    examples = "".join(
        f'<li><a href="{html.escape(item["source_url"])}" target="_blank" rel="noreferrer">{html.escape(item["product_name"])} · {html.escape(item["source_locator"])}</a><blockquote>{html.escape(item["evidence_text"][:420])}</blockquote></li>'
        for item in evidence[:3]
    ) or "<li>현재 범위에서 자동 선별된 공식 문단이 없습니다.</li>"
    evidence_html = f'<details class="evidence"><summary>공식 근거 후보 {len(evidence)}건 보기(대표 최대 3건)</summary><ul>{examples}</ul><p>상태: Codex 후보 · 전문가 미확인 · release 근거로 자동 사용하지 않음</p></details>'
    binding_rows = "".join(
        "<li>" + html.escape(" · ".join(filter(None, [
            f'품목 {item["item_sequence"]}',
            f'성분 {item["ingredient_id"]}' if item["ingredient_id"] else "",
            f'최대 1일량 {item["max_daily_amount"]}' if item["max_daily_amount"] else "",
            f'최소 간격 {item["minimum_interval_hours"]}시간' if item["minimum_interval_hours"] else "",
            f'최소 연령 {item["minimum_age_years"]}세' if item["minimum_age_years"] else "",
            f'최대 연속 {item["maximum_continuous_days"]}일' if item["maximum_continuous_days"] else "",
            f'조건 {item["flags"]}' if item["flags"] else "",
        ]))) + "</li>" for item in bindings
    ) or "<li>별도 runtime 기준값 없음</li>"
    binding_html = f'<details class="evidence"><summary>판정 runtime binding {len(bindings)}건</summary><ul>{binding_rows}</ul><p>상태: Codex 후보 · 전문가 미확인 · supports_release=false</p></details>'
    return base.replace("</article>", evidence_html + binding_html + "</article>")


def scenario_card(row: dict[str, object], assisted: bool = False) -> str:
    case = row["case_payload"]
    product_summaries = []
    for item in case.get("productInputs", []):
        if item.get("inputType") == "product_search_query":
            product_summaries.append(f'검색어 “{item.get("productNameQuery", "") or "없음"}”')
            continue
        summary = f'{item.get("productName", "제품명 없음")} · 1회 {item.get("unitsPerDose", "-")}단위 · 하루 {item.get("dosesPerDay", "-")}회'
        if item.get("hoursSincePreviousDose") is not None:
            summary += f' · 이전 복용 후 {item["hoursSincePreviousDose"]}시간'
        product_summaries.append(summary)
    products = ", ".join(product_summaries) or "제품 입력 없음"
    profile = case.get("userProfile", {})
    profile_labels = {
        "ageYears": "나이", "pregnant": "임신", "lactating": "수유", "liverDisease": "간질환",
        "kidneyDisease": "신장질환", "giBleedingOrUlcer": "위장관 출혈·궤양",
        "hypertensionOrCardiovascularDisease": "고혈압·심혈관질환", "willDrive": "운전 예정", "alcohol": "음주",
    }
    conditions = []
    for key, label in profile_labels.items():
        value = profile.get(key)
        if key == "ageYears" and value is not None:
            conditions.append(f"{label} {value}세")
        elif value is True:
            conditions.append(label)
    if profile.get("medications"):
        conditions.append("병용약 " + ", ".join(profile["medications"]))
    if profile.get("redFlagSymptoms"):
        conditions.append("긴급증상 " + ", ".join(profile["redFlagSymptoms"]))
    detail = f'복용 제품: {products} · 사용자 조건: {", ".join(conditions) if conditions else "특이사항 없음"} · critical: {row["critical"]}'
    recommended = "0" if row["scenario_family"] in {"normal_use", "unsupported_product"} else "1"
    return card(
        str(row["scenario_id"]), str(row["scenario_family"]), detail,
        "independent_scenarios",
        [("1", "위험 신호 있음"), ("0", "위험 신호 없음"), ("uncertain", "판단 보류")],
        recommended if assisted else "",
        precheck=assisted,
    )


def build_html(payload: dict, default_role: str = "", default_reviewer_id: str = "", prefill_independent: bool = False) -> str:
    candidates = "".join(card(row["candidate_id"], row["listed_product_name"], f'{row["class_id"]} · {row["listed_package"]} · 현재 상태: {row["candidate_status"]}', "official_candidates", [("include_for_verification", "허가 검증 대상으로 포함"), ("hold", "보류"), ("exclude", "제외")], "include_for_verification") for row in payload["sections"]["official_candidates"])
    exceptions = "".join(card(row.get("item_sequence", "unknown"), row.get("product_name", "제품명 없음"), row.get("reasons", "사유 없음"), "normalization_exceptions", [("correct", "정규화 수정"), ("reject", "거절 유지")]) for row in payload["sections"]["normalization_exceptions"]) or '<p class="empty">실제 수집·정규화가 실행되지 않아 예외 행이 없습니다.</p>'
    normalization = "".join(card(row["ingredient_id"], row["system_normalized_name"], f'원문명: {row["raw_names"]} · 시스템 표준명: {row["system_normalized_name"]}', "normalization_reference", [("correct", "표준명 정확"), ("incorrect", "표준명 수정 필요(메모에 정답 입력)"), ("uncertain", "판단 보류")], "correct") for row in payload["sections"]["normalization_reference"])
    evidence_by_rule = {}
    for item in payload["sections"]["rule_evidence_shortlist"]:
        evidence_by_rule.setdefault(item["rule_id"], []).append(item)
    for items in evidence_by_rule.values():
        items.sort(key=lambda item: int(item["rank"]))
    bindings_by_rule = {}
    for item in payload["sections"]["runtime_rule_bindings"]:
        bindings_by_rule.setdefault(item["rule_id"], []).append(item)
    rules = "".join(rule_card(row, evidence_by_rule.get(row["rule_id"], []), bindings_by_rule.get(row["rule_id"], [])) for row in payload["sections"]["draft_rules"])
    scenarios = "".join(scenario_card(row, assisted=prefill_independent) for row in payload["sections"]["independent_scenarios"])
    embedded_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    if prefill_independent:
        embedded_payload["review_method"] = "codex_prefilled_external_human_confirmation"
        embedded_payload["predictions_exposed"] = len(payload["sections"]["independent_scenarios"])
        embedded_payload["independent_blinding"] = False
    payload_json = json.dumps(embedded_payload, ensure_ascii=False).replace("</", "<\\/")
    role_options = [("", "선택"), ("pharmacist_expert", "약사·약학 전문가"), ("independent_scenario_reviewer", "독립 시나리오 검토자"), ("normalization_reviewer", "성분 정규화 검토자"), ("research_advisor", "연구 지도자")]
    role_html = "".join(f'<option value="{value}"{" selected" if value == default_role else ""}>{label}</option>' for value, label in role_options)
    reviewer_readonly = " readonly" if default_reviewer_id else ""
    role_disabled = " disabled" if default_role else ""
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>OTC 통합 검토</title>
<style>:root{{--blue:#3182f6;--text:#191f28;--muted:#6b7684;--soft:#f9fafb}}*{{box-sizing:border-box}}body{{margin:0;background:var(--soft);color:var(--text);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif}}main{{max-width:760px;margin:auto;padding:48px 24px}}h1{{font-size:40px;line-height:1.35}}.lead{{color:var(--muted);line-height:1.7}}.notice{{margin:24px 0;padding:16px;border-radius:12px;background:#fff4e5;color:#8b5a00}}.reviewer,.toolbar,.wizard-nav{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}}input,textarea,select,button{{font:inherit}}.reviewer input,.reviewer select,textarea{{width:100%;border:1px solid #d1d6db;border-radius:10px;padding:12px;background:#fff}}section{{margin-top:36px}}section>h2{{font-size:24px}}section.role-hidden,.review-card.wizard-hidden{{display:none}}.review-card{{margin:12px 0;padding:24px;border:1px solid #e5e8eb;border-radius:14px;background:#fff}}.review-card h3{{margin:0}}.review-card p{{color:var(--muted);line-height:1.6;overflow-wrap:anywhere}}.recommendation{{padding:12px;border-radius:10px;background:#e8f3ff;color:#1b64da!important;font-weight:700}}.recommendation.independent{{background:#f2f4f6;color:#4e5968!important}}.choices{{display:flex;flex-wrap:wrap;gap:8px}}.choices label{{padding:10px 12px;border:1px solid #d1d6db;border-radius:10px}}.comment{{display:block;margin-top:14px;color:var(--muted)}}.evidence{{margin-top:16px;padding:14px;border-radius:10px;background:#f2f4f6}}.evidence summary{{cursor:pointer;font-weight:700}}.evidence li{{margin:12px 0}}.evidence a{{color:var(--blue);font-weight:600}}blockquote{{margin:8px 0;padding-left:12px;border-left:3px solid #d1d6db;color:var(--muted);line-height:1.55}}button{{min-height:48px;border:0;border-radius:10px;background:var(--blue);color:#fff;font-weight:700;padding:0 16px}}button.secondary{{background:#e8f3ff;color:var(--blue)}}#progress{{font-weight:700;color:var(--muted)}}.empty{{padding:20px;background:#fff;border-radius:12px;color:var(--muted)}}@media(max-width:600px){{main{{padding:30px 18px}}h1{{font-size:30px}}.reviewer,.toolbar,.wizard-nav{{grid-template-columns:1fr}}}}</style></head>
<body><main><p style="color:#3182f6;font-weight:700">research_v3 · 사람 검토</p><h1>일반의약품 연구 통합 검토</h1><p class="lead">후보 선정, 정규화 예외, 규칙 초안과 독립 시나리오 기준정답을 한 파일에서 검토합니다.</p><div class="notice">검토자와 역할, Codex 추천안을 미리 채웠습니다. 내용이 맞으면 <b>추천안 승인하고 다음</b>만 누르세요. 마지막 항목에서 결과 JSON이 자동 저장됩니다.</div>
<div class="reviewer"><label>검토자 코드<input id="reviewerId" value="{html.escape(default_reviewer_id)}" autocomplete="off"{reviewer_readonly}></label><label>역할<select id="reviewerRole"{role_disabled}>{role_html}</select></label></div>
<section data-allowed-role="research_advisor"><h2>1. 공식 지정 후보 {len(payload['sections']['official_candidates'])}건</h2>{candidates}</section>
<section data-allowed-role="normalization_reviewer"><h2>2. 정규화 예외 {len(payload['sections']['normalization_exceptions'])}건</h2>{exceptions}</section>
<section data-allowed-role="normalization_reviewer"><h2>3. 성분 정규화 기준 검토 {len(payload['sections']['normalization_reference'])}건</h2>{normalization}</section>
<section data-allowed-role="pharmacist_expert"><h2>4. draft 규칙 {len(payload['sections']['draft_rules'])}건</h2>{rules}</section>
<section data-allowed-role="independent_scenario_reviewer"><h2>5. 독립 시나리오 {len(payload['sections']['independent_scenarios'])}건</h2>{scenarios}</section>
<p id="progress"></p><div class="wizard-nav"><button id="backButton" class="secondary" type="button">이전</button><button id="nextButton" type="button">추천안 승인하고 다음</button></div>
<div class="toolbar"><button id="exportButton" type="button">검토 결과 JSON 저장</button><button id="importButton" class="secondary" type="button">기존 결과 불러오기</button><input id="importFile" type="file" accept="application/json" hidden></div></main>
<script id="sourcePayload" type="application/json">{payload_json}</script><script>
const source=JSON.parse(document.getElementById('sourcePayload').textContent);const file=document.getElementById('importFile');const role=document.getElementById('reviewerRole');let wizardCards=[];let wizardIndex=0;
function renderWizard(){{wizardCards.forEach((card,index)=>card.classList.toggle('wizard-hidden',index!==wizardIndex));const card=wizardCards[wizardIndex];document.getElementById('progress').textContent=card?`${{wizardIndex+1}} / ${{wizardCards.length}}`:'';document.getElementById('backButton').disabled=wizardIndex===0;document.getElementById('nextButton').textContent=card?.dataset.recommendedValue?'추천안 승인하고 다음':'선택하고 다음';}}
function updateRoleView(){{const selected=role.value;document.querySelectorAll('section[data-allowed-role]').forEach(section=>section.classList.toggle('role-hidden',!selected||section.dataset.allowedRole!==selected));wizardCards=selected?[...document.querySelectorAll(`section[data-allowed-role="${{selected}}"] .review-card`)]:[];wizardIndex=0;renderWizard();}}
role.addEventListener('change',updateRoleView);
function collect(){{const reviewerId=document.getElementById('reviewerId').value.trim();const reviewerRole=role.value;if(!reviewerId||!reviewerRole)throw new Error('검토자 ID와 역할을 입력하세요.');const decisions={{}};document.querySelectorAll(`section[data-allowed-role="${{reviewerRole}}"] .review-card`).forEach(card=>{{const key=card.dataset.section+':'+card.dataset.itemId;const checked=card.querySelector('input[type=radio]:checked');const comment=card.querySelector('textarea').value.trim();if(checked)decisions[key]={{decision:checked.value,comment}};}});return{{...source,reviewer:{{reviewer_id:reviewerId,reviewer_role:reviewerRole,reviewed_at:new Date().toISOString()}},human_decisions:decisions}}}}
document.getElementById('backButton').onclick=()=>{{if(wizardIndex>0){{wizardIndex--;renderWizard();}}}};
document.getElementById('nextButton').onclick=()=>{{const card=wizardCards[wizardIndex];if(!card)return alert('역할을 선택하세요.');let checked=card.querySelector('input[type=radio]:checked');if(!checked&&card.dataset.recommendedValue){{checked=card.querySelector(`input[value="${{CSS.escape(card.dataset.recommendedValue)}}"]`);checked.checked=true;}}if(!checked)return alert('독립 기준정답을 선택하세요.');if(wizardIndex<wizardCards.length-1){{wizardIndex++;renderWizard();}}else{{document.getElementById('exportButton').click();}}}};
document.getElementById('exportButton').onclick=()=>{{try{{const data=collect();const blob=new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}});const a=document.createElement('a');const safeId=data.reviewer.reviewer_id.replace(/[^0-9A-Za-z가-힣_-]+/g,'_');a.href=URL.createObjectURL(blob);a.download=`otc_review_${{data.reviewer.reviewer_role}}_${{safeId}}.json`;a.click();URL.revokeObjectURL(a.href)}}catch(error){{alert(error.message)}}}};
document.getElementById('importButton').onclick=()=>file.click();file.onchange=async()=>{{const data=JSON.parse(await file.files[0].text());document.getElementById('reviewerId').value=data.reviewer?.reviewer_id||'';role.value=data.reviewer?.reviewer_role||'';updateRoleView();Object.entries(data.human_decisions||{{}}).forEach(([key,value])=>{{const radio=document.querySelector(`input[name="${{CSS.escape(key)}}"][value="${{CSS.escape(value.decision)}}"]`);if(radio)radio.checked=true;const comment=document.querySelector(`[data-comment-for="${{CSS.escape(key)}}"]`);if(comment)comment.value=value.comment||'';}})}};
updateRoleView();
</script></body></html>'''


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUTPUT.write_text(build_html(payload), encoding="utf-8")
    (OUTPUT.parent / "OTC_약사전문가_검토.html").write_text(build_html(payload, "pharmacist_expert", "EXT-PHARM-001"), encoding="utf-8")
    (OUTPUT.parent / "OTC_독립시나리오_검토.html").write_text(build_html(payload, "independent_scenario_reviewer", "EXT-INDEP-001", prefill_independent=True), encoding="utf-8")
    manifest = {"schema_version": "1.0.0", "output": OUTPUT.relative_to(ROOT).as_posix(), "counts": {key: len(value) for key, value in payload["sections"].items()}, "human_decisions_prefilled": 0, "independent_codex_recommendations_prefilled": 13}
    (OUTPUT.parent / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
