# v5.0 OTC literature screening — frozen lightweight criterion

Screen each `(record_id, question_id)` independently from title, abstract, publication types, and MeSH terms. Do not use external models, human-reference labels, or prior decisions. Do not quote source text and do not provide stepwise proofs.

Output exactly four fields:

- `decision`: `retain`, `deprioritize`, or `uncertain`
- `reason_codes`: one or more of `population`, `exposure`, `outcome`, `human_signal`, `design_signal`, `animal_term_present`, `insufficient_abstract`, `off_topic`
- `confidence`: `high`, `medium`, or `low`
- `evidence_basis`: `abstract` when an abstract is present, otherwise `title_only`

Decision rule:

- `retain`: the record gives interpretable human evidence about an in-scope exposure and an in-scope safety outcome, harm, absence of harm, interaction, overdose, duplicate use, dosing risk, or risk-modifying population.
- `deprioritize`: the record is clearly off-topic; lacks the in-scope exposure or safety outcome; is efficacy, pharmacokinetics, assay, mechanism, manufacturing, veterinary, animal-only, or in-vitro-only work; or concerns only an out-of-scope route or formulation.
- `uncertain`: the record is plausibly relevant but title/abstract information is insufficient to distinguish `retain` from `deprioritize`.

Reason-code rule:

- Use `population`, `exposure`, `outcome`, `human_signal`, and `design_signal` for signals that materially support the decision.
- Add `animal_term_present` when animal or in-vitro terminology materially drives deprioritization or uncertainty.
- Add `insufficient_abstract` when missing or inadequate abstract detail materially drives the decision.
- Use `off_topic` when the subject is clearly outside the question.
- Do not emit explanations beyond these codes.

Question scope:

- `OTC-LIT-Q01-ACETAMINOPHEN`: acetaminophen/paracetamol oral or unspecified-route use; overdose, duplicate use, high dose, short interval, hepatic disease, alcohol use, children/adolescents, or older adults; safety outcomes including liver injury, toxicity, adverse events, emergency care, or death. IV-only exposure is out of scope.
- `OTC-LIT-Q02-NSAID`: oral or unspecified-route ibuprofen, dexibuprofen, naproxen, or applicable NSAID-class exposure; duplicate NSAID use, pregnancy/lactation, kidney disease, ulcer history, anticoagulant/antiplatelet use; bleeding, renal, pregnancy, interaction, or other safety outcomes. Non-oral-only exposure is out of scope.
- `OTC-LIT-Q03-COLD-ALLERGY`: oral or unspecified-route cetirizine, chlorpheniramine/chlorphenamine, phenylephrine, pentoxyverine/carbetapentane, guaifenesin, caffeine, or applicable antihistamine/decongestant/antitussive/expectorant class; driving or machinery use, hypertension/cardiovascular disease, or sedative/CNS-depressant co-use; sedation, psychomotor, cardiovascular, interaction, misuse, or other safety outcomes.
- `OTC-LIT-Q04-DIGESTIVE`: oral or unspecified-route pancreatin/pancrelipase/pancrealipase/PERT, Pancellase, Panprosin, Crease-PEG, Prozyme 6, digestive enzyme products, simethicone/simeticone, ursodeoxycholic acid/ursodiol/UDCA, bromelain, or applicable digestive-product class; human adverse events, allergy, bleeding, interactions, or long-term/repeated-use safety. Endogenous enzymes, biomarkers, assays, cell lines, and industrial enzymes without oral therapeutic exposure are out of scope.
- `OTC-LIT-Q05-TOPICAL`: topical methyl salicylate/wintergreen oil, menthol, camphor, Mentha arvensis/canadensis oil, thymol, or applicable topical counterirritant products; repeated/excessive use, children, or anticoagulant/antiplatelet use; salicylate toxicity, local reactions, pediatric poisoning, bleeding, interactions, or other safety outcomes. Oral peppermint oil, mothballs, flavors, and cleaning uses are out of scope.

Confidence:

- `high`: title/abstract clearly supports the decision.
- `medium`: one material element is implicit or incomplete.
- `low`: title-only or sparse information limits certainty.

Each output row must contain only `record_id`, `question_id`, and the four allowed screening fields. Preserve input order.
