import csv
import json
from pathlib import Path

from scripts.research.predict_independent_scenarios import run


def write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_predictions_are_frozen_without_reading_gold_labels(tmp_path: Path) -> None:
    rules = tmp_path / "rules.csv"
    scenarios = tmp_path / "scenarios.csv"
    output = tmp_path / "predictions.csv"
    write(rules, ["rule_id", "ingredient_id", "conditions_json"], [{"rule_id": "RULE-Z", "ingredient_id": "zinc", "conditions_json": json.dumps({"daily_total_mg_gt": 35})}])
    write(scenarios, ["scenario_id", "input_json", "gold_hazards_json"], [{"scenario_id": "S-1", "input_json": json.dumps({"ingredient": "zinc", "daily_total_mg": 36}), "gold_hazards_json": "SHOULD_NOT_BE_READ"}])
    result = run(rules, scenarios, output)
    row = next(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert result["predictions"] == 1 and result["frozen_before_human_gold"] is True
    assert json.loads(row["predicted_hazards_json"]) == ["RULE-Z"]
    assert "SHOULD_NOT_BE_READ" not in output.read_text(encoding="utf-8-sig")
