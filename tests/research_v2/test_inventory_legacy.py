from __future__ import annotations

from pathlib import Path

from scripts.research.inventory_legacy import inventory


def test_inventory_records_sha256_and_classification(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "old.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    rows = inventory([source], repo_root=tmp_path)

    assert len(rows) == 1
    assert len(rows[0]["sha256"]) == 64
    assert rows[0]["trust_status"] == "legacy_untrusted"
    assert rows[0]["disposition"] == "audit_only"
    assert rows[0]["relative_path"] == "old.csv"


def test_inventory_skips_generated_research_and_dependency_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "legacy.csv").write_text("x\n1\n", encoding="utf-8")
    for directory in ("research_v2", "execution_package", "node_modules", ".git"):
        path = tmp_path / directory
        path.mkdir()
        (path / "ignored.txt").write_text("ignored", encoding="utf-8")

    rows = inventory([tmp_path], repo_root=tmp_path)

    assert [row["relative_path"] for row in rows] == ["data/legacy.csv"]
