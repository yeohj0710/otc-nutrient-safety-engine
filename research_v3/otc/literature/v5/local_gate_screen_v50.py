"""Deterministic local-LLM gate screening for the v5 literature corpus.

The model reads each title/abstract once and emits seven constrained one-token
gate choices.  Decision labels, reason codes, confidence, exact-source quotes,
and uncertainty handling are deterministic projections of those gates.  The
script can write pilot outputs or process immutable batches prepared by
``agent_screen_v50.py``.  Formal checkpoint ingestion remains the
orchestrator's responsibility.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[4]
V5 = ROOT / "research_v3" / "otc" / "literature" / "v5"
ORCHESTRATOR_PATH = V5 / "agent_screen_v50.py"
DEFAULT_14B_SNAPSHOT = Path(
    r"C:\Users\hjyeo\.cache\huggingface\hub\models--Qwen--Qwen2.5-14B-Instruct"
    r"\snapshots\cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"
)
DEFAULT_14B_ID = "Qwen/Qwen2.5-14B-Instruct"
DEFAULT_14B_REVISION = "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"
DEFAULT_MAX_INPUT_TOKENS = 3072
DEFAULT_BATCH_SIZE = 4

GATE_ORDER = (
    "source",
    "exposure",
    "route",
    "risk_context",
    "result_type",
    "attribution",
    "publication_role",
)
GATE_OPTIONS: dict[str, tuple[str, ...]] = {
    "source": (
        "human_primary",
        "human_case",
        "pharmacovigilance_or_population",
        "human_evidence_review",
        "preclinical_only",
        "unclear",
    ),
    "exposure": (
        "direct_actual",
        "class_actual",
        "mention_only",
        "absent",
        "unclear",
    ),
    "route": (
        "in_scope_or_unspecified",
        "mixed_includes_in_scope",
        "out_of_scope_only",
        "unclear",
    ),
    "risk_context": ("in_scope", "absent", "unclear"),
    "result_type": (
        "observed_safety_or_harm",
        "efficacy_or_pk_only",
        "process_or_method_only",
        "no_result",
        "unclear",
    ),
    "attribution": (
        "direct_exposure",
        "allowed_class",
        "other_drug_or_condition",
        "unlinked",
        "unclear",
    ),
    "publication_role": ("case_report", "review", "other", "unclear"),
}

QUESTION_ORDER = (
    "OTC-LIT-Q01-ACETAMINOPHEN",
    "OTC-LIT-Q02-NSAID",
    "OTC-LIT-Q03-COLD-ALLERGY",
    "OTC-LIT-Q04-DIGESTIVE",
    "OTC-LIT-Q05-TOPICAL",
)

QUESTION_RULES = {
    QUESTION_ORDER[0]: """
DIRECT EXPOSURE: oral/general acetaminophen, paracetamol, Tylenol, Panadol,
Calpol, propacetamol, or an equivalent name. Bare APAP counts only when the surrounding text
means acetaminophen use/ingestion/overdose, never automatic positive airway
pressure, CPAP, or sleep-apnea equipment. CLASS EXPOSURE: an administered
anilide/para-aminophenol analgesic only when the result is explicitly
applicable to acetaminophen. IN-SCOPE RISK: liver disease/impairment/failure,
alcohol use, child/adolescent, older adult, or the exposure itself being
duplicate use, overdose/intoxication/poisoning/suicide-attempt ingestion,
at least 4,000 mg/day, 1,000 mg four times/day, a dosing interval below four
hours, or chronic supratherapeutic use. These exposure patterns satisfy the risk
gate without a second population condition. ROUTE: oral, general ingestion,
overdose, or unspecified is in scope; acetaminophen that is explicitly IV,
infusion, injection, Ofirmev, Perfalgan, or propacetamol only is out of scope. Hospital
admission, emergency treatment, organ injury, symptoms, toxicity, adverse
events, or death after acetaminophen exposure are safety/harm results.
""",
    QUESTION_ORDER[1]: """
