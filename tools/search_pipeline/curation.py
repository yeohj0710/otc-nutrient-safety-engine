from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .schemas import EVIDENCE_EXTRACTION_COLUMNS, SCREENING_LOG_COLUMNS
from .storage import SYSTEMATIC_SEARCH_DIR, ensure_layout, read_csv_rows, upsert_csv_rows, write_csv_rows


@dataclass(frozen=True)
class TargetProfile:
    label: str
    population_terms: tuple[str, ...]
    ingredient_terms: tuple[str, ...]
    outcome_terms: tuple[str, ...]


PROFILE_TARGETS: dict[str, dict[str, TargetProfile]] = {
    "anticoag_renal": {
        "anticoag_refined": TargetProfile(
            label="anticoagulant users with bleeding or INR concern",
            population_terms=("warfarin", "anticoagulant", "anticoagulation", "atrial fibrillation", "inr"),
            ingredient_terms=(
                "omega-3",
                "omega 3",
                "fish oil",
                "epa",
                "dha",
                "polyunsaturated fatty acid",
                "vitamin k",
                "coenzyme q10",
                "coq10",
                "cranberry",
                "glucosamine",
                "herbal",
                "supplement",
            ),
            outcome_terms=("bleeding", "hemorrhage", "haemorrhage", "inr", "platelet", "interaction", "adverse event"),
        ),
        "kidney_stone_refined": TargetProfile(
            label="kidney stone or hypercalciuria risk group",
            population_terms=("kidney stone", "renal stone", "nephrolithiasis", "urolithiasis", "hypercalciuria"),
            ingredient_terms=("calcium", "vitamin d", "vitamin c", "ascorbic acid", "supplement"),
            outcome_terms=("hypercalcemia", "hypercalciuria", "kidney stone", "nephrolithiasis", "recurrence", "adverse"),
        ),
    },
    "otc_nutrients": {
        "high_dose_vitd_calcium": TargetProfile(
            label="high-dose vitamin D and calcium exposure",
            population_terms=("adult", "supplement", "dietary", "over-the-counter", "otc"),
            ingredient_terms=("vitamin d", "cholecalciferol", "calciferol", "calcium"),
            outcome_terms=("hypercalcemia", "hypercalciuria", "nephrolithiasis", "toxicity", "adverse"),
        ),
        "b6_bcomplex_neuropathy": TargetProfile(
            label="vitamin B6 or B-complex high-dose exposure",
            population_terms=("adult", "supplement", "dietary", "over-the-counter", "otc"),
            ingredient_terms=("pyridoxine", "vitamin b6", "b6", "b-complex", "benfotiamine"),
            outcome_terms=("neuropathy", "neurotoxicity", "toxicity", "adverse", "paresthesia"),
        ),
        "mineral_gi_interaction": TargetProfile(
            label="OTC mineral supplement exposure",
            population_terms=("adult", "supplement", "dietary", "over-the-counter", "otc"),
            ingredient_terms=("iron", "ferrous", "magnesium", "calcium", "zinc"),
            outcome_terms=("constipation", "diarrhea", "interaction", "absorption", "adverse"),
        ),
    },
}

EXCLUDE_TERMS = (
    "mouse",
    "mice",
    "rat",
    "rats",
    "broiler",
    "turkey",
    "cat",
    "cats",
    "pig",
    "pigs",
    "swine",
    "in vitro",
    "molecular docking",
    "mmgbsa",
    "admet",
    "simulation",
)

STUDY_TERMS = (
    "systematic review",
    "meta-analysis",
    "randomized",
    "randomised",
    "clinical trial",
    "cohort",
    "case report",
    "case series",
    "pharmacokinetic",
)

RULE_SEED_COLUMNS = [
    "rule_seed_id",
    "profile",
    "target_group",
    "ingredient_or_exposure",
    "risk_context",
    "trigger",
    "proposed_action",
    "evidence_basis",
    "priority",
    "review_status",
]

PRIORITY_COLUMNS = [
    "record_id",
    "target_id",
    "pmid",
    "year",
    "priority",
    "suggested_decision",
    "matched_population_terms",
    "matched_ingredient_terms",
    "matched_outcome_terms",
    "matched_study_terms",
    "title",
    "url",
]


