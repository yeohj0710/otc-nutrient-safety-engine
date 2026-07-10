#!/usr/bin/env python3
"""Hash versioned AI prompts without asserting that a model run occurred."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt_dir")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    prompt_dir = Path(args.prompt_dir)
    prompts = []
    for path in sorted(prompt_dir.glob("*.md")):
        prompts.append(
            {
                "name": path.name,
                "path": str(path.as_posix()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if not prompts:
        raise SystemExit("No prompt files found")
    result = {
        "status": "prompts_frozen_model_not_selected",
        "prompts": prompts,
        "held_out_tuning_prohibited": True,
        "model": None,
        "model_version": None,
        "run_executed": False,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
