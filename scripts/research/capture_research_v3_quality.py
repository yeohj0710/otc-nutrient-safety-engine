from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(command: list[str], cwd: Path) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "output": completed.stdout,
    }


def capture(repo: Path) -> dict[str, object]:
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    checks = {
        "research_tests": run([sys.executable, "-m", "pytest", "tests/research", "-q"], repo),
        "app_tests": run([npm, "test", "--", "--run"], repo),
        "lint": run([npm, "run", "lint"], repo),
        "typecheck": run([npm, "run", "typecheck"], repo),
        "production_build": run([npm, "run", "build"], repo),
    }
    research_match = re.search(r"(\d+) passed", str(checks["research_tests"]["output"]))
    app_match = re.search(r"Tests\s+(\d+) passed", str(checks["app_tests"]["output"]))
    path_match = re.search(r"Generating static pages.*?\((\d+)/(\d+)\)", str(checks["production_build"]["output"]), re.S)
    return {
        "schema_version": "1.0.0",
        "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "checks": checks,
        "summary": {
            "research_tests_passed": int(research_match.group(1)) if research_match else None,
            "app_tests_passed": int(app_match.group(1)) if app_match else None,
            "static_paths_generated": int(path_match.group(2)) if path_match else None,
            "all_exit_codes_zero": all(item["exit_code"] == 0 for item in checks.values()),
        },
        "scope_note": "호환성·빌드 검증. 사람 전문 검토나 독립 임상 성능 평가가 아님.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = capture(args.repo.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["summary"]["all_exit_codes_zero"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
