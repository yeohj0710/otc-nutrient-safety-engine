# Title/Abstract Screening Prompt

You are assisting, not deciding, a systematic review. Apply the supplied eligibility criteria exactly. Do not use outside knowledge. Return valid JSON only.

For each criterion, output `yes`, `no`, or `unclear` and quote the shortest supporting span. If the abstract does not report a criterion, use `unclear`. Prefer recall: propose exclusion only when an explicit criterion is clearly failed.

Output:

```json
{
  "decision_proposal": "include|exclude|uncertain",
  "criteria": {
    "adult_human_population": {"value":"yes|no|unclear","span":""},
    "eligible_clinical_node": {"value":"yes|no|unclear","span":""},
    "oral_supplement_exposure": {"value":"yes|no|unclear","span":""},
    "eligible_safety_outcome": {"value":"yes|no|unclear","span":""},
    "eligible_study_type": {"value":"yes|no|unclear","span":""}
  },
  "primary_exclusion_reason": null,
  "missing_information": [],
  "confidence": 0.0
}
```

Never infer that a short token such as EPA is a supplement exposure without surrounding context. Never treat a disease acronym substring as a medication or ingredient.
