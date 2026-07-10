# AGENTS.md — 여형준 연구 실행 규칙

## Scope

이 파일은 저장소 전체에 적용한다. 하위 디렉터리에 더 구체적인 `AGENTS.md`가 있으면 그 규칙을 함께 따른다.

## Identity

- Student: 여형준
- Student ID: 2020194025
- Study: 항응고제 복용자와 신장결석 고위험군의 영양소 보충제 안전성
- Product boundary: evidence-traceable counseling-support prototype
- Never import Kwon-specific identity, data, rules, metrics, or prose into the Yeo study.

## Source hierarchy

1. frozen protocol
2. raw database exports and full texts
3. adjudicated extraction/RoB/GRADE data
4. released rules
5. generated metrics and thesis
6. legacy files, which are untrusted

If two sources disagree, do not silently choose. Record the conflict and resolve it at the highest applicable level.

## Research integrity

- Never invent search counts, screening decisions, full-text findings, expert ratings, or citations.
- Never call a top-N retrieval a systematic search.
- Preserve raw inputs; transformations are append-only and reproducible.
- Every derived file records source hashes, script version, date, and command.
- Manual decisions require reviewer ID and timestamp.
- AI output is a proposal until human adjudication.
- A source title or abstract is not enough to create a released clinical rule.

## Coding

- Use typed schemas and validation at boundaries.
- Tests cover units, dose thresholds, missing data, conflicts, provenance, and student/repo identity.
- Do not hard-code thesis metrics in UI or prose.
- Generate metrics from frozen data.
- Use deterministic runtime rules; LLM parsing requires user confirmation.
- No secrets, paid full texts, or personal data in git.

## Analysis

- Keep confirmatory and exploratory analyses separate.
- Report denominators and confidence intervals.
- Do not pool clinically incompatible outcomes.
- Keep government thresholds, clinical effects, and adverse-event signals in separate evidence layers.
- Record all exclusions and analysis-set derivations.

## Thesis writing

- Do not draft final Results/Discussion/Conclusion before evidence freeze.
- Each numeric claim must exist in the claim ledger and metrics manifest.
- Each literature claim must map to evidence ID and locator.
- Avoid repetitive abstract nouns and generic AI phrasing.
- Use direct, concrete Korean; state uncertainty and limitations.
- Do not inflate the prototype into a clinically validated device.

## Work log

Maintain:

- `research_v2/DECISIONS.md`
- `research_v2/CHANGELOG_RESEARCH.md`
- `research_v2/HUMAN_ACTION_REQUIRED.md`
- `research_v2/audit/gate_status.json`

A human action item must state exactly what is needed, why it cannot be automated, the required input format, and which downstream tasks are blocked. Continue all unblocked work.

## Definition of done

A task is done only when its artifact exists, schema validation passes, tests pass, acceptance criteria are measured, and the task is linked to a commit. Prose stating that work was done is not evidence of completion.
