#!/usr/bin/env python3
"""Validate JSON or JSONL artifacts against a JSON Schema."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install jsonschema before running this validator") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema")
    parser.add_argument("artifact")
    parser.add_argument("--jsonl", action="store_true")
    parser.add_argument("--out", default="json_schema_validation.json")
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    artifact = Path(args.artifact)
    if args.jsonl:
        instances = []
        for line_number, line in enumerate(artifact.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                instances.append((line_number, json.loads(line)))
    else:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        instances = [(1, item) for item in payload] if isinstance(payload, list) else [(1, payload)]

    errors: list[dict[str, object]] = []
    for item_number, instance in instances:
        for error in sorted(validator.iter_errors(instance), key=lambda value: list(value.path)):
            errors.append(
                {
                    "item": item_number,
                    "path": "/".join(str(part) for part in error.absolute_path),
                    "message": error.message,
                }
            )
    result = {"schema": args.schema, "artifact": args.artifact, "items": len(instances), "errors": errors, "pass": not errors}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
