import hashlib
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_product_search_evaluation_is_reproducible_and_scoped() -> None:
    cases = ROOT / "research_v3/otc/validation/product_search_cases.csv"
    runtime = ROOT / "src/generated/otc-runtime.json"
    result = json.loads((ROOT / "research_v3/otc/validation/product_search_evaluation.json").read_text(encoding="utf-8"))
    assert result["status"] == "evaluated_fixed_development_cases_not_external_user_study"
    assert result["cases"] == 26 and result["successes"] == 26 and result["value"] == 1
    assert result["cases_sha256"] == canonical_text_sha256(cases)
    assert result["runtime_sha256"] == canonical_text_sha256(runtime)


def test_normalization_accuracy_uses_completed_human_reference() -> None:
    with (ROOT / "research_v3/otc/validation/normalization_reference.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    metrics = json.loads((ROOT / "research_v3/otc/metrics_manifest.json").read_text(encoding="utf-8"))
    result = metrics["metrics"]["ingredient_normalization_accuracy"]
    assert len(rows) == 31
    assert all(row["human_reference_name"] and row["human_reviewer_id"] for row in rows)
    assert result["status"] == "evaluated_human_locked_reference"
    assert result["value"] == 1.0 and result["numerator"] == 31 and result["denominator"] == 31
