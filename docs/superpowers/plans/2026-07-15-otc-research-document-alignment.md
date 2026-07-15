# OTC Research and Document Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the analysis dataset, website runtime, thesis, protocol, reports, and audits use one explicit 13-product, 28-ingredient, 47-binding scope while preserving Shinshin Arex source records as an excluded candidate and preserving the non-blinded evaluation boundary.

**Architecture:** Keep the 16-candidate authorization master intact, add an explicit analysis inclusion contract, and derive site-facing metrics from calculation-selected rows instead of broad variant rows. Generate and audit human-readable documents from authoritative manifests, then rebuild the canonical DOCX/PDF files with a formal academic layout and full visual QA.

**Tech Stack:** Python 3, CSV/JSON, pytest, python-docx, LibreOffice, Poppler, TypeScript/Next.js, Vitest, Vercel CLI.

---

### Task 1: Make the analysis scope explicit

**Files:**
- Modify: `scripts/research/otc/build_nedrug_masters.py`
- Modify: `scripts/research/otc/build_runtime.py`
- Modify: `tests/research/test_build_nedrug_masters.py`
- Modify: `tests/research/test_build_otc_runtime.py`
- Generate: `research_v3/otc/normalized/product_master.csv`
- Generate: `research_v3/otc/normalized/analysis_exclusions.csv`
- Generate: `research_v3/otc/normalized/product_ingredient.csv`
- Generate: `src/generated/otc-runtime.json`

- [ ] **Step 1: Add failing tests for the analysis contract**

Assert that `SAFE-OTC-13` remains in the authorization master with `analysis_status=excluded`, appears in `analysis_exclusions.csv`, and is absent from both runtime products and runtime official candidates.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_build_nedrug_masters.py tests/research/test_build_otc_runtime.py -q`

Expected: failure because the analysis fields and exclusion file do not exist yet.

- [ ] **Step 3: Implement the smallest shared fix**

Add `analysis_status` and `analysis_exclusion_reason` to every product master row. Keep the source records and 49 product-ingredient-variant rows for Shinshin Arex, but mark it excluded because one package count maps to more than one authorized size. Generate a one-row exclusion log and skip analysis-excluded products before runtime unresolved-candidate output.

- [ ] **Step 4: Regenerate data and rerun the tests**

Run:

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/build_nedrug_masters.py
.venv-research\Scripts\python.exe scripts/research/otc/build_runtime.py
.venv-research\Scripts\python.exe -m pytest tests/research/test_build_nedrug_masters.py tests/research/test_build_otc_runtime.py -q
```

Expected: 16 candidate rows, 14 source-verified products, 13 analysis products, one explicit exclusion, 13 runtime products, and no Shinshin Arex runtime entry.

### Task 2: Audit site and research data alignment

**Files:**
- Create: `scripts/research/otc/audit_runtime_alignment.py`
- Create: `tests/research/test_otc_runtime_alignment.py`
- Generate: `research_v3/otc/audit/runtime_research_alignment.json`
- Modify: `scripts/research/otc/build_metrics.py`
- Modify: `tests/research/test_otc_metrics.py`

- [ ] **Step 1: Write the failing alignment test**

The audit must verify 13 runtime products, 28 unique runtime ingredients, 47 runtime product-ingredient bindings, exact product/ingredient identity, amount/unit agreement after the two declared liquid conversions, complete source/locator fields, 32 verified administration constraints, and zero excluded-product leaks.

- [ ] **Step 2: Run the new test and confirm failure**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_otc_runtime_alignment.py -q`

Expected: failure because the audit module is absent.

- [ ] **Step 3: Implement the audit and scope-aware metrics**

Keep broad master metrics under explicit names and add analysis metrics for 13 products, 28 ingredients, 47 selected bindings, 57 analysis product-ingredient-variant rows, and 32 administration constraints. Preserve `release_ready=false`, `independent_blinding=false`, and `performance_claim_allowed=false`.

- [ ] **Step 4: Generate the audit and metrics**

Run:

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/audit_runtime_alignment.py
.venv-research\Scripts\python.exe scripts/research/otc/build_metrics.py
.venv-research\Scripts\python.exe -m pytest tests/research/test_otc_runtime_alignment.py tests/research/test_otc_metrics.py -q
```

Expected: alignment audit `valid=true` and focused tests pass.

### Task 3: Synchronize the research narrative

**Files:**
- Modify: `research_v3/thesis/otc_thesis_working.md`
- Modify: `research_v3/protocol/otc_research_plan_working.md`
- Modify: `research_v3/reports/FINAL_RESEARCH_REPORT.md`
- Modify: `research_v3/reports/GATE_0_10_REPORT.md`
- Modify: `research_v3/DECISIONS.md`
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md`
- Modify: `research_v3/otc/data_dictionary.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Rewrite the thesis in final reading order**

