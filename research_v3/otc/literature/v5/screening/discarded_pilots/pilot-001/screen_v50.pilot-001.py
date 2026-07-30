"""Local semantic-LLM, resumable Phase C screening for the v5.0 PubMed corpus.

The script only writes below research_v3/otc/literature/v5/screening and to
research_v3/logs/v50_progress.json.  The screening unit is the exact pair
(record_id, question_id), so one deduplicated paper can receive an independent
decision for every question that retrieved it.

Commands:

    python screen_v50.py freeze
    python screen_v50.py run --question-id OTC-LIT-Q01-ACETAMINOPHEN
    python screen_v50.py run-all
    python screen_v50.py status
    python screen_v50.py smoke-test

Use --start and --limit with run to allocate disjoint, canonical slices of one
question to parallel agents.  Parallel work across different questions is not
permitted: the command refuses Q02 until Q01 has coverage 1.0, and so on.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import importlib.metadata
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
CORPUS = V5 / "evidence_map.csv"
QUERY_DEFINITIONS = V5 / "query_definitions.json"
PROMPT = V5 / "prompts" / "agent_screening_prompt_v50.md"
SCREENING = V5 / "screening"
PROMPT_LOCK = SCREENING / "prompt_lock.json"
FROZEN_PROMPT = SCREENING / "agent_screening_prompt_v50.frozen.md"
CHECKPOINTS = SCREENING / "checkpoints.jsonl"
BATCHES = SCREENING / "batches.jsonl"
DECISIONS_CSV = SCREENING / "decisions.csv"
MANIFEST = SCREENING / "screening_manifest.json"
LOCK_FILE = SCREENING / ".screen_v50.lock"
PROGRESS = ROOT / "research_v3" / "logs" / "v50_progress.json"
SMOKE_REPORT = V5 / "etc" / "screening_smoke_test.json"

QUESTION_ORDER = (
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
)

DECISIONS = {"retain", "deprioritize", "uncertain"}
CONFIDENCES = {"high", "medium", "low"}
REASON_CODES = {
    "exposure_outcome_direct",
    "exposure_outcome_class_level",
    "case_report_relevant",
    "exposure_only",
    "outcome_only",
    "off_topic",
    "animal_or_in_vitro_only",
    "mechanism_or_assay_only",
    "population_mismatch",
    "route_or_formulation_mismatch",
    "insufficient_detail",
    "title_only_probable_relevant",
    "title_only_probable_off_topic",
    "title_only_insufficient",
}
TITLE_ONLY_CODES = {
    "title_only_probable_relevant",
    "title_only_probable_off_topic",
    "title_only_insufficient",
}
EXECUTION_MODE = "local_semantic_llm_7b_multipass_one_token_v1"
DEFAULT_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
MAX_INPUT_TOKENS = 1024
TRUNCATION_STRATEGY = "preserve_metadata_and_abstract_head_tail"
MACHINE_CONTRACT_BEGIN = "<!-- MACHINE_INFERENCE_CONTRACT_BEGIN -->"
MACHINE_CONTRACT_END = "<!-- MACHINE_INFERENCE_CONTRACT_END -->"

QUANTIZATION_CONFIG = {
    "load_in_4bit": True,
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_compute_dtype": "bfloat16",
    "bnb_4bit_use_double_quant": True,
}
GENERATION_CONFIG = {
    "strategy": "batched_multipass_one_token_masked_argmax",
    "do_sample": False,
    "num_beams": 1,
    "use_cache": False,
    "max_new_tokens": 1,
    "decision_rule": "argmax_over_stage_allowed_final_logits",
    "tie_break": "declared_option_order",
    "max_input_tokens": MAX_INPUT_TOKENS,
    "truncation_strategy": TRUNCATION_STRATEGY,
}

QUESTION_CRITERIA = {
    QUESTION_ORDER[0]: (
        "DIRECT EXPOSURE: acetaminophen/paracetamol/APAP. ALLOWED CLASS: anilide or "
        "para-aminophenol analgesic evidence only when explicitly applicable to acetaminophen. "
        "RISK CONTEXT (OR): duplicate use, overdose, high dose, short interval, liver disease, "
        "alcohol use, child/adolescent, or older adult."
    ),
    QUESTION_ORDER[1]: (
        "DIRECT EXPOSURE: ibuprofen, dexibuprofen, or naproxen. ALLOWED CLASS: an actually "
        "administered traditional nonselective NSAID such as diclofenac when the finding is "
        "applicable to that class. EXCLUDE as class exposure: aspirin-only or coxib-only unless "
        "explicitly generalized to applicable nonselective NSAIDs. RISK CONTEXT (OR): duplicate "
        "NSAID use, pregnancy/lactation, kidney disease, peptic-ulcer history, or anticoagulant/"
        "antiplatelet use."
    ),
    QUESTION_ORDER[2]: (
        "DIRECT EXPOSURE: cetirizine, chlorpheniramine, phenylephrine, pentoxyverine, "
        "guaifenesin, or caffeine. ALLOWED CLASS: an actually administered first-generation H1 "
        "antihistamine such as diphenhydramine when explicitly generalized to that class, or an "
        "applicable sympathomimetic decongestant/class finding. RISK CONTEXT (OR): driving or "
        "psychomotor performance, hypertension/cardiovascular disease, or sedative co-use."
    ),
    QUESTION_ORDER[3]: (
        "DIRECT EXPOSURE: oral pancreatin/pancrelipase/PERT, Pancellase, Panprosin, Prozyme 6, "
        "Crease-PEG, diastase digestive preparations, assigned lipase/cellulase digestive "
        "products, simethicone/simeticone, ursodeoxycholic acid/ursodiol/UDCA, or bromelain. "
        "ALLOWED CLASS: another actually administered oral digestive-enzyme product. Generic "
        "protease/amylase/lipase/cellulase is not exposure when endogenous, an assay, an "
        "inhibitor, or an industrial/food enzyme without human digestive-product use."
    ),
    QUESTION_ORDER[4]: (
        "DIRECT EXPOSURE: topical methyl salicylate, L-menthol/menthol, dl-camphor/camphor, "
        "Mentha arvensis or Mentha canadensis cornmint/Japanese-mint oil, or thymol. RISK CONTEXT "
        "(OR): child or anticoagulant/antiplatelet use. Child accidental ingestion of a topical "
        "balm is eligible. Camphor mothballs and oral peppermint-oil capsules are route/"
        "formulation candidates but not eligible topical exposure."
    ),
}

SALIENT_TERM_PATTERNS = {
    QUESTION_ORDER[0]: r"(?i)\b(?:acetaminophen|paracetamol|APAP|tylenol)\b",
    QUESTION_ORDER[1]: (
        r"(?i)\b(?:ibuprofen|dexibuprofen|naproxen|NSAID|nonsteroidal|diclofenac|"
        r"ketoprofen|indomethacin|meloxicam|piroxicam)\b"
    ),
    QUESTION_ORDER[2]: (
        r"(?i)\b(?:cetirizine|chlorpheniramine|phenylephrine|pentoxyverine|guaifenesin|"
        r"caffeine|antihistamine|decongestant|sympathomimetic|methylxanthine)\b"
    ),
    QUESTION_ORDER[3]: (
        r"(?i)\b(?:pancreatin|pancrelipase|pancrelipase|PERT|simethicone|simeticone|"
        r"ursodeoxycholic|ursodiol|UDCA|bromelain|protease|proteinase|amylase|lipase|"
        r"cellulase|digestive enzyme)\b"
    ),
    QUESTION_ORDER[4]: (
        r"(?i)\b(?:methyl salicylate|menthol|camphor|Mentha|cornmint|Japanese mint|"
        r"peppermint|thymol)\b"
    ),
}
DIRECT_NAME_PATTERNS = {
    QUESTION_ORDER[0]: r"(?i)\b(?:acetaminophen|paracetamol|APAP)\b",
    QUESTION_ORDER[1]: r"(?i)\b(?:ibuprofen|dexibuprofen|naproxen)\b",
    QUESTION_ORDER[2]: (
        r"(?i)\b(?:cetirizine|chlorpheniramine|phenylephrine|pentoxyverine|"
        r"guaifenesin|caffeine)\b"
    ),
    QUESTION_ORDER[3]: (
        r"(?i)\b(?:pancreatin|pancrelipase|PERT|Pancellase|Panprosin|Prozyme\s*6|"
        r"Crease-PEG|diastase|lipase|cellulase|simethicone|simeticone|"
        r"ursodeoxycholic|ursodiol|UDCA|bromelain)\b"
    ),
    QUESTION_ORDER[4]: (
        r"(?i)\b(?:methyl salicylate|menthol|camphor|Mentha\s+(?:arvensis|canadensis)|"
        r"cornmint|Japanese mint|thymol)\b"
    ),
}
EXPLICIT_EXPOSURE_PATTERNS = {
    QUESTION_ORDER[0]: DIRECT_NAME_PATTERNS[QUESTION_ORDER[0]],
    QUESTION_ORDER[1]: (
        r"(?i)\b(?:ibuprofen|dexibuprofen|naproxen|diclofenac|ketoprofen|"
        r"indomethacin|meloxicam|piroxicam|nonselective NSAID)\b"
    ),
    QUESTION_ORDER[2]: (
        r"(?i)\b(?:cetirizine|chlorpheniramine|phenylephrine|pentoxyverine|guaifenesin|"
        r"caffeine|diphenhydramine|first-generation H1 antihistamine|"
        r"sympathomimetic decongestant)\b"
    ),
    QUESTION_ORDER[3]: DIRECT_NAME_PATTERNS[QUESTION_ORDER[3]] + r"|(?i:\b(?:protease|amylase)\b)",
    QUESTION_ORDER[4]: (
        DIRECT_NAME_PATTERNS[QUESTION_ORDER[4]]
        + r"|(?i:\b(?:peppermint(?:-oil)?|camphor mothball)\b)"
    ),
}
Q04_NONEXPOSURE_CONTEXT = re.compile(
    r"(?i)\b(?:endogenous|serum|biomarker|assay|gene expression|protease inhibitor|"
    r"enzyme inhibitor|inhibit(?:ed|s|ion)?|cell line|cultured cell)\b"
)
NEGATED_EXPOSURE_CONTEXT = re.compile(
    r"(?i)\b(?:not|never|neither|no|none|nobody|no\s+one)\b(?:\W+\w+){0,4}\W+"
    r"(?:administered|given|received|used|detected|exposed)|"
    r"\bwithout\b(?:\W+\w+){0,4}\W+(?:administration|exposure|use)"
)
EXPOSURE_ACTION_PATTERN = re.compile(
    r"(?i)\b(?:receiv(?:e|ed|es|ing)|administer(?:ed|s|ing)?|use[ds]?|using|ingest(?:ed|s|ion|ing)?|"
    r"swallow(?:ed|s)?|inhale[ds]?|inhalation|apply|applied|expos(?:e|ed|ure)|overdos(?:e|ed|ing)|took|taken|"
    r"treated with|therapy|supplement(?:ed|ation)?)\b"
)
DIRECT_RELATION_PATTERN = re.compile(
    r"(?i)\b(?:receiv(?:e|ed|es|ing)|administer(?:ed|s|ing)?|use[ds]?|using|ingest(?:ed|s|ion|ing)?|"
    r"swallow(?:ed|s)?|inhale[ds]?|inhalation|apply|applied|expos(?:e|ed|ure)|overdos(?:e|ed|ing)|took|taken|"
    r"treated|therapy|containing|associated|attributed|caused|induced|after)\b"
)


def resolve_retain_kind(
    row: dict[str, str], question_id: str, semantic_answer: str
) -> str:
    """Resolve direct versus class identity after the semantic retain gate.

    This narrow lexical resolver cannot create a retain decision. It only keeps
    an already retained exposure at class level or promotes it to direct when a
    named assigned ingredient is connected to administration or attribution in
    the title or a tight local text window.
    """
    if semantic_answer not in {"direct", "class"}:
        return semantic_answer
    direct = re.compile(DIRECT_NAME_PATTERNS[question_id])
    title = " ".join((row.get("title") or "").split())
    if direct.search(title):
        return "direct"
    text = " ".join((row.get("abstract") or "").split())
    for match in direct.finditer(text):
        left = max(0, match.start() - 64)
        right = min(len(text), match.end() + 64)
        if DIRECT_RELATION_PATTERN.search(text[left:right]):
            return "direct"
    return "class"


def has_explicit_question_exposure(row: dict[str, str], question_id: str) -> bool:
    """Find an unambiguous entity-plus-administration statement.

    This can rescue a false-negative semantic exposure gate, but cannot by
    itself retain a record; route and attributable-safety stages still decide.
    """
    pattern = re.compile(EXPLICIT_EXPOSURE_PATTERNS[question_id])
    text = " ".join(
        f"{row.get('title') or ''}. {row.get('abstract') or ''}".split()
    )
    for match in pattern.finditer(text):
        left = max(0, match.start() - 96)
        right = min(len(text), match.end() + 96)
        window = text[left:right]
        if NEGATED_EXPOSURE_CONTEXT.search(window):
            continue
        if question_id == QUESTION_ORDER[3] and Q04_NONEXPOSURE_CONTEXT.search(window):
            continue
        if DIRECT_RELATION_PATTERN.search(window):
            return True
    return False

OUTPUT_KEYBOOK: dict[str, dict[str, Any]] = {
    "retain_direct_high": {"decision": "retain", "reason_codes": ["exposure_outcome_direct"], "confidence": "high"},
    "retain_direct_medium": {"decision": "retain", "reason_codes": ["exposure_outcome_direct"], "confidence": "medium"},
    "retain_class_high": {"decision": "retain", "reason_codes": ["exposure_outcome_class_level"], "confidence": "high"},
    "retain_class_medium": {"decision": "retain", "reason_codes": ["exposure_outcome_class_level"], "confidence": "medium"},
    "exposure_only": {"decision": "deprioritize", "reason_codes": ["exposure_only"], "confidence": "medium"},
    "outcome_only": {"decision": "deprioritize", "reason_codes": ["outcome_only"], "confidence": "medium"},
    "off_topic": {"decision": "deprioritize", "reason_codes": ["off_topic"], "confidence": "medium"},
    "animal_or_in_vitro_only": {"decision": "deprioritize", "reason_codes": ["animal_or_in_vitro_only"], "confidence": "high"},
    "mechanism_or_assay_only": {"decision": "deprioritize", "reason_codes": ["mechanism_or_assay_only"], "confidence": "high"},
    "route_mismatch": {"decision": "deprioritize", "reason_codes": ["route_or_formulation_mismatch"], "confidence": "medium"},
    "population_mismatch": {"decision": "deprioritize", "reason_codes": ["population_mismatch"], "confidence": "medium"},
    "uncertain_low": {"decision": "uncertain", "reason_codes": ["insufficient_detail"], "confidence": "low"},
    "uncertain_medium": {"decision": "uncertain", "reason_codes": ["insufficient_detail"], "confidence": "medium"},
    "title_retain": {"decision": "retain", "reason_codes": ["title_only_probable_relevant"], "confidence": "low"},
    "title_uncertain": {"decision": "uncertain", "reason_codes": ["title_only_insufficient"], "confidence": "low"},
    "title_off_topic": {"decision": "deprioritize", "reason_codes": ["title_only_probable_off_topic"], "confidence": "low"},
}
ABSTRACT_OUTPUT_KEYS = frozenset({
    "retain_direct_high", "retain_direct_medium", "retain_class_high", "retain_class_medium",
    "exposure_only", "outcome_only", "off_topic", "animal_or_in_vitro_only",
    "mechanism_or_assay_only", "route_mismatch", "population_mismatch",
    "uncertain_low", "uncertain_medium",
})
TITLE_ONLY_OUTPUT_KEYS = frozenset({"title_retain", "title_uncertain", "title_off_topic"})
FUSED_ALLOWED_OUTPUTS: dict[str, tuple[str, ...]] = {
    "abstract": (
        "direct", "likely", "class", "medium", "use", "outcome", "other",
        "animal", "method", "route", "population", "maybe", "unknown",
    ),
    "title_only": ("retain", "maybe", "other"),
}
MULTIPASS_STAGE_OPTIONS: dict[str, tuple[str, ...]] = {
    "preclinical_only": ("yes", "no"),
    "question_exposure": ("yes", "no"),
    "route_mismatch": ("yes", "no"),
    "attributable_human_harm": ("yes", "no"),
    "harm_outcome_present": ("yes", "no"),
    "retain_kind": ("direct", "class", "maybe"),
    "mechanism_only": ("yes", "no", "maybe"),
    "title_attributable_harm": ("yes", "no", "maybe"),
    "title_question_exposure": ("yes", "no", "maybe"),
    "nonretain_reason": ("use", "method", "route", "population", "outcome", "other", "maybe"),
    "title_only": ("retain", "maybe", "other"),
}
MULTIPASS_OUTPUT_SURFACES = {
    stage: {
        option: (
            "Include" if stage == "title_only" and option == "retain"
            else option.capitalize()
        )
        for option in options
    }
    for stage, options in MULTIPASS_STAGE_OPTIONS.items()
}
MULTIPASS_OUTPUT_SURFACES["preclinical_only"] = {
    "yes": "Animal", "no": "Clinical",
}
for _mismatch_stage in ("route_mismatch",):
    MULTIPASS_OUTPUT_SURFACES[_mismatch_stage] = {
        "yes": "Wrong", "no": "Correct", "maybe": "Maybe",
    }
for _result_stage in (
    "attributable_human_harm", "harm_outcome_present", "title_attributable_harm"
):
    MULTIPASS_OUTPUT_SURFACES[_result_stage] = {
        "yes": "reported", "no": "missing", "maybe": "unknown",
    }
FUSED_TO_CANONICAL_KEY = {
    "abstract": {
        "direct": "retain_direct_high",
        "likely": "retain_direct_medium",
        "class": "retain_class_high",
        "medium": "retain_class_medium",
        "use": "exposure_only",
        "outcome": "outcome_only",
        "other": "off_topic",
        "animal": "animal_or_in_vitro_only",
        "method": "mechanism_or_assay_only",
        "route": "route_mismatch",
        "population": "population_mismatch",
        "maybe": "uncertain_medium",
        "unknown": "uncertain_low",
    },
    "title_only": {
        "retain": "title_retain",
        "maybe": "title_uncertain",
        "other": "title_off_topic",
    },
}
FUSED_PATH_BY_CANONICAL_KEY = {
    "abstract": {
        "retain_direct_high": "no yes yes direct",
        "retain_direct_medium": "no yes yes likely",
        "retain_class_high": "no yes yes class",
        "retain_class_medium": "no yes yes medium",
        "exposure_only": "no yes no use",
        "outcome_only": "no no yes outcome",
        "off_topic": "no no no other",
        "animal_or_in_vitro_only": "yes animal",
        "mechanism_or_assay_only": "no yes no method",
        "route_mismatch": "no yes no route",
        "population_mismatch": "no yes no population",
        "uncertain_medium": "maybe maybe",
        "uncertain_low": "maybe unknown",
    },
    "title_only": {
        "title_retain": "retain",
        "title_uncertain": "maybe",
        "title_off_topic": "other",
    },
}
FUSED_DERIVED_STAGE_OUTPUTS = {
    "abstract": {
        "direct": {"preclinical_only": "no", "question_exposure_and_risk_context": "yes", "attributable_human_harm": "yes", "retain_kind": "direct", "confidence": "high"},
        "likely": {"preclinical_only": "no", "question_exposure_and_risk_context": "yes", "attributable_human_harm": "yes", "retain_kind": "direct", "confidence": "medium"},
        "class": {"preclinical_only": "no", "question_exposure_and_risk_context": "yes", "attributable_human_harm": "yes", "retain_kind": "class", "confidence": "high"},
        "medium": {"preclinical_only": "no", "question_exposure_and_risk_context": "yes", "attributable_human_harm": "yes", "retain_kind": "class", "confidence": "medium"},
        "use": {"preclinical_only": "no", "question_exposure_and_risk_context": "yes", "attributable_human_harm": "no", "nonretain_reason": "exposure_only"},
        "outcome": {"preclinical_only": "no", "question_exposure_and_risk_context": "no", "harm_outcome_present": "yes", "nonretain_reason": "outcome_only"},
        "other": {"preclinical_only": "no", "question_exposure_and_risk_context": "no", "harm_outcome_present": "no", "nonretain_reason": "off_topic"},
        "animal": {"preclinical_only": "yes", "nonretain_reason": "animal_or_in_vitro_only"},
        "method": {"preclinical_only": "no", "attributable_human_harm": "no", "nonretain_reason": "mechanism_or_assay_only"},
        "route": {"preclinical_only": "no", "question_exposure": "yes", "risk_context_or_route": "mismatch", "nonretain_reason": "route_or_formulation_mismatch"},
        "population": {"preclinical_only": "no", "question_exposure": "yes", "risk_context_or_route": "mismatch", "nonretain_reason": "population_mismatch"},
        "maybe": {"preclinical_only": "maybe", "terminal": "uncertain_medium"},
        "unknown": {"preclinical_only": "maybe", "terminal": "uncertain_low"},
    },
    "title_only": {
        "retain": {"title_exposure": "yes", "title_attributable_harm": "yes"},
        "maybe": {"title_exposure": "yes_or_maybe", "title_attributable_harm": "unclear"},
        "other": {"title_exposure": "no", "title_attributable_harm": "no"},
    },
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def stage_path_trie(path_token_ids: dict[str, list[int]]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for canonical_key, token_ids in sorted(path_token_ids.items()):
        node = root
        for token_id in token_ids:
            node = node.setdefault(str(token_id), {})
        node["$canonical_key"] = canonical_key
    return root


@lru_cache(maxsize=4)
def build_model_provenance(model_id: str, revision: str) -> dict[str, Any]:
    """Resolve the pinned local snapshot and hash configuration/tokenizer files."""
    try:
        from huggingface_hub import snapshot_download
        import bitsandbytes
        import torch
        import transformers
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(f"local semantic-screening dependency is missing: {exc}") from exc

    snapshot = Path(
        snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_files_only=True,
        )
    ).resolve()
    model_names = {
        "config.json",
        "generation_config.json",
        "model.safetensors.index.json",
    }
    tokenizer_names = {
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "merges.txt",
        "chat_template.jinja",
    }
    model_hashes = {
        path.relative_to(snapshot).as_posix(): sha256_file(path)
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and path.name in model_names
    }
    tokenizer_hashes = {
        path.relative_to(snapshot).as_posix(): sha256_file(path)
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and (path.name in tokenizer_names or path.name.startswith("tokenizer."))
    }
    if "config.json" not in model_hashes:
        raise RuntimeError(f"model snapshot lacks config.json: {snapshot}")
    if not tokenizer_hashes:
        raise RuntimeError(f"model snapshot lacks tokenizer files: {snapshot}")

    tokenizer = AutoTokenizer.from_pretrained(
        snapshot,
        local_files_only=True,
        trust_remote_code=False,
    )
    fused_path_token_ids: dict[str, dict[str, list[int]]] = {}
    fused_path_tries: dict[str, dict[str, Any]] = {}
    max_path_tokens = 0
    for evidence_basis, paths in FUSED_PATH_BY_CANONICAL_KEY.items():
        path_ids: dict[str, list[int]] = {}
        seen: set[tuple[int, ...]] = set()
        for canonical_key, path_surface in paths.items():
            token_ids = [
                int(value) for value in tokenizer.encode(path_surface, add_special_tokens=False)
            ]
            if len(token_ids) != len(path_surface.split()):
                raise RuntimeError(
                    f"each staged path word must be one context token: "
                    f"basis={evidence_basis} path={path_surface!r} ids={token_ids}"
                )
            if tuple(token_ids) in seen:
                raise RuntimeError(f"duplicate staged path: {path_surface}")
            seen.add(tuple(token_ids))
            path_ids[canonical_key] = token_ids
            max_path_tokens = max(max_path_tokens, len(token_ids))
        fused_path_token_ids[evidence_basis] = path_ids
        fused_path_tries[evidence_basis] = stage_path_trie(path_ids)
    stage_output_token_ids: dict[str, dict[str, int]] = {}
    for stage, outputs in MULTIPASS_STAGE_OPTIONS.items():
        token_map: dict[str, int] = {}
        for output in outputs:
            surface = MULTIPASS_OUTPUT_SURFACES[stage][output]
            token_ids = tokenizer.encode(surface, add_special_tokens=False)
            if len(token_ids) != 1:
                raise RuntimeError(
                    f"multipass output must be one token: stage={stage} output={output}"
                )
            token_map[output] = int(token_ids[0])
        if len(set(token_map.values())) != len(token_map):
            raise RuntimeError(f"multipass stage has duplicate token IDs: {stage}")
        stage_output_token_ids[stage] = token_map

    generation = {
        **GENERATION_CONFIG,
        "multipass_stage_options": MULTIPASS_STAGE_OPTIONS,
        "multipass_output_surfaces": MULTIPASS_OUTPUT_SURFACES,
        "stage_output_token_ids": stage_output_token_ids,
        "stage_output_token_ids_sha256": canonical_sha256(stage_output_token_ids),
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
    }
    cuda = {
        "available": bool(torch.cuda.is_available()),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "device_capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
        "bfloat16_supported": bool(torch.cuda.is_bf16_supported()) if torch.cuda.is_available() else False,
    }
    provenance = {
        "model_id": model_id,
        "model_revision": revision,
        "local_files_only": True,
        "snapshot_path": str(snapshot),
        "quantization_config": QUANTIZATION_CONFIG,
        "quantization_config_sha256": canonical_sha256(QUANTIZATION_CONFIG),
        "generation_config": generation,
        "generation_config_sha256": canonical_sha256(generation),
        "model_config_file_hashes": model_hashes,
        "model_config_files_sha256": canonical_sha256(model_hashes),
        "tokenizer_file_hashes": tokenizer_hashes,
        "tokenizer_files_sha256": canonical_sha256(tokenizer_hashes),
        "fused_path_token_ids": fused_path_token_ids,
        "fused_path_tries": fused_path_tries,
        "fused_path_tries_sha256": canonical_sha256(fused_path_tries),
        "stage_output_token_ids": stage_output_token_ids,
        "stage_output_token_ids_sha256": canonical_sha256(stage_output_token_ids),
        "software": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "bitsandbytes": bitsandbytes.__version__,
            "huggingface_hub": importlib.metadata.version("huggingface-hub"),
        },
        "cuda": cuda,
    }
    provenance["model_provenance_sha256"] = canonical_sha256(provenance)
    return provenance


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def assert_allowed_write(path: Path) -> None:
    resolved = path.resolve()
    if _is_relative_to(resolved, V5.resolve()):
        return
    logs = (ROOT / "research_v3" / "logs").resolve()
    if resolved.parent == logs and (
        resolved.name.startswith("v50_") or resolved.name.startswith(".v50_")
    ):
        return
    raise RuntimeError(f"refusing write outside v5/v50 logs: {resolved}")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    assert_allowed_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    assert_allowed_write(temporary)
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write_bytes(path, payload)


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    assert_allowed_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows]
    if not lines:
        return 0
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return len(lines)


DECISION_CSV_COLUMNS = (
    "record_id",
    "pmid",
    "question_id",
    "decision",
    "reason_codes",
    "confidence",
    "evidence_basis",
    "status",
    "batch_id",
    "screener",
    "execution_mode",
    "screened_at_utc",
    "prompt_sha256",
    "corpus_sha256",
    "ruleset_sha256",
    "inference_key",
    "fused_output",
    "fused_output_token_id",
    "stage_path",
    "stage_outputs",
    "inference_batch_size",
    "model_id",
    "model_revision",
    "quantization_config",
    "generation_config",
    "model_config_file_hashes",
    "tokenizer_file_hashes",
    "model_provenance_sha256",
    "input_truncated",
    "abstract_original_tokens",
    "abstract_retained_tokens",
    "max_input_tokens",
    "truncation_strategy",
    "batch_input_sha256",
    "batch_output_sha256",
)


def materialize_decisions_csv(checkpoint_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Write a sorted, one-row-per-checkpoint CSV without changing checkpoints."""
    question_rank = {question_id: index for index, question_id in enumerate(QUESTION_ORDER)}
    ordered = sorted(
        checkpoint_rows,
        key=lambda row: (
            question_rank.get(str(row.get("question_id", "")), len(QUESTION_ORDER)),
            str(row.get("record_id", "")),
            str(row.get("pmid", "")),
        ),
    )
    if len({(row.get("record_id"), row.get("question_id")) for row in ordered}) != len(ordered):
        raise RuntimeError("cannot materialize decisions.csv from duplicate checkpoint pairs")
    allowed_columns = set(DECISION_CSV_COLUMNS)
    for row in ordered:
        extra = sorted(set(row) - allowed_columns)
        missing = sorted(allowed_columns - set(row))
        if extra or missing:
            raise RuntimeError(
                f"checkpoint/decisions.csv schema mismatch for "
                f"{row.get('record_id')}/{row.get('question_id')}: "
                f"missing={missing} extra={extra}"
            )

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=DECISION_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in ordered:
        csv_row: dict[str, Any] = {}
        for column in DECISION_CSV_COLUMNS:
            value = row.get(column, "")
            if column in {
                "reason_codes",
                "quantization_config",
                "generation_config",
                "model_config_file_hashes",
                "tokenizer_file_hashes",
                "stage_outputs",
            }:
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            csv_row[column] = value
        writer.writerow(csv_row)
    atomic_write_bytes(DECISIONS_CSV, buffer.getvalue().encode("utf-8"))
    return {
        "path": repo_relative(DECISIONS_CSV),
        "rows": len(ordered),
        "sha256": sha256_file(DECISIONS_CSV),
        "sort": ["question_order", "record_id", "pmid"],
        "source": repo_relative(CHECKPOINTS),
    }


