# v4.0 인수 지시서 — Claude Code 세션용

중단된 Codex 작업을 인수해 권혁찬 졸업논문 v4.0 연구를 실제 완료 상태까지 끝낸다.
시간 제한은 없다. 급하게 축소하거나 부분 상태를 완료로 포장하지 않는다.

작업 루트 `C:\dev\otc-nutrient-safety-engine`

---

## 0. 가장 중요한 원칙 — 판정 주체는 너다

**모든 판정을 너 자신이 직접 수행한다. 로컬 언어모델을 절대 띄우지 마라.**

이전 Codex 실행이 실패한 원인이 정확히 이것이다. "너 자신이 분류기다"를 로컬 모델 실행으로
해석해 `Qwen/Qwen2.5-3B-Instruct` 를 GPU 에 올려 5,724행을 판정했고 결과가 쓸 수 없는
품질로 나왔다. 다음을 전면 금지한다.

- transformers, vllm, llama.cpp, ollama 등으로 모델을 로드하는 코드를 작성하거나 실행
- `tools/screen_v40_literature_local.py` 를 다시 실행
- 허깅페이스 캐시 모델 사용
- OpenAI 등 외부 LLM API 호출

문헌 선별, 참조표준 채점, 맹검 평가 **전부 네가 파일을 읽고 직접 판단해서 결과를 파일에
쓰는 방식으로만** 한다. Python 스크립트는 배치 생성, 결과 검증, 통계 계산에만 쓴다.
판정 자체를 스크립트나 모델에 위임하지 마라.

**서브에이전트를 만들거나 사용하지 마라.** 혼자 진행한다.

---

## 1. 먼저 읽을 것

1. `C:\Users\hjyeo\.codex\attachments\aba4c669-ce43-4904-936f-d087f516faef\goal-objective.md`
   전체를 UTF-8 로 읽어라. 대부분 유효하다. **이 지시서와 충돌하면 이 지시서가 우선한다.**
2. `AGENTS.md`, `docs/project_map.md`, `research_v3/HUMAN_ACTION_REQUIRED.md`,
   `research_v3/project_identity.json`, `research_v3/protocol/protocol-v4.0-full-ai.md`,
   `research_v3/protocol/amendments.csv`, `research_v3/protocol/v4.0-ai-literature-layer-plan.md`
3. `research_v3/logs/RESUME.md`, `research_v3/logs/v40_run_report.json`
4. 미추적 파일 `research_v3/otc/literature/prompts/ai_reference_prompt.md` — P3-A용
   독립 참조표준 프롬프트다. 검토·개선해서 쓰고 P3 산출물과 함께 커밋하라. 삭제하지 마라.

`git status`, 최근 커밋, 현재 매니페스트를 직접 확인하라.
아래 인수 정보는 출발점이고 **현재 파일 상태가 권위다.**

---

## 2. 인수 상태

브랜치 main, HEAD `3b4a515 research(v4): complete AI screening corpus`.
`origin/main` 은 `361e5ac` 로 로컬보다 뒤처져 있다. **reset 하거나 로컬 커밋을 버리지 마라.**
동결 태그 `v3-otc-frozen` → `4188272`.

### 완료 (유효)

- **P0** 사람 산출물 보존 커밋, 동결 매니페스트, `protocol-v4.0-full-ai.md`, AM-OTC-001
- **P1** AI 자율 PICOS 5개, PubMed 실검색 hit 5,742 → 고유 PMID 5,724
  (초록 보유 5,424 / 제목만 300). 원시 ESearch·EFetch XML, query, 메타데이터, SHA-256 보존.
  주요 파일 `research_v3/otc/literature/picos/picos_definition.json`,
  `evidence_map.csv`, `search_log.csv`, `searches/`

### 폐기 대상

- **P2** 로컬 3B 판정 전체. `retain 225/5,724 = 3.9%`, `fallback_invalid_output 415행`.
  주제를 좁게 겨냥한 코퍼스에서 96% 가 주제 무관일 수 없고, 415행은 모델이 스키마를
  못 지켜 강제 처리된 행이라 판정이라 부를 수 없다.

### 미실행

