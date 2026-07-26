# v4.0 Full-AI Literature Layer Implementation Plan

> **For agentic workers:** Execute inline in the P0–P5 order from the goal objective. Do not dispatch subagents, pause for review, or reorder the blind-evaluation gates.

**Goal:** Add a fully AI-generated PubMed evidence layer and an honestly labeled AI-reference evaluation to the existing authorization-grounded OTC safety engine, then regenerate and synchronize every required research deliverable.

**Architecture:** Keep the MFDS authorization layer deterministic and authoritative. Build a separate PubMed evidence pipeline under `research_v3/otc/literature/`, connect retained sentence-level evidence to rules without changing rule decisions, and isolate unlabeled case generation from blind AI scoring and engine prediction linkage. Generate all reported counts and metrics from source files and hashes.

**Tech Stack:** Python 3.14, NCBI E-utilities XML, CSV/JSON/JSONL, pytest, Next.js 16, TypeScript, Vitest, python-docx, LibreOffice PDF conversion, Git.

---

### Task 1: Freeze v3 and adopt the v4.0 protocol

**Files:**
- Create: `research_v3/audit/v40_freeze_manifest.json`
- Create: `research_v3/protocol/protocol-v4.0-full-ai.md`
- Create: `research_v3/protocol/amendments.csv`
- Create: `research_v3/logs/TIME_BUDGET.md`
- Create: `tools/build_v40_freeze_manifest.py`
- Modify: `research_v3/DECISIONS.md`

- [ ] Preserve `research_v3/approvals/` and `research_v3/human_review_minimal/` in a standalone commit.
- [ ] Create the annotated `v3-otc-frozen` tag at that commit.
- [ ] Run `python -X utf8 tools/build_v40_freeze_manifest.py` and verify every manifest hash against the tagged blob.
- [ ] Record AM-OTC-001 without claiming direct supervisor approval for this repository.
- [ ] Commit the v4.0 protocol and freeze audit.

### Task 2: Derive PICOS and retrieve the PubMed corpus

**Files:**
- Create: `tools/v40_literature_pipeline.py`
- Create: `tests/research/test_v40_literature_pipeline.py`
- Create: `research_v3/otc/literature/picos/picos_definition.json`
- Create: `research_v3/otc/literature/search_log.csv`
- Create: `research_v3/otc/literature/evidence_map.csv`
- Create: `research_v3/otc/literature/searches/<question_id>/<run_id>/query.txt`
- Create: `research_v3/otc/literature/searches/<question_id>/<run_id>/efetch_*.xml`
- Create: `research_v3/otc/literature/searches/<question_id>/<run_id>/checksum.sha256`
- Create: `research_v3/otc/literature/searches/<question_id>/<run_id>/response_metadata.json`

- [ ] Build three to six grouped ingredient-hazard questions from the 28 authorization-derived ingredients and 16 rule scopes without reading the legacy K1–K5 queries.
- [ ] Freeze the PICOS prompt text and SHA-256 in `picos_definition.json`.
- [ ] Test query encoding, ESearch count parsing, EFetch pagination, PubMed XML normalization, duplicate PMID handling, and input-hash stability.
- [ ] Run ESearch before EFetch, apply the required 10,000 → 7,000 → 5,000 total-row reduction ladder when the clock requires it, and enforce at most three NCBI requests per second.
- [ ] Verify that raw XML hashes and normalized rows reproduce exactly from the recorded run metadata.
- [ ] Commit P1.

### Task 3: Classify every retrieved literature row

**Files:**
- Create: `research_v3/otc/literature/prompts/screening_prompt.md`
- Create: `research_v3/otc/literature/prompts/screening_prompt.sha256`
- Create: `research_v3/otc/literature/screening/checkpoints/*.jsonl`
- Create: `research_v3/otc/literature/screening/screening_results.csv`
- Create: `research_v3/otc/literature/screening/screening_manifest.json`

- [ ] Fix the exact `retain`, `deprioritize`, and `uncertain` prompt before any classification.
- [ ] Classify batches of 100 rows locally; mark missing abstracts as `title_only` with confidence no higher than `low`.
- [ ] Append immutable checkpoint rows with batch IDs and hashes.
- [ ] After each five batches, compare requested and returned record IDs; reclassify only missing IDs.
- [ ] Require every corpus row exactly once before writing `coverage=1.0` and `run_complete=true`.
- [ ] Commit every ten completed batches and make the final P2 commit after the coverage audit.

### Task 4: Measure the classifier against an AI reference

**Files:**
- Create: `tools/measure_v40_ai_reference.py`
- Create: `tests/research/test_measure_v40_ai_reference.py`
- Create: `research_v3/measurement/ai_reference_checkpoints/*.jsonl`
- Create: `research_v3/measurement/screener_vs_ai_reference.json`

