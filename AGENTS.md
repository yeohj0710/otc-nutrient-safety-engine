<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Project navigation

Before exploring the repo from scratch, check `docs/project_map.md`.

- Main page: `app/page.tsx`
- Main client UI: `src/components/rule-explorer-client.tsx`
- Result card UI: `src/components/rule-card.tsx`
- Safety engine: `src/lib/safety-engine/index.ts`
- Knowledge loader/normalizer: `src/lib/knowledge/`
- Primary legacy data source: `data/knowledge_pack.json`
- Runtime index: `src/generated/knowledge-index.json`
- Project map: `docs/project_map.md`

## v4.0 research boundary

- The active question is Korean OTC product-name safety lookup.
- MFDS authorization records are the deterministic authority for product, ingredient, amount, administration constraints, and rule decisions.
- PubMed is a separate AI-selected literature layer. It supports evidence claims but cannot override authorization facts or released rule logic.
- Keep authorization evidence and literature evidence in separate fields. Preserve conflicts as `conflict`.
- New literature artifacts belong only under `research_v3/otc/literature/`. Do not modify `research_v3/search/provisional_pubmed_20260710/`.
- Human judgment files are preserved legacy inputs and must not enter the v4.0 chain: `research_v3/screening/`, `research_v3/human_review_minimal/`, expert review artifacts, and `human_reference_label`.
- AI-reference metrics must name their source: `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`, `agreement_vs_ai_reference`, `ai_reference_standard`, `ai_cross_checked`.
- `independent_blinding` means human blinding and remains false. AI blinding uses `independent_blinding_ai`.
- `release_ready` remains false. Do not deploy from this workflow.
- Current v4.0 screening is partial: 300/5,724 rows. Do not claim completion or performance.
- Do not delete `tools/search_pipeline/embase_adapter.py`.
- Keep 신신파스아렉스 source records but exclude it from analysis and runtime.
- Released rules require both source and locator. The 32 administration constraints and 15 released rules are different states.
- The systematic search pipeline is Python-based and separate from the Next.js runtime. Its code is in `tools/search_pipeline/` and its preserved outputs are in `data/systematic_search/`.
- Treat `data/knowledge_pack.json` and prior nutrient search outputs as superseded exploratory material only.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build` after site changes. Do not deploy.