P3-A, P3-B, P3-C, P4.
P5 는 "300/5,724 부분 실행" 시점 산출물이 이미 만들어졌고 **Notion 페이지와 Google Drive 에도
그 부분 상태가 올라가 있다.** 최종 단계에서 전부 재생성·재동기화해야 한다.

---

## 3. 실행 순서

P2 → P3-A → P3-B → P3-C → P4 → P5 → 최종 감사.
앞 단계의 완료 조건을 충족하기 전에 다음으로 넘어가지 마라.

### P2 — 3B 산출물 폐기와 에이전트 직접 선별

#### P2-0. 폐기 처리

git 히스토리를 조작하지 마라. 파일을 옮겨 격리한다.

- 다음을 `research_v3/otc/literature/screening_discarded_local3b/` 로 이동:
  `screening/screening_checkpoints.jsonl`, `screening/screening_results.csv`,
  `screening/screening_manifest.json`
- `tools/screen_v40_literature_local.py` 도 같은 폴더로 이동
- 그 폴더에 `README.md` 를 만들어 한 문단으로 적어라: 소형 로컬 모델을 사용한 중단된
  실행 시도이며 판정 품질이 연구 요건에 미달해 폐기했다. v4.0 체인의 입력·정답·근거·
  비교 대상 어디에도 사용하지 않는다.
- `research_v3/DECISIONS.md` 에 폐기 결정과 사유를 한 줄로 기록하라
- **논문, 발표 원고, Notion, 최종 보고서, 매니페스트 어디에도 이 실행을 언급하지 마라.**
  결과 비교 절을 만들지 마라. 존재하지 않는 것으로 취급하라

#### P2-1. 판정 프롬프트 확정

- `research_v3/otc/literature/prompts/agent_screening_prompt.md` 에 저장하고 SHA-256 기록
- 실행 중 절대 바꾸지 마라. 바꾸면 처음부터 다시 해야 한다
- 라벨은 `retain` / `deprioritize` / `uncertain`. 사람의 include/exclude 가 아니다
- 판정 기준: 해당 연구질문의 노출과 결과가 함께 다뤄질 가능성이 있으면 retain,
  주제가 뚜렷이 다르면 deprioritize, 초록만으로 판단이 서지 않으면 uncertain.
  사람이 일반의약품을 복용하는 상황이 대상이므로 동물 전용·시험관 전용 연구는
  deprioritize 하고 근거 코드를 남긴다
- 초록에 없는 사실을 만들지 마라. 임상 권고·복용 지시·용량 판단을 만들지 마라

#### P2-2. 배치 생성

- `research_v3/otc/literature/screening/batches/` 에 배치당 40~60행
- 각 배치는 `{batch_id, input_sha256, rows:[{record_id, pmid, question_id, title, abstract}]}`
- 전체 5,724행이 정확히 한 번씩 배치에 들어가야 한다

#### P2-3. 판정

- **네가 배치를 읽고 직접 판정한다.**
- append-only JSONL `research_v3/otc/literature/screening/checkpoints.jsonl`
- 줄 스키마 `{record_id, question_id, decision, reason_codes, confidence, evidence_basis, status}`
- `evidence_basis` 는 `title_abstract` 또는 `title_only`.
  제목만 있는 300행은 `title_only` 로 분리하고 `confidence` 상한을 `low` 로 강제하라
- **fallback 이나 파싱 실패라는 개념이 없어야 한다.** 네가 직접 쓰므로 스키마 위반이
  나올 수 없다. 판단이 어려우면 `uncertain` 을 쓰고 이유를 남겨라
- 배치 5개마다 커버리지 검증 스크립트를 돌려라. 요청한 `(record_id, question_id)` 가
  정확히 한 번씩 돌아왔는지 확인하고 누락을 재배치하라. **100% 가 될 때까지 반복하라**
- 배치 10개마다 커밋하라. 세션이 끊겨도 작업이 남아야 한다
- 세션이 끊기면 체크포인트에서 이어서 재개하라. **부분 커버리지를 완료로 쓰지 마라**

#### P2-4. 확정

- `research_v3/otc/literature/screening/screening_manifest.json` 생성
- 기록할 것: `screener: "agent_direct"`, 커버리지, 프롬프트 SHA-256, 입력 SHA-256,
  판정 분포, 근거 형태별 분포, 배치 목록과 해시, `run_complete`
