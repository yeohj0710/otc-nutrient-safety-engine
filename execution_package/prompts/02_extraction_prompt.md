# Full-text Evidence Extraction Prompt

Use only the supplied article passages. Extract only explicitly reported information. Every non-null field must include a page/section/table locator and supporting text. Use `null` for unreported data. Do not calculate an effect unless a separate `derived=true` field and formula are provided.

Required fields:

- population and eligibility
- medication/clinical context
- ingredient, formulation, daily dose, duration
- comparator
- outcome definition and timepoint
- events and denominators
- effect measure, value, confidence interval
- adjusted covariates
- adverse-event withdrawals
- funding/conflicts
- directness to the clinical node

Return JSON conforming to `schemas/extraction_record.schema.json`. Do not write a clinical recommendation.
