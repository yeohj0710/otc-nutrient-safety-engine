# Kwon PubMed Feasibility Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete an honest, reproducible PubMed-only single-reviewer evidence-map and software-feasibility thesis for Kwon without fabricating unavailable institutional searches, independent clinical review, or expert validation.

**Architecture:** Freeze a protocol amendment that lowers the claim level, retrieve every PubMed record for K1-K5 with segmented ESearch/EFetch and raw hashes, then run deterministic normalization, deduplication, screening assistance, verified extraction, evidence mapping, rule compilation, technical scenarios, metrics generation, and thesis production. Human-unavailable outcomes remain explicitly “not evaluated”; they are not replaced with synthetic approvals or expert labels.

**Tech Stack:** Python 3.12, NCBI E-utilities/EDirect-compatible HTTP, CSV/JSON/JSONL, existing Next.js/Vitest application, python-docx/Poppler for thesis rendering.

---

### Task 1: Freeze the scope-reduction amendment

**Files:**
- Create: `research_v2/protocol/amendment_001_pubmed_feasibility.md`
- Create: `research_v2/protocol/claim_boundary.json`
- Modify: `research_v2/DECISIONS.md`
- Modify: `research_v2/audit/gate_status.json`
- Test: `tests/research_v2/test_scope_reduction.py`

- [ ] Write a test requiring `study_design=pubmed_single_reviewer_feasibility`, prohibited systematic-review and clinical-validation claims, and explicit non-evaluated metrics.
- [ ] Run `.venv-research\Scripts\python.exe -m pytest tests\research_v2\test_scope_reduction.py -q`; expect failure before files exist.
- [ ] Add the amendment and machine-readable claim boundary.
- [ ] Re-run the test; expect pass.
- [ ] Commit with `git commit -m docs:freeze-pubmed-feasibility-scope`.

### Task 2: Retrieve complete PubMed result sets

**Files:**
- Create: `scripts/research/pubmed_full_retrieval.py`
- Create: `tests/research_v2/test_pubmed_full_retrieval.py`
- Create on execution: `research_v2/search/raw/pubmed/K1` through `K5`
- Create on execution: `research_v2/search/search_run_log.csv`

- [ ] Write tests for count reconciliation, date segmentation above 9,999 records, retry/backoff, XML page preservation, and SHA-256 manifests.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement count-only ESearch, year/date segmentation, paged UID retrieval, batched EFetch, raw response preservation, and fail-closed reconciliation.
- [ ] Run targeted tests and confirm pass.
- [ ] Execute all five frozen queries. Require `hit_count == exported_count == imported_count`; otherwise stop that node with a recorded error.
- [ ] Commit code and raw manifests without secret values.

### Task 3: Normalize, deduplicate, and create screening worklists

**Files:**
- Create: `scripts/research/build_screening_dataset.py`
- Create: `tests/research_v2/test_screening_dataset.py`
- Create on execution: `research_v2/search/normalized/records.csv`
- Create on execution: `research_v2/search/dedup_log.csv`
- Create on execution: `research_v2/screening/title_abstract.csv`

- [ ] Test PMID/DOI/title duplicate precedence, study-family grouping, K-node provenance, and no cross-family dev/held-out leakage.
- [ ] Implement deterministic normalization and exact/fuzzy duplicate proposals.
- [ ] Produce a single-reviewer worklist with no AI auto-exclusions.
- [ ] Screen all titles/abstracts using the frozen eligibility criteria; preserve uncertain items for full text.
- [ ] Generate PRISMA-like feasibility counts labeled as single-reviewer, not PRISMA-compliant systematic-review counts.

### Task 4: Verify full text, extract, appraise, and synthesize

**Files:**
- Populate: `research_v2/screening/full_text.csv`
- Populate: `research_v2/extraction/extraction.csv`
- Populate: `research_v2/extraction/source_quotes.csv`
- Populate: `research_v2/risk_of_bias/assessments.csv`
- Populate: `research_v2/synthesis/grade.csv`
- Create: `research_v2/synthesis/evidence_map.csv`
- Create: `research_v2/synthesis/focused_results.json`

- [ ] Retrieve legal open/full texts and record failed retrieval attempts without inventing decisions.
- [ ] Verify each included value against a page/section/table locator.
- [ ] Mark RoB and certainty as single-reviewer provisional assessments.
- [ ] Build all five evidence-map rows.
- [ ] Apply the prespecified focused-node score. If quantitative compatibility is absent, generate SWiM results instead of a meta-analysis.

### Task 5: Compile rules and run technical validation

**Files:**
- Populate: `research_v2/rules/rule_trace.csv`
- Create: `research_v2/rules/rules.jsonl`
- Create: `research_v2/validation/technical_scenarios.jsonl`
- Create: `research_v2/validation/technical_metrics.json`
- Modify: application runtime to consume only the new released feasibility ruleset.

- [ ] Create rules only from verified extraction rows and source quote IDs.
- [ ] Do not label a rule clinically validated; use `evidence_verified` or `content_reviewed_single_reviewer` status unless schema changes explicitly allow the feasibility status.
- [ ] Generate technical boundary and regression scenarios from rule predicates, not expert gold.
- [ ] Report branch coverage, provenance completeness, deterministic repeatability, and critical technical regression count; do not report clinical sensitivity/specificity.
- [ ] Run Python, Node, TypeScript, and production build tests.

### Task 6: Freeze evidence and produce the reduced-claim thesis

**Files:**
- Create: `research_v2/audit/evidence_freeze.json`
- Create: `research_v2/thesis/metrics_manifest.json`
- Create: `research_v2/thesis/claim_ledger.csv`
- Create: `research_v2/thesis/thesis.docx`
- Create: `research_v2/thesis/thesis.pdf`
- Create: `research_v2/audit/final_gate_report.json`

- [ ] Change the freeze validator so it checks the claim boundary and requires unavailable clinical metrics to be absent rather than fabricated.
- [ ] Generate every numeric thesis claim from the manifest.
- [ ] Draft Methods→Results→Introduction→Discussion→Conclusion→Abstract after evidence freeze.
- [ ] State PubMed-only, single-reviewer, no independent expert validation, and no clinical performance estimate in the abstract, methods, discussion, and conclusion.
- [ ] Build DOCX/PDF using the audited Kwon layout contract, render every page, and fix clipping/tables/citations.
- [ ] Run the reduced-scope release validator and record both passed feasibility gates and intentionally non-applicable clinical gates.
- [ ] Commit the final reproducible release without pushing or deploying.

## Self-review

- Spec coverage: identity, complete PubMed retrieval, raw hashes, deduplication, screening, extraction, evidence map, focused synthesis, rules, software testing, metrics, thesis, and rendering are covered.
- Gaps are explicit: institutional databases, dual review, IRB-dependent recruitment, and expert clinical validation are not silently substituted.
- Placeholder scan: no implementation placeholder is permitted in released artifacts; unavailable results must use structured `not_evaluated` fields.
- Type consistency: K1-K5 and the current `research_v2` schemas remain the only active identities.