- **커버리지가 1.0 이 아니면 `run_complete` 를 true 로 쓰지 마라**
- 커밋하라

### P3-A — 독립 AI 참조표준

1. P2 판정 결과를 strata 로 사용해 층화 무작위 표본 300건을 뽑아라.
   층별 프레임 크기, 표본 수, 가중치, 시드를 매니페스트에 기록하라
2. 블라인드 파일에 P2 라벨·confidence·reason_codes·batch_id 를 절대 넣지 마라
3. **P2 와 다른 프롬프트를 써라.** `ai_reference_prompt.md` 가
   `P=Y|I=Y|C=U|O=Y|S=Y` 형식으로 PICOS 요소를 각각 평가하도록 작성돼 있다.
   검토·개선해서 쓰고 해시를 기록하라
4. P·I·C·O·S 를 각각 평가한 뒤 **코드의 명시적 규칙**으로 종합 라벨을 도출하라.
   주제 적합성을 통째로 한 번에 묻지 마라
5. 라운드별로 행 순서를 독립 무작위화하고 시드를 기록하라. 3회 독립 판정 후 다수결.
   세 라벨이 모두 다르면 `unresolved` 로 남기고 건수를 보고하라
6. 라운드 간 일치율과 κ 를 기록하라
7. 층화 가중치를 적용해 산출하라. **단순 평균을 쓰지 마라.**
   `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`,
   `precision_vs_ai_reference`, `f1_vs_ai_reference`, `agreement_vs_ai_reference`
8. Rogan–Gladen 보정 + 층화 부트스트랩 10,000회로 코퍼스 수준 retain 규모의
   점추정과 95% CI 를 계산하라
9. 위양성·위음성 사례를 실제 제목과 함께 각각 최대 20건 기록하라
10. 출력 `research_v3/measurement/screener_vs_ai_reference.json`.
    블라인드 표본, 라운드별 출력, 프롬프트, 해시, 매니페스트를 재현 가능한 위치에 보존하라
11. 통계 함수에 테스트를 추가하라. 특히 층화 가중, Rogan–Gladen, 부트스트랩 CI
12. 커밋하라. `ai_reference_prompt.md` 도 이때 함께 커밋하라

### P3-B — 규칙엔진 AI 맹검 독립평가

1. 분석 제품 13개 × 규칙 유형 16개의 **실제 조합 공간**에서 무라벨 사례를 생성하라.
   규칙 유형별 최소 10건, 총 200건 이상. 위험 있음과 없음을 모두 포함하라.
   양성만 만들면 특이도를 낼 수 없다
2. 실제 허가 제품·성분·함량·복용 조건에서만 만들어라. 없는 제품·성분·용량을 만들지 마라
3. 사례 생성 단계에서 정답 라벨이나 엔진 예측을 만들지 마라.
   출력 `research_v3/otc/validation/ai_independent_cases/`
4. 평가 프롬프트는 사례 생성 프롬프트, P2 프롬프트, P3-A 프롬프트와 **모두 달라야 한다**
5. 평가 중 다음을 절대 읽지 마라: 엔진 예측, 기존 Codex 예상 답안,
   `research_v3/otc/validation/independent_scenarios.csv` 의 `human_reference_label`,
   사람이 만든 모든 판정 파일
6. 블라인드 사례만 읽고 라운드별 무작위 순서와 시드를 기록하라.
   3회 독립 판정 후 다수결, 3-way 불일치는 `unresolved`
7. **AI 라벨 파일을 해시와 함께 먼저 잠가라.** 잠금 파일의 생성 시각과 SHA-256 을 기록하라
8. 잠근 뒤에만 **별도 단계**에서 엔진 예측을 연결하라.
   코드 구조와 감사 로그로 순서를 증명할 수 있어야 한다
9. 기존 13건도 같은 AI 절차로 재평가하되, 라벨 잠금 전에는 기존 human label 이나
   prediction 을 읽지 마라. 비교는 잠금 후 별도 후처리에서만 하라
10. 지표: 위 다섯 개 + 중대 위음성 수, Wilson 95% CI, 부트스트랩,
    규칙 유형별 분해, 실패 사례 최대 20건
