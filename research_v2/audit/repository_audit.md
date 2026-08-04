# Repository and legacy audit

## Audit metadata

- Audit date: 2026-07-10
- Repository: `C:\dev\otc-nutrient-safety-engine`
- Commands: `git`, `rg`, Python/PDF extraction, Poppler render, CSV field/count audit, public deployment HTTP check
- Active research lineage: `research_v2`
- Legacy policy: all pre-v2 data, metrics, rules, documents, and generated outputs are `legacy_untrusted`

## Repository identity and history

- Origin: `https://github.com/yeohj0710/otc-nutrient-safety-engine.git`
- Branch: `main`
- HEAD before v2 work: `212510dc368ef2414136bc676729b8f8aab67370`
- History: 21 commits, 2026-06-01 through 2026-06-04
- First commit: `b83e94276592b817080a55bc97ca2f5dbe2a162c`
- Tags before v2 work: 0
- Initial working tree: clean
- Identity judgment: 권혁찬(2021194024) and repository match. The supplied execution package did not match because it was authored for 여형준; the repo copy was ported before bootstrap.

## Existing dataset audit

| Asset | Observed state | v2 disposition |
|---|---|---|
| `data/systematic_search/search_runs.csv` | 6 PubMed runs; each capped at 50 or 100 records | top-N retrieval; not a systematic-search denominator |
| `data/systematic_search/retrieved_records.csv` | 435 records, 18 duplicate flags | audit and regression input only |
| `data/systematic_search/screening_log.csv` | 435 AI suggestions; 0 human final decisions | not screened evidence |
| `data/systematic_search/evidence_extraction.csv` | 435 title/abstract-derived rows; every field filled by template text | not verified full-text extraction |
| `data/systematic_search/secondary_search_runs_20260603.csv` | 6 runs, 20 stored records each, 2,123,667 aggregate hits | supplementary top-N audit only |
| `data/systematic_search/safety_rule_seed_20260603.csv` | 9/9 `seed_requires_human_source_check` | no released v2 rule |
| `data/systematic_search/scenario_evaluation_20260603.csv` | 6 development-aligned scenarios | regression examples, not independent validation |
| `data/knowledge_pack.json` and generated runtime data | broad multi-study scoping pack | reusable code/schema reference only; evidence values excluded |

The application-visible `52,701` is the sum of six search-run hit counts, while `435` is the capped stored set. These values do not represent a PRISMA-compatible search and screening flow.

## Deployment audit

- Vercel project: `otc-nutrient-safety-engine`
- Public URL: `https://otc-nutrient-safety-engine.vercel.app/`
- 2026-07-10 HTTP check: 200, 92,082 bytes
- Visible identity: 연세대학교 약학대학 6학년 권혁찬
- Visible legacy metrics: search 52,701; supplementary search 2,123,667; priority literature 371; dose rules 68
- Current local generator output: 110 rules and 176 evidence chunks
- Judgment: public deployment and current local runtime are stale/inconsistent. Neither set of counts may be used in the v2 thesis or release until generated from frozen evidence and `metrics_manifest.json`.

## Environment audit

- Node lockfile: `package-lock.json` present; Next.js 16.2.1, React 19.2.4
- Python requirements: lower bounds only in `requirements.txt`; no research lockfile
- `.env.example` keys: `NCBI_EMAIL`, `NCBI_API_KEY`, `OPENAI_API_KEY`
- Actual repo `.env` file: absent
- Matching process environment keys at audit time: none
- Baseline Node tests: 7 files, 33 tests passed
- Baseline typecheck: passed
- Baseline bundled-Python tests: failed with `ModuleNotFoundError: No module named 'requests'` (`X-01`)
- Baseline generator reproducibility: `src/generated/literature-candidates.json` changed only because `generatedAt` used wall-clock time (`X-02`)

## Document audit

- Baseline research plan: 7 pages; identifies 권혁찬, 2021194024, review-thesis format, and ingredient/dose-centered scope.
- Existing thesis: 21 pages, but student ID is blank on the cover; English abstract contains Korean; many tables render as unformatted text; results rely on capped search data; full-text review and restricted-database search are deferred; appendices repeat prose.
- Judgment: the documents are legacy references, not final research outputs. Final results/discussion/conclusion writing remains prohibited before evidence freeze.

## Gate 0 conclusion

Gate 0 passes for repository identity and legacy isolation. It does not validate the existing evidence or application. Gate 1 requires human approval of K1-K5 and the protocol. Search-strategy validation and code preparation may continue while approval is pending.
