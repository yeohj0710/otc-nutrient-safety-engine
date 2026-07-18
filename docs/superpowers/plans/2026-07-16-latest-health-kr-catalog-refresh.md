# Latest health.kr Catalog Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the OTC research candidate layer from the corrected 776-SKU catalog and 458 confirmed health.kr identities without promoting any record into the MFDS product master, released rules, or runtime safety set.

**Architecture:** Treat `data/portable/v1/products.json` as the corrected cross-project display/content contract and the canonical `data/enrichment-queue.json`/CSV as a local verification source for identifiers and safety fields that portable v1 does not expose. Join both sources by stable catalog `product_id`, validate their hashes and status agreement, then emit only minimal derived CSV/JSON fields. Match the 16 MFDS research products and 13 runtime products through ordered exact identifiers and strict identity evidence; preserve conflicts and unlinked rows instead of using fuzzy names.

**Tech Stack:** Python 3, CSV/JSON Schema, SHA-256 provenance, pytest, TypeScript/React, Vitest, Next.js 16.

---

### Task 1: Lock the latest catalog contract with failing tests

**Files:**
- Modify: `tests/research/test_catalog_candidate_bridge.py`
- Modify: `tests/research/test_health_kr_catalog.py`
- Modify: `__tests__/otc-product-flow.test.ts`

- [ ] Add fixtures containing corrected `name`, `capacity`, `specification`, `normalized_name`, `normalized_capacity` plus deliberately conflicting `app_*` values.
- [ ] Assert portable schema/manifest hashes, 776 unique IDs, four isolated statuses, and `official_content.schema_version=1.0` paragraph/table blocks.
- [ ] Assert matching and display never use `app_name`, `app_capacity`, prices, images, or private source IDs.
- [ ] Run the focused tests and confirm they fail against the old queue/public-copy and `products.json` assumptions.

### Task 2: Add portable and canonical queue adapters

**Files:**
- Modify: `scripts/research/otc/health_kr_catalog.py`
- Modify: `scripts/research/otc/import_health_kr_catalog.py`

- [ ] Add byte-snapshot readers for canonical queue JSON, canonical CSV, correction evidence, portable products, schema, and manifest.
- [ ] Validate manifest file hashes, schema version, product IDs/order, portable/queue status agreement, confirmed medicine identity/source, and normalized content blocks.
- [ ] Expose corrected display accessors and official identity precedence: `official_item_seq`, `official_product_key`, standard code/barcode, then exact official name+manufacturer+dosage form+pack unit.
- [ ] Reject `app_*` as a matching or display source and reject literal `br`, HTML fragments, replacement characters, and damaged ranges from derived text.

### Task 3: Refresh the candidate bridge without old catalog files

**Files:**
- Modify: `scripts/research/otc/catalog_candidate_bridge.py`
- Modify: `tests/research/test_catalog_candidate_bridge.py`
- Regenerate: `research_v3/otc/selection/catalog_existing_product_intersection.csv`
- Regenerate: `research_v3/otc/selection/catalog_fuzzy_match_review.csv`
- Regenerate: `research_v3/otc/selection/catalog_additional_otc_candidates.csv`
- Regenerate: `research_v3/otc/selection/catalog_candidate_summary.json`
- Regenerate: `research_v3/otc/audit/catalog_candidate_bridge.json`

- [ ] Replace `data/products.json`, `data/catalog.csv`, and old public queue inputs with portable v1 plus canonical queue/CSV/corrections/manifest inputs.
- [ ] Preserve exact-name screening as a review signal only; never promote by fuzzy name.
- [ ] Emit corrected name/specification fields and current status counts from the input rather than constants.
- [ ] Preserve minimal provenance and prove no raw record, price, image, or `app_*` field is exported.

### Task 4: Normalize 458 confirmed identities and rematch existing research products