11. 출력 `research_v3/otc/validation/ai_independent_evaluation.json`
12. 참고 코드: `scripts/research/otc/build_independent_cases.py`,
    `scripts/research/otc/predict-independent.ts`, `src/lib/otc/independent-evaluation.ts`,
    `scripts/research/otc/evaluate.py`
13. 기존 사람 파일을 수정하지 마라. 새 AI 전용 파일·디렉터리를 써라
14. 테스트 후 커밋하라

### P3-C — 상태 갱신

P3-A 와 P3-B 의 개수·블라인드·잠금 순서·무결성이 **모두** 충족된 경우에만 설정하라.

```
independent_blinding_ai            = true
independent_evaluation_ai_complete = true
performance_claim_allowed          = true
complete                           = true
release_ready                      = false
independent_blinding               = false
```

- `performance_claim_allowed=true` 는 "AI 평가자를 사용했다는 사실을 항상 병기하는 조건"이다
- 성능 수치를 좋게 맞추려고 프롬프트·사례·라벨을 조정하지 마라
- `unresolved`, 낮은 일치도, 실패 사례를 그대로 보고하라
- 필수 절차나 표본 수가 미달이면 `complete=false` 를 유지하라
- 각 플래그 옆에 근거 파일 경로를 기록하라
- `research_v3/project_identity.json` 의 `released_rule_count` 를 실제 15로 고쳐라
- `research_v3/HUMAN_ACTION_REQUIRED.md` 1번을 "AI 평가로 대체됨(AM-OTC-001)"으로 바꿔라.
  사람이 완료한 것처럼 쓰지 마라. 2번 약사 재검토와 3번 범위 확장은 선택·권장으로 유지하라
- metrics manifest 와 종료 감사 파일을 함께 갱신하고 커밋하라

### P4 — 문헌 근거지도·개인화·사이트

1. retain 문헌으로 규칙 16개 **전부**에 문헌 근거를 연결하라
2. `research_v3/otc/rules/supporting_literature.csv` 를 확장하라. 현재 13행뿐이다
3. 각 연결은 초록의 **문장 단위 locator** 가 필수다
4. 허가원문 근거와 PubMed 문헌 근거를 **별도 컬럼·별도 권한**으로 유지하라
5. 문헌은 설명용 근거이며 **규칙 판정 로직을 바꾸지 않는다**
6. 허가사항과 문헌이 충돌하면 `conflict` 로 보존하고 어느 한쪽을 지우지 마라
7. `literature_link_manifest.json` 에 기록: 규칙 16개 중 문헌 보유 수, 새 연결 수,
   conflict 수, 제품명→성분→문헌 개인화 축, 근거 행 수, 입력·출력 해시
8. 관찰되지 않은 개인화 축을 만들지 마라
9. UI 결과 카드에서 "허가근거"와 "참고 문헌"을 시각적·문구상 분리하고
   "참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지 않는다"를 표시하라
10. Next.js 16 코드를 바꾸기 전에 `node_modules/next/dist/docs/` 의 관련 문서를 읽어라
11. 정적 경로 156 유지
12. 정합성 감사 재실행: 제품 13 / 성분 28 / 계산 연결 47 / 복용 조건 32 /
    신신파스아렉스 분석·런타임 누출 0
13. `npm run typecheck` → `npm run lint` → `npm test` → `npm run build`.
    기존 연구 139 · 앱 69 시험을 깨뜨리지 마라
14. **배포하지 마라. `npx vercel` 을 실행하지 마라**
15. 커밋하라

### P5 — 최종 문서·논문·Notion·Google Drive

1. 현재 중간 보고서와 논문을 **최종 매니페스트 수치로 재생성**하라.
   기억이나 이 지시서의 숫자를 하드코딩하지 말고 매니페스트를 읽는 코드에서 생성하라.
   기존 생성 코드 `tools/build_v40_reporting.py`, `tools/build_v40_run_report.py`
2. 논문 제목·초록·서론·방법·결과·고찰·한계·결론을 최종 v4.0 상태로 다시 써라
3. 방법에 포함: 허가원문 결정층과 PubMed AI 근거층의 이층 구조, AI 자율 PICOS,
   coverage=1.0, 프롬프트 해시, AI 참조표준, AI 맹검 독립평가, 사람 판정 0건
