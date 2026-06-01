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

## 권혁찬 OTC 영양성분 연구 컨텍스트

- 이 repo는 권혁찬 연구용이며, 기존 여형준 연구처럼 결정적 규칙 엔진과 문헌검색 pipeline을 쓰되 연구 질문은 다르게 둔다.
- 기존 연구가 항응고제 복용자와 신장 관련 고위험군 같은 환자/질환 맥락을 중심으로 했다면, 이 연구는 일반의약품과 건강기능식품 경계에 있는 고함량 영양성분 자체를 중심으로 한다.
- 1차 타겟은 고함량 지용성 비타민·칼슘 축, 비타민 B6/B군 복합제 축, 철분·마그네슘·칼슘 미네랄 축이다.
- 랩미팅 설명은 PubMed 중심으로 유지하고, Embase는 후속 확장 경로로만 언급한다.
- The Embase implementation still exists in `tools/search_pipeline/embase_adapter.py` as internal follow-up work. Do not remove it unless the user explicitly asks.
- The systematic search pipeline is Python-based and separate from the Next.js runtime:
  - Code: `tools/search_pipeline/`
  - Search outputs: `data/systematic_search/`
  - PubMed search log: `data/systematic_search/search_runs.csv`
  - Retrieved records: `data/systematic_search/retrieved_records.csv`
- Treat `data/knowledge_pack.json` as reusable exploratory scoping data only. Final 권혁찬 thesis evidence should come from new systematic search logs under `data/systematic_search/`.
- Current presentation framing: PubMed API prototype is implemented and run for OTC-like nutrient ingredients; Embase remains a later RIS export automation path.