DIRECT EXPOSURE: ibuprofen, dexibuprofen, or naproxen. CLASS EXPOSURE: an
actually administered traditional nonselective NSAID such as diclofenac,
ketoprofen, indomethacin, meloxicam, or piroxicam when the finding applies to
the eligible class. Aspirin-only and coxib-only studies are not eligible class
exposure unless explicitly generalized to traditional nonselective NSAIDs.
IN-SCOPE RISK: pregnancy/lactation, kidney disease/impairment, peptic-ulcer or
GI-bleeding history, anticoagulant/antiplatelet use, or duplicate NSAID use.
ROUTE: oral/general/unspecified use is in scope; topical, ophthalmic, or
injection-only exposure is out of scope. Observed adverse events, bleeding,
renal harm, pregnancy/fetal harm, hospitalization, interaction harm, or death
are safety/harm results.
""",
    QUESTION_ORDER[2]: """
DIRECT EXPOSURE: cetirizine, chlorpheniramine/chlorphenamine, phenylephrine,
pentoxyverine/carbetapentane, guaifenesin, or caffeine. CLASS EXPOSURE: an
actually administered applicable H1 antihistamine, sympathomimetic
decongestant, antitussive/expectorant, or methylxanthine whose result applies
to the named ingredients. IN-SCOPE RISK: driving or psychomotor performance,
hypertension/cardiovascular disease, or sedative/CNS-depressant co-use.
ROUTE: oral cold/allergy preparations or unspecified use are in scope;
intranasal, ophthalmic, or injection-only formulations are out of scope.
Drowsiness, impaired driving/psychomotor performance, blood-pressure or
cardiovascular harm, interaction harm, adverse events, hospitalization, or
death are safety/harm results.
""",
    QUESTION_ORDER[3]: """
DIRECT EXPOSURE: an orally used digestive product containing pancreatin,
pancrelipase/pancrealipase/PERT, Pancellase, Panprosin, Crease-PEG, Prozyme 6,
diastase/protease/cellulase/lipase assigned as a digestive preparation,
simethicone/simeticone, ursodeoxycholic acid/ursodiol/UDCA, or bromelain.
CLASS EXPOSURE: another actually administered oral digestive-enzyme product
whose result applies to the eligible enzyme class. Generic protease, amylase,
lipase, or cellulase is mention-only/absent when endogenous, a serum marker,
an assay, gene expression, an inhibitor, a cell-line reagent, or an
industrial/food enzyme without human oral digestive-product use. IN-SCOPE
RISK/POPULATION: digestive disorder/indigestion, pancreatic exocrine
insufficiency/pancreatitis/cystic fibrosis, post-pancreatic surgery state,
gallbladder/bile-duct/cholestatic disease, abdominal discomfort, bloating, or
gas. ROUTE: oral product, tablet/capsule/granule, PERT, or unspecified product
use is in scope; inhaled, injected, or industrial exposure only is out of
scope. Adverse events, toxicity, interaction, organ injury, hospitalization,
or death are safety/harm results; efficacy or digestive improvement alone is
not.
""",
    QUESTION_ORDER[4]: """