@contextmanager
def exclusive_lock() -> Iterator[None]:
    assert_allowed_write(LOCK_FILE)
    SCREENING.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{repo_relative(path)}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"{repo_relative(path)}:{line_number}: object required")
            rows.append(value)
    return rows


def _prompt_contract(prompt_text: str) -> tuple[set[str], set[str]]:
    label_section = prompt_text.split("## 라벨", 1)[-1].split("## 판정 원칙", 1)[0]
    reason_section = prompt_text.split("## 사유 코드", 1)[-1].split("## 출력 계약", 1)[0]
    labels = set(re.findall(r"^- `([^`]+)`:", label_section, flags=re.M))
    reasons = set(re.findall(r"^- `([^`]+)`\s*$", reason_section, flags=re.M))
    return labels, reasons


def machine_inference_contract(prompt_text: str | None = None) -> str:
    text = prompt_text if prompt_text is not None else PROMPT.read_text(encoding="utf-8")
    if MACHINE_CONTRACT_BEGIN not in text or MACHINE_CONTRACT_END not in text:
        raise RuntimeError("prompt lacks the machine-inference contract markers")
    contract = text.split(MACHINE_CONTRACT_BEGIN, 1)[1].split(MACHINE_CONTRACT_END, 1)[0].strip()
    required = (
        "FUSED_SYSTEM:", "FUSED_ABSTRACT_TASK:", "FUSED_TITLE_TASK:",
        "FUSED_ABSTRACT_CHOICES:", "FUSED_TITLE_CHOICES:", "FUSED_STAGE_TRACE:",
        "FUSED_ABSTRACT_PATHS:", "FUSED_TITLE_PATHS:",
        "STAGE_PRECLINICAL_ONLY_TASK:", "STAGE_QUESTION_EXPOSURE_TASK:",
        "STAGE_ROUTE_MISMATCH_TASK:",
        "STAGE_ATTRIBUTABLE_HARM_TASK:", "STAGE_HARM_PRESENT_TASK:",
        "STAGE_RETAIN_KIND_TASK:", "STAGE_MECHANISM_ONLY_TASK:",
        "STAGE_NONRETAIN_REASON_TASK:",
        "STAGE_TITLE_ONLY_TASK:",
        "STAGE_TITLE_ATTRIBUTABLE_HARM_TASK:", "STAGE_TITLE_EXPOSURE_TASK:",
    )
    missing = [value for value in required if value not in contract]
    if missing:
        raise RuntimeError(f"machine-inference contract is incomplete: {missing}")
    return contract


