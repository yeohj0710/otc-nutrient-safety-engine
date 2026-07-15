# Korean OTC Safety Research Reorientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active nutrient-centered research direction with an evidence-traceable Korean OTC product safety system while preserving all prior work as superseded lineage.

**Architecture:** Keep `research_v3` as the research lineage, mark its nutrient artifacts as superseded, and add an `otc` domain with source snapshots, normalized product/ingredient tables, evidence-bound rules, development and independent scenarios, and generated metrics. The Next.js app reads generated OTC runtime data and applies deterministic TypeScript rules; documents and reports read the same metrics manifest.

**Tech Stack:** Python 3 (collection, normalization, research validation), TypeScript/Next.js 16 (product search and rule engine), Vitest/pytest (tests), CSV/JSON (traceable data), python-docx/LibreOffice (DOCX/PDF and visual QA).

---

### Task 1: Freeze the direction decision and lineage boundary

**Files:**
- Modify: `research_v3/DECISIONS.md`
- Modify: `research_v3/README.md`
- Modify: `research_v3/project_identity.json`
- Create: `research_v3/reports/DIRECTION_MISMATCH_REPORT.md`

- [ ] Record the latest user decision as controlling, the June 18 nutrient plan as contradictory evidence, and `release_ready=false` as invariant.
- [ ] Set `research_direction` to `korean_otc_product_safety`, `direction_status` to `active`, and the prior direction to `superseded` with its reason.
- [ ] Run `python -m json.tool research_v3/project_identity.json`; expect exit code 0.
- [ ] Run `rg -n "superseded|korean_otc_product_safety|release_ready=false" research_v3/DECISIONS.md research_v3/README.md research_v3/project_identity.json research_v3/reports/DIRECTION_MISMATCH_REPORT.md`; expect all four files represented.

### Task 2: Define normalized OTC data contracts

**Files:**
- Create: `research_v3/otc/schema/product.schema.json`
- Create: `research_v3/otc/schema/ingredient.schema.json`
- Create: `research_v3/otc/schema/product_ingredient.schema.json`
- Create: `research_v3/otc/schema/source.schema.json`
- Create: `research_v3/otc/schema/rule.schema.json`
- Create: `research_v3/otc/data_dictionary.md`
- Create: `tests/research/test_otc_schema.py`

- [ ] Write failing tests asserting required product, ingredient, join, source, and rule fields from the objective.
- [ ] Run `pytest tests/research/test_otc_schema.py -q`; expect failure because schemas do not exist.
- [ ] Add JSON Schemas with stable IDs, enums for OTC status and rule status, dose units, source IDs, locators, retrieval dates, hashes, and provenance status.
- [ ] Run the focused test; expect pass.

### Task 3: Implement official-source acquisition and immutable snapshots

**Files:**
- Create: `scripts/research/otc/fetch_mfds_products.py`
- Create: `scripts/research/otc/hash_snapshot.py`
- Create: `research_v3/otc/sources/source_registry.json`
- Create: `tests/research/test_fetch_mfds_products.py`

- [ ] Test URL construction, pagination, retry-safe errors, raw response preservation, retrieval timestamp, and SHA-256 generation using fixtures.
- [ ] Run the focused test and confirm failure before implementation.
- [ ] Implement API-key-from-environment acquisition with no credential persistence and an offline fixture mode.
- [ ] Run the focused test and confirm pass.

### Task 4: Normalize products and compound ingredients

**Files:**
- Create: `scripts/research/otc/normalize_products.py`
- Create: `research_v3/otc/normalization/ingredient_aliases.csv`
- Create: `tests/research/test_normalize_otc_products.py`

- [ ] Test OTC filtering, withdrawn-product exclusion, ingredient row splitting, units, Korean aliases, product-to-many-ingredients joins, source locators, and rejected-row reporting.
- [ ] Run the focused test and confirm failure.
- [ ] Implement deterministic normalization and write products, ingredients, product-ingredient joins, and rejection reports.
- [ ] Run the focused test and confirm pass.

### Task 5: Establish a defensible representative-OTC scope

**Files:**
- Create: `research_v3/otc/selection/selection_protocol.md`
- Create: `research_v3/otc/selection/source_evidence.csv`
- Create: `research_v3/otc/selection/included_classes.csv`
- Create: `scripts/research/otc/validate_selection.py`
- Create: `tests/research/test_otc_selection.py`

- [ ] Encode criteria combining Korean authorization, official utilization/production/supply evidence, class representativeness, and data completeness without claiming an unsupported sales ranking.
- [ ] Test that every included class has at least one authoritative source and an explicit rationale.
- [ ] Validate the focused first-wave classes: analgesic/antipyretic and NSAID, multi-symptom cold, antihistamine, cough/expectorant/decongestant, and gastrointestinal OTC.
- [ ] Run the selection validator and focused tests; expect pass.

### Task 6: Build evidence-bound deterministic rules

**Files:**
- Create: `research_v3/otc/rules/rules.csv`
- Create: `scripts/research/otc/validate_rules.py`
- Create: `tests/research/test_otc_rules.py`
- Create: `src/lib/otc/schema.ts`
- Create: `src/lib/otc/engine.ts`
- Create: `__tests__/otc-engine.test.ts`