Use `국문초록 → Abstract → 서론 → 연구방법 → 연구결과 → 고찰 → 결론 → 참고문헌 → 부록`. Distinguish the 16-candidate master from the 13-product analysis set, explain the Shinshin Arex exclusion, describe the 32 source-verified administration constraints, and report the 13-case non-blinded confirmation without treating it as independent performance evidence.

- [ ] **Step 2: Update the protocol and decision record**

Record the post-protocol deviations: scope refinement to calculation-ready products, explicit exclusion of Shinshin Arex, new per-product administration constraints, and the non-blinded external confirmation. Do not rewrite history or claim retrospective approval for the new constraints.

- [ ] **Step 3: Update reports and data dictionary**

Use `product-ingredient-variant row` for 106 broad rows and `runtime product-ingredient binding` for 47 site rows. Remove stale 97-test, released-0, missing-label, preview-pending, and Shinshin-resolution language.

- [ ] **Step 4: Add consistency tests or audit checks**

Assert that the thesis, report, protocol, and metrics carry the analysis counts and the non-blinded claim boundary, while `complete` and `release_ready` remain false.

### Task 4: Rebuild canonical DOCX and PDF artifacts

**Files:**
- Modify: `scripts/research/otc/build_thesis_docx.py`
- Modify: `research_v3/thesis/권혁찬_졸업논문_최종본.docx`
- Modify: `research_v3/thesis/권혁찬_졸업논문_최종본.pdf`
- Modify: `research_v3/protocol/권혁찬_OTC_연구계획서_최종본.docx`
- Modify: `research_v3/protocol/권혁찬_OTC_연구계획서_최종본.pdf`
- Create: `research_v3/otc/etc/document_backups/20260715_research_alignment/`

- [ ] **Step 1: Back up current canonical artifacts**

Copy the four current canonical files into the dated repository backup folder before overwriting them.

- [ ] **Step 2: Upgrade the DOCX builder**

Use static Pretendard families, formal academic cover metadata, real heading styles, page numbering, explicit table geometry, table headers, captions, clean references, and restrained navy accents. Remove all working-draft and non-canonical cover text while keeping the research limitation in the body.

- [ ] **Step 3: Generate DOCX and PDF files**

Use the bundled Python runtime for python-docx and `scripts/research/otc/render_docx_windows.py` with `soffice.com` for PDF conversion.

- [ ] **Step 4: Render every PDF page and inspect at 100%**

Render all pages to PNG under `research_v3/otc/etc/document_qa/20260715_research_alignment/`. Inspect every page for clipping, overflow, font substitution, table breaks, page numbering, references, and researcher identity. Iterate until no visual defect remains.

- [ ] **Step 5: Run structural and accessibility audits**

Check heading order, table header flags, metadata, embedded font names, cross-student contamination, placeholder text, and stale working-copy language.

### Task 5: Recalculate all validation evidence

**Files:**
- Regenerate: `research_v3/otc/audit/software_validation.json`
- Regenerate: `research_v3/otc/metrics_manifest.json`
- Regenerate: `research_v3/metrics_manifest.json`
- Regenerate: `research_v3/otc/audit/completion_audit.json`
- Regenerate: `research_v3/otc/audit/claim_consistency.json`

- [ ] **Step 1: Run the full research suite**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research -q`

- [ ] **Step 2: Run app tests and static checks**

Run:

```powershell
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

- [ ] **Step 3: Capture validation and regenerate audits**

Record fresh test counts and build paths, rebuild metrics, rerun completion and identity audits, and verify that the only incomplete completion requirement remains `independent_evaluation_complete`.

### Task 6: Publish the verified update

**Files:**
- Update only the task-related files in Git.
- Synchronize the four canonical document files to the established G-drive final folders after making a dated backup.

- [ ] **Step 1: Review the exact Git diff**

Exclude unrelated pre-existing dirty files from staging. Confirm that no human review status was fabricated and no superseded nutrient metrics were reintroduced.

- [ ] **Step 2: Commit and push the intended files**

Commit the data-contract, audit, document, and generated-artifact changes together with a precise message, then push `main` to `origin/main`.

- [ ] **Step 3: Deploy production to Vercel**

Run: `vercel deploy . --prod -y`

Expected: a successful production deployment URL for `https://otc-nutrient-safety-engine.vercel.app`.

- [ ] **Step 4: Report the remaining human-only requirement**

State that the documents and software are synchronized, but the research is still not complete because a prediction-blinded independent evaluation has not been performed.
