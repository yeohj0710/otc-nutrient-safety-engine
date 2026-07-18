from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "research" / "verify_pubmed_raw_manifests.py"
SPEC = importlib.util.spec_from_file_location("verify_pubmed_raw_manifests", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_detects_hash_mismatch(tmp_path: Path) -> None:
    run = tmp_path / "K1"
    run.mkdir()
    raw = run / "raw.xml"
    raw.write_text("actual", encoding="utf-8")
    (run / "raw_manifest.json").write_text(
        json.dumps({
            "node_id": "K1",
            "raw_files": [{"path": "raw.xml", "size": 6, "sha256": "wrong"}],
        }),
        encoding="utf-8",
    )
    report = MODULE.verify(tmp_path)
    assert report["valid"] is False
    assert report["failures"][0]["error"] == "integrity_mismatch"
