<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Which version is final

`docs/version_map.md` is the answer sheet. The one thing to remember: **this study ends at
v5.0, 여형준's supplement study (`nutrition-safety-engine`) ends at v4.0.** This repo also
contains a `research_v3/logs/v40_run_report.json`, which is a *superseded* track here — do
not read numbers across the two repos by filename.

## Project navigation

Before exploring the repo from scratch, check `docs/project_map.md`.

- Main page: `app/page.tsx`
- Main client UI: `src/components/rule-explorer-client.tsx`
- OTC checker UI: `src/components/otc-product-safety-client.tsx`
- Result card UI: `src/components/rule-card.tsx`
- Safety engine: `src/lib/safety-engine/index.ts`
- OTC rule engine: `src/lib/otc/engine.ts`
- Knowledge loader/normalizer: `src/lib/knowledge/`
- Primary legacy data source: `data/knowledge_pack.json`
- Runtime index: `src/generated/knowledge-index.json`
- Project map: `docs/project_map.md`

## v4.0 research boundary

- The active question is Korean OTC product-name safety lookup.
- MFDS authorization records are the deterministic authority for product, ingredient, amount, administration constraints, and rule decisions.
- PubMed is a separate AI-selected literature layer. It supports evidence claims but cannot override authorization facts or released rule logic.
- The literature layer covers 9 of the 16 rules with 10 links. The other 7 rules
  (`OTC-RULE-003` max_daily_dose, `009` gi_bleeding_ulcer, `010` sedation_driving,
  `011` alcohol, `013` sedative_medication, `015` maximum_duration, `016` urgent_referral)
  have no linked literature for two reasons recorded in
  `research_v3/otc/literature/v5/downstream/literature_link_manifest.json`:
  6 candidate rejections (5 distinct papers) are `not_in_v5_corpus` — the AM-OTC-002
  query, which dropped the outcome block and kept only P AND I, did not retrieve them;
  4 are `no_retain_decision_for_rule_question` — the paper is in the corpus but was not
  retained for a question the rule is allowed to draw from (the two `015` papers are
  retained for Q01 while the rule allows only Q03/Q04).
  **This is not a search-window gap.** The executed date filters are 2010/01/01 for
  Q01–Q03 and 2000/01/01 for Q04–Q05 (embedded in the hashed query strings), the v5.0
  corpus spans publication years 2000–2026, and all 9 unlinked candidates fall inside
  their rule's allowed-question window. AM-OTC-003 stated a 2022-01-01 window as the
  cause; `AM-OTC-004` corrects that. Report the gap as a result; do not describe the
  literature layer as the study's contribution.
- Keep authorization evidence and literature evidence in separate fields. Preserve conflicts as `conflict`.
- Every rule-to-literature link needs a sentence-level locator (`abstract:sentence:N`) plus the quoted sentence. `scripts/research/otc/build_supporting_literature.py` re-checks the quote against the corpus abstract on every build.
- New literature artifacts belong only under `research_v3/otc/literature/`. Do not modify `research_v3/search/provisional_pubmed_20260710/`.
- Human judgment files are preserved legacy inputs and must not enter the v4.0 chain: `research_v3/screening/`, `research_v3/human_review_minimal/`, expert review artifacts, and `human_reference_label`.
- AI-reference metrics must name their source: `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`, `agreement_vs_ai_reference`, `ai_reference_standard`, `ai_cross_checked`. Never write a bare "민감도".
- `independent_blinding` means human blinding and remains false. AI blinding uses
  `independent_blinding_ai`, and its value is **per layer, not global**. v4.0 literature
  screening: true, evidenced by `research_v3/otc/validation/ai_independent_evaluation.json`.
  The v5.0 semantic adjudication selection: **false** — it was recorded true with no
  execution receipt and was corrected by `V50-PC-001` (see `research_v3/logs/DECISIONS_v50.md`).
  Do not restate this flag as globally true; cite the layer.
- `release_ready` remains false; deployment is not clinical release approval. Deploy only
  when the researcher explicitly asks. The site was deployed on 2026-07-30 on that
  instruction (https://otc-nutrient-safety-engine.vercel.app); an earlier blanket
  "do not deploy" rule no longer matches practice and was replaced by `AM-OTC-004`.
- v4.0 screening is complete: 5,724/5,724 rows, coverage 1.0, human decisions 0. Performance may be cited only alongside the fact that the reference standard is an AI evaluator.
- Do not delete `tools/search_pipeline/embase_adapter.py`.
- Keep 신신파스아렉스 source records but exclude it from analysis and runtime.
- Released rules require both source and locator. The 32 administration constraints and 15 released rules are different states.
- The systematic search pipeline is Python-based and separate from the Next.js runtime. Its code is in `tools/search_pipeline/` and its preserved outputs are in `data/systematic_search/`.
- Treat `data/knowledge_pack.json` and prior nutrient search outputs as superseded exploratory material only.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build` after site changes. Deploy only on an explicit request from the researcher.
