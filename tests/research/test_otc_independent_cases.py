import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "otc" / "validate_independent_cases.py"
SPEC = importlib.util.spec_from_file_location("validate_independent_cases", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_case_payloads_remain_unlabeled_while_external_confirmation_is_recorded() -> None:
    result = MODULE.validate()
    assert result == {"valid": True, "cases": 13, "families": 12, "verified_product_inputs": 16, "human_labels": 13, "predictions": 13, "errors": []}
