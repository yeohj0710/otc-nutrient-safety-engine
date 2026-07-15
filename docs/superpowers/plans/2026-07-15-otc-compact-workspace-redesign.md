# OTC Compact Safety Workspace Implementation Plan

> **For agentic workers:** Execute this plan inline in the current session. Do not delegate or create a worktree because the authoritative repository intentionally contains user-owned dirty changes.

**Goal:** Replace the long four-step OTC form with a compact, original workspace that makes product comparison, personal-condition input, and deterministic safety results usable from one screen.

**Architecture:** Keep the existing runtime schema and deterministic engine unchanged. Recompose the client into three responsive work areas: medicine selection, personal conditions, and a live result rail. Add pure selection helpers for quick-check presets and keep all result claims bound to released runtime rules.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, CSS Modules, Vitest, Playwright CLI.

---

### Task 1: Lock the interaction contract

**Files:**
- Modify: `__tests__/otc-product-flow.test.ts`
- Modify: `src/components/otc-product-safety-client.tsx`

- [ ] Add a failing test for preset selection that resolves known product IDs, skips unknown IDs, and does not duplicate products.
- [ ] Run `npm test -- --run __tests__/otc-product-flow.test.ts` and confirm the new helper test fails before implementation.
- [ ] Implement `buildSelectedProducts(runtime, productIds)` with `{ unitsPerDose: 1, dosesPerDay: 1 }` defaults.
- [ ] Run the focused test and confirm it passes.

### Task 2: Build the compact workspace

**Files:**
- Modify: `src/components/otc-product-safety-client.tsx`
- Modify: `src/components/otc-product-safety.module.css`

- [ ] Add a compact search header with live result count and three original quick-check combinations.
- [ ] Replace the numbered vertical flow with a desktop three-column workspace and a single-column mobile flow.
- [ ] Add editable per-product dose, daily frequency, previous-dose interval, and continuous-use duration fields.
- [ ] Add age, medication, urgent-symptom, disease, pregnancy/lactation, driving, and alcohol inputs.
- [ ] Keep results live, rank urgent findings first, show calculated ingredient totals, and keep source locators behind details controls.
- [ ] Add a mobile result jump control and ensure all controls have visible labels, focus states, and at least 44px touch targets.

### Task 3: Reframe the page around the tool

**Files:**
- Modify: `app/page.tsx`
- Modify: `src/components/site-frame.tsx`
- Modify: `app/globals.css`

- [ ] Replace the tall landing-page hero with a compact research-service header and accurate runtime status badges.
- [ ] Remove the stale claim that expert review is unfinished; state `15` released rules without implying blind independent validation or release readiness.
- [ ] Keep the Yonsei identity visible but quiet, and keep the research-use disclaimer in the page frame.
- [ ] Apply Pretendard-first Korean typography, restrained navy/mint accents, dense spacing, and no decorative gradients or copied reference layouts.

### Task 4: Verify behavior and rendering

**Files:**
- Store temporary browser artifacts under: `etc/ui-redesign/browser/`

- [ ] Run `npm test` and confirm all Vitest tests pass.
- [ ] Run `npm run lint`, `npm run typecheck`, and `npm run build`.
- [ ] Use Playwright CLI at 1440×1000 and 390×844 to verify search, preset selection, condition toggles, live findings, evidence expansion, keyboard focus, and zero horizontal overflow.
- [ ] Capture final desktop and mobile full-page screenshots under `etc/ui-redesign/browser/` and inspect them visually.
- [ ] Confirm `research_v3/otc/audit/completion_audit.json` remains `complete=false` and `release_ready=false`.