- [ ] Test that released rules require a retrievable source and concrete locator; rules without either remain draft.
- [ ] Test duplicate ingredient, same NSAID class, daily maximum, minimum interval, age, pregnancy/lactation, liver/kidney/GI bleeding, sedation/driving, alcohol, anticoagulant, decongestant/hypertension, duration, and urgent-referral rule shapes.
- [ ] Implement deterministic evaluation and structured totals; AI receives results only for plain-language summarization.
- [ ] Run Python and Vitest focused tests; expect pass.

### Task 7: Build product-name-first application flow

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/globals.css`
- Create: `src/components/otc-product-safety-client.tsx`
- Create: `src/components/otc-product-safety.module.css`
- Create: `src/generated/otc-runtime.json`
- Create: `scripts/research/otc/build_runtime.py`
- Create: `__tests__/otc-product-flow.test.tsx`

- [ ] Test that no results appear before search, product selection loads ingredients and default directions, co-medications are additive, and unsupported products produce a non-diagnostic message.
- [ ] Implement search, selected-product list, minimal age/condition/medication inputs, prioritized results, calculated totals, source links, and urgent-action language.
- [ ] Apply the required Toss Korean UI reference tokens and static/variable Pretendard rules appropriate to web output.
- [ ] Run the component tests and verify 390 px overflow, keyboard focus, contrast, loading, error, and empty states in a real browser.

### Task 8: Separate development and independent evaluation

**Files:**
- Create: `research_v3/otc/validation/development_scenarios.csv`
- Create: `research_v3/otc/validation/independent_scenarios.csv`
- Create: `scripts/research/otc/evaluate.py`
- Create: `tests/research/test_otc_evaluation.py`

- [ ] Add the 13 required scenario families with disjoint IDs and provenance fields.
- [ ] Test confusion-matrix counts, sensitivity, specificity, PPV, NPV, accuracy, Wilson 95% intervals, critical false negatives, product search success, ingredient normalization accuracy, and source/locator rate.
- [ ] Keep expert/human labels distinct from Codex predictions and refuse performance claims when independent labels are absent.
- [ ] Run the evaluation tests and report; expect pass without fabricated human review.

### Task 9: Generate one authoritative metrics manifest

**Files:**
- Modify: `scripts/research/build_research_v3_metrics.py`
- Modify: `research_v3/metrics_manifest.json`
- Create: `tests/research/test_otc_metrics.py`

- [ ] Test that nutrient counts cannot enter active OTC metrics and that product, ingredient, rule, evidence, evaluation, software, document, and deployment metrics are derived from files.
- [ ] Generate the manifest with status fields for missing human review and `release_ready=false`.
- [ ] Run consistency tests against README, reports, site data, and document inputs.

### Task 10: Rebuild the unified human review flow

**Files:**
- Create: `scripts/research/otc/build_review_wizard.py`
- Create: `research_v3/otc/review/OTC_통합검토.html`
- Create: `tests/research/test_otc_review_wizard.py`

- [ ] Test that candidate class selection, product normalization exceptions, draft rules, and independent labels are shown with evidence while no human field is pre-completed.
- [ ] Generate one offline HTML flow with import/export JSON, hashes, reviewer identity, timestamp, and explicit AI-versus-human status.
- [ ] Run the focused test and open the HTML locally for interaction verification.

### Task 11: Rewrite research plan, thesis, and reports from OTC results

**Files:**
- Create: `research_v3/thesis/otc_thesis_working.md`
- Modify: `scripts/research/build_research_v3_thesis_docx.py`
- Modify: `research_v3/reports/FINAL_RESEARCH_REPORT.md`
- Modify: `research_v3/reports/GATE_0_10_REPORT.md`
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md`
- Create: `research_v3/protocol/otc_research_plan_working.md`

- [ ] Draft in methods, results, introduction, discussion, conclusion, Korean abstract, English abstract order using only active OTC manifest values.
- [ ] Generate working DOCX/PDF with installed static Pretendard family names and no canonical promotion.
- [ ] Inspect DOCX XML for `Pretendard`, render every page, inspect every PNG at 100%, and record page-level QA.
- [ ] Run claim, identity, metric, citation, and other-student contamination validators; expect pass or explicit blockers.

### Task 12: Full verification, preview, and delivery synchronization

**Files:**
- Modify: `scripts/research/verify_research_v3_package.py`
- Modify: `research_v3/REPRODUCE.md`
- Modify: `research_v3/reports/GATE_0_10_REPORT.md`

- [ ] Run research tests, app tests, lint, typecheck, and production build in `C:\dev\otc-nutrient-safety-engine`.
- [ ] Start the built app and verify the complete product search-to-result story in a real browser.
- [ ] Create a preview deployment only when its browser verification can be completed; do not touch production.
- [ ] Back up existing G-drive deliverables under `03_최종산출물/etc`, then synchronize working outputs and hashes without canonical promotion.
- [ ] Run the package verifier and leave `release_ready=false` until every gate is evidenced and the user explicitly authorizes release actions.
