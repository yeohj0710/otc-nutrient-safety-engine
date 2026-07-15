<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Project Navigation

Before exploring the repo from scratch, check `docs/project_map.md`.

- Main page: `app/page.tsx`
- Main client UI: `src/components/rule-explorer-client.tsx`
- Result card UI: `src/components/rule-card.tsx`
- Safety engine: `src/lib/safety-engine/index.ts`
- Knowledge loader/normalizer: `src/lib/knowledge/`
- Primary data source: `data/knowledge_pack.json`
- Runtime index: `src/generated/knowledge-index.json`

## 권혁찬 국내 일반의약품 연구 컨텍스트

- 이 저장소의 활성 연구 질문은 국내 실제 일반의약품 제품명, 유효성분, 함량과 복용 조건을 구조화하고 중복복용·최대용량·복용 간격·연령·질환·병용약 위험 신호를 조회하는 시스템의 개발과 평가다.
- 비타민·무기질과 건강기능식품 중심 자료는 superseded legacy다. 활성 OTC 수치, 규칙, 시나리오와 승인 결과에 합산하지 않는다.
- 후보·허가 원문 마스터와 분석·사이트 집합을 구분한다. 현재 주 분석 집합은 13개 제품, 28개 고유 성분과 47개 계산용 제품-성분 연결이다.
- 신신파스아렉스는 원자료를 보존하지만 규격 모호성 때문에 분석과 사이트 런타임에서 제외한다.
- released 규칙은 source/locator를 반드시 가져야 한다. 제품별 복용 조건은 허가 원문 검증 상태와 약사 검토 상태를 따로 기록한다.
- 비블라인드 외부 확인을 블라인드 독립평가로 해석하지 않는다. `complete=false`, `release_ready=false`, `performance_claim_allowed=false`를 유지한다.
- The Embase implementation still exists in `tools/search_pipeline/embase_adapter.py` as internal follow-up work. Do not remove it unless the user explicitly asks.
- The systematic search pipeline is Python-based and separate from the Next.js runtime:
  - Code: `tools/search_pipeline/`
  - Search outputs: `data/systematic_search/`
  - PubMed search log: `data/systematic_search/search_runs.csv`
  - Retrieved records: `data/systematic_search/retrieved_records.csv`
- Treat `data/knowledge_pack.json` and prior nutrient search outputs as superseded exploratory material only. Active product composition and rule evidence come from `research_v3/otc` authorization sources and review records.