- [ ] Draw a seeded stratified sample from P2 labels and record frame sizes, weights, seed, and sample hash.
- [ ] Score only blinded PICOS fields with a prompt that differs from P2; perform three independent judgments and retain three-way disagreements as unresolved.
- [ ] Test stratified weighting, Wilson intervals, Rogan–Gladen correction bounds, and stratified bootstrap resampling.
- [ ] Report `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`, round agreement, corrected corpus retain count, 95% interval, and up to 20 actual false-positive and false-negative titles.

### Task 5: Generate and score blind engine cases

**Files:**
- Create: `tools/build_v40_independent_eval.py`
- Create: `tests/research/test_v40_independent_eval.py`
- Create: `research_v3/otc/validation/ai_independent_cases/*.json`
- Create: `research_v3/otc/validation/ai_independent_evaluation.json`

- [ ] Generate at least 200 unlabeled cases from the actual 13-product composition and 16-rule scope, with at least 10 cases per rule type and both alert and non-alert conditions.
- [ ] Ensure case files contain no expected label, engine result, Codex answer, or legacy human label.
- [ ] Randomize with a recorded seed and perform three independent blind AI judgments.
- [ ] Lock the AI labels and their hash before running the deterministic engine.
- [ ] Join engine predictions only after the lock, then compute AI-reference sensitivity, specificity, precision, F1, Wilson intervals, critical false negatives, rule-type breakdowns, and up to 20 failures.
- [ ] Re-evaluate the legacy 13 cases through the same blind path without reading `human_reference_label` and report agreement with the prior nonblind output separately.
- [ ] Commit P3 evaluation artifacts.

### Task 6: Apply the completion gate

**Files:**
- Modify: `research_v3/project_identity.json`
- Modify: `research_v3/otc/audit/completion_audit.json`
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md`
- Modify: `research_v3/otc/metrics_manifest.json`
- Modify: `research_v3/metrics_manifest.json`
- Modify: `research_v3/DECISIONS.md`

- [ ] Count released rules directly from `rules.csv`; correct `released_rule_count` only from that computed value.
- [ ] Set `independent_blinding_ai`, `independent_evaluation_ai_complete`, `performance_claim_allowed`, and `complete` true only if all P3 artifacts pass schema, coverage, blinding-order, and metric audits.
- [ ] Keep `independent_blinding=false` and `release_ready=false`.
- [ ] Store the evidence path beside every state flag and replace the former mandatory human blind review with “AI 평가로 대체됨(AM-OTC-001)”.

### Task 7: Connect literature evidence and expose it in the site

**Files:**
- Modify: `research_v3/otc/rules/supporting_literature.csv`
- Create: `research_v3/otc/rules/literature_link_manifest.json`
- Modify: `scripts/build-literature-candidates.ts`
- Modify: `src/types/knowledge.ts`
- Modify: `src/components/rule-card.tsx`
- Test: `src/components/rule-card.test.tsx` or the repository’s nearest existing rule-card test

- [ ] Link retained PubMed evidence to all supported rule types with PMID and exact abstract-sentence locators.
- [ ] Keep authorization and literature sources in separate fields; preserve conflicts explicitly and never change released decision logic because of literature.
- [ ] Add the evidence fields to the generated runtime index and test schema rejection for missing or conflated provenance.
- [ ] Render authorization evidence as the decision source and PubMed evidence as clearly labeled reference literature.
- [ ] Run `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, and the research integrity audit; do not deploy.
- [ ] Commit P4.

### Task 8: Regenerate research documents and synchronize deliverables

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/project_map.md`
- Create: `research_v3/reports/발표원고_v4.0.md`
- Create: `research_v3/reports/notion_update.md`
- Create/modify: the canonical v4.0 thesis DOCX and PDF through the existing thesis pipeline or a deterministic `python-docx` generator
- Create: `research_v3/logs/v40_run_report.json`

- [ ] Read every thesis number from the final manifests; state the two-layer method, AI-only decision count, AI-reference naming, lineage separation, and limitations.
- [ ] Use the document and PDF skills, static Pretendard families, rendered-page inspection, and DOCX/PDF content checks.
- [ ] Back up the existing G: thesis DOCX/PDF with the `_v3백업` suffix before replacing canonical filenames.
- [ ] Write the presentation script and paste-ready Notion draft; update the Notion page only if authenticated access is available.
- [ ] Synchronize the required artifact list to the exact G: folders and record every copied file.
- [ ] Populate every final-report field from manifests; use `null` and an explicit unresolved reason where evidence is unavailable.
- [ ] Commit P5 and run final verification without deployment.