4. 한계에 포함: AI 참조표준 대비 재현도이지 절대적 진실 대비 정확도가 아님,
   분류기와 참조표준이 같은 모델이므로 독립성이 부분적, PubMed 단일 자료원,
   판매량 자료 부재, 복용 조건 32개는 허가원문 검증까지만 완료
5. "민감도"를 단독으로 쓰지 말고 "AI 참조표준 대비 민감도"로 써라
6. DOCX/PDF 는 설치된 정적 Pretendard 계열을 쓰고, DOCX XML 에서 Pretendard 문자열과
   PDF 글꼴 포함을 확인하라. **PDF 모든 페이지를 이미지로 렌더해 잘림·고아 행·빈 페이지를
   직접 눈으로 검사하라**
7. `README.md`, `AGENTS.md`, `docs/project_map.md`, `metrics_manifest.json` 최종 갱신
8. 발표 원고 `research_v3/reports/발표원고_v4.0.md` — 슬라이드별 3~5문장.
   문제 → 주제 전환 → 허가원문 → AI PICOS → 문헌 선별 → AI 참조표준 성능 →
   규칙 16개 근거 → 맹검평가 → 한계 → 결론.
   **PPTX 를 만들지 마라. 디자인 작업을 하지 마라**
9. Notion 원고 `research_v3/reports/notion_update.md` — 상단 현재 상태만 교체하는 완성본.
   기존 [대체됨] 절과 하위 페이지는 유지. **현재 Notion 상단에 300/5,724 부분 상태가
   올라가 있으므로 반드시 최종 상태로 교체해야 한다**
10. Notion 접근 도구가 실제로 이미 제공되는 경우에만
    https://app.notion.com/p/3723b1f9b9ae802b9561d4487802e046 을 직접 갱신하고 다시 읽어
    확인하라. 없으면 설치·로그인 시도로 시간을 쓰지 말고 원고만 만들고
    `notion_updated=false` 와 이유를 보고서에 기록하라
11. 최종 보고서 `research_v3/logs/v40_run_report.json`.
    필수 절: phases, picos, corpus, screening, ai_reference, blind_eval, state_flags,
    rule_evidence, site, thesis, notion_updated, files_synced, closure,
    scope_reductions, unresolved
12. 추정하지 않은 값은 null 로 두되, 모든 필수 작업이 정상 완료되면 실제 결과로 채워라
13. `research_complete` 와 모든 상태 플래그를 실제 근거 파일과 대조하라

### Google Drive 최종 동기화

