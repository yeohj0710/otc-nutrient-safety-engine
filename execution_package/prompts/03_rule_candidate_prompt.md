# Rule Candidate Prompt

Create a *draft candidate* only from verified extraction records and GRADE assessment. Do not introduce a dose, duration, contraindication, causal statement, or population not present in the inputs. Link every condition and message clause to evidence IDs and quote IDs.

Prefer `information_needed` when necessary context is absent. Use `no_reviewed_rule`, never `safe`, when no released rule applies. State uncertainty in plain Korean. Output JSON conforming to `schemas/rule.schema.json` with status `draft_ai`.