def generate_screening_outputs(
    output_root: Path = SYSTEMATIC_SEARCH_DIR,
    *,
    profile: str,
    date_tag: str | None = None,
) -> None:
    ensure_layout(output_root)
    targets = _targets(profile)
    review_date = date_tag or date.today().isoformat()
    records = read_csv_rows(output_root / "retrieved_records.csv")

    screening_rows: list[dict[str, str]] = []
    evidence_rows: list[dict[str, str]] = []
    priority_rows: list[dict[str, str]] = []

    for record in records:
        classification = classify_record(record, targets)
        screening_rows.append(
            {
                "record_id": record.get("record_id", ""),
                "suggested_decision": classification["decision"],
                "human_final_decision": "",
                "exclusion_reason": classification["reason"],
                "reviewer": "rule_based_classifier_v1",
                "review_date": review_date,
            }
        )
        evidence_rows.append(
            {
                "record_id": record.get("record_id", ""),
                "population": classification["population"],
                "supplement": classification["supplement"],
                "dose": "manual extraction required",
                "comparator": "manual extraction required",
                "outcome": classification["outcome"],
                "safety_signal": classification["signal"],
                "locator": "title/abstract",
                "linked_target": record.get("target_id", ""),
            }
        )
        priority_rows.append(
            {
                "record_id": record.get("record_id", ""),
                "target_id": record.get("target_id", ""),
                "pmid": record.get("pmid", ""),
                "year": record.get("year", ""),
                "priority": classification["priority"],
                "suggested_decision": classification["decision"],
                "matched_population_terms": "; ".join(classification["population_terms"]),
                "matched_ingredient_terms": "; ".join(classification["ingredient_terms"]),
                "matched_outcome_terms": "; ".join(classification["outcome_terms"]),
                "matched_study_terms": "; ".join(classification["study_terms"]),
                "title": record.get("title", ""),
                "url": record.get("url", ""),
            }
        )

    upsert_csv_rows(output_root / "screening_log.csv", screening_rows, SCREENING_LOG_COLUMNS, "record_id")
    upsert_csv_rows(
        output_root / "evidence_extraction.csv",
        evidence_rows,
        EVIDENCE_EXTRACTION_COLUMNS,
        "record_id",
    )

    suffix = _suffix(review_date)
    write_csv_rows(output_root / f"screening_priority_{suffix}.csv", priority_rows, PRIORITY_COLUMNS)


def classify_record(record: dict[str, str], targets: dict[str, TargetProfile]) -> dict[str, object]:
    target = targets.get(record.get("target_id", ""))
    text = _record_text(record)
    population_terms = _matched_terms(text, target.population_terms if target else ())
    ingredient_terms = _matched_terms(text, target.ingredient_terms if target else ())
    outcome_terms = _matched_terms(text, target.outcome_terms if target else ())
    study_terms = _matched_terms(text, STUDY_TERMS)
    exclude_terms = _matched_terms(text, EXCLUDE_TERMS)

    if record.get("is_duplicate", "").lower() == "true":
        decision = "exclude_duplicate"
        reason = "duplicate record marked by deduplication step"
    elif exclude_terms:
        decision = "likely_exclude"
        reason = "nonhuman or nonclinical terms: " + "; ".join(exclude_terms)
    elif ingredient_terms and outcome_terms and population_terms:
        decision = "include_candidate"
        reason = "title/abstract matches population, ingredient, and safety outcome"
    elif ingredient_terms and outcome_terms:
        decision = "maybe_needs_manual_review"
        reason = "title/abstract matches ingredient and safety outcome, but population/context needs review"
    elif ingredient_terms or outcome_terms:
        decision = "manual_review_low"
        reason = "partial keyword match only"
    else:
        decision = "likely_exclude"
        reason = "no target ingredient and safety outcome match"

    score = len(population_terms) + len(ingredient_terms) + len(outcome_terms) + len(study_terms)
    if decision == "include_candidate" and score >= 5:
        priority = "manual_review_high"
    elif decision in {"include_candidate", "maybe_needs_manual_review"}:
        priority = "manual_review_medium"
    elif decision == "manual_review_low":
        priority = "manual_review_low"
    else:
        priority = "likely_exclude"

    return {
        "decision": decision,
        "reason": reason,
        "priority": priority,
        "population": target.label if target else "manual verification required",
        "supplement": "; ".join(ingredient_terms) or "manual extraction required",
        "outcome": "; ".join(outcome_terms) or "manual extraction required",
        "signal": _signal(decision),
        "population_terms": population_terms,
        "ingredient_terms": ingredient_terms,
        "outcome_terms": outcome_terms,
        "study_terms": study_terms,
    }