루트 `G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\03_최종산출물\`

`03_연구데이터_research_v3\` 에 복사:
picos_definition.json, screener_vs_ai_reference.json, ai_independent_evaluation.json,
supporting_literature.csv, literature_link_manifest.json, metrics_manifest.json,
v40_run_report.json, amendments.csv, protocol-v4.0-full-ai.md, notion_update.md

`01_논문_최종본\` 에 복사: 권혁찬_졸업논문_최종본.docx, 권혁찬_졸업논문_최종본.pdf
상위 `04_발표자료\` 에 복사: 발표원고_v4.0.md

- 기존 백업이 이미 있다: `권혁찬_졸업논문_최종본_v3백업.docx/.pdf`,
  `metrics_manifest_v3백업.json`. **백업을 덮어쓰거나 삭제하지 마라**
- 덮어쓰기 전에 대상과 백업 존재 여부를 다시 확인하라
- `90_legacy_구버전_열지말것` 폴더는 절대 건드리지 마라
- 복사 후 원본과 복사본의 SHA-256 을 비교하고 `files_synced` 에 실제 목록을 기록하라

---

## 4. 절대 금지

- **로컬 LLM 을 로드·실행하는 모든 행위.** 판정은 네가 직접 한다
- 외부 LLM API 호출
- 폐기한 3B 산출물을 v4.0 체인의 입력·정답·근거·비교 대상으로 사용하거나 문서에 언급
- 사람 판정 파일을 수정하거나 v4.0 체인에 입력·정답·링크로 연결:
  `research_v3/screening/title_abstract.csv`, `research_v3/screening/full_text.csv`,
  `research_v3/human_review_minimal/`, `research_v3/rules/EXPERT_REVIEW_GUIDE.md`,
  `expert_rule_review_*`, `independent_scenarios.csv` 의 `human_reference_label`
- `research_v3/search/provisional_pubmed_20260710/` 수정
- 이전 영양성분 계보 수치를 OTC 결과에 합산
- AI 평가를 사람 평가라고 표현. `independent_blinding` 을 true 로 설정
- `release_ready` 를 true 로 설정
- 복용 조건 32개와 released 규칙 15개의 상태를 합침
- locator 없는 문헌 근거를 released 로 승격
- 사람이 검토할 큐·승인 대기·빈칸 생성
- "판매량 상위" 표현. "대표 일반의약품 후보"만 쓴다
- 신신파스아렉스를 분석·런타임에 포함
- `tools/search_pipeline/embase_adapter.py` 삭제
- PRISMA 최종 포함·제외 수, 메타분석, 사람 RoB·GRADE, 임상 권고 생성
- 배포
- `git reset --hard`, `git checkout` 으로 사용자 변경 폐기
- 부분 결과를 완료로 보고
- 숫자 하드코딩

---

## 5. 작업 방식

- 모든 파일은 `C:\dev\otc-nutrient-safety-engine` 안에서 수정하라
- 편집 전 현재 파일을 읽고 기존 변경을 보존하라
- 생성 중간물·렌더·백업은 적절한 `etc` 하위에 둬라
- PowerShell 과 Python 출력은 UTF-8 을 강제하라. CSV 는 `utf-8-sig` 로 읽어라
- 30분마다 `research_v3/logs/RESUME.md` 를 갱신하라
- 단계 완료 시마다 커밋하라. 체크포인트·매니페스트는 해시·행 수·중복·누락을 검증하라
- 같은 명령이 3회 실패하면 원인과 대안을 기록하고 다음 안전 경로를 택하라
- 주기적으로 `git status` 를 확인하고 로컬 main 의 기존 커밋을 보존하라
- push 는 선택이지만 배포는 금지다
- 사용자에게 중간 질문하지 말고 저장소 근거로 결정하라.
  판단한 내용은 `research_v3/DECISIONS.md` 에 기록하라

---

## 6. 최종 완료 감사

1. `goal-objective.md` 의 모든 명시 요구사항을 체크리스트로 다시 대조하라
2. P2 커버리지 1.0 과 `run_complete=true` 를 재검증하고,
   **로컬 모델이 사용되지 않았음을 코드·로그로 증명하라**
3. 폐기한 3B 산출물이 어떤 산출물·문서에서도 참조되지 않는지 경로·코드 검색으로 확인하라
4. P3-A 300건, 3라운드, 층화 가중치, Rogan–Gladen, 10,000회 부트스트랩을 검증하라
5. P3-B 총 200건 이상, 규칙 유형별 최소 10건, 양·음성 포함, 3라운드,
   label lock 이 엔진 예측 연결보다 **먼저** 일어났음을 감사 로그로 검증하라
6. 사람 판정 자료가 v4.0 입력·정답·링크에 전혀 포함되지 않았는지
   경로·해시·코드 참조를 감사하라
7. 규칙 16개 모두에 문장 locator 문헌 근거가 있는지 확인하라
8. 제품 13 / 성분 28 / 연결 47 / 조건 32 / 제외 제품 누출 0 확인
9. typecheck, lint, 전체 테스트, build 의 최신 exit code 와 개수를 기록하라
10. 논문 DOCX/PDF 의 내용·글꼴·전체 페이지 렌더를 확인하라
11. Notion 과 Google Drive 의 최종 상태를 실제로 다시 읽어 확인하라
12. `git diff --check` 와 `git status` 를 확인하라
13. 필수 절차가 하나라도 미완료거나 증거가 약하면 **완료로 선언하지 마라**
14. 모든 증거가 충족될 때만 `complete=true` 와 `performance_claim_allowed=true` 를
    유지하고 최종 완료를 보고하라

모든 보고와 로그는 한국어로 쓴다.
