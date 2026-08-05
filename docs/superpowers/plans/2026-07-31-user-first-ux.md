# OTC Nutrient Safety Engine User-first UX Implementation Plan

> **For Codex:** Execute this plan locally. Do not deploy without an explicit request.

**Goal:** Replace repetitive ingredient-level warnings with concise user-level findings and make the checker’s real coverage visible at the point of use.

**Architecture:** Preserve the deterministic rule engine and sealed research artifacts. Add a presentation helper that groups duplicate-ingredient findings only when they belong to the same selected product combination, then improve the result layout and scope summary.

**Tech Stack:** Next.js 16, React, TypeScript, CSS Modules, Vitest

---

### Task 1: Lock the grouping and scope contracts

**Files:**
- Modify: `__tests__/otc-evidence-ux.test.ts`
- Modify: `__tests__/otc-layout-contract.test.ts`

- [x] Test that six duplicate-ingredient findings for one product pair become one display finding.
- [x] Test that different product pairs and non-duplicate rules remain separate.
- [x] Require a visible selected-scope summary in the result panel.

### Task 2: Add the presentation-only grouping helper

**Files:**
- Modify: `src/lib/otc/presentation.ts`

- [x] Merge only `duplicate_ingredient` findings with the same sorted product IDs.
- [x] Deduplicate ingredient IDs, product IDs, and evidence links.
- [x] Generate concrete Korean summary text from ingredient names.

### Task 3: Improve result density and layout

**Files:**
- Modify: `src/components/otc-product-safety-client.tsx`
- Modify: `src/components/otc-product-safety.module.css`
- Modify: `app/page.tsx`

- [x] Use grouped findings in result counts, cards, and mobile result link.
- [x] Show selected products, connected rule bindings, and administration constraints near the result.
- [x] Give the result column more desktop width while retaining the single-column mobile layout.
- [x] Preserve the distinction between authorization evidence and explanatory literature.

### Task 4: Verify locally

**Files:**
- Test: `__tests__/otc-evidence-ux.test.ts`
- Test: `__tests__/otc-layout-contract.test.ts`

- [x] Run the focused tests.
- [x] Run `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build`.
- [x] Do not commit or deploy unless explicitly requested.