def write_rule_seed(
    output_root: Path = SYSTEMATIC_SEARCH_DIR,
    *,
    profile: str,
    date_tag: str | None = None,
) -> Path:
    ensure_layout(output_root)
    suffix = _suffix(date_tag or date.today().isoformat())
    rows = _rule_seed_rows(profile)
    path = output_root / f"safety_rule_seed_{suffix}.csv"
    write_csv_rows(path, rows, RULE_SEED_COLUMNS)
    return path


def _targets(profile: str) -> dict[str, TargetProfile]:
    if profile not in PROFILE_TARGETS:
        choices = ", ".join(sorted(PROFILE_TARGETS))
        raise ValueError(f"Unknown curation profile: {profile}. Choices: {choices}")
    return PROFILE_TARGETS[profile]


def _record_text(record: dict[str, str]) -> str:
    return " ".join(
        [
            record.get("title", ""),
            record.get("abstract_or_summary", ""),
            record.get("journal_or_source", ""),
        ]
    ).lower()


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if _term_matches(text, term)]


def _term_matches(text: str, term: str) -> bool:
    escaped = re.escape(term.lower())
    if re.search(r"[A-Za-z0-9]", term):
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    else:
        pattern = escaped
    return re.search(pattern, text) is not None


def _signal(decision: str) -> str:
    if decision in {"include_candidate", "maybe_needs_manual_review"}:
        return "candidate safety signal from title/abstract keyword classification"
    if decision == "manual_review_low":
        return "weak candidate signal, human verification required"
    return "not treated as evidence until human review"


def _suffix(value: str) -> str:
    return value.replace("-", "")[:8]