def _machine_contract_keys(contract: str, label: str) -> set[str]:
    prefix = f"{label}:"
    line = next((value for value in contract.splitlines() if value.startswith(prefix)), None)
    if line is None:
        raise RuntimeError(f"machine-inference contract lacks {label}")
    payload = line[len(prefix):].strip().removesuffix(".")
    values = [value.strip() for value in payload.split("|") if value.strip()]
    if len(values) != len(set(values)):
        raise RuntimeError(f"machine-inference contract duplicates {label} choices")
    return set(values)


def _machine_contract_paths(contract: str, label: str) -> set[str]:
    prefix = f"{label}:"
    line = next((value for value in contract.splitlines() if value.startswith(prefix)), None)
    if line is None:
        raise RuntimeError(f"machine-inference contract lacks {label}")
    values = [value.strip() for value in line[len(prefix):].strip().removesuffix(".").split("||")]
    if len(values) != len(set(values)):
        raise RuntimeError(f"machine-inference contract duplicates {label} paths")
    return set(values)


def verify_prompt_contract() -> str:
    if not PROMPT.exists():
        raise RuntimeError(f"missing frozen-source prompt: {repo_relative(PROMPT)}")
    text = PROMPT.read_text(encoding="utf-8")
    labels, reasons = _prompt_contract(text)
    if labels != DECISIONS:
        raise RuntimeError(f"prompt label vocabulary changed: {sorted(labels)}")
    if reasons != REASON_CODES:
        missing = sorted(REASON_CODES - reasons)
        extra = sorted(reasons - REASON_CODES)
        raise RuntimeError(f"prompt reason vocabulary changed: missing={missing} extra={extra}")
    contract = machine_inference_contract(text)
    abstract_keys = _machine_contract_keys(contract, "FUSED_ABSTRACT_CHOICES")
    title_keys = _machine_contract_keys(contract, "FUSED_TITLE_CHOICES")
    if abstract_keys != set(FUSED_ALLOWED_OUTPUTS["abstract"]):
        raise RuntimeError(
            f"prompt abstract output-key contract changed: {sorted(abstract_keys)}"
        )
    if title_keys != set(FUSED_ALLOWED_OUTPUTS["title_only"]):
        raise RuntimeError(
            f"prompt title-only output-key contract changed: {sorted(title_keys)}"
        )
    abstract_paths = _machine_contract_paths(contract, "FUSED_ABSTRACT_PATHS")
    title_paths = _machine_contract_paths(contract, "FUSED_TITLE_PATHS")
    if abstract_paths != set(FUSED_PATH_BY_CANONICAL_KEY["abstract"].values()):
        raise RuntimeError("prompt abstract staged-path contract changed")
    if title_paths != set(FUSED_PATH_BY_CANONICAL_KEY["title_only"].values()):
        raise RuntimeError("prompt title-only staged-path contract changed")
    return sha256_file(PROMPT)