**Files:**
- Modify: `scripts/research/otc/import_health_kr_catalog.py`
- Modify: `tests/research/test_health_kr_catalog.py`
- Create: `research_v3/otc/selection/catalog_health_kr_existing_product_matches.csv`
- Create: `research_v3/otc/selection/catalog_health_kr_official_products.json`
- Regenerate: `research_v3/otc/selection/catalog_health_kr_status_index.csv`
- Regenerate: `research_v3/otc/selection/catalog_health_kr_research_candidates.csv`
- Regenerate: `research_v3/otc/selection/catalog_health_kr_same_ingredient_groups.csv`
- Regenerate: `research_v3/otc/selection/catalog_health_kr_conflict_review.csv`
- Regenerate: `research_v3/otc/selection/catalog_health_kr_summary.json`
- Regenerate: `research_v3/otc/audit/catalog_health_kr_integration.json`

- [ ] Separate official-drug entities from retail SKUs and report both official-item and SKU duplicate counts.
- [ ] Normalize only needed official fields and block structures into a local JSON index; keep long source text out of CSV and the web bundle.
- [ ] Match all 16 product-master rows and the 13 runtime rows by ordered exact evidence and emit `matched`, `conflict`, or `unlinked` with reasons.
- [ ] Keep every candidate at `mfds_promotion_evidence_complete=false` and `runtime_promotion_allowed=false` unless the existing MFDS master independently supplies that evidence; do not add catalog products to the runtime.

### Task 5: Expose compact, non-promotional catalog status in the current UI

**Files:**
- Modify: `scripts/research/otc/build_runtime.py`
- Modify: `src/lib/otc/schema.ts`
- Modify: `src/components/otc-product-safety-client.tsx`
- Modify: `src/components/otc-product-safety.module.css`
- Modify: `tests/research/test_build_otc_runtime.py`
- Modify: `__tests__/otc-product-flow.test.ts`
- Regenerate: `src/generated/otc-runtime.json`

- [ ] Update global coverage to 776/458 from the refreshed summary.
- [ ] For strictly matched existing runtime products only, expose corrected display name/form/specification, health.kr source URL, and explicit `research candidate / MFDS runtime separately verified` states.
- [ ] Put detailed source/status text in the existing collapsed product-information area so labels do not expand the main layout.
- [ ] Prove no price, image, private source ID, raw official content, or unconfirmed product is present in the web bundle.

### Task 6: Refresh research documentation and metrics without changing performance claims

**Files:**
- Modify: `research_v3/REPRODUCE.md`
- Modify: `research_v3/DECISIONS.md`
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md`
- Modify: `research_v3/otc/data_dictionary.md`
- Modify: `research_v3/reports/FINAL_RESEARCH_REPORT.md`
- Modify: `research_v3/thesis/otc_thesis_working.md`
- Modify: `scripts/research/otc/build_metrics.py`
- Regenerate: `research_v3/metrics_manifest.json`
- Regenerate: `research_v3/otc/metrics_manifest.json`

- [ ] Replace obsolete hashes and 369/82/137/188 counts with values calculated from the current source.
- [ ] Report 458 confirmed as health.kr-linked research candidates, never MFDS-authorized runtime products.
- [ ] Preserve `complete=false`, `release_ready=false`, `independent_blinding=false`, and `performance_claim_allowed=false`.
- [ ] Record missingness, rematch outcomes, conflicts, and the portable/canonical source roles.

### Task 7: Run fresh end-to-end validation

**Files:**
- Modify only generated audit/metrics outputs produced by the documented commands.

- [ ] Run focused pytest red/green tests for source contract, app_* exclusion, duplicate groups, strict matching, promotion gates, and web-bundle privacy.
- [ ] Regenerate both catalog outputs from one byte snapshot per source and verify every output SHA-256.
- [ ] Run all research pytest, app Vitest, lint, typecheck, production build, and runtime alignment.
- [ ] Report exact input/status/unique-official/rematch/promotion/missingness/conflict counts from generated JSON only.
- [ ] Do not commit, push, deploy, or mark the research complete.