DIRECT EXPOSURE: a topical product containing methyl salicylate/wintergreen
oil, L-menthol/menthol, dl-camphor/camphor, Mentha arvensis or Mentha
canadensis cornmint/Japanese-mint oil, or thymol. CLASS EXPOSURE: an actually
used topical counterirritant product whose result applies to the eligible
ingredients. IN-SCOPE RISK: infant/child/adolescent or anticoagulant/
antiplatelet use. ROUTE: topical/dermal patch, plaster, ointment, balm, cream,
liniment, or rub is in scope. A child accidentally ingesting such a topical
product remains in scope. Oral peppermint-oil capsules, camphor mothballs,
food flavoring, and oral-dental exposure alone are out of scope. Observed
poisoning, bleeding, burns, neurologic symptoms, interaction harm,
hospitalization, or death are safety/harm results.
""",
}

EXPOSURE_PATTERNS = {
    QUESTION_ORDER[0]: re.compile(
        r"acetaminophen|paracetamol|tylenol|panadol|calpol|ofirmev|perfalgan|(?<![A-Za-z])APAP(?![A-Za-z])",
        re.I,
    ),
    QUESTION_ORDER[1]: re.compile(
        r"ibuprofen|dexibuprofen|naproxen|NSAID|nonsteroidal|diclofenac|ketoprofen|indomethacin|meloxicam|piroxicam",
        re.I,
    ),
    QUESTION_ORDER[2]: re.compile(
        r"cetirizine|chlorpheniramine|chlorphenamine|phenylephrine|pentoxyverine|carbetapentane|guaifenesin|caffeine|antihistamine|decongestant|sympathomimetic|methylxanthine",
        re.I,
    ),
    QUESTION_ORDER[3]: re.compile(
        r"pancreatin|pancrelipase|pancrealipase|\bPERT\b|pancellase|panprosin|prozyme|crease-?PEG|diastase|protease|amylase|lipase|cellulase|simethicone|simeticone|ursodeoxycholic|ursodiol|\bUDCA\b|bromelain|digestive enzyme",
        re.I,
    ),
    QUESTION_ORDER[4]: re.compile(
        r"methyl salicylate|wintergreen|menthol|camphor|Mentha (?:arvensis|canadensis)|cornmint|Japanese[- ]mint|thymol|counterirritant",
        re.I,
    ),
}
RISK_PATTERNS = {
    QUESTION_ORDER[0]: re.compile(
        r"overdos|intoxicat|poison|supratherapeutic|high[- ]dose|chronic use|repeated dose|duplicate|short interval|liver|hepatic|alcohol|ethanol|child|adolescen|pediatric|paediatric|elder|older adult|aged",
        re.I,
    ),
    QUESTION_ORDER[1]: re.compile(
        r"pregnan|lactat|breastfeed|renal|kidney|peptic|ulcer|gastrointestinal bleed|anticoagul|antiplatelet|warfarin|clopidogrel|duplicate|concomitant NSAID",
        re.I,
    ),
    QUESTION_ORDER[2]: re.compile(
        r"driv|psychomotor|vehicle|hypertens|blood pressure|cardiovascular|sedat|benzodiazep|opioid|CNS depress|alcohol",
        re.I,
    ),
    QUESTION_ORDER[3]: re.compile(
        r"indigestion|dyspepsia|digestive|pancrea|exocrine|cystic fibrosis|pancreatect|gallbladder|bile duct|biliary|cholesta|abdominal|bloating|flatulence|gas",
        re.I,
    ),
    QUESTION_ORDER[4]: re.compile(
        r"infant|child|adolescen|pediatric|paediatric|anticoagul|antiplatelet|warfarin|clopidogrel",
        re.I,
    ),
}
SAFETY_PATTERN = re.compile(
    r"adverse|toxici|toxic|poison|intoxicat|injur|failure|damage|bleed|hemorrhag|haemorrhag|"
    r"hospital|admission|emergency|death|died|fatal|mortality|symptom|drows|sedat|impair|"
    r"burn|seizure|coma|interaction|complication|well tolerated|tolerability|no adverse|safe(?:ty)?",
    re.I,
)
SOURCE_PATTERN = re.compile(
    r"patient|subject|participant|volunteer|child|adolescen|adult|woman|women|man|men|case|"
    r"cohort|trial|survey|database|reporting system|review|meta-analysis|rat|mice|mouse|rabbit|"
    r"animal|cell|in vitro|ex vivo",
    re.I,
)
ROUTE_PATTERN = re.compile(
    r"oral|ingest|swallow|tablet|capsule|granule|intraven|\bIV\b|infusion|inject|topical|"
    r"dermal|patch|plaster|ointment|balm|cream|liniment|rub|intranasal|ophthalmic|inhal",
    re.I,
)
CASE_PATTERN = re.compile(r"we (?:report|present)(?: a)? case|case report of", re.I)
REVIEW_TYPES = {"review", "systematic review", "meta-analysis"}

SYSTEM_PROMPT = """You are a conservative systematic-review title/abstract screener.
Classify exactly seven independent gates from the supplied record and question.
Search retrieval, MeSH indexing, a drug in the background, or a comparator arm
does not prove actual exposure. Do not transfer an outcome caused by another
drug, procedure, or disease to the question exposure. Use unclear when the
source text cannot support a gate. A negative observed safety result such as
'no adverse events' is still an observed safety result. Overdose/intoxication,
hospital admission, emergency treatment, symptoms, organ injury, interactions,
and death are safety/harm evidence when linked to the question exposure.

