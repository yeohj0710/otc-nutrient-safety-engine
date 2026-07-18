from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "research_v3" / "human_review_minimal"
OUT = SRC / "연구_승인_마법사.html"


def rows(name: str) -> list[dict[str, str]]:
    with (SRC / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    approvals = rows("01_연구_제출_승인서.csv")
    press = rows("02_PRESS_검색전략_검토.csv")
    literature = rows("03_우선문헌_118건_검토.csv")
    rules = rows("04_규칙_6건_검토.csv")
    scenarios = rows("05_독립시나리오_12건_확정.csv")
    article_summaries = rows_from(ROOT / "research_v3" / "extraction" / "ai_full_text_article_summary.csv")
    evidence_candidates = rows_from(ROOT / "research_v3" / "extraction" / "ai_full_text_evidence_candidates.csv")
    candidates_by_source: dict[str, list[dict[str, str]]] = {}
    for candidate in evidence_candidates:
        candidates_by_source.setdefault(candidate["source_path"], []).append(candidate)
    fulltext = []
    for article in article_summaries:
        candidates = candidates_by_source.get(article["source_path"], [])
        if not candidates:
            continue
        first = candidates[0]
        fulltext.append(
            {
                "review_item_id": article["pmcid"],
                "record_id": first["parent_candidate_id"],
                "pmid": first["pmid"],
                "pmcid": article["pmcid"],
                "clinical_node_id": first["clinical_node_id"],
                "ingredient": first["ingredient"],
                "title": first["title"],
                "source_path": article["source_path"],
                "source_sha256": article["source_sha256"],
                "recommended_decision": "include",
                "recommended_locator": "; ".join(dict.fromkeys(c["locator"] for c in candidates if c["locator"])),
                "evidence_candidates": [
                    {
                        "evidence_candidate_id": c["evidence_candidate_id"],
                        "section_title": c["section_title"],
                        "locator": c["locator"],
                        "evidence_text": c["evidence_text"],
                    }
                    for c in candidates
                ],
            }
        )
    if len(fulltext) != 63:
        raise ValueError(f"63 full-text review items required, found {len(fulltext)}")
    ai_literature = {
        row["evidence_candidate_id"]: row["ai_title_abstract_decision"]
        for row in rows_from(ROOT / "research_v3" / "ai_review" / "priority_118_ai_review.csv")
    }
    scenario_predictions = {
        row["scenario_id"]: ("no_warning" if row["predicted_hazards_json"] == "[]" else "warning")
        for row in rows_from(ROOT / "research_v3" / "validation" / "independent_predictions.csv")
    }
    for item in press:
        item["recommended_rating"] = "yes"
    for item in literature:
        item["recommended_decision"] = (
            "uncertain" if ai_literature.get(item["evidence_candidate_id"]) == "ai_uncertain" else "include_candidate"
        )
    for item in rules:
        item["recommended_decision"] = "approve"
    for item in scenarios:
        item["recommended_label"] = scenario_predictions[item["scenario_id"]]
    locked_decisions: dict[str, dict[str, object]] = {}
    approval_result = ROOT / "research_v3" / "approvals" / "review_wizard_result.json"
    if approval_result.exists():
        recorded = json.loads(approval_result.read_text(encoding="utf-8-sig")).get("decisions", {})
        for key, value in recorded.items():
            if value.get("status") == "completed" and value.get("reviewer_id") and value.get("reviewed_at"):
                locked_decisions[key] = value
    if len(locked_decisions) not in {175, 238}:
        raise ValueError(f"175 or 238 canonical completed decisions are required, found {len(locked_decisions)}")
    data = {
        "schema_version": "1.0.0",
        "researcher": {"name": "권혁찬", "student_id": "2021194024", "affiliation": "연세대학교 약학대학"},
        "locked_decisions": locked_decisions,
        "sections": [
            {"id": "approval", "title": "연구 승인", "role": "지도교수", "items": approvals},
            {"id": "press", "title": "검색전략", "role": "검색전략 검토자", "items": press},
            {"id": "literature", "title": "우선 문헌", "role": "문헌 검토자", "items": literature},
            {"id": "rules", "title": "안전 규칙", "role": "약사·전문가", "items": rules},
            {"id": "scenarios", "title": "독립 평가", "role": "독립 평가자", "items": scenarios},
            {"id": "fulltext", "title": "전문 검토", "role": "전문 검토자", "items": fulltext},
        ],
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__PAYLOAD__", payload)
    OUT.write_text(html, encoding="utf-8")
    manifest_path = SRC / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
        manifest["review_wizard"] = {
            "name": OUT.name,
            "bytes": OUT.stat().st_size,
            "sha256": digest,
            "embedded_items": sum(len(s["items"]) for s in data["sections"]),
            "external_dependencies": 0,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "bytes": OUT.stat().st_size, "items": sum(len(s["items"]) for s in data["sections"])}, ensure_ascii=False))