def freeze_prompt(
    model_id: str = DEFAULT_MODEL_ID,
    model_revision: str = DEFAULT_MODEL_REVISION,
) -> dict[str, Any]:
    source_sha = verify_prompt_contract()
    source_bytes = PROMPT.read_bytes()
    model_provenance = build_model_provenance(model_id, model_revision)
    with exclusive_lock():
        if PROMPT_LOCK.exists():
            lock = load_json(PROMPT_LOCK)
            if lock.get("prompt_sha256") != source_sha:
                raise RuntimeError("screening prompt changed after freeze; formal pilot discard is required")
            if not FROZEN_PROMPT.exists() or sha256_file(FROZEN_PROMPT) != source_sha:
                raise RuntimeError("frozen prompt snapshot is missing or does not match its lock")
            if lock.get("model_provenance_sha256") != model_provenance["model_provenance_sha256"]:
                raise RuntimeError("model provenance differs from the frozen screening lock")
            return lock
        atomic_write_bytes(FROZEN_PROMPT, source_bytes)
        lock = {
            "schema_version": "1.0.0",
            "frozen_at_utc": utc_now(),
            "source_path": repo_relative(PROMPT),
            "frozen_path": repo_relative(FROZEN_PROMPT),
            "prompt_sha256": source_sha,
            "decision_vocabulary": sorted(DECISIONS),
            "reason_code_vocabulary": sorted(REASON_CODES),
            "confidence_vocabulary": sorted(CONFIDENCES),
            "evidence_basis_vocabulary": ["abstract", "title_only"],
            "execution_mode": EXECUTION_MODE,
            "machine_inference_contract_sha256": sha256_bytes(
                machine_inference_contract(source_bytes.decode("utf-8")).encode("utf-8")
            ),
            "model_id": model_id,
            "model_revision": model_revision,
            "quantization_config": model_provenance["quantization_config"],
            "generation_config": model_provenance["generation_config"],
            "model_config_file_hashes": model_provenance["model_config_file_hashes"],
            "tokenizer_file_hashes": model_provenance["tokenizer_file_hashes"],
            "model_provenance": model_provenance,
            "model_provenance_sha256": model_provenance["model_provenance_sha256"],
            "human_decisions": 0,
        }
        atomic_write_json(PROMPT_LOCK, lock)
        return lock


def assert_prompt_unchanged(
    model_id: str | None = None,
    model_revision: str | None = None,
) -> dict[str, Any]:
    if not PROMPT_LOCK.exists():
        raise RuntimeError(
            "screening prompt is not frozen; run the explicit freeze command before run/status"
        )
    lock = load_json(PROMPT_LOCK)
    current_sha = verify_prompt_contract()
    expected = lock.get("prompt_sha256")
    if current_sha != expected:
        raise RuntimeError(f"screening prompt changed during main screening: {expected} -> {current_sha}")
    if not FROZEN_PROMPT.exists() or sha256_file(FROZEN_PROMPT) != expected:
        raise RuntimeError("frozen prompt snapshot mismatch")
    locked_model_id = str(lock.get("model_id", ""))
    locked_revision = str(lock.get("model_revision", ""))
    if model_id is not None and model_id != locked_model_id:
        raise RuntimeError(f"model ID differs from frozen lock: {locked_model_id} != {model_id}")
    if model_revision is not None and model_revision != locked_revision:
        raise RuntimeError(
            f"model revision differs from frozen lock: {locked_revision} != {model_revision}"
        )
    current_provenance = build_model_provenance(locked_model_id, locked_revision)
    if current_provenance["model_provenance_sha256"] != lock.get("model_provenance_sha256"):
        raise RuntimeError("local model config/tokenizer provenance changed after freeze")
    return lock


def load_question_order() -> tuple[str, ...]:
    if not QUERY_DEFINITIONS.exists():
        raise RuntimeError(f"missing query definitions: {repo_relative(QUERY_DEFINITIONS)}")
    payload = load_json(QUERY_DEFINITIONS)
    observed = tuple(row.get("question_id", "") for row in payload.get("questions", []))
    if observed != QUESTION_ORDER:
        raise RuntimeError(f"question order mismatch: {observed}")
    return observed


def split_memberships(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("question_ids JSON must be an array")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in re.split(r"[;,|]", raw) if item.strip()]


def load_corpus() -> tuple[list[dict[str, str]], str]:
    if not CORPUS.exists():
        raise RuntimeError(f"missing Phase B corpus: {repo_relative(CORPUS)}")
    with CORPUS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"record_id", "pmid", "title", "abstract", "question_ids"}
    fields = set(rows[0]) if rows else set()
    missing = sorted(required - fields)
    if missing:
        raise RuntimeError(f"evidence_map.csv missing columns: {missing}")
    seen_records: set[str] = set()
    known = set(QUESTION_ORDER)
    for index, row in enumerate(rows, start=2):
        record_id = row.get("record_id", "").strip()
        if not record_id:
            raise RuntimeError(f"evidence_map.csv:{index}: empty record_id")
        if record_id in seen_records:
            raise RuntimeError(f"duplicate record_id in corpus: {record_id}")
        seen_records.add(record_id)
        memberships = split_memberships(row.get("question_ids", ""))
        if not memberships:
            raise RuntimeError(f"{record_id}: no question membership")
        unknown = sorted(set(memberships) - known)
        if unknown:
            raise RuntimeError(f"{record_id}: unknown question memberships {unknown}")
        if len(memberships) != len(set(memberships)):
            raise RuntimeError(f"{record_id}: duplicate question membership")
        row["_question_ids"] = json.dumps(memberships, ensure_ascii=False)
    return rows, sha256_file(CORPUS)


def question_rows(corpus: Sequence[dict[str, str]], question_id: str) -> list[dict[str, str]]:
    rows = [row for row in corpus if question_id in json.loads(row["_question_ids"])]
    return sorted(rows, key=lambda row: (row["record_id"], row.get("pmid", "")))


def checkpoint_index(
    rows: Sequence[dict[str, Any]], prompt_sha: str, corpus_sha: str
) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    expected_model_sha = (
        load_json(PROMPT_LOCK).get("model_provenance_sha256") if PROMPT_LOCK.exists() else None
    )
    for line_number, row in enumerate(rows, start=1):
        if row.get("prompt_sha256") != prompt_sha:
            raise RuntimeError(f"checkpoints.jsonl:{line_number}: prompt hash mismatch")
        if row.get("corpus_sha256") != corpus_sha:
            raise RuntimeError(f"checkpoints.jsonl:{line_number}: corpus hash mismatch")
        if row.get("model_provenance_sha256") != expected_model_sha:
            raise RuntimeError(f"checkpoints.jsonl:{line_number}: model provenance mismatch")
        key = (str(row.get("record_id", "")), str(row.get("question_id", "")))
        if key in index:
            raise RuntimeError(f"duplicate screening checkpoint pair: {key}")
        validate_decision(row, key)
        index[key] = row
    return index


def validate_decision(row: dict[str, Any], key: tuple[str, str]) -> None:
    decision = row.get("decision")
    confidence = row.get("confidence")
    basis = row.get("evidence_basis")
    reasons = row.get("reason_codes")
    if decision not in DECISIONS:
        raise RuntimeError(f"{key}: invalid decision {decision!r}")
    if confidence not in CONFIDENCES:
        raise RuntimeError(f"{key}: invalid confidence {confidence!r}")
    if basis not in {"abstract", "title_only"}:
        raise RuntimeError(f"{key}: invalid evidence_basis {basis!r}")
    if not isinstance(reasons, list) or not 1 <= len(reasons) <= 3:
        raise RuntimeError(f"{key}: reason_codes must contain 1-3 values")
    unknown = sorted(set(reasons) - REASON_CODES)
    if unknown:
        raise RuntimeError(f"{key}: unknown reason_codes {unknown}")
    if basis == "title_only":
        if confidence != "low" or not set(reasons).intersection(TITLE_ONLY_CODES):
            raise RuntimeError(f"{key}: title_only requires low confidence and title_only reason")
    elif set(reasons).intersection(TITLE_ONLY_CODES):
        raise RuntimeError(f"{key}: abstract decision uses a title_only reason")
    inference_key = row.get("inference_key")
    if inference_key is not None:
        expected = OUTPUT_KEYBOOK.get(str(inference_key))
        if expected is None:
            raise RuntimeError(f"{key}: invalid inference_key {inference_key!r}")
        for field in ("decision", "confidence"):
            if row.get(field) != expected[field]:
                raise RuntimeError(f"{key}: inference_key {inference_key} disagrees with {field}")
        expected_reasons = list(expected["reason_codes"])
        allowed_reasons = [expected_reasons]
        if expected["decision"] == "retain":
            allowed_reasons.append(expected_reasons + ["case_report_relevant"])
        if row.get("reason_codes") not in allowed_reasons:
            raise RuntimeError(
                f"{key}: inference_key {inference_key} disagrees with reason_codes"
            )
    fused_output = row.get("fused_output")
    if fused_output is not None:
        trace = row.get("stage_outputs")
        if not isinstance(trace, dict) or not trace:
            raise RuntimeError(f"{key}: stage_outputs must be a non-empty object")
        expected_path = ";".join(f"{stage}={answer}" for stage, answer in trace.items())
        if row.get("stage_path") != expected_path:
            raise RuntimeError(f"{key}: stage_path does not serialize stage_outputs")
        if basis == "title_only":
            if trace.get("title_attributable_harm") == "yes":
                replayed = "title_retain"
            elif trace.get("title_question_exposure") == "no":
                replayed = "title_off_topic"
            else:
                replayed = "title_uncertain"
        elif trace.get("preclinical_only") == "yes":
            replayed = "animal_or_in_vitro_only"
        elif trace.get("preclinical_only") == "maybe":
            replayed = "uncertain_low"
        elif any(trace.get(stage) == "maybe" for stage in (
            "question_exposure", "route_mismatch", "population_mismatch",
            "attributable_human_harm", "harm_outcome_present", "mechanism_only",
        )):
            replayed = "uncertain_medium"
        elif trace.get("route_mismatch") == "yes":
            replayed = "route_mismatch"
        elif trace.get("population_mismatch") == "yes":
            replayed = "population_mismatch"
        elif "retain_kind" in trace:
            replayed = {"direct": "retain_direct_high", "class": "retain_class_high", "maybe": "uncertain_medium"}.get(trace["retain_kind"])
        elif "mechanism_only" in trace:
            replayed = "mechanism_or_assay_only" if trace["mechanism_only"] == "yes" else "exposure_only"
        elif "harm_outcome_present" in trace:
            replayed = "outcome_only" if trace["harm_outcome_present"] == "yes" else "off_topic"
        else:
            replayed = {
                "use": "exposure_only", "method": "mechanism_or_assay_only",
                "route": "route_mismatch", "population": "population_mismatch",
                "outcome": "outcome_only", "other": "off_topic", "maybe": "uncertain_medium",
            }.get(trace.get("nonretain_reason"))
        if replayed != inference_key:
            raise RuntimeError(f"{key}: stage_outputs replay disagrees with inference_key")


def evidence_basis_for(row: dict[str, str]) -> str:
    abstract = (row.get("abstract") or "").strip()
    declared = (row.get("has_abstract") or "").strip().lower()
    return "abstract" if abstract and declared not in {"false", "0", "no"} else "title_only"


def _explicit_case_report(row: dict[str, str]) -> bool:
    publication_types = (row.get("publication_types") or "").lower()
    narrative = " ".join(
        ((row.get("title") or ""), (row.get("abstract") or ""))
    ).lower()
    return (
        "case report" in publication_types
        or "case report" in narrative
        or "we report a case" in narrative
    )


def decision_from_key(
    inference_key: str,
    evidence_basis: str,
    key: tuple[str, str],
    source_row: dict[str, str],
) -> dict[str, Any]:
    if inference_key not in OUTPUT_KEYBOOK:
        raise RuntimeError(f"{key}: local model returned an unknown output key {inference_key!r}")
    if evidence_basis == "abstract" and inference_key not in ABSTRACT_OUTPUT_KEYS:
        raise RuntimeError(f"{key}: abstract row returned title-only key {inference_key}")
    if evidence_basis == "title_only" and inference_key not in TITLE_ONLY_OUTPUT_KEYS:
        raise RuntimeError(f"{key}: title-only row returned abstract key {inference_key}")
    result = {
        **OUTPUT_KEYBOOK[inference_key],
        "evidence_basis": evidence_basis,
        "inference_key": inference_key,
    }
    if result["decision"] == "retain" and _explicit_case_report(source_row):
        result["reason_codes"] = [*result["reason_codes"], "case_report_relevant"]
    validate_decision(result, key)
    return result