Return exactly seven ASCII digits with no spaces or prose, in this order:
source, exposure, route, risk_context, result_type, attribution,
publication_role.

Digit meanings by position:
1 source: 1 human_primary; 2 human_case; 3 pharmacovigilance_or_population;
  4 human_evidence_review; 5 preclinical_only; 6 unclear.
2 exposure: 1 direct_actual human use; 2 allowed_class actual human use;
  3 mention_only; 4 absent; 5 unclear.
3 route: 1 in_scope_or_unspecified; 2 mixed_includes_in_scope;
  3 out_of_scope_only; 4 unclear.
4 risk_context: 1 in_scope and connected to actual exposure; 2 absent;
  3 unclear.
5 result_type: 1 observed_safety_or_harm; 2 efficacy_or_pk_only;
  3 process_or_method_only; 4 no_result; 5 unclear.
6 attribution: 1 direct_exposure; 2 allowed_class; 3 other_drug_or_condition;
  4 unlinked; 5 unclear.
7 publication_role: 1 case_report; 2 review; 3 other; 4 unclear.

Important: direct_actual and class_actual require actual human use,
administration, ingestion, overdose, dispensing to an exposed person, or
detection in a human specimen. Animal/cell exposure is not actual human
exposure. A population-level prescription, sales, or reporting-system record
can support actual exposure only when it measures exposed people or reports.
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def load_orchestrator() -> Any:
    spec = importlib.util.spec_from_file_location("agent_screen_v50_runtime", ORCHESTRATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load orchestrator: {ORCHESTRATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [part for part in str(value or "").split(";") if part]


def normalized_record(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["title"] = str(result.get("title") or "")
    result["abstract"] = str(result.get("abstract") or "")
    has_abstract = result.get("has_abstract")
    if isinstance(has_abstract, str):
        has_abstract = has_abstract.strip().lower() == "true"
    result["has_abstract"] = bool(has_abstract and result["abstract"].strip())
    result["publication_types"] = as_list(result.get("publication_types"))
    result["mesh_terms"] = as_list(result.get("mesh_terms"))
    return result


def question_block(question_id: str) -> str:
    if question_id not in QUESTION_RULES:
        raise RuntimeError(f"unknown question: {question_id}")
    return " ".join(QUESTION_RULES[question_id].split())


def record_user_prompt(record: Mapping[str, Any], abstract_text: str) -> str:
    return (
        f"QUESTION_ID: {record['question_id']}\n"
        f"QUESTION RULES: {question_block(record['question_id'])}\n"
        f"PUBLICATION_TYPES: {'; '.join(record['publication_types']) or '[none]'}\n"
        f"MESH_TERMS: {'; '.join(record['mesh_terms']) or '[none]'}\n"
        f"TITLE: {record['title'] or '[empty]'}\n"
        f"ABSTRACT: {abstract_text or '[none]'}\n"
        "SEVEN-DIGIT CODE:"
    )


@dataclass(frozen=True)
class Rendered:
    text: str
    input_truncated: bool
    abstract_original_tokens: int
    abstract_retained_tokens: int


class GateModel:
    def __init__(
        self,
        snapshot: Path,
        model_id: str,
        revision: str,
        max_input_tokens: int,
        batch_size: int,
        min_probability: float,
        min_margin: float,
    ) -> None:
        self.snapshot = snapshot.resolve()
        self.model_id = model_id
        self.revision = revision
        self.max_input_tokens = max_input_tokens
        self.batch_size = batch_size
        self.min_probability = min_probability
        self.min_margin = min_margin
        self.tokenizer: Any = None
        self.model: Any = None
        self.digit_ids: dict[int, int] = {}

    def load(self) -> None:
        if self.model is not None:
            return
        if not self.snapshot.is_dir():
            raise RuntimeError(f"model snapshot is missing: {self.snapshot}")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        torch.set_float32_matmul_precision("high")
        tokenizer = AutoTokenizer.from_pretrained(self.snapshot, local_files_only=True)
        tokenizer.padding_side = "left"
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
        digit_ids: dict[int, int] = {}
        for digit in range(1, 7):
            encoded = tokenizer.encode(str(digit), add_special_tokens=False)
            if len(encoded) != 1:
                raise RuntimeError(f"digit {digit} is not a single tokenizer token: {encoded}")
            digit_ids[digit] = encoded[0]
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            self.snapshot,
            local_files_only=True,
            device_map="auto",
            quantization_config=quantization,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
            low_cpu_mem_usage=True,
        )
        model.eval()
        model.generation_config.do_sample = False
        model.generation_config.temperature = None
        model.generation_config.top_p = None
        model.generation_config.top_k = None
        self.tokenizer = tokenizer
        self.model = model
        self.digit_ids = digit_ids

    def render(self, record: Mapping[str, Any]) -> Rendered:
        assert self.tokenizer is not None
        abstract = record["abstract"]
        original_ids = self.tokenizer.encode(abstract, add_special_tokens=False)

        def chat_text(candidate_abstract: str) -> str:
            return self.tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": record_user_prompt(record, candidate_abstract)},
                ],
                tokenize=False,
                add_generation_prompt=True,
            )

        full = chat_text(abstract)
        full_count = len(self.tokenizer.encode(full, add_special_tokens=False))
        if full_count <= self.max_input_tokens:
            return Rendered(full, False, len(original_ids), len(original_ids))

        empty = chat_text("")
        base_count = len(self.tokenizer.encode(empty, add_special_tokens=False))
        budget = max(32, self.max_input_tokens - base_count - 16)
        marker_ids = self.tokenizer.encode("\n[... middle omitted ...]\n", add_special_tokens=False)
        body_budget = max(16, budget - len(marker_ids))
        head_count = max(8, int(body_budget * 0.68))
        tail_count = max(8, body_budget - head_count)
        retained_ids = original_ids[:head_count] + marker_ids + original_ids[-tail_count:]
        retained = self.tokenizer.decode(retained_ids, skip_special_tokens=True)
        rendered = chat_text(retained)
        while len(self.tokenizer.encode(rendered, add_special_tokens=False)) > self.max_input_tokens:
            head_count = max(8, head_count - 16)
            tail_count = max(8, tail_count - 8)
            retained_ids = original_ids[:head_count] + marker_ids + original_ids[-tail_count:]
            retained = self.tokenizer.decode(retained_ids, skip_special_tokens=True)
            rendered = chat_text(retained)
        return Rendered(rendered, True, len(original_ids), head_count + tail_count)

    def infer(self, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        self.load()
        assert self.tokenizer is not None and self.model is not None
        import torch

        rendered = [self.render(record) for record in records]
        encoded = self.tokenizer(
            [item.text for item in rendered],
            return_tensors="pt",
            padding=True,
            add_special_tokens=False,
        ).to(self.model.device)
        initial_length = encoded["input_ids"].shape[1]
        allowed_by_stage = [
            [self.digit_ids[index] for index in range(1, len(GATE_OPTIONS[gate]) + 1)]
            for gate in GATE_ORDER
        ]

        def prefix_allowed_tokens_fn(_batch_id: int, input_ids: Any) -> list[int]:
            step = int(input_ids.shape[-1] - initial_length)
            return allowed_by_stage[min(step, len(allowed_by_stage) - 1)]

        started = time.perf_counter()
        with torch.inference_mode():
            generated = self.model.generate(
                **encoded,
                max_new_tokens=len(GATE_ORDER),
                min_new_tokens=len(GATE_ORDER),
                do_sample=False,
                num_beams=1,
                use_cache=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=None,
                prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
                return_dict_in_generate=True,
                output_scores=True,
            )
        elapsed = time.perf_counter() - started
        new_tokens = generated.sequences[:, initial_length:]
        if new_tokens.shape[1] != len(GATE_ORDER):
            raise RuntimeError(f"model returned {new_tokens.shape[1]} gate tokens")
        results: list[dict[str, Any]] = []
        for row_index, record in enumerate(records):
            gates: dict[str, str] = {}
            diagnostics: dict[str, Any] = {}
            for stage_index, gate in enumerate(GATE_ORDER):
                token_id = int(new_tokens[row_index, stage_index].item())
                allowed_ids = allowed_by_stage[stage_index]
                if token_id not in allowed_ids:
                    raise RuntimeError(f"invalid constrained token {token_id} for {gate}")
                raw_logits = generated.scores[stage_index][row_index, allowed_ids].float()
                probabilities = torch.softmax(raw_logits, dim=-1)
                order = torch.argsort(probabilities, descending=True)
                selected_position = allowed_ids.index(token_id)
                selected_probability = float(probabilities[selected_position].item())
                second_probability = (
                    float(probabilities[order[1]].item()) if len(allowed_ids) > 1 else 0.0
                )
                selected = GATE_OPTIONS[gate][selected_position]
                calibrated_unclear = False
                if (
                    selected != "unclear"
                    and (
                        selected_probability < self.min_probability
                        or selected_probability - second_probability < self.min_margin
                    )
                ):
                    selected = "unclear"
                    calibrated_unclear = True
                gates[gate] = selected
                diagnostics[gate] = {
                    "selected_digit": selected_position + 1,
                    "selected_probability": round(selected_probability, 8),
                    "second_probability": round(second_probability, 8),
                    "margin": round(selected_probability - second_probability, 8),
                    "calibrated_to_unclear": calibrated_unclear,
                }
            results.append(
                {
                    "gates": gates,
                    "diagnostics": diagnostics,
                    "input_truncated": rendered[row_index].input_truncated,
                    "abstract_original_tokens": rendered[row_index].abstract_original_tokens,
                    "abstract_retained_tokens": rendered[row_index].abstract_retained_tokens,
                    "batch_model_seconds": elapsed,
                }
            )
        return results

    def provenance(self) -> dict[str, Any]:
        files = (
            "config.json",
            "generation_config.json",
            "model.safetensors.index.json",
            "tokenizer.json",
            "tokenizer_config.json",
        )
        hashes = {
            name: sha256_file(self.snapshot / name)
            for name in files
            if (self.snapshot / name).is_file()
        }
        value = {
            "schema_version": "local-gate-model-v1",
            "model_id": self.model_id,
            "model_revision": self.revision,
            "local_snapshot": str(self.snapshot),
            "config_file_hashes": hashes,
            "quantization": {
                "load_in_4bit": True,
                "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_compute_dtype": "bfloat16",
                "bnb_4bit_use_double_quant": True,
            },
            "generation": {
                "strategy": "single_prefill_seven_constrained_digit_tokens",
                "do_sample": False,
                "num_beams": 1,
                "use_cache": True,
                "max_new_tokens": 7,
                "max_input_tokens": self.max_input_tokens,
                "truncation_strategy": "question_metadata_title_plus_abstract_head_68_tail_32",
                "min_selected_probability": self.min_probability,
                "min_top_two_margin": self.min_margin,
            },
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "question_rules_sha256": hashlib.sha256(canonical_json(QUESTION_RULES)).hexdigest(),
            "classifier_path": str(SCRIPT_PATH),
            "classifier_sha256": sha256_file(SCRIPT_PATH),
        }
        value["model_provenance_sha256"] = hashlib.sha256(canonical_json(value)).hexdigest()
        return value


def source_segments(record: Mapping[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if record["title"]:
        result.append(("title", record["title"]))
    abstract = record["abstract"]
    if abstract:
        spans = list(re.finditer(r"\S(?:.*?)(?:[.!?](?=\s|$)|$)", abstract, re.S))
        if spans:
            result.extend(("abstract", match.group(0)) for match in spans if match.group(0).strip())
        else:
            result.append(("abstract", abstract))
    return result


def short_exact(text: str, pattern: re.Pattern[str] | None = None, limit: int = 360) -> str:
    if not text:
        return ""
    match = pattern.search(text) if pattern else None
    if len(text) <= limit:
        return text
    center = match.start() if match else 0
    left = max(0, center - limit // 3)
    right = min(len(text), left + limit)
    left = max(0, right - limit)
    if left:
        boundary = text.find(" ", left, min(left + 30, len(text)))
        if boundary >= 0:
            left = boundary + 1
    if right < len(text):
        boundary = text.rfind(" ", max(left, right - 30), right)
        if boundary > left:
            right = boundary
    return text[left:right]


def best_segment(
    record: Mapping[str, Any],
    patterns: Sequence[re.Pattern[str]],
    *,
    require_all: bool = False,
) -> str:
    best_text = ""
    best_score = -1
    for _field, text in source_segments(record):
        hits = [bool(pattern.search(text)) for pattern in patterns]
        if require_all and not all(hits):
            continue
        score = sum(hits)
        if score > best_score and score > 0:
            best_text, best_score = text, score
    if not best_text:
        return ""
    first_pattern = next((pattern for pattern in patterns if pattern.search(best_text)), None)
    return short_exact(best_text, first_pattern)


def evidence_quotes(record: Mapping[str, Any], gates: Mapping[str, str]) -> dict[str, str]:
    qid = record["question_id"]
    exposure_pattern = EXPOSURE_PATTERNS[qid]
    risk_pattern = RISK_PATTERNS[qid]
    quotes = {gate: "" for gate in GATE_ORDER}
    quotes["source"] = best_segment(record, (SOURCE_PATTERN,))
    if gates["exposure"] in {"direct_actual", "class_actual", "mention_only", "unclear"}:
        quotes["exposure"] = best_segment(record, (exposure_pattern,))
    if gates["route"] != "unclear":
        quotes["route"] = best_segment(record, (exposure_pattern, ROUTE_PATTERN)) or best_segment(
            record, (ROUTE_PATTERN,)
        )
    if gates["risk_context"] in {"in_scope", "unclear"}:
        quotes["risk_context"] = best_segment(record, (risk_pattern,))
    if gates["result_type"] != "no_result":
        result_pattern = SAFETY_PATTERN if gates["result_type"] in {
            "observed_safety_or_harm",
            "unclear",
        } else re.compile(r"efficacy|effective|pharmacokinetic|concentration|assay|method|activity", re.I)
        quotes["result_type"] = best_segment(record, (result_pattern,))
    if gates["attribution"] in {"direct_exposure", "allowed_class"}:
        quotes["attribution"] = best_segment(
            record, (exposure_pattern, SAFETY_PATTERN), require_all=True
        )
    elif gates["attribution"] in {"other_drug_or_condition", "unlinked", "unclear"}:
        quotes["attribution"] = best_segment(record, (SAFETY_PATTERN,))
    publication_types = record["publication_types"]
    if gates["publication_role"] == "case_report":
        exact = next((item for item in publication_types if item.casefold() == "case reports"), "")
        quotes["publication_role"] = exact or best_segment(record, (CASE_PATTERN,))
    elif gates["publication_role"] == "review":
        exact = next((item for item in publication_types if item.casefold() in REVIEW_TYPES), "")
        quotes["publication_role"] = exact
    return quotes


def normalize_gates(gates: Mapping[str, str]) -> dict[str, str]:
    """Convert internally inconsistent terminal combinations to explicit uncertainty."""
    result = dict(gates)
    exposure = result["exposure"]
    attribution = result["attribution"]
    if exposure == "direct_actual" and attribution == "allowed_class":
        result["attribution"] = "unclear"
    elif exposure == "class_actual" and attribution == "direct_exposure":
        result["attribution"] = "unclear"
    elif exposure in {"absent", "mention_only"} and attribution in {
        "direct_exposure",
        "allowed_class",
    }:
        result["attribution"] = "unlinked"
    return result


def output_for_record(
    orchestrator: Any,
    record: Mapping[str, Any],
    inference: Mapping[str, Any],
) -> dict[str, Any]:
    gates = normalize_gates(inference["gates"])
    if not record["title"].strip() and not record["abstract"].strip():
        gates = {gate: "unclear" for gate in GATE_ORDER}
    quotes = evidence_quotes(record, gates)
    basis = "abstract" if record["has_abstract"] else "title_only"
    try:
        decision, reasons, confidence = orchestrator._expected_mapping(gates, basis, quotes)
    except RuntimeError:
        for gate in ("attribution", "result_type", "risk_context", "route", "exposure", "source"):
            if gates[gate] != "unclear":
                gates[gate] = "unclear"
                break
        quotes = evidence_quotes(record, gates)
        decision, reasons, confidence = orchestrator._expected_mapping(gates, basis, quotes)
    uncertain_gate = [gate for gate in GATE_ORDER if gates[gate] == "unclear"] if decision == "uncertain" else []
    value = {
        "record_id": record["record_id"],
        "question_id": record["question_id"],
        "decision": decision,
        "reason_codes": reasons,
        "confidence": confidence,
        "evidence_basis": basis,
        "gates": gates,
        "evidence_quotes": quotes,
        "uncertain_gate": uncertain_gate,
        "rationale": (
            "The quoted source text supports the recorded exposure, risk-context, "
            "result-type, and attribution gate selections."
        ),
    }
    orchestrator.validate_agent_decision(value, record, context=f"generated:{record['record_id']}")
    return value


def screen_records(
    model: GateModel,
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    orchestrator = load_orchestrator()
    normalized = [normalized_record(record) for record in records]
    outputs: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for start in range(0, len(normalized), model.batch_size):
        batch = normalized[start : start + model.batch_size]
        inferred = model.infer(batch)
        for record, inference in zip(batch, inferred, strict=True):
            outputs.append(output_for_record(orchestrator, record, inference))
            diagnostics.append(
                {
                    "record_id": record["record_id"],
                    "question_id": record["question_id"],
                    **inference,
                }
            )
    return outputs, diagnostics


def load_records(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") or payload.get("rows")
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"input has no records/rows: {path}")
    return payload, records


def model_from_args(args: argparse.Namespace) -> GateModel:
    return GateModel(
        snapshot=Path(args.model_snapshot),
        model_id=args.model_id,
        revision=args.model_revision,
        max_input_tokens=args.max_input_tokens,
        batch_size=args.inference_batch_size,
        min_probability=args.min_probability,
        min_margin=args.min_margin,
    )


def run_one(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    payload, records = load_records(input_path)
    model = model_from_args(args)
    started = utc_now()
    clock = time.perf_counter()
    outputs, diagnostics = screen_records(model, records)
    elapsed = time.perf_counter() - clock
    atomic_write_jsonl(output_path, outputs)
    diagnostic_path = output_path.with_suffix(output_path.suffix + ".diagnostics.json")
    report = {
        "schema_version": "local-gate-run-v1",
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "input_path": str(input_path),
        "input_sha256": sha256_file(input_path),
        "input_declared_sha256": payload.get("batch_input_sha256") or payload.get("input_sha256"),
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
        "rows": len(outputs),
        "elapsed_seconds": elapsed,
        "rows_per_second": len(outputs) / elapsed if elapsed else None,
        "decision_distribution": dict(Counter(row["decision"] for row in outputs)),
        "evidence_basis_distribution": dict(Counter(row["evidence_basis"] for row in outputs)),
        "truncated_rows": sum(item["input_truncated"] for item in diagnostics),
        "model_provenance": model.provenance(),
        "diagnostics": diagnostics,
    }
    atomic_write_json(diagnostic_path, report)
    return {key: value for key, value in report.items() if key != "diagnostics"}


def add_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-snapshot", default=str(DEFAULT_14B_SNAPSHOT))
    parser.add_argument("--model-id", default=DEFAULT_14B_ID)
    parser.add_argument("--model-revision", default=DEFAULT_14B_REVISION)
    parser.add_argument("--max-input-tokens", type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    parser.add_argument("--inference-batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--min-probability", type=float, default=0.0)
    parser.add_argument("--min-margin", type=float, default=0.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run-one", help="screen one pilot or formal batch JSON")
    run.add_argument("--input", required=True)
    run.add_argument("--output", required=True)
    add_model_args(run)
    provenance = subparsers.add_parser("provenance", help="print model/classifier provenance")
    add_model_args(provenance)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run-one":
        result = run_one(args)
    elif args.command == "provenance":
        result = model_from_args(args).provenance()
    else:
        raise RuntimeError(f"unknown command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