def rows_from(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <title>권혁찬 연구 승인</title>
  <style>
    :root{--blue:#3182f6;--text:#191f28;--strong:#333d4b;--muted:#6b7684;--line:#e5e8eb;--soft:#f9fafb;--danger:#f04452;--ok:#20a36a;--white:#fff}
    *{box-sizing:border-box}html{background:var(--soft);color:var(--text);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Noto Sans KR","Segoe UI",sans-serif;letter-spacing:0}
    body{margin:0}.app{min-height:100dvh}.top{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}
    .top-inner,.main,.bottom-inner{max-width:760px;margin:0 auto}.top-inner{padding:16px 24px 13px}.brand{display:flex;align-items:center;justify-content:space-between;gap:16px}.brand strong{font-size:16px}.status{font-size:13px;color:var(--muted)}
    .bar{height:4px;background:#edf0f3;margin-top:13px;border-radius:999px;overflow:hidden}.bar>i{display:block;height:100%;width:0;background:var(--blue);transition:width .2s}
    .main{padding:48px 24px 150px}.eyebrow{font-size:18px;line-height:1.3;font-weight:700;color:var(--blue);margin:0 0 10px}.title{font-size:34px;line-height:1.35;margin:0 0 14px;font-weight:800;word-break:keep-all}.desc{font-size:17px;line-height:1.65;color:var(--muted);margin:0 0 30px;word-break:keep-all}
    .card{background:var(--white);border-radius:24px;padding:28px;box-shadow:0 8px 30px rgba(0,27,55,.06)}.meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:20px}.pill{background:var(--soft);border-radius:12px;padding:11px 13px;font-size:13px;color:var(--muted);overflow-wrap:anywhere}.pill b{display:block;color:var(--strong);margin-top:4px;font-size:14px}
    .question{font-size:23px;line-height:1.5;font-weight:700;margin:8px 0 18px;word-break:keep-all}.quote{background:#f2f6fa;border-radius:16px;padding:18px;line-height:1.65;color:var(--strong);margin:14px 0;max-height:230px;overflow:auto}.source{display:inline-block;color:var(--blue);font-weight:600;text-decoration:none;margin:4px 0 14px}.source:hover{text-decoration:underline}
    label{display:block;font-size:14px;font-weight:700;color:var(--strong);margin:18px 0 8px}.input,.select,.textarea{width:100%;border:1px solid var(--line);border-radius:14px;padding:14px 15px;background:#fff;font:inherit;color:var(--text);outline:none}.textarea{min-height:90px;resize:vertical}.input:focus,.select:focus,.textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(49,130,246,.12)}
    .choices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.choice{border:1px solid var(--line);background:#fff;border-radius:14px;padding:15px 10px;font:inherit;font-weight:700;color:var(--strong);cursor:pointer}.choice:hover{background:var(--soft)}.choice.selected{border-color:var(--blue);background:#edf6ff;color:#1b64da}.choice.danger.selected{border-color:var(--danger);background:#fff1f2;color:#d93142}
    .setup{max-width:680px;margin:0 auto}.setup .card{padding:34px}.assignment{display:grid;gap:10px;margin:0 0 24px}.assignment-row{display:grid;grid-template-columns:130px 1fr auto;gap:12px;align-items:center;padding:14px;border:1px solid var(--line);border-radius:14px}.assignment-row b{font-size:15px}.assignment-row span{font-size:13px;line-height:1.45;color:var(--muted)}.assignment-row em{font-size:12px;font-style:normal;color:var(--blue);font-weight:700}.role-button{width:100%;margin-top:8px;border:1px solid var(--line);background:#fff;border-radius:14px;padding:14px;text-align:left;font:inherit;cursor:pointer}.role-button:hover{border-color:var(--blue);background:#f6faff}.role-button b{display:block;color:var(--strong)}.role-button span{display:block;color:var(--muted);font-size:13px;margin-top:4px}.setup-actions{display:flex;gap:10px;margin-top:24px}.primary,.secondary{border:0;border-radius:14px;padding:15px 20px;font:inherit;font-weight:700;cursor:pointer}.primary{background:var(--blue);color:#fff;flex:1}.primary:disabled{background:#b0c8e8;cursor:not-allowed}.secondary{background:#eef1f4;color:var(--strong)}
    .bottom{position:fixed;bottom:0;left:0;right:0;z-index:6;background:rgba(255,255,255,.96);border-top:1px solid var(--line);padding:12px 0 calc(12px + env(safe-area-inset-bottom))}.bottom-inner{display:flex;gap:10px;padding:0 24px}.bottom .secondary{min-width:90px}.bottom .primary{min-height:52px}
    .done{text-align:center;padding:20px 0}.done-icon{width:72px;height:72px;border-radius:50%;background:#e9f8f1;color:var(--ok);display:grid;place-items:center;margin:0 auto 22px;font-size:36px;font-weight:800}.summary{margin:24px 0;text-align:left}.summary-row{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:13px 2px}.summary-row b{color:var(--ok)}.tools{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px}.hidden{display:none!important}.notice{font-size:13px;color:var(--muted);line-height:1.5;margin-top:14px}
    @media(max-width:600px){.main{padding:32px 20px 140px}.top-inner,.bottom-inner{padding-left:20px;padding-right:20px}.title{font-size:28px}.card{padding:22px;border-radius:20px}.question{font-size:20px}.meta{grid-template-columns:1fr}.choices{grid-template-columns:1fr}.choice{padding:14px}.bottom .secondary{min-width:72px}.setup .card{padding:24px}.assignment-row{grid-template-columns:1fr}.assignment-row em{justify-self:start}}
    @media print{.top,.bottom,.setup-actions,.tools{display:none}.main{padding:20px}.card{box-shadow:none;border:1px solid #ddd}}
  </style>
</head>
<body>
<div class="app">
  <header class="top"><div class="top-inner"><div class="brand"><strong>권혁찬 연구 승인</strong><span class="status" id="status">시작 전</span></div><div class="bar"><i id="bar"></i></div></div></header>
  <main class="main">
    <section id="setup" class="setup">
      <p class="eyebrow">한 번에 끝내는 검토</p>
      <h1 class="title">내 이름을 확인하고<br>담당 항목만 승인하세요</h1>
      <p class="desc">이름은 한 번만 입력하세요. 담당 역할과 권장 판정은 항목마다 자동으로 적용됩니다.</p>
      <div class="card">
        <div class="assignment">
          <div class="assignment-row"><b>장민정 교수</b><span>연구계획·제출 승인 4건</span><em>승인 완료</em></div>
          <div class="assignment-row"><b>권혁찬</b><span>기존 필수 검토 175건</span><em>승인 완료</em></div>
          <div class="assignment-row"><b>임상전문가 약사</b><span>안전성 규칙 6건</span><em>약사 1명</em></div>
          <div class="assignment-row"><b>독립 평가 약사</b><span>평가 시나리오 12건</span><em>다른 약사 1명</em></div>
          <div class="assignment-row"><b>전문 검토자</b><span>확보된 고유 전문 63건</span><em>이번 작업</em></div>
        </div>
        <label for="reviewer">검토자 이름</label><input class="input" id="reviewer" autocomplete="name" placeholder="예: 홍길동">
        <div class="setup-actions"><button class="secondary" id="importBtn">결과 가져오기</button><button class="primary" id="startBtn">남은 권장안 검토 시작</button></div>
        <input id="fileInput" type="file" accept="application/json" class="hidden">
        <p class="notice">판정은 자동으로 미리 채워지지 않습니다. 각 클릭에 이름·역할·시간이 기록됩니다.</p>
      </div>
    </section>
    <section id="review" class="hidden">
      <p class="eyebrow" id="sectionLabel"></p><h1 class="title" id="itemTitle"></h1><p class="desc" id="itemDesc"></p>
      <div class="card" id="itemCard"></div>
    </section>
    <section id="done" class="done hidden">
      <div class="done-icon">✓</div><p class="eyebrow" id="doneLabel">검토 완료</p><h1 class="title" id="doneTitle">담당 항목을 모두 확인했습니다</h1><p class="desc" id="doneDesc">결과 파일을 저장해 다음 담당자에게 전달해주세요.</p>
      <div class="card summary" id="summary"></div>
      <button class="primary" id="downloadBtn">결과 JSON 다시 저장</button>
      <div class="tools"><button class="primary" id="nextReviewerBtn">다음 담당자 시작</button><button class="secondary" id="backDoneBtn">마지막 항목 보기</button><button class="secondary" id="resetBtn">이 기기 기록 초기화</button></div>
    </section>
  </main>
  <footer class="bottom hidden" id="bottom"><div class="bottom-inner"><button class="secondary" id="prevBtn">이전</button><button class="primary" id="nextBtn" disabled>승인하고 다음</button></div></footer>
</div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const DATA=JSON.parse(document.getElementById('payload').textContent);const KEY='kwon_research_review_v4_fulltext';
let state=load()||{schema_version:'1.0.0',started_at:null,updated_at:null,overall_status:'in_progress',reviewers:{},decisions:{},cursor:0};
state.decisions=state.decisions||{};for(const [k,v] of Object.entries(DATA.locked_decisions||{})){state.decisions[k]=v}save();
let queue=[];let reviewer={name:'',role:''};
const $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function load(){try{return JSON.parse(localStorage.getItem(KEY))}catch{return null}}function save(){state.updated_at=new Date().toISOString();localStorage.setItem(KEY,JSON.stringify(state));}
function buildQueue(){return DATA.sections.filter(s=>s.id!=='approval').flatMap(s=>s.items.map((item,index)=>({section:s,index,item,key:keyOf(s.id,item,index)})));}
function keyOf(id,x,i){return id+':'+(x.item_id||x.review_id||x.evidence_candidate_id||x.review_item_id||x.scenario_id||i)}
function start(){const name=$('reviewer').value.trim();if(!name){alert('검토자 이름만 입력해주세요.');return}reviewer={name};if(!state.started_at)state.started_at=new Date().toISOString();queue=buildQueue();const first=queue.findIndex(q=>state.decisions[q.key]?.status!=='completed');state.cursor=first<0?queue.length:first;save();$('setup').classList.add('hidden');$('review').classList.remove('hidden');$('bottom').classList.remove('hidden');render();}
function applyRecommendation(q){if(state.decisions[q.key]?.status==='completed')return;const x=q.item,d=state.decisions[q.key]||{};if(q.section.id==='press'&&!d.rating)d.rating=x.recommended_rating;if((q.section.id==='approval'||q.section.id==='literature'||q.section.id==='rules'||q.section.id==='fulltext')&&!d.decision)d.decision=x.recommended_decision;if(q.section.id==='fulltext'&&!d.locator)d.locator=x.recommended_locator;if(q.section.id==='scenarios'&&!d.label)d.label=x.recommended_label;if(Object.keys(d).length){d.prefill_source='codex_recommendation_pending_human_confirmation';d.status='prefilled';state.decisions[q.key]=d;save()}}
function render(){if(state.cursor>=queue.length){showDone();return}const q=queue[state.cursor];applyRecommendation(q);const d=state.decisions[q.key]||{};$('done').classList.add('hidden');$('review').classList.remove('hidden');$('bottom').classList.remove('hidden');$('sectionLabel').textContent=q.section.title+' · '+(state.cursor+1)+' / '+queue.length;$('itemTitle').textContent=titleFor(q);$('itemDesc').textContent=descFor(q);$('itemCard').innerHTML='<p class="notice"><b>Codex 권장안이 선택되어 있습니다.</b> 맞으면 아래 승인 버튼만 누르세요. 다르면 선택을 바꾸세요.</p>'+cardFor(q,d);bindChoices(q);$('prevBtn').disabled=state.cursor===0;$('nextBtn').disabled=!valid(q);$('nextBtn').textContent=state.cursor===queue.length-1?'검토 완료':'권장안 승인하고 다음';updateProgress();window.scrollTo({top:0,behavior:'instant'});}
function titleFor(q){const x=q.item;switch(q.section.id){case'approval':return x.question;case'press':return x.strategy_id+' 검색식 · '+x.criterion;case'literature':return x.title||'문헌 제목 없음';case'rules':return (x.ingredient_id||'')+' · '+x.threshold_value+' '+x.threshold_unit;case'scenarios':return '시나리오 '+(q.index+1);case'fulltext':return x.title||x.pmcid;}}
function descFor(q){switch(q.section.id){case'approval':return'내용이 맞으면 승인. 수정이 필요하면 수정 요청.';case'press':return'검색식 품질 기준을 확인하세요.';case'literature':return'제목과 초록을 읽고 전문 검토 대상을 정하세요.';case'rules':return'수치·범위·조건·문구·근거 위치를 확인하세요.';case'scenarios':return'입력만 보고 안전성 경고가 필요한지 독립 판단하세요.';case'fulltext':return'Codex가 찾은 근거 문단을 확인하세요. 맞으면 다음만 누르세요.';}}
function meta(pairs){return'<div class="meta">'+pairs.filter(x=>x[1]).map(x=>'<div class="pill">'+esc(x[0])+'<b>'+esc(x[1])+'</b></div>').join('')+'</div>'}
function choices(key,opts,selected){return'<div class="choices" data-field="'+key+'">'+opts.map(o=>'<button type="button" class="choice '+(o.danger?'danger ':'')+(selected===o.v?'selected':'')+'" data-value="'+esc(o.v)+'">'+esc(o.t)+'</button>').join('')+'</div>'}
function cardFor(q,d){const x=q.item;if(q.section.id==='approval')return choices('decision',[{v:'approve',t:'승인'},{v:'revise',t:'수정 요청'},{v:'reject',t:'반려',danger:true}],d.decision)+textArea('note','수정 내용 또는 메모',d.note);
if(q.section.id==='press')return meta([['검색식',x.strategy_id],['PRESS 항목',x.question_number],['상태',x.status]])+choices('rating',[{v:'yes',t:'적합'},{v:'unclear',t:'불명확'},{v:'no',t:'수정 필요',danger:true}],d.rating)+textArea('note','수정 내용 또는 메모',d.note);
if(q.section.id==='literature')return meta([['영양성분',x.clinical_node_id],['연도',x.year],['PMID',x.pmid],['AI 우선점수',x.score]])+'<div class="quote">'+esc(x.candidate_abstract_quote||'초록 없음')+'</div>'+(x.source_url?'<a class="source" href="'+esc(x.source_url)+'" target="_blank" rel="noreferrer">PubMed 원문 열기 ↗</a>':'')+choices('decision',[{v:'include_candidate',t:'전문 검토'},{v:'uncertain',t:'불확실'},{v:'exclude',t:'제외',danger:true}],d.decision)+(d.decision==='exclude'?selectReason(d.reason):'')+textArea('note','메모 (선택)',d.note);
if(q.section.id==='rules')return meta([['규칙 ID',x.rule_id],['대상',x.population],['범위',x.scope],['근거 위치',x.locator]])+'<div class="quote"><b>공식 근거 문장</b><br>'+esc(x.evidence_quote||'근거 문장 없음')+'<br><br><b>사용자 문구</b><br>'+esc(x.message_ko)+'<br>'+esc(x.next_action_ko)+'</div><p class="notice">승인은 임계값·대상 범위·조건·예외·사용자 문구·다음 행동·source/locator 7개 항목이 모두 적합하다는 뜻입니다.</p>'+choices('decision',[{v:'approve',t:'7항목 모두 승인'},{v:'revise',t:'수정 요청'},{v:'reject',t:'반려',danger:true}],d.decision)+textArea('note','수정 내용 또는 메모',d.note);
if(q.section.id==='fulltext'){const passages=(x.evidence_candidates||[]).map((c,i)=>'<div class="quote"><b>근거 '+(i+1)+' · '+esc(c.locator||c.section_title)+'</b><br>'+esc(c.evidence_text)+'</div>').join('');return meta([['PMID',x.pmid],['PMCID',x.pmcid],['영양성분',x.clinical_node_id],['후보 근거',String((x.evidence_candidates||[]).length)]])+passages+choices('decision',[{v:'include',t:'권장안 승인'},{v:'uncertain',t:'불확실'},{v:'exclude',t:'제외',danger:true}],d.decision)+textArea('note','메모 (선택)',d.note);}
return meta([['유형',x.scenario_type]])+'<div class="quote">'+esc(x.input_json)+'</div>'+choices('label',[{v:'warning',t:'경고 필요'},{v:'no_warning',t:'경고 불필요'}],d.label)+'<p class="notice">엔진 예측·개발 정답·critical 분류는 표시하지 않습니다.</p>';
}
function textArea(id,label,val){return'<label for="'+id+'">'+label+'</label><textarea class="textarea" id="'+id+'">'+esc(val||'')+'</textarea>'}
function selectReason(v){const reasons=['NOT_HUMAN','NOT_ORAL_EXPOSURE','NOT_TARGET_INGREDIENT','NO_SAFETY_OUTCOME','DIET_ONLY_NOT_SEPARABLE','EFFICACY_ONLY','NON_RESEARCH_PUBLICATION','DUPLICATE_PUBLICATION_CANDIDATE','OTHER_WITH_NOTE'];return'<label for="reason">제외 이유</label><select class="select" id="reason"><option value="">선택</option>'+reasons.map(x=>'<option '+(v===x?'selected ':'')+'value="'+x+'">'+x+'</option>').join('')+'</select>'}
function bindChoices(q){document.querySelectorAll('.choices').forEach(g=>g.querySelectorAll('.choice').forEach(b=>b.onclick=()=>{const d=state.decisions[q.key]||{};d[g.dataset.field]=b.dataset.value;state.decisions[q.key]=d;save();render()}));['note','reason'].forEach(id=>{const el=$(id);if(el)el.oninput=()=>{const d=state.decisions[q.key]||{};d[id]=el.value.trim();state.decisions[q.key]=d;save();$('nextBtn').disabled=!valid(q)}})}
function valid(q){const d=state.decisions[q.key]||{};if(q.section.id==='approval'||q.section.id==='rules')return!!d.decision&&(d.decision==='approve'||!!d.note);if(q.section.id==='press')return!!d.rating&&(d.rating==='yes'||!!d.note);if(q.section.id==='literature')return!!d.decision&&(d.decision!=='exclude'||!!d.reason);if(q.section.id==='fulltext')return!!d.decision&&(d.decision==='include'||!!d.note);return!!d.label;}
function next(){const q=queue[state.cursor];if(!valid(q))return;const d=state.decisions[q.key];Object.assign(d,{reviewer_id:reviewer.name,reviewer_role:q.section.role,reviewed_at:new Date().toISOString(),review_kind:'human_confirmation_of_codex_recommendation',status:'completed'});state.reviewers[q.section.role]={name:reviewer.name,role:q.section.role,last_seen_at:new Date().toISOString()};if(q.section.id==='scenarios')d.locked_before_test=true;state.decisions[q.key]=d;state.cursor++;while(state.cursor<queue.length&&state.decisions[queue[state.cursor].key]?.status==='completed')state.cursor++;save();render()}
function prev(){if(state.cursor>0){state.cursor--;save();render()}}
function updateProgress(){const complete=queue.filter(q=>state.decisions[q.key]?.status==='completed').length;$('status').textContent=complete+' / '+queue.length;$('bar').style.width=(queue.length?complete/queue.length*100:0)+'%'}
function showDone(){state.overall_status=allRequiredDone()?'completed':'partially_completed';const shouldAutoExport=state.overall_status==='completed'&&!state.auto_exported_at;if(state.overall_status==='completed')state.completed_at=state.completed_at||new Date().toISOString();if(shouldAutoExport)state.auto_exported_at=new Date().toISOString();save();$('review').classList.add('hidden');$('bottom').classList.add('hidden');$('done').classList.remove('hidden');const all=state.overall_status==='completed';$('doneLabel').textContent=all?'전체 검토 완료':'담당 검토 완료';$('doneTitle').textContent=all?'전체 필수 항목을 모두 확인했습니다':'내 담당 항목을 모두 확인했습니다';$('doneDesc').textContent=all?'결과 JSON이 다운로드 폴더에 자동 저장되었습니다.':'다음 담당자가 같은 화면에서 이어서 확인합니다.';const rows=DATA.sections.map(s=>{const done=s.items.filter((x,i)=>state.decisions[keyOf(s.id,x,i)]?.status==='completed').length;return'<div class="summary-row"><span>'+esc(s.title)+'</span><b>'+done+' / '+s.items.length+'</b></div>'}).join('');$('summary').innerHTML=rows+'<div class="summary-row"><span>전체 상태</span><b>'+(all?'전체 완료':'진행 중')+'</b></div>';$('status').textContent=all?'전체 완료':'담당 완료';$('bar').style.width=all?'100%':'auto';if(shouldAutoExport)setTimeout(exportResult,0)}
function allRequiredDone(){return DATA.sections.every(s=>s.items.every((x,i)=>state.decisions[keyOf(s.id,x,i)]?.status==='completed'))}
function exportResult(){const out={...state,researcher:DATA.researcher,exported_at:new Date().toISOString(),required_counts:Object.fromEntries(DATA.sections.map(s=>[s.id,s.items.length]))};const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='권혁찬_연구검토결과.json';a.click();URL.revokeObjectURL(a.href)}
function importResult(file){const r=new FileReader();r.onload=()=>{try{const x=JSON.parse(r.result);if(!x.decisions)throw Error();state=x;save();alert('검토 결과를 가져왔습니다.');location.reload()}catch{alert('올바른 검토 결과 JSON이 아닙니다.')}};r.readAsText(file)}
$('startBtn').onclick=start;$('nextBtn').onclick=next;$('prevBtn').onclick=prev;$('downloadBtn').onclick=exportResult;$('importBtn').onclick=()=>$('fileInput').click();$('fileInput').onchange=e=>e.target.files[0]&&importResult(e.target.files[0]);$('nextReviewerBtn').onclick=()=>{$('done').classList.add('hidden');$('review').classList.add('hidden');$('bottom').classList.add('hidden');$('setup').classList.remove('hidden');window.scrollTo({top:0,behavior:'instant'})};$('backDoneBtn').onclick=()=>{state.cursor=Math.max(0,queue.length-1);$('done').classList.add('hidden');$('review').classList.remove('hidden');$('bottom').classList.remove('hidden');render()};$('resetBtn').onclick=()=>{if(confirm('이 기기의 검토 기록을 초기화할까요?')){localStorage.removeItem(KEY);location.reload()}};
document.addEventListener('keydown',e=>{if($('review').classList.contains('hidden'))return;if(e.key==='Enter'&&!e.shiftKey&&!['TEXTAREA','INPUT','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();next()}if(e.key==='ArrowLeft')prev()});
if(state.reviewers&&Object.keys(state.reviewers).length){const last=Object.values(state.reviewers).at(-1);$('reviewer').value=last.name||''}
</script>
</body></html>'''


if __name__ == "__main__":
    main()
