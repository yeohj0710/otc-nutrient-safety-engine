from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


RATIO_RE = re.compile(
    r"(?i)\b(odds ratio|risk ratio|relative risk|hazard ratio|incidence rate ratio|OR|RR|HR|IRR)"
    r"\s*(?:[,=:]|of|was)?\s*([0-9]+(?:\.[0-9]+)?)"
    r"(?:\s*[;(,]?\s*95%\s*(?:CI|confidence interval)\s*[,=:]?\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*(?:to|[-–—])\s*([0-9]+(?:\.[0-9]+)?))?"
)
PERCENT_RE = re.compile(r"(?<![\w.])([<>~]?)\s*([0-9]+(?:\.[0-9]+)?)(?:\s*[-–—]\s*([0-9]+(?:\.[0-9]+)?))?\s*%")
FRACTION_RE = re.compile(r"(?<![\w.])([0-9]+)\s*/\s*([0-9]+)(?![\w.])")

FIELDS = [
    "quantitative_id", "evidence_id", "record_id", "ingredient_id", "statistic_type",
    "measure_label", "estimate", "ci_lower", "ci_upper", "range_lower", "range_upper",
    "numerator", "denominator", "unit", "exact_text", "source_id", "locator",
    "extraction_method", "validation_status", "synthesis_eligible",
]


def normalized_label(label: str) -> str:
    value = label.lower().replace(" ", "_")
    return {
        "odds_ratio": "OR", "risk_ratio": "RR", "relative_risk": "RR",
        "hazard_ratio": "HR", "incidence_rate_ratio": "IRR",
    }.get(value, label.upper())


def extract_row(row: dict[str, str]) -> list[dict[str, str]]:
    quote = row["verbatim_quote"]
    found: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []
    for match in RATIO_RE.finditer(quote):
        occupied.append(match.span())
        found.append({
            "statistic_type": "relative_effect_measure",
            "measure_label": normalized_label(match.group(1)),
            "estimate": match.group(2),
            "ci_lower": match.group(3) or "",
            "ci_upper": match.group(4) or "",
            "unit": "ratio",
            "exact_text": match.group(0),
        })
    for match in PERCENT_RE.finditer(quote):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        lower, upper = match.group(2), match.group(3) or ""
        found.append({
            "statistic_type": "reported_percentage",
            "measure_label": "percentage",
            "estimate": lower if not upper else "",
            "range_lower": lower if upper else "",
            "range_upper": upper,
            "unit": "%",
            "exact_text": match.group(0),
        })
    for match in FRACTION_RE.finditer(quote):
        found.append({
            "statistic_type": "reported_fraction",
            "measure_label": "fraction",
            "numerator": match.group(1),
            "denominator": match.group(2),
            "unit": "count",
            "exact_text": match.group(0),
        })
    output = []
    for index, item in enumerate(found, start=1):
        record = {field: "" for field in FIELDS}
        record.update(item)
        record.update({
            "quantitative_id": f"QT-{row['evidence_id']}-{index:02d}",
            "evidence_id": row["evidence_id"],
            "record_id": row["record_id"],
            "ingredient_id": row["ingredient_id"],
            "source_id": row["source_id"],
            "locator": row["locator"],
            "extraction_method": "deterministic_regex_from_human_verified_quote",
            "validation_status": "codex_structured_not_independently_verified",
            "synthesis_eligible": "false",
        })
        output.append(record)
    return output


def build(input_path: Path, output_path: Path, report_path: Path) -> dict[str, object]:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    quantitative = [item for row in evidence for item in extract_row(row)]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(quantitative)
    output_bytes = output_path.read_bytes()
    report = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_evidence_rows": len(evidence),
        "rows_with_reported_statistics": len({row["evidence_id"] for row in quantitative}),
        "reported_statistics": len(quantitative),
        "counts_by_type": {
            kind: sum(row["statistic_type"] == kind for row in quantitative)
            for kind in ("relative_effect_measure", "reported_percentage", "reported_fraction")
        },
        "output": output_path.as_posix(),
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "claim_boundary": "Exact reported statistics only. No causal interpretation, risk-of-bias judgment, pooling, or clinical conclusion; synthesis_eligible is false for every row.",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(build(args.input.resolve(), args.output.resolve(), args.report.resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