def _rule_seed_rows(profile: str) -> list[dict[str, str]]:
    if profile == "anticoag_renal":
        return [
            _seed(
                profile,
                "anticoagulant users",
                "omega-3 or fish oil",
                "warfarin or other anticoagulant use",
                "supplement contains omega-3/fish oil and user reports anticoagulant use or bleeding history",
                "show caution message and ask user to confirm anticoagulant, antiplatelet, surgery, and bleeding history",
                "PubMed systematic search target anticoag_refined plus NIH/NCCIH safety materials",
                "high",
            ),
            _seed(
                profile,
                "anticoagulant users",
                "vitamin K intake change",
                "warfarin use",
                "vitamin K supplement or abrupt dietary vitamin K change in warfarin user",
                "advise stable intake and clinician-led INR monitoring rather than unsupervised dose change",
                "NIH ODS vitamin K fact sheet and anticoagulant interaction guidance",
                "high",
            ),
            _seed(
                profile,
                "anticoagulant users",
                "CoQ10 or multi-nutrient product",
                "warfarin use with INR monitoring",
                "CoQ10 or multi-nutrient product that may alter warfarin response",
                "flag as interaction requiring medication and INR review",
                "exploratory knowledge pack and follow-up full text review",
                "medium",
            ),
            _seed(
                profile,
                "renal high-risk group",
                "supplemental calcium",
                "kidney stone history or hypercalciuria",
                "calcium supplement use in user with stone history, hypercalciuria, or high vitamin D co-use",
                "separate dietary calcium from supplemental calcium and recommend clinician review of total intake",
                "PubMed kidney_stone_refined search plus NIH ODS calcium and kidney stone guidance",
                "high",
            ),
            _seed(
                profile,
                "renal high-risk group",
                "vitamin D",
                "hypercalciuria, nephrolithiasis, or renal risk",
                "high-dose vitamin D or combined calcium/vitamin D in renal high-risk context",
                "flag need for serum calcium, urinary calcium, and total intake review",
                "NIH ODS vitamin D/calcium fact sheets and kidney stone search output",
                "high",
            ),
            _seed(
                profile,
                "renal high-risk group",
                "vitamin C",
                "stone history or hyperoxaluria",
                "high-dose vitamin C supplement in user with calcium oxalate stone or hyperoxaluria history",
                "warn that high-dose supplemental vitamin C needs individual review in stone-prone users",
                "NIH ODS vitamin C fact sheet and kidney stone guidance",
                "medium",
            ),
        ]

    if profile == "otc_nutrients":
        return [
            _seed(
                profile,
                "OTC high-dose nutrient",
                "vitamin D",
                "adult self-supplementation",
                "vitamin D exceeds 100 mcg/day or 4,000 IU/day",
                "flag high-dose intake and ask about calcium use, hypercalcemia, kidney stones, and lab monitoring",
                "NIH ODS vitamin D fact sheet",
                "high",
            ),
            _seed(
                profile,
                "OTC high-dose nutrient",
                "calcium",
                "supplemental calcium use",
                "supplemental calcium around 1,000 mg/day or higher, especially with renal stone history",
                "separate food calcium from supplemental calcium and check total intake",
                "NIH ODS calcium fact sheet",
                "high",
            ),
            _seed(
                profile,
                "OTC high-dose nutrient",
                "vitamin B6",
                "B6 or B-complex product",
                "adult B6 intake exceeds 12 mg/day or approaches 100 mg/day",
                "use dual threshold warning for neuropathy risk and route to manual review for chronic use",
                "EFSA vitamin B6 UL opinion and NIH ODS vitamin B6 fact sheet",
                "high",
            ),
            _seed(
                profile,
                "OTC mineral product",
                "magnesium",
                "supplement, laxative, or antacid use",
                "supplemental elemental magnesium exceeds 350 mg/day or renal impairment is reported",
                "flag diarrhea and hypermagnesemia risk context, with severity higher in renal impairment",
                "NIH ODS magnesium fact sheet",
                "high",
            ),
            _seed(
                profile,
                "OTC mineral product",
                "iron",
                "self-directed iron supplementation",
                "iron intake is 45 mg/day or higher without treatment indication",
                "flag GI adverse effects and separate therapeutic prescription use from self-use",
                "NIH ODS iron fact sheet",
                "medium",
            ),
            _seed(
                profile,
                "OTC mineral product",
                "zinc",
                "chronic zinc supplementation",
                "zinc exceeds 40 mg/day or chronic high-dose use is reported",
                "flag copper deficiency, GI symptoms, and medication spacing issues",
                "NIH ODS zinc fact sheet",
                "medium",
            ),
            _seed(
                profile,
                "OTC fat-soluble vitamin",
                "preformed vitamin A",
                "retinol-containing product",
                "preformed vitamin A exceeds 3,000 mcg RAE/day",
                "distinguish retinol from beta-carotene and flag toxicity risk",
                "NIH ODS vitamin A fact sheet",
                "medium",
            ),
            _seed(
                profile,
                "OTC fat-soluble vitamin",
                "vitamin E",
                "anticoagulant or antiplatelet co-use",
                "high-dose vitamin E with anticoagulant or antiplatelet use",
                "flag possible bleeding risk context and ask about medication co-use",
                "NIH ODS vitamin E fact sheet and anticoagulant safety materials",
                "medium",
            ),
            _seed(
                profile,
                "OTC interaction rule",
                "vitamin K",
                "warfarin-like anticoagulant use",
                "vitamin K supplement or abrupt intake change in warfarin user",
                "warn against sudden intake changes and recommend INR monitoring discussion",
                "NIH ODS vitamin K fact sheet",
                "medium",
            ),
        ]

    choices = ", ".join(sorted(PROFILE_TARGETS))
    raise ValueError(f"Unknown rule seed profile: {profile}. Choices: {choices}")


def _seed(
    profile: str,
    target_group: str,
    ingredient: str,
    risk_context: str,
    trigger: str,
    action: str,
    evidence_basis: str,
    priority: str,
) -> dict[str, str]:
    slug = "_".join(
        part.lower().replace("/", "_").replace(" ", "_").replace("-", "_")
        for part in [profile, target_group, ingredient]
    )
    return {
        "rule_seed_id": slug,
        "profile": profile,
        "target_group": target_group,
        "ingredient_or_exposure": ingredient,
        "risk_context": risk_context,
        "trigger": trigger,
        "proposed_action": action,
        "evidence_basis": evidence_basis,
        "priority": priority,
        "review_status": "seed_requires_human_source_check",
    }
