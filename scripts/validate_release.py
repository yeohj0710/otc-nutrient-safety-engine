#!/usr/bin/env python3
"""Validate the active research release boundary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    boundary = json.loads((REPO / "research_v2" / "protocol" / "claim_boundary.json").read_text(encoding="utf-8"))
    design = boundary.get("study_design")
    if design != "pubmed_single_reviewer_feasibility":
        raise SystemExit(f"unsupported active release boundary: {design}")
    runtime = Path(sys.executable)
    bundled = Path(r"C:\Users\hjyeo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    if bundled.exists():
        runtime = bundled
    result = subprocess.run([str(runtime), str(REPO / "scripts" / "validate_feasibility_release.py")], cwd=REPO)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
