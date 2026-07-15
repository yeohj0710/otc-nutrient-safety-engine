from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATION = ROOT / "research_v3" / "otc" / "validation"


def validate() -> dict[str, object]:
    with (VALIDATION / "independent_scenarios.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    families: set[str] = set()
    verified_product_inputs = 0
    human_labels = 0
    predictions = 0
    for row in rows:
        path = VALIDATION / row["case_payload_ref"]
        if not path.is_file():
            errors.append(f'{row["scenario_id"]}:missing_case')
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        families.add(payload.get("scenarioFamily", ""))
        if payload.get("scenarioId") != row["scenario_id"] or payload.get("scenarioFamily") != row["scenario_family"]:
            errors.append(f'{row["scenario_id"]}:identity_mismatch')
        if payload.get("referenceLabel") is not None or payload.get("prediction") is not None:
            errors.append(f'{row["scenario_id"]}:label_or_prediction_prefilled')
        if not payload.get("productInputs") or not isinstance(payload.get("userProfile"), dict):
            errors.append(f'{row["scenario_id"]}:invalid_input')
        verified_product_inputs += sum(item.get("inputType") == "verified_product" for item in payload.get("productInputs", []))
        human_labels += bool(row["human_reference_label"])
        predictions += bool(row["prediction"])
        if row["status"] == "human_label_locked_prediction_recorded":
            if not row["human_reference_label"] or not row["prediction"]:
                errors.append(f'{row["scenario_id"]}:evaluated_row_missing_label_or_prediction')
            if row["review_method"] != "codex_prefilled_external_human_confirmation":
                errors.append(f'{row["scenario_id"]}:unexpected_review_method')
            if row["independent_blinding"].lower() != "false":
                errors.append(f'{row["scenario_id"]}:blinding_misrepresented')
        elif row["human_reference_label"] or row["prediction"]:
            errors.append(f'{row["scenario_id"]}:unevaluated_row_has_label_or_prediction')
    return {"valid": not errors, "cases": len(rows), "families": len(families), "verified_product_inputs": verified_product_inputs, "human_labels": human_labels, "predictions": predictions, "errors": errors}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["valid"] else 1)
