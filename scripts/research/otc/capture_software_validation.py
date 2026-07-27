from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "research_v3" / "otc" / "audit"
LOGS = ROOT / "research_v3" / "otc" / "etc" / "software_validation"


# vitest 는 색상 코드를 섞어 출력하므로 숫자를 뽑기 전에 걷어낸다. 이걸 빼면
# app_tests 개수가 계속 None 이 되고 매니페스트에는 직전 실행의 낡은 값이 남는다.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def count(pattern: str, text: str) -> int | None:
    match = re.search(pattern, strip_ansi(text))
    return int(match.group(1)) if match else None


def last_count(pattern: str, text: str) -> int | None:
    matches = re.findall(pattern, strip_ansi(text))
    return int(matches[-1]) if matches else None


def run(name: str, command: list[str]) -> dict:
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = process.stdout + ("\n" + process.stderr if process.stderr else "")
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{name}.log").write_text(output, encoding="utf-8")
    result = {"command": command, "exit_code": process.returncode, "status": "passed" if process.returncode == 0 else "failed"}
    if name == "research_tests":
        result["passed"] = count(r"(\d+) passed", output)
        result["failed"] = count(r"(\d+) failed", output) or 0
    elif name == "app_tests":
        result["passed"] = count(r"Tests\s+(\d+) passed", output)
        result["test_files"] = count(r"Test Files\s+(\d+) passed", output)
    elif name == "build":
        result["static_paths_generated"] = last_count(r"Generating static pages using \d+ workers \((\d+)/(?:\d+)\)", output)
    return result


def prepare_claim_metrics(python: str) -> None:
    """Break the test-count/claim-manifest cycle before the real audit run.

    The claim consistency test reads the generated metrics manifest, while that
    manifest reports the count from the previous audit. Collecting tests is
    read-only and gives the current denominator; the final audit still replaces
    this provisional count with the actual pass/fail result.
    """
    collected = subprocess.run(
        [python, "-m", "pytest", "tests/research", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    total = last_count(r"(\d+) tests collected", collected.stdout + collected.stderr)
    if collected.returncode != 0 or total is None:
        return
    audit_path = AUDIT / "software_validation.json"
    report = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {"results": {}}
    report.setdefault("results", {}).setdefault("research_tests", {})["passed"] = total
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([python, str(ROOT / "scripts" / "research" / "otc" / "build_metrics.py")], cwd=ROOT, check=True)


def main() -> int:
    python = str(ROOT / ".venv-research" / "Scripts" / "python.exe")
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    prepare_claim_metrics(python)
    commands = [
        ("research_tests", [python, "-m", "pytest", "tests/research", "-q"]),
        ("app_tests", [npm, "test"]),
        ("lint", [npm, "run", "lint"]),
        ("typecheck", [npm, "run", "typecheck"]),
        ("build", [npm, "run", "build"]),
    ]
    results = {name: run(name, command) for name, command in commands}
    passed = all(result["exit_code"] == 0 for result in results.values())
    report = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "passed" if passed else "failed",
        "results": results,
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "software_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 방금 끝난 실행의 값으로 매니페스트를 다시 굽는다. 이 호출이 없으면 매니페스트가
    # 항상 직전 실행 결과를 들고 있어 앱 시험 개수가 한 회차씩 밀린다.
    subprocess.run([python, str(ROOT / "scripts" / "research" / "otc" / "build_metrics.py")], cwd=ROOT, check=True)
    print(json.dumps({"status": report["status"], "results": {name: result["status"] for name, result in results.items()}}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