def ruleset_sha256() -> str:
    return canonical_sha256(
        {
            "execution_mode": EXECUTION_MODE,
            "question_criteria": QUESTION_CRITERIA,
            "salient_term_patterns": SALIENT_TERM_PATTERNS,
            "direct_name_patterns": DIRECT_NAME_PATTERNS,
            "direct_relation_pattern": DIRECT_RELATION_PATTERN.pattern,
            "explicit_exposure_patterns": EXPLICIT_EXPOSURE_PATTERNS,
            "q04_nonexposure_context": Q04_NONEXPOSURE_CONTEXT.pattern,
            "negated_exposure_context": NEGATED_EXPOSURE_CONTEXT.pattern,
            "output_keybook": OUTPUT_KEYBOOK,
            "retain_gate": [
                "question exposure present",
                "safety or harm outcome attributable to that exposure",
                "human clinical/case/pharmacovigilance/human-evidence review",
            ],
            "retain_forbidden": [
                "efficacy only",
                "pharmacokinetics only",
                "mere co-mention",
                "human cell or in-vitro only",
            ],
        }
    )


class LocalSemanticScreener:
    """Pinned Qwen screener using one fused semantic forward and masked logits."""

    def __init__(self, model_id: str, model_revision: str, inference_batch_size: int) -> None:
        if inference_batch_size <= 0:
            raise RuntimeError("inference_batch_size must be positive")
        self.model_id = model_id
        self.model_revision = model_revision
        self.inference_batch_size = inference_batch_size
        self.provenance = build_model_provenance(model_id, model_revision)
        self._model: Any = None
        self._tokenizer: Any = None
        self._contract_cache: dict[str, str] | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as exc:
            raise RuntimeError(f"local semantic-screening dependency is missing: {exc}") from exc
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("CUDA with bfloat16 support is required for local screening")
        snapshot = self.provenance["snapshot_path"]
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot, local_files_only=True, trust_remote_code=False, padding_side="left"
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
        model = AutoModelForCausalLM.from_pretrained(
            snapshot,
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            dtype=torch.bfloat16,
            device_map={"": 0},
            low_cpu_mem_usage=True,
            attn_implementation="sdpa",
        )
        model.eval()
        model.generation_config.do_sample = False
        model.generation_config.temperature = None
        model.generation_config.top_p = None
        model.generation_config.top_k = None
        self._tokenizer = tokenizer
        self._model = model

    def _contract_value(self, label: str) -> str:
        if self._contract_cache is None:
            prompt_path = FROZEN_PROMPT if FROZEN_PROMPT.exists() else PROMPT
            contract = machine_inference_contract(prompt_path.read_text(encoding="utf-8"))
            self._contract_cache = {
                line.split(":", 1)[0]: line.split(":", 1)[1].strip()
                for line in contract.splitlines() if ":" in line
            }
        value = self._contract_cache.get(label)
        if value is None:
            raise RuntimeError(f"machine-inference contract lacks {label}")
        return value

    def _render_text(
        self, row: dict[str, str], question_id: str, abstract_text: str, task_label: str
    ) -> str:
        assert self._tokenizer is not None
        basis = evidence_basis_for(row)
        salient = self._salient_context(abstract_text, question_id) if basis == "abstract" else ""
        scope_text = (
            "The question exposure was already classified absent; evaluate any human safety result."
            if task_label == "STAGE_HARM_PRESENT_TASK"
            else QUESTION_CRITERIA[question_id]
        )
        user_text = (
            f"SCOPE: {scope_text}\n"
            f"TITLE: {(row.get('title') or '').strip()}\n"
            f"ABSTRACT: {abstract_text}\n"
            f"VERBATIM_TERM_CONTEXT: {salient}\n"
            f"PUBLICATION_TYPES: {(row.get('publication_types') or '').strip()}\n"
            f"MESH: {(row.get('mesh_terms') or '').strip()}\n"
            f"TASK: {self._contract_value(task_label)}\n"
            "ANSWER:"
        )
        messages = [
            {"role": "system", "content": self._contract_value("FUSED_SYSTEM")},
            {"role": "user", "content": user_text},
        ]
        return self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    @staticmethod
    def _salient_context(abstract_text: str, question_id: str) -> str:
        """Repeat a few verbatim target-term sentences for visibility after truncation.

        Selection is input construction only.  The semantic model still decides
        whether the mentioned term is an administered exposure or an unrelated
        assay, endogenous enzyme, inhibitor, or negated exposure.
        """
        if not abstract_text or abstract_text == "(no abstract)":
            return ""
        pattern = re.compile(SALIENT_TERM_PATTERNS[question_id])
        candidates: list[tuple[int, int, str]] = []
        for position, sentence in enumerate(re.split(r"(?<=[.!?])\s+", abstract_text)):
            sentence = " ".join(sentence.split())
            if not sentence or not pattern.search(sentence):
                continue
            score = 2 if EXPOSURE_ACTION_PATTERN.search(sentence) else 1
            candidates.append((-score, position, sentence))
        selected = sorted(candidates)[:3]
        return " ".join(item[2] for item in sorted(selected, key=lambda item: item[1]))[:1200]

    def _render(self, row: dict[str, str], question_id: str) -> tuple[str, dict[str, Any]]:
        assert self._tokenizer is not None
        basis = evidence_basis_for(row)
        abstract = (row.get("abstract") or "").strip() if basis == "abstract" else "(no abstract)"
        original_ids = self._tokenizer.encode(abstract, add_special_tokens=False)
        task_labels = (
            (
                "STAGE_PRECLINICAL_ONLY_TASK", "STAGE_QUESTION_EXPOSURE_TASK",
                "STAGE_ROUTE_MISMATCH_TASK",
                "STAGE_ATTRIBUTABLE_HARM_TASK", "STAGE_HARM_PRESENT_TASK",
                "STAGE_RETAIN_KIND_TASK", "STAGE_MECHANISM_ONLY_TASK",
                "STAGE_NONRETAIN_REASON_TASK",
            )
            if basis == "abstract" else (
                "STAGE_TITLE_ATTRIBUTABLE_HARM_TASK", "STAGE_TITLE_EXPOSURE_TASK",
            )
        )

        def max_rendered_tokens(value: str) -> int:
            return max(
                len(self._tokenizer.encode(
                    self._render_text(row, question_id, value, task_label),
                    add_special_tokens=False,
                ))
                for task_label in task_labels
            )

        metadata = {
            "input_truncated": False,
            "abstract_original_tokens": len(original_ids) if basis == "abstract" else 0,
            "abstract_retained_tokens": len(original_ids) if basis == "abstract" else 0,
            "max_input_tokens": MAX_INPUT_TOKENS,
            "truncation_strategy": "none",
        }
        actual = max_rendered_tokens(abstract)
        if actual <= MAX_INPUT_TOKENS:
            return abstract, metadata
        if basis != "abstract":
            raise RuntimeError(f"title/metadata exceed {MAX_INPUT_TOKENS} tokens for {row['record_id']}")
        overhead = max_rendered_tokens("")
        marker = "\n[...abstract middle omitted...]\n"
        marker_tokens = len(self._tokenizer.encode(marker, add_special_tokens=False))
        keep = MAX_INPUT_TOKENS - overhead - marker_tokens - 12
        while keep >= 2:
            head_count = (keep + 1) // 2
            tail_count = keep // 2
            head = self._tokenizer.decode(original_ids[:head_count], skip_special_tokens=True)
            tail = self._tokenizer.decode(original_ids[-tail_count:], skip_special_tokens=True)
            shortened = head.rstrip() + marker + tail.lstrip()
            actual = max_rendered_tokens(shortened)
            if actual <= MAX_INPUT_TOKENS:
                metadata.update({
                    "input_truncated": True,
                    "abstract_retained_tokens": head_count + tail_count,
                    "truncation_strategy": TRUNCATION_STRATEGY,
                })
                return shortened, metadata
            keep -= max(8, actual - MAX_INPUT_TOKENS + 4)
        raise RuntimeError(f"unable to fit deterministic input for {row['record_id']}")

    def infer(self, rows: Sequence[dict[str, str]], question_id: str) -> list[dict[str, Any]]:
        if not rows:
            return []
        self._ensure_loaded()
        assert self._tokenizer is not None and self._model is not None
        import torch

        prepared: dict[int, tuple[dict[str, str], str, dict[str, Any]]] = {}
        for index, row in enumerate(rows):
            abstract_text, truncation = self._render(row, question_id)
            prepared[index] = (row, abstract_text, truncation)

        task_labels = {
            "preclinical_only": "STAGE_PRECLINICAL_ONLY_TASK",
            "question_exposure": "STAGE_QUESTION_EXPOSURE_TASK",
            "route_mismatch": "STAGE_ROUTE_MISMATCH_TASK",
            "attributable_human_harm": "STAGE_ATTRIBUTABLE_HARM_TASK",
            "harm_outcome_present": "STAGE_HARM_PRESENT_TASK",
            "retain_kind": "STAGE_RETAIN_KIND_TASK",
            "mechanism_only": "STAGE_MECHANISM_ONLY_TASK",
            "nonretain_reason": "STAGE_NONRETAIN_REASON_TASK",
            "title_only": "STAGE_TITLE_ONLY_TASK",
            "title_attributable_harm": "STAGE_TITLE_ATTRIBUTABLE_HARM_TASK",
            "title_question_exposure": "STAGE_TITLE_EXPOSURE_TASK",
        }
        token_maps = self.provenance["stage_output_token_ids"]

        def run_stage(stage: str, indices: Sequence[int]) -> dict[int, str]:
            rendered_items: list[tuple[int, str, int]] = []
            for index in indices:
                row, abstract_text, _ = prepared[index]
                rendered = self._render_text(
                    row, question_id, abstract_text, task_labels[stage]
                )
                token_length = len(self._tokenizer.encode(rendered, add_special_tokens=False))
                rendered_items.append((index, rendered, token_length))
            rendered_items.sort(key=lambda value: (value[2], prepared[value[0]][0]["record_id"]))
            answers: dict[int, str] = {}
            choices = MULTIPASS_STAGE_OPTIONS[stage]
            candidate_ids = [int(token_maps[stage][choice]) for choice in choices]
            for start in range(0, len(rendered_items), self.inference_batch_size):
                chunk = rendered_items[start:start + self.inference_batch_size]
                encoded = self._tokenizer(
                    [item[1] for item in chunk],
                    return_tensors="pt", padding=True, truncation=False,
                    add_special_tokens=False,
                )
                if int(encoded["input_ids"].shape[1]) > MAX_INPUT_TOKENS:
                    raise RuntimeError("deterministic multipass input limit failed")
                encoded = encoded.to(self._model.device)
                with torch.inference_mode():
                    logits = self._model(
                        **encoded, use_cache=False, logits_to_keep=1
                    ).logits[:, -1, :]
                selected = torch.argmax(logits[:, candidate_ids], dim=1).detach().cpu().tolist()
                for item, selected_index in zip(chunk, selected, strict=True):
                    answers[item[0]] = choices[int(selected_index)]
            return answers

        traces: dict[int, dict[str, str]] = {index: {} for index in prepared}
        terminal: dict[int, tuple[str, str]] = {}

        title_indices = [
            index for index, (row, _, _) in prepared.items()
            if evidence_basis_for(row) == "title_only"
        ]
        title_harm = run_stage("title_attributable_harm", title_indices)
        title_exposure_pending: list[int] = []
        for index, answer in title_harm.items():
            traces[index]["title_attributable_harm"] = answer
            if answer == "yes":
                terminal[index] = ("title_retain", "retain")
            else:
                title_exposure_pending.append(index)
        for index, answer in run_stage("title_question_exposure", title_exposure_pending).items():
            traces[index]["title_question_exposure"] = answer
            if answer == "no":
                terminal[index] = ("title_off_topic", "other")
            else:
                terminal[index] = ("title_uncertain", "maybe")

        abstract_indices = [
            index for index, (row, _, _) in prepared.items()
            if evidence_basis_for(row) == "abstract"
        ]
        preclinical = run_stage("preclinical_only", abstract_indices)
        exposure_pending: list[int] = []
        for index, answer in preclinical.items():
            traces[index]["preclinical_only"] = answer
            if answer == "yes":
                terminal[index] = ("animal_or_in_vitro_only", "animal")
            elif answer == "maybe":
                terminal[index] = ("uncertain_low", "maybe")
            else:
                exposure_pending.append(index)

        exposure = run_stage("question_exposure", exposure_pending)
        route_pending: list[int] = []
        outcome_pending: list[int] = []
        for index, answer in exposure.items():
            row = prepared[index][0]
            resolved_answer = (
                "yes"
                if answer == "no" and has_explicit_question_exposure(row, question_id)
                else answer
            )
            traces[index]["question_exposure_model"] = answer
            traces[index]["question_exposure"] = resolved_answer
            if resolved_answer == "yes":
                route_pending.append(index)
            elif resolved_answer == "no":
                outcome_pending.append(index)
            else:
                terminal[index] = ("uncertain_medium", "maybe")

        route_answers = run_stage("route_mismatch", route_pending)
        attributable_pending: list[int] = []
        for index, answer in route_answers.items():
            traces[index]["route_mismatch"] = answer
            if answer == "yes":
                terminal[index] = ("route_mismatch", "route")
            elif answer == "no":
                attributable_pending.append(index)
            else:
                terminal[index] = ("uncertain_medium", "maybe")

        attributable = run_stage("attributable_human_harm", attributable_pending)
        retain_pending: list[int] = []
        for index, answer in attributable.items():
            traces[index]["attributable_human_harm"] = answer
            if answer == "yes":
                retain_pending.append(index)
            elif answer == "no":
                terminal[index] = ("exposure_only", "use")
            else:
                terminal[index] = ("uncertain_medium", "maybe")

        harm_present = run_stage("harm_outcome_present", outcome_pending)
        for index, answer in harm_present.items():
            traces[index]["harm_outcome_present"] = answer
            if answer == "maybe":
                terminal[index] = ("uncertain_medium", "maybe")
            elif answer == "yes":
                terminal[index] = ("outcome_only", "outcome")
            else:
                terminal[index] = ("off_topic", "other")

        retain_kind = run_stage("retain_kind", retain_pending)
        for index, answer in retain_kind.items():
            row = prepared[index][0]
            resolved_answer = resolve_retain_kind(row, question_id, answer)
            traces[index]["retain_kind_model"] = answer
            traces[index]["retain_kind"] = resolved_answer
            if resolved_answer == "direct":
                terminal[index] = ("retain_direct_high", resolved_answer)
            elif resolved_answer == "class":
                terminal[index] = ("retain_class_high", resolved_answer)
            else:
                terminal[index] = ("uncertain_medium", "maybe")

        decisions: list[dict[str, Any]] = []
        for index in range(len(rows)):
            row, _, truncation = prepared[index]
            basis = evidence_basis_for(row)
            inference_key, final_output = terminal[index]
            terminal_stage = next(reversed(traces[index]))
            token_id = int(token_maps[terminal_stage][traces[index][terminal_stage]])
            decisions.append({
                **decision_from_key(inference_key, basis, (row["record_id"], question_id), row),
                "fused_output": final_output,
                "fused_output_token_id": token_id,
                "stage_path": ";".join(f"{stage}={answer}" for stage, answer in traces[index].items()),
                "stage_outputs": traces[index],
                **truncation,
            })
        return decisions


