from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.evaluate_research_v3_draft_rules import evaluate


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(rules_path: Path, scenarios_path: Path, output: Path) -> dict[str, object]:
    rules = read_rows(rules_path)
    scenarios = read_rows(scenarios_path)
    frozen_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = []
    for scenario in scenarios:
        payload = json.loads(scenario["input_json"])
        rows.append({"scenario_id": scenario["scenario_id"], "predicted_hazards_json": json.dumps(evaluate(rules, payload), ensure_ascii=False), "predicted_at_utc": frozen_at, "rules_sha256": sha256(rules_path), "scenario_inputs_sha256": sha256(scenarios_path)})
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["scenario_id", "predicted_hazards_json", "predicted_at_utc", "rules_sha256", "scenario_inputs_sha256"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return {"predictions": len(rows), "rules_sha256": sha256(rules_path), "scenario_inputs_sha256": sha256(scenarios_path), "output_sha256": sha256(output), "frozen_before_human_gold": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=Path("research_v3/rules/rules.csv"))
    parser.add_argument("--scenarios", type=Path, default=Path("research_v3/human_review_minimal/05_독립시나리오_12건_확정.csv"))
    parser.add_argument("--output", type=Path, default=Path("research_v3/validation/independent_predictions.csv"))
    args = parser.parse_args()
    print(json.dumps(run(args.rules, args.scenarios, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
