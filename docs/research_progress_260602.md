# 260602 Research Progress

## Context

This repo is the separated implementation and research workspace for Kwon Hyukchan's ingredient-centered OTC nutrient safety project. The parent lab workspace contains the broader nutrition safety system work, but this branch of the research should remain focused on high-dose OTC/dietary-supplement nutrient preparations rather than patient-group-first questions.

The current Notion plan already defines three first-pass targets:

- vitamin D/calcium: hypercalcemia, hypercalciuria, nephrolithiasis, toxicity
- vitamin B6/B-complex: neuropathy and neurotoxicity
- iron/magnesium/calcium/zinc: gastrointestinal adverse effects and absorption/drug interactions

## What changed today

- Synced the GitHub repository to `C:\dev\otc-nutrient-safety-engine`.
- Added `data/systematic_search/safety_rule_seed_260602.csv` as a first safety-rule seed table.
- Added `data/systematic_search/screening_priority_260602.csv` as an agent-generated triage table for the 148 retrieved PubMed records.
- Added this progress note to connect the Notion research plan, existing search results, and next screening work.

## Safety Rule Seeds

The first rule seeds should not be treated as final medical recommendations. They are structured placeholders for the deterministic rule engine and should be checked against product labels, public monographs, and included studies before becoming final rules.

High-priority rule candidates:

- Vitamin D: flag adult self-supplementation above 100 mcg/day or 4,000 IU/day; map to hypercalcemia, hypercalciuria, kidney stones, and severe toxicity outcomes.
- Calcium: separate total calcium from supplemental calcium; flag high supplemental calcium especially with kidney stone history, high vitamin D intake, or renal risk.
- Vitamin B6: use a dual threshold, with EFSA 2023's 12 mg/day adult UL as an early caution and the US FNB 100 mg/day adult UL as a stronger alert.
- Magnesium: use supplemental elemental magnesium only for the 350 mg/day adult UL; upgrade severity with renal impairment or laxative/antacid use.
- Iron: flag self-directed intake at or above 45 mg/day unless clearly therapeutic; include GI adverse effects and levothyroxine/mineral spacing rules.
- Zinc: flag intake above 40 mg/day and chronic high-dose use; include copper deficiency and antibiotic/penicillamine spacing rules.

Medium-priority rule candidates:

- Vitamin A: track preformed retinol separately from beta-carotene; flag adult intake above 3,000 mcg RAE/day, especially in pregnancy/liver-risk contexts.
- Vitamin E: flag high-dose vitamin E, especially with anticoagulant or antiplatelet use.
- Vitamin K: treat as an interaction/stability rule for warfarin-like anticoagulants rather than a direct toxicity rule.

## Screening Implication

The first PubMed retrieval saved 148 records and marked 132 as `include_candidate`, but the automated screen is intentionally broad. Several records are likely off-scope because they are animal studies, postoperative supplementation, disease epidemiology, or therapeutic settings that do not represent OTC high-dose nutrient self-use.

`screening_priority_260602.csv` should be used before manual full-text review:

- `manual_review_high`: likely most useful for evidence extraction or rule drafting.
- `manual_review_medium`: potentially useful, but the abstract should be checked for supplement context and outcome specificity.
- `manual_review_low`: keep only if it supports background or mechanism.
- `likely_exclude`: likely outside the current evidence map unless a later reviewer finds a specific reason.

## Next Work

1. Review `manual_review_high` records first and fill `human_final_decision` in `screening_log.csv`.
2. For included records, copy dose, population, comparator, and locator into `evidence_extraction.csv`.
3. Convert the strongest rows in `safety_rule_seed_260602.csv` into draft JSON rules only after evidence rows have a locator and source.
4. Add domestic product examples for OTC/high-dose B-complex, vitamin D/calcium, iron, magnesium, and zinc to test whether the rule fields match real labels.

## Source Basis

- NIH ODS Vitamin D, Calcium, Vitamin B6, Magnesium, Iron, Zinc, Vitamin A, Vitamin E, and Vitamin K fact sheets.
- EFSA 2023 Scientific Opinion on the tolerable upper intake level for vitamin B6.
- Existing project files: `docs/research_plan_260601.md`, `docs/search_strategy_260601.md`, and `data/systematic_search/*`.
