from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research_v3" / "audit" / "v40_freeze_manifest.json"
FROZEN_TAG = "v3-otc-frozen"

FROZEN_PATHS = (
    Path("AGENTS.md"),
    Path("README.md"),
    Path("research_v3/DECISIONS.md"),
    Path("research_v3/HUMAN_ACTION_REQUIRED.md"),
    Path("research_v3/project_identity.json"),
    Path("research_v3/metrics_manifest.json"),
    Path("research_v3/otc/metrics_manifest.json"),
    Path("research_v3/otc/audit/completion_audit.json"),
    Path("research_v3/otc/normalized/product_master.csv"),
    Path("research_v3/otc/normalized/ingredient_master.csv"),
    Path("research_v3/otc/normalized/product_ingredient.csv"),
    Path("research_v3/otc/normalized/administration_constraints.csv"),
    Path("research_v3/otc/normalized/analysis_exclusions.csv"),
    Path("research_v3/otc/rules/rules.csv"),
    Path("research_v3/otc/rules/supporting_literature.csv"),
    Path("research_v3/otc/validation/independent_scenarios.csv"),
    Path("research_v3/screening/title_abstract.csv"),
    Path("research_v3/screening/full_text.csv"),
)
FROZEN_TREES = (
    Path("research_v3/approvals"),
    Path("research_v3/human_review_minimal"),
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def collect_paths() -> list[Path]:
    paths = list(FROZEN_PATHS)
    tag_paths = {
        Path(line)
        for line in git("ls-tree", "-r", "--name-only", FROZEN_TAG).splitlines()
    }
    for tree in FROZEN_TREES:
        paths.extend(path for path in tag_paths if tree in path.parents)
    unique = sorted(set(paths), key=lambda item: item.as_posix())
    missing = [path.as_posix() for path in unique if path not in tag_paths]
    if missing:
        raise FileNotFoundError(f"동결 대상 파일이 없습니다: {missing}")
    return unique


def main() -> None:
    tag_commit = git("rev-list", "-n", "1", FROZEN_TAG)
    records = []
    for relative in collect_paths():
        content = git_bytes("show", f"{FROZEN_TAG}:{relative.as_posix()}")
        records.append(
            {
                "path": relative.as_posix(),
                "bytes": len(content),
                "sha256": sha256(content),
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_tag": FROZEN_TAG,
        "frozen_commit": tag_commit,
        "artifact_count": len(records),
        "artifacts": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
