# Evidence Verification Prompt

Compare a candidate extraction or rule with the supplied source passages. Identify only verifiable discrepancies. Classify each as:

- unsupported
- wrong_value
- wrong_unit
- wrong_population
- wrong_timepoint
- wrong_direction
- overgeneralized
- missing_uncertainty
- locator_mismatch
- no_error

Return the source span, candidate field, error class, and a concise correction proposal. This output is not final adjudication.
