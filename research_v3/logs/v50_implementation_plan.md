# MECIR 문헌 코퍼스 v5 구현 계획

> **For agentic workers:** 이 계획은 현재 Codex 세션이 단계별로 실행한다. 새 실행은 질문별 선별을 Q01부터 Q05까지 순차로 완료하고, 실행자·모델·시각·선행 질문 해시를 배치 영수증에 남긴다.

**Goal:** 프로토콜 v5.0에 맞는 PubMed P AND I 검색식으로 문헌 코퍼스 v5를 만들고, 실제 수행 범위까지 전량 선별·문헌 결합·감사를 재현 가능하게 기록한다.

**Architecture:** `research_v3/otc/literature/v5/`에 검색 정의, 탐침, 원시 XML, 정규화 코퍼스, 선별 체크포인트와 v5 문헌 연결을 격리한다. `research_v3/logs/v50_*`에는 진행 상태와 단일 실행 원장을 둔다. 허가원문 계층과 기존 v4 문헌 파일은 읽기 전용으로 유지한다.

**Tech Stack:** Python 3, NCBI E-utilities, CSV/JSON/JSONL, SHA-256, pytest 호환 검증

---

### Task 1: 보호 경로 기준선과 검색 정의 고정

**Files:**
- Create: `research_v3/otc/literature/v5/query_definitions.json`
- Create: `research_v3/otc/literature/v5/ingredient_mappings.json`
- Create: `research_v3/logs/v50_protected_baseline.json`

- [x] **Step 1:** 현재 Git 상태와 보호 경로의 파일별 SHA-256 집계를 기록한다.
- [x] **Step 2:** Q01–Q05의 검색어를 P/I/O로 분류하고 O 용어를 최종 질의에서 제외한다.
- [x] **Step 3:** 각 I 블록에 25개 이상의 서로 다른 검색어와 배정된 28개 성분 전부를 연결한다.
- [x] **Step 4:** 한글 성분의 영문 실체, 매핑 근거, 매핑 불가능 여부를 기록한다.

### Task 2: Phase A 탐침

**Files:**
- Create: `research_v3/otc/literature/v5/pipeline_v50.py`
- Create: `research_v3/otc/literature/v5/probe_report.json`

- [x] **Step 1:** ESearch `retmax=0`만 호출해 질문별 건수와 쿼리 번역 경고를 받는다.
- [x] **Step 2:** 질의문 SHA-256, 실행 시각, P/I/O 용어, v4 대비 변화, §3 규칙 1–10 결과를 기록한다.
- [x] **Step 3:** 금지 필터와 O 용어가 최종 질의에 없는지 프로그램으로 검증한다.

### Task 3: Phase B 전량 인출과 코퍼스 정규화

**Files:**
- Create: `research_v3/otc/literature/v5/searches/<QID>/<RUNID>/*.xml`
- Create: `research_v3/otc/literature/v5/searches/<QID>/<RUNID>/checksum.sha256`
- Create: `research_v3/otc/literature/v5/evidence_map.csv`
- Create: `research_v3/otc/literature/v5/corpus_manifest.json`

- [x] **Step 1:** PubMed History Server를 사용해 질문별 모든 레코드를 500건 이하 배치로 인출한다.
- [x] **Step 2:** 10,000 UID 제한이 발생하면 날짜 구간을 겹치지 않게 분할하고 합계가 Phase B 시작 시점의 새 ESearch 건수와 같은지 확인한다. Phase A와 수치가 달라지면 두 건수와 시각을 모두 보존한다.
- [x] **Step 3:** DOI를 우선하고 DOI가 없으면 제목 완전일치로 중복 제거한다.
- [x] **Step 4:** 원시 XML 체크섬, evidence map 해시, 행수·고유 PMID·DOI/제목 기준 고유 논문수·질문별 분포를 대조한다.

### Task 4: Phase C 분류기 보존·점검과 경계 재판정

**Files:**
- Preserve: `research_v3/otc/literature/v5/screening/classifier_decisions.csv`
- Create: `research_v3/otc/literature/v5/screening/classifier_validation.json`
- Create: `research_v3/otc/literature/v5/prompts/frozen_semantic_adjudication_prompt.md`
- Create: `research_v3/otc/literature/v5/screening/adjudication_selection.json`
- Create: `research_v3/otc/literature/v5/screening/batches/adjudication/<QID>/*.jsonl`
- Create: `research_v3/otc/literature/v5/screening/agent_outputs/adjudication/<QID>/*.jsonl`
- Create: `research_v3/otc/literature/v5/screening/semantic_adjudications.json`
- Create: `research_v3/otc/literature/v5/screening/adjudication_manifest.json`
- Modify: `research_v3/otc/literature/v5/screening/decisions.csv`
- Create/Modify: `research_v3/logs/v50_progress.json`

- [x] **Step 1:** 결정적 분류기의 기존 43,207개 라벨을 별도 원본으로 보존하고, 근거 없는 과거 담당자 귀속을 원장에서 제거한다.
- [x] **Step 2:** 실제 문헌 사례 20건 이상으로 분류기 불변식을 검사하고 통과·실패를 모두 기록한다.
- [x] **Step 3:** `uncertain` 전수와 미리 정한 경계·대조 사례를 합쳐 최대 5,000건을 고른 뒤 분류기 라벨과 선정 이유를 뺀 입력을 만든다.
- [x] **Step 4:** 동결 프롬프트에 연결된 5,000건의 재판정 입력·출력을 Q01부터 Q05까지 계약 검사했다. 현재 파일 수정 시각은 질문 순서와 일치하지만, 실행자와 질문 내 병렬 처리를 증명하는 해시 영수증은 없어 구체적인 실행 귀속은 지원되지 않는다.
- [x] **Step 5:** 모든 입력·출력의 스키마, ID, 순서, 해시를 검사하고 재판정 라벨로 최종 결정을 덮어쓴다.
- [x] **Step 6:** 분류기·재판정·최종 분포, 불일치 수와 비율, 라벨 이동 행렬을 기록한다.

### Task 5: Phase D v5 규칙–문헌 결합

**Files:**
- Create: `research_v3/otc/literature/v5/downstream/supporting_literature.csv`
- Create: `research_v3/otc/literature/v5/downstream/literature_link_manifest.json`
- Create: `research_v3/otc/literature/v5/downstream/locator_verification.json`

- [x] **Step 1:** 선별이 100%일 때만 v4 연결 스키마를 v5 코퍼스에 재적용한다.
- [x] **Step 2:** 모든 연결에 `abstract:sentence:N`과 정확한 초록 문장을 넣는다.
- [x] **Step 3:** v5 경로를 입력으로 하는 원문 대조 검증을 실행한다.

### Task 6: Phase E 원장·개정·최종 감사

**Files:**
- Modify: `research_v3/protocol/amendments.csv`
- Create: `research_v3/logs/DECISIONS_v50.md`
- Create: `research_v3/logs/v50_run_report.json`
- Create when partial: `research_v3/logs/RESUME_v50.md`

- [x] **Step 1:** AM-OTC-002를 중복 없이 추가한다.
- [x] **Step 2:** 판단이 갈린 용어 분류, 성분 매핑, 중복 처리와 하류 실행 여부를 기록한다.
- [x] **Step 3:** Phase A–D의 수치·해시·분포·미해결 항목을 단일 원장에 기록한다.
- [x] **Step 4:** 보호 경로 집계 SHA-256과 Git 상태를 기준선과 비교한다.
- [x] **Step 5:** 파이프라인 자체 검증과 연구 테스트를 실행하고 실제 성공·실패만 보고한다.