def coverage_snapshot(
    corpus: Sequence[dict[str, str]], decisions: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for question_id in QUESTION_ORDER:
        requested = question_rows(corpus, question_id)
        found = [decisions[(row["record_id"], question_id)] for row in requested if (row["record_id"], question_id) in decisions]
        total = len(requested)
        screened = len(found)
        result[question_id] = {
            "total_memberships": total,
            "screened_memberships": screened,
            "remaining_memberships": total - screened,
            "coverage": screened / total if total else 1.0,
            "complete": screened == total,
            "decision_distribution": dict(sorted(Counter(row["decision"] for row in found).items())),
            "confidence_distribution": dict(sorted(Counter(row["confidence"] for row in found).items())),
            "evidence_basis_distribution": dict(sorted(Counter(row["evidence_basis"] for row in found).items())),
        }
    return result


def assert_question_gate(question_id: str, snapshot: dict[str, dict[str, Any]]) -> None:
    index = QUESTION_ORDER.index(question_id)
    incomplete = [qid for qid in QUESTION_ORDER[:index] if not snapshot[qid]["complete"]]
    if incomplete:
        raise RuntimeError(f"question-order gate blocked {question_id}; incomplete predecessors={incomplete}")
    illegally_started = [
        qid for qid in QUESTION_ORDER[index + 1 :] if snapshot[qid]["screened_memberships"] > 0
    ]
    if illegally_started and not snapshot[question_id]["complete"]:
        raise RuntimeError(f"later questions already started before {question_id} completed: {illegally_started}")


def write_progress(
    corpus: Sequence[dict[str, str]], corpus_sha: str, prompt_sha: str,
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    model_provenance = load_json(PROMPT_LOCK)["model_provenance"]
    questions = coverage_snapshot(corpus, decisions)
    completed = sum(1 for value in questions.values() if value["complete"])
    active = next((qid for qid in QUESTION_ORDER if not questions[qid]["complete"]), None)
    decision_rows = list(decisions.values())
    payload = {
        "schema_version": "5.0.0",
        "updated_at_utc": utc_now(),
        "phase": "C",
        "execution_mode": EXECUTION_MODE,
        "prompt_sha256": prompt_sha,
        "ruleset_sha256": ruleset_sha256(),
        "model_provenance": model_provenance,
        "model_provenance_sha256": model_provenance["model_provenance_sha256"],
        "corpus_path": repo_relative(CORPUS),
        "corpus_sha256": corpus_sha,
        "question_order": list(QUESTION_ORDER),
        "questions_completed": completed,
        "active_question": active,
        "questions": questions,
        "input_truncation": {
            "max_input_tokens": MAX_INPUT_TOKENS,
            "strategy": TRUNCATION_STRATEGY,
            "screened_rows": len(decision_rows),
            "truncated_rows": sum(bool(row.get("input_truncated")) for row in decision_rows),
        },
        "all_questions_complete": completed == len(QUESTION_ORDER),
        "human_decisions": 0,
        "independent_blinding": False,
        "release_ready": False,
    }
    atomic_write_json(PROGRESS, payload)
    return payload


def write_manifest(
    corpus: Sequence[dict[str, str]], corpus_sha: str, prompt_sha: str,
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    model_provenance = load_json(PROMPT_LOCK)["model_provenance"]
    questions = coverage_snapshot(corpus, decisions)
    batches = read_jsonl(BATCHES)
    committed = [row for row in batches if row.get("event") == "committed"]
    prepared_ids = {row.get("batch_id") for row in batches if row.get("event") == "prepared"}
    committed_ids = {row.get("batch_id") for row in committed}
    all_rows = list(decisions.values())
    decisions_csv = materialize_decisions_csv(all_rows)
    reason_counter: Counter[str] = Counter()
    for row in all_rows:
        reason_counter.update(row["reason_codes"])
    total_pairs = sum(value["total_memberships"] for value in questions.values())
    screened_pairs = len(decisions)
    payload = {
        "schema_version": "5.0.0",
        "updated_at_utc": utc_now(),
        "phase": "C",
        "execution_mode": EXECUTION_MODE,
        "semantic_llm_screening": True,
        "deterministic_generation": True,
        "prompt_path": repo_relative(PROMPT),
        "frozen_prompt_path": repo_relative(FROZEN_PROMPT),
        "prompt_sha256": prompt_sha,
        "ruleset_sha256": ruleset_sha256(),
        "model_provenance": model_provenance,
        "model_provenance_sha256": model_provenance["model_provenance_sha256"],
        "input_path": repo_relative(CORPUS),
        "input_sha256": corpus_sha,
        "checkpoint_path": repo_relative(CHECKPOINTS),
        "checkpoint_sha256": sha256_file(CHECKPOINTS) if CHECKPOINTS.exists() else None,
        "decisions_csv_path": decisions_csv["path"],
        "decisions_csv_sha256": decisions_csv["sha256"],
        "decisions_csv_rows": decisions_csv["rows"],
        "decisions_csv_materialization": decisions_csv,
        "batches_path": repo_relative(BATCHES),
        "batches_sha256": sha256_file(BATCHES) if BATCHES.exists() else None,
        "question_order": list(QUESTION_ORDER),
        "questions": questions,
        "total_memberships": total_pairs,
        "screened_memberships": screened_pairs,
        "coverage": screened_pairs / total_pairs if total_pairs else 1.0,
        "decision_distribution": dict(sorted(Counter(row["decision"] for row in all_rows).items())),
        "confidence_distribution": dict(sorted(Counter(row["confidence"] for row in all_rows).items())),
        "evidence_basis_distribution": dict(sorted(Counter(row["evidence_basis"] for row in all_rows).items())),
        "reason_code_distribution": dict(sorted(reason_counter.items())),
        "input_truncation": {
            "max_input_tokens": MAX_INPUT_TOKENS,
            "strategy": TRUNCATION_STRATEGY,
            "screened_rows": len(all_rows),
            "truncated_rows": sum(bool(row.get("input_truncated")) for row in all_rows),
        },
        "batch_events": len(batches),
        "committed_batches": len(committed),
        "interrupted_batch_ids": sorted(str(value) for value in prepared_ids - committed_ids),
        "append_only_checkpoints": True,
        "append_only_batches": True,
        "run_complete": all(value["complete"] for value in questions.values()),
        "human_decisions": 0,
        "release_ready": False,
    }
    atomic_write_json(MANIFEST, payload)
    return payload


def _decision_core(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": row["record_id"],
        "question_id": row["question_id"],
        "decision": row["decision"],
        "reason_codes": row["reason_codes"],
        "confidence": row["confidence"],
        "evidence_basis": row["evidence_basis"],
        "inference_key": row["inference_key"],
        "fused_output": row["fused_output"],
        "fused_output_token_id": row["fused_output_token_id"],
        "stage_path": row["stage_path"],
        "stage_outputs": row["stage_outputs"],
        "input_truncated": row["input_truncated"],
        "abstract_original_tokens": row["abstract_original_tokens"],
        "abstract_retained_tokens": row["abstract_retained_tokens"],
        "max_input_tokens": row["max_input_tokens"],
        "truncation_strategy": row["truncation_strategy"],
    }


def provenance_audit_fields(
    provenance: dict[str, Any], inference_batch_size: int
) -> dict[str, Any]:
    return {
        "inference_batch_size": inference_batch_size,
        "model_id": provenance["model_id"],
        "model_revision": provenance["model_revision"],
        "quantization_config": provenance["quantization_config"],
        "generation_config": provenance["generation_config"],
        "model_config_file_hashes": provenance["model_config_file_hashes"],
        "tokenizer_file_hashes": provenance["tokenizer_file_hashes"],
        "model_provenance_sha256": provenance["model_provenance_sha256"],
    }


def screen_batch(
    rows: Sequence[dict[str, str]], question_id: str, agent_id: str,
    corpus_sha: str, prompt_sha: str, screener: LocalSemanticScreener,
) -> tuple[list[dict[str, Any]], str]:
    assert_prompt_unchanged(screener.model_id, screener.model_revision)
    started = utc_now()
    input_cards = [
        {
            "record_id": row["record_id"],
            "pmid": row.get("pmid", ""),
            "question_id": question_id,
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "has_abstract": row.get("has_abstract", ""),
            "publication_types": row.get("publication_types", ""),
            "mesh_terms": row.get("mesh_terms", ""),
        }
        for row in rows
    ]
    input_hash = canonical_sha256(input_cards)
    batch_digest = canonical_sha256({
        "input_sha256": input_hash,
        "prompt_sha256": prompt_sha,
        "model_provenance_sha256": screener.provenance["model_provenance_sha256"],
        "ruleset_sha256": ruleset_sha256(),
    })
    batch_id = f"V50-{question_id.split('-Q', 1)[-1].split('-', 1)[0]}-{batch_digest[:16]}"
    batch_static = {
        "batch_id": batch_id,
        "question_id": question_id,
        "assigned_agent": agent_id,
        "execution_mode": EXECUTION_MODE,
        "requested_rows": len(rows),
        "input_sha256": input_hash,
        "corpus_sha256": corpus_sha,
        "prompt_sha256": prompt_sha,
        "ruleset_sha256": ruleset_sha256(),
        "max_input_tokens": MAX_INPUT_TOKENS,
        "truncation_strategy": TRUNCATION_STRATEGY,
        "model_provenance": screener.provenance,
        **provenance_audit_fields(screener.provenance, screener.inference_batch_size),
        "first_record_id": rows[0]["record_id"],
        "last_record_id": rows[-1]["record_id"],
    }
    with exclusive_lock():
        events = [row for row in read_jsonl(BATCHES) if row.get("batch_id") == batch_id]
        if any(row.get("event") == "committed" for row in events):
            raise RuntimeError(f"batch already committed but was scheduled again: {batch_id}")
        event = "resumed" if events else "prepared"
        append_jsonl(BATCHES, [{**batch_static, "event": event, "started_at_utc": started}])

    semantic_decisions = screener.infer(rows, question_id)
    results: list[dict[str, Any]] = []
    for row, decision in zip(rows, semantic_decisions, strict=True):
        results.append({
            "record_id": row["record_id"],
            "pmid": row.get("pmid", ""),
            "question_id": question_id,
            **decision,
        })
    output_hash = canonical_sha256([_decision_core(row) for row in results])
    completed_at = utc_now()
    checkpoint_rows = [{
        **result,
        "status": "screened",
        "batch_id": batch_id,
        "screener": agent_id,
        "execution_mode": EXECUTION_MODE,
        "screened_at_utc": completed_at,
        "prompt_sha256": prompt_sha,
        "corpus_sha256": corpus_sha,
        "ruleset_sha256": ruleset_sha256(),
        **provenance_audit_fields(screener.provenance, screener.inference_batch_size),
        "batch_input_sha256": input_hash,
        "batch_output_sha256": output_hash,
    } for result in results]
    with exclusive_lock():
        assert_prompt_unchanged(screener.model_id, screener.model_revision)
        append_jsonl(CHECKPOINTS, checkpoint_rows)
        append_jsonl(BATCHES, [{
            **batch_static,
            "event": "committed",
            "started_at_utc": started,
            "completed_at_utc": completed_at,
            "new_rows": len(checkpoint_rows),
            "output_sha256": output_hash,
            "input_truncated_rows": sum(bool(row["input_truncated"]) for row in results),
            "appended_rows": len(checkpoint_rows),
        }])
    return checkpoint_rows, batch_id


def run_question(
    question_id: str, agent_id: str, batch_size: int,
    screener: LocalSemanticScreener,
    start: int | None = None, limit: int | None = None,
) -> dict[str, Any]:
    if question_id not in QUESTION_ORDER:
        raise RuntimeError(f"unknown question_id: {question_id}")
    if batch_size <= 0:
        raise RuntimeError("batch_size must be positive")
    load_question_order()
    lock = assert_prompt_unchanged(screener.model_id, screener.model_revision)
    prompt_sha = str(lock["prompt_sha256"])
    corpus, corpus_sha = load_corpus()
    all_for_question = question_rows(corpus, question_id)

    with exclusive_lock():
        existing = checkpoint_index(read_jsonl(CHECKPOINTS), prompt_sha, corpus_sha)
        snapshot = coverage_snapshot(corpus, existing)
        assert_question_gate(question_id, snapshot)

    canonical = all_for_question
    if start is not None:
        if start < 0:
            raise RuntimeError("start must be zero or greater")
        end = None if limit is None else start + limit
        canonical = canonical[start:end]
    elif limit is not None:
        canonical = canonical[:limit]

    pending = [row for row in canonical if (row["record_id"], question_id) not in existing]
    appended = 0
    appended_since_materialization = 0
    batch_ids: list[str] = []
    for offset in range(0, len(pending), batch_size):
        assert_prompt_unchanged(screener.model_id, screener.model_revision)
        chunk = pending[offset : offset + batch_size]
        checkpoint_rows, batch_id = screen_batch(
            chunk, question_id, agent_id, corpus_sha, prompt_sha, screener
        )
        count = len(checkpoint_rows)
        appended += count
        appended_since_materialization += count
        batch_ids.append(batch_id)
        for checkpoint_row in checkpoint_rows:
            existing[(checkpoint_row["record_id"], checkpoint_row["question_id"])] = checkpoint_row
        if appended_since_materialization >= 5000:
            with exclusive_lock():
                write_progress(corpus, corpus_sha, prompt_sha, existing)
                write_manifest(corpus, corpus_sha, prompt_sha, existing)
            appended_since_materialization = 0

    with exclusive_lock():
        current = checkpoint_index(read_jsonl(CHECKPOINTS), prompt_sha, corpus_sha)
        progress = write_progress(corpus, corpus_sha, prompt_sha, current)
        manifest = write_manifest(corpus, corpus_sha, prompt_sha, current)
    return {
        "question_id": question_id,
        "requested_memberships": len(canonical),
        "pending_at_start": len(pending),
        "appended": appended,
        "batch_ids": batch_ids,
        "question": progress["questions"][question_id],
        "all_questions_complete": manifest["run_complete"],
    }


def status(write_files: bool = False) -> dict[str, Any]:
    load_question_order()
    lock = assert_prompt_unchanged()
    prompt_sha = str(lock["prompt_sha256"])
    corpus, corpus_sha = load_corpus()
    decisions = checkpoint_index(read_jsonl(CHECKPOINTS), prompt_sha, corpus_sha)
    questions = coverage_snapshot(corpus, decisions)
    for index, question_id in enumerate(QUESTION_ORDER):
        if questions[question_id]["screened_memberships"] and any(
            not questions[prior]["complete"] for prior in QUESTION_ORDER[:index]
        ):
            raise RuntimeError(f"question-order violation detected at {question_id}")
    if write_files:
        with exclusive_lock():
            progress = write_progress(corpus, corpus_sha, prompt_sha, decisions)
            manifest = write_manifest(corpus, corpus_sha, prompt_sha, decisions)
        return {"progress": progress, "manifest": manifest}
    return {
        "prompt_sha256": prompt_sha,
        "corpus_sha256": corpus_sha,
        "checkpoint_rows": len(decisions),
        "questions": questions,
        "run_complete": all(value["complete"] for value in questions.values()),
    }


def synthetic_smoke_test(screener: LocalSemanticScreener) -> dict[str, Any]:
    """Run semantic checks on synthetic records only; never touches the corpus."""
    long_abstract = (
        "Older adult volunteers actually received acetaminophen and serial blood samples were collected. "
        + ("Baseline characteristics and scheduled follow-up procedures were documented. " * 300)
        + "The administered acetaminophen produced only concentration-time data; adverse events "
        "and other safety outcomes were not assessed or reported."
    )
    examples = [
        {
            "record_id": "SYNTH-RETAIN",
            "pmid": "",
            "title": "Acetaminophen-associated acute liver failure in an adult: a case report.",
            "abstract": (
                "We report an adult patient who developed acute liver failure after a documented "
                "acetaminophen overdose and required hospitalization. The treating team attributed "
                "the hepatic injury to acetaminophen exposure."
            ),
            "has_abstract": "true",
            "publication_types": "Case Reports;Journal Article",
            "mesh_terms": "Acetaminophen;Drug-Induced Liver Injury;Humans",
        },
        {
            "record_id": "SYNTH-EFFICACY",
            "pmid": "",
            "title": "Acetaminophen for short-term dental pain.",
            "abstract": (
                "In 120 older adults randomized to acetaminophen or placebo, the primary endpoint was pain "
                "score reduction at six hours. Plasma acetaminophen concentrations and pain scores "
                "were the only measurements."
            ),
            "has_abstract": "true",
            "publication_types": "Randomized Controlled Trial",
            "mesh_terms": "Acetaminophen;Pain;Aged;Humans",
        },
        {
            "record_id": "SYNTH-OUTCOME-ONLY",
            "pmid": "",
            "title": "Isoniazid-induced acute liver failure without acetaminophen exposure.",
            "abstract": (
                "An older adult developed acute liver failure attributed to isoniazid treatment. "
                "Acetaminophen and related analgesics were not administered or detected."
            ),
            "has_abstract": "true",
            "publication_types": "Case Reports;Journal Article",
            "mesh_terms": "Isoniazid;Drug-Induced Liver Injury;Aged;Humans",
        },
        {
            "record_id": "SYNTH-INVITRO",
            "pmid": "",
            "title": "Acetaminophen toxicity mechanisms in cultured human hepatocytes.",
            "abstract": (
                "Cultured human hepatocyte cell lines were exposed to acetaminophen in vitro. "
                "No patients, clinical cases, pharmacovigilance records, or other human outcomes "
                "were studied."
            ),
            "has_abstract": "true",
            "publication_types": "Journal Article",
            "mesh_terms": "Acetaminophen;Cells, Cultured;Hepatocytes",
        },
        {
            "record_id": "SYNTH-LONG-PK",
            "pmid": "",
            "title": "Pharmacokinetic sampling after acetaminophen exposure.",
            "abstract": long_abstract,
            "has_abstract": "true",
            "publication_types": "Clinical Study",
            "mesh_terms": "Acetaminophen;Pharmacokinetics;Aged;Humans",
        },
        {
            "record_id": "SYNTH-TITLE-ONLY",
            "pmid": "",
            "title": "Acetaminophen use in older adults.",
            "abstract": "",
            "has_abstract": "false",
            "publication_types": "Journal Article",
            "mesh_terms": "Acetaminophen;Aged;Humans",
        },
    ]
    outputs = screener.infer(examples, QUESTION_ORDER[0])
    expected_q01_keys = (
        "retain_direct_high",
        "exposure_only",
        "outcome_only",
        "animal_or_in_vitro_only",
        "exposure_only",
        "title_uncertain",
    )
    for example, output, expected_key in zip(
        examples, outputs, expected_q01_keys, strict=True
    ):
        if output["inference_key"] != expected_key:
            raise RuntimeError(
                f"synthetic exact-key failure for {example['record_id']}: "
                f"expected={expected_key} actual={output}"
            )
    if "case_report_relevant" not in outputs[0]["reason_codes"]:
        raise RuntimeError(f"synthetic retain case lacks deterministic case reason: {outputs[0]}")
    if not outputs[4]["input_truncated"]:
        raise RuntimeError("synthetic long abstract did not exercise deterministic head/tail truncation")

    q04_examples = [
        {
            "record_id": "SYNTH-Q04-IN-VITRO",
            "pmid": "",
            "title": "Protease activity in cultured human tumor cells.",
            "abstract": "A protease assay was performed in cultured human tumor cell lines in vitro.",
            "has_abstract": "true",
            "publication_types": "Journal Article",
            "mesh_terms": "Proteases;Cells, Cultured",
        },
        {
            "record_id": "SYNTH-Q04-ORAL-SAFETY",
            "pmid": "",
            "title": "Adverse reactions to oral pancreatic enzyme replacement in patients.",
            "abstract": (
                "Patients receiving oral pancrelipase digestive enzyme replacement developed "
                "documented allergic adverse reactions attributed to the product."
            ),
            "has_abstract": "true",
            "publication_types": "Clinical Study",
            "mesh_terms": "Pancrelipase;Administration, Oral;Humans;Drug-Related Side Effects",
        },
    ]
    q04_outputs = screener.infer(q04_examples, QUESTION_ORDER[3])
    expected_q04_keys = ("animal_or_in_vitro_only", "retain_direct_high")
    for example, output, expected_key in zip(
        q04_examples, q04_outputs, expected_q04_keys, strict=True
    ):
        if output["inference_key"] != expected_key:
            raise RuntimeError(
                f"synthetic exact-key failure for {example['record_id']}: "
                f"expected={expected_key} actual={output}"
            )

    q05_example = [{
        "record_id": "SYNTH-Q05-CHILD-INGESTION",
        "pmid": "",
        "title": "Camphor poisoning after accidental ingestion of a topical balm by a child.",
        "abstract": (
            "A child accidentally ingested a camphor-containing topical balm and developed "
            "seizures requiring hospitalization; clinicians attributed the poisoning to the product."
        ),
        "has_abstract": "true",
        "publication_types": "Case Reports",
        "mesh_terms": "Camphor;Administration, Topical;Child;Poisoning;Humans",
    }]
    q05_output = screener.infer(q05_example, QUESTION_ORDER[4])[0]
    if (
        q05_output["inference_key"] != "retain_direct_high"
        or "case_report_relevant" not in q05_output["reason_codes"]
        or "route_or_formulation_mismatch" in q05_output["reason_codes"]
    ):
        raise RuntimeError(f"synthetic Q05 child accidental-ingestion case failed: {q05_output}")

    def fixture(
        record_id: str,
        title: str,
        abstract: str,
        *,
        publication_types: str = "Journal Article",
        mesh_terms: str = "Humans",
    ) -> dict[str, str]:
        return {
            "record_id": record_id,
            "pmid": "",
            "title": title,
            "abstract": abstract,
            "has_abstract": "true" if abstract else "false",
            "publication_types": publication_types,
            "mesh_terms": mesh_terms,
        }

    adversarial_specs: list[tuple[str, list[tuple[dict[str, str], str]]]] = [
        (
            QUESTION_ORDER[0],
            [
                (
                    fixture(
                        "ADV-Q01-NO-AE",
                        "Acetaminophen safety in children.",
                        "Children received acetaminophen and no treatment-emergent adverse events occurred.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q01-NOT-ASSESSED",
                        "Acetaminophen pharmacokinetics in older adults.",
                        "Older adults received acetaminophen; only pharmacokinetics were measured and adverse events were not assessed or reported.",
                    ),
                    "exposure_only",
                ),
                (
                    fixture(
                        "ADV-Q01-CO-MENTION",
                        "Isoniazid liver injury in an acetaminophen user.",
                        "The patient received acetaminophen for fever. Separately, investigators attributed the acute liver injury solely to isoniazid; they reported no harm from acetaminophen.",
                    ),
                    "exposure_only",
                ),
            ],
        ),
        (
            QUESTION_ORDER[1],
            [
                (
                    fixture(
                        "ADV-Q02-DIRECT",
                        "Fetal renal dysfunction after maternal ibuprofen exposure.",
                        "Pregnant patients used ibuprofen and fetal renal dysfunction was attributed to the maternal ibuprofen exposure.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q02-CLASS",
                        "Diclofenac-associated gastrointestinal bleeding.",
                        "Anticoagulated adults exposed to the nonselective NSAID diclofenac developed upper gastrointestinal bleeding attributed to diclofenac.",
                    ),
                    "retain_class_high",
                ),
                (
                    fixture(
                        "ADV-Q02-EXPOSURE",
                        "Ibuprofen efficacy in chronic kidney disease.",
                        "Adults with kidney disease received ibuprofen; pain efficacy was the only outcome and safety was not assessed.",
                    ),
                    "exposure_only",
                ),
                (
                    fixture(
                        "ADV-Q02-OUTCOME",
                        "Aspirin-associated bleeding.",
                        "Aspirin-only users developed gastrointestinal bleeding. No patient received ibuprofen, dexibuprofen, naproxen, or another applicable nonselective NSAID.",
                    ),
                    "outcome_only",
                ),
            ],
        ),
        (
            QUESTION_ORDER[2],
            [
                (
                    fixture(
                        "ADV-Q03-DRIVING",
                        "Driving impairment after chlorpheniramine.",
                        "Drivers who received chlorpheniramine had impaired on-road driving and psychomotor performance attributed to the drug.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q03-CLASS",
                        "First-generation H1 antihistamines and driving.",
                        "Diphenhydramine exposure impaired driving; the study explicitly generalized this safety finding to first-generation H1 antihistamines including chlorpheniramine.",
                    ),
                    "retain_class_high",
                ),
                (
                    fixture(
                        "ADV-Q03-NO-AE",
                        "Cetirizine safety trial.",
                        "Drivers received cetirizine and no adverse events occurred during follow-up.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q03-PK",
                        "Guaifenesin pharmacokinetics.",
                        "Adults with hypertension received guaifenesin; only plasma pharmacokinetics were measured and safety was not assessed.",
                    ),
                    "exposure_only",
                ),
                (
                    fixture(
                        "ADV-Q03-OUTCOME",
                        "Diazepam-associated sedation.",
                        "The introduction mentioned cetirizine, but nobody received it. In the study, diazepam caused severe sedation in a driver.",
                    ),
                    "outcome_only",
                ),
            ],
        ),
        (
            QUESTION_ORDER[3],
            [
                (
                    fixture(
                        "ADV-Q04-BIOMARKER",
                        "Serum pancreatic lipase and pancreatitis severity.",
                        "Serum endogenous pancreatic lipase predicted severe pancreatitis; no digestive enzyme product was administered.",
                    ),
                    "outcome_only",
                ),
                (
                    fixture(
                        "ADV-Q04-HIV",
                        "Adverse events with an HIV protease inhibitor.",
                        "Patients receiving an HIV protease inhibitor developed adverse events; no digestive enzyme product was administered.",
                    ),
                    "outcome_only",
                ),
                (
                    fixture(
                        "ADV-Q04-CLASS",
                        "Allergy to an oral digestive enzyme supplement.",
                        "Patients ingested an oral multi-enzyme digestive product containing protease and lipase and developed allergic reactions attributed to the product.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q04-INHALED",
                        "Occupational allergy after cellulase inhalation.",
                        "Workers inhaled aerosolized industrial cellulase and developed occupational allergy attributed to inhalation.",
                    ),
                    "route_mismatch",
                ),
                (
                    fixture(
                        "ADV-Q04-IV",
                        "Intravenous bromelain-derived protease.",
                        "Patients received an intravenous bromelain-derived protease formulation and developed infusion reactions.",
                    ),
                    "route_mismatch",
                ),
                (
                    fixture(
                        "ADV-Q04-BROMELAIN",
                        "Bleeding associated with oral bromelain.",
                        "Adults received oral bromelain and clinically important bleeding was attributed to bromelain.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q04-ORLISTAT",
                        "Orlistat, pancreatic lipase, and adverse events.",
                        "Orlistat inhibited endogenous pancreatic lipase and caused adverse events; no lipase or digestive enzyme product was administered.",
                    ),
                    "outcome_only",
                ),
            ],
        ),
        (
            QUESTION_ORDER[4],
            [
                (
                    fixture(
                        "ADV-Q05-SALICYLATE",
                        "Systemic salicylism from topical methyl salicylate.",
                        "A child had repeated topical methyl salicylate exposure that caused systemic salicylism requiring hospitalization.",
                    ),
                    "retain_direct_high",
                ),
                (
                    fixture(
                        "ADV-Q05-MOTHBALL",
                        "Camphor mothball poisoning in a child.",
                        "A child swallowed camphor mothballs rather than a topical medicinal product and developed seizures.",
                    ),
                    "route_mismatch",
                ),
                (
                    fixture(
                        "ADV-Q05-PEPPERMINT",
                        "Adverse events from oral peppermint-oil capsules.",
                        "Anticoagulated adults swallowed oral peppermint-oil capsules and developed gastrointestinal adverse events; no Mentha arvensis or cornmint topical product was used.",
                    ),
                    "route_mismatch",
                ),
                (
                    fixture(
                        "ADV-Q05-EFFICACY",
                        "Analgesic efficacy of topical menthol.",
                        "Children applied topical menthol; only analgesic efficacy was measured and safety was not assessed.",
                    ),
                    "exposure_only",
                ),
                (
                    fixture(
                        "ADV-Q05-CORNMINT",
                        "Contact dermatitis from cornmint oil.",
                        "Topical Mentha arvensis cornmint oil caused contact dermatitis in a child, attributed to the product.",
                    ),
                    "retain_direct_high",
                ),
            ],
        ),
    ]
    adversarial_results: list[dict[str, Any]] = []
    for question_id, cases in adversarial_specs:
        case_rows = [case[0] for case in cases]
        expected_keys = [case[1] for case in cases]
        case_outputs = screener.infer(case_rows, question_id)
        for row, output, expected_key in zip(
            case_rows, case_outputs, expected_keys, strict=True
        ):
            if output["inference_key"] != expected_key:
                raise RuntimeError(
                    f"adversarial exact-key failure for {row['record_id']}: "
                    f"expected={expected_key} actual={output}"
                )
            adversarial_results.append(
                {
                    "record_id": row["record_id"],
                    "question_id": question_id,
                    "expected_inference_key": expected_key,
                    **output,
                }
            )
    return {
        "synthetic_only": True,
        "model_provenance_sha256": screener.provenance["model_provenance_sha256"],
        "abstract_examples": [
            {"record_id": row["record_id"], **decision}
            for row, decision in zip(examples, outputs, strict=True)
        ],
        "long_input_test": {
            "original_tokens": outputs[4]["abstract_original_tokens"],
            "retained_tokens": outputs[4]["abstract_retained_tokens"],
            "strategy": outputs[4]["truncation_strategy"],
        },
        "q04_boundary_examples": [
            {"record_id": row["record_id"], **decision}
            for row, decision in zip(q04_examples, q04_outputs, strict=True)
        ],
        "q05_boundary_example": {"record_id": q05_example[0]["record_id"], **q05_output},
        "adversarial_examples": adversarial_results,
        "adversarial_example_count": len(adversarial_results),
        "passed": True,
    }


def add_model_arguments(parser: argparse.ArgumentParser, include_batch_size: bool = True) -> None:
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    if include_batch_size:
        parser.add_argument("--inference-batch-size", type=int, default=8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze", help="Freeze prompt and local-model provenance.")
    add_model_arguments(freeze, include_batch_size=False)

    run = subparsers.add_parser("run", help="Screen one question with strict predecessor gating.")
    run.add_argument("--question-id", required=True, choices=QUESTION_ORDER)
    run.add_argument("--agent-id", default=os.getenv("CODEX_AGENT_ID", "codex-agent"))
    run.add_argument("--batch-size", type=int, default=200)
    run.add_argument("--start", type=int)
    run.add_argument("--limit", type=int)
    add_model_arguments(run)

    run_all = subparsers.add_parser("run-all", help="Resume and screen Q01 through Q05 sequentially.")
    run_all.add_argument("--agent-id", default=os.getenv("CODEX_AGENT_ID", "codex-agent"))
    run_all.add_argument("--batch-size", type=int, default=200)
    add_model_arguments(run_all)

    status_parser = subparsers.add_parser("status", help="Validate checkpoints and report actual coverage.")
    status_parser.add_argument("--write", action="store_true", help="Refresh progress and manifest files.")
    smoke = subparsers.add_parser("smoke-test", help="Load the pinned model and classify synthetic examples only.")
    add_model_arguments(smoke)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "freeze":
        result = freeze_prompt(args.model_id, args.model_revision)
    elif args.command == "run":
        if args.limit is not None and args.limit <= 0:
            raise RuntimeError("limit must be positive")
        screener = LocalSemanticScreener(
            args.model_id, args.model_revision, args.inference_batch_size
        )
        result = run_question(
            args.question_id, args.agent_id, args.batch_size,
            screener,
            start=args.start, limit=args.limit,
        )
    elif args.command == "run-all":
        screener = LocalSemanticScreener(
            args.model_id, args.model_revision, args.inference_batch_size
        )
        results = []
        for question_id in QUESTION_ORDER:
            results.append(
                run_question(question_id, args.agent_id, args.batch_size, screener)
            )
        result = {"questions": results, "status": status(write_files=True)}
    elif args.command == "smoke-test":
        screener = LocalSemanticScreener(
            args.model_id, args.model_revision, args.inference_batch_size
        )
        result = synthetic_smoke_test(screener)
        result["prompt_sha256"] = sha256_file(PROMPT)
        result["screening_code_sha256"] = sha256_file(Path(__file__))
        result["smoke_result_sha256"] = canonical_sha256(result)
        atomic_write_json(SMOKE_REPORT, result)
    else:
        result = status(write_files=args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
