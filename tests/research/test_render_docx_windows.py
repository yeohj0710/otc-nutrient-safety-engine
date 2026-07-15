from pathlib import Path

import pytest

from scripts.research.otc.render_docx_windows import (
    find_libreoffice_console,
    validate_bootstrap,
)


def test_find_libreoffice_uses_console_launcher(tmp_path: Path):
    program = tmp_path / "program"
    program.mkdir()
    (program / "soffice.exe").touch()
    (program / "soffice.com").touch()

    assert find_libreoffice_console(program) == program / "soffice.com"


def test_validate_bootstrap_accepts_required_keys(tmp_path: Path):
    bootstrap = tmp_path / "bootstrap.ini"
    bootstrap.write_text(
        "[Bootstrap]\n"
        "InstallMode=<installmode>\n"
        "ProductKey=LibreOffice 26.2\n"
        "UserInstallation=$SYSUSERCONFIG/LibreOffice/4\n",
        encoding="utf-8",
    )

    validate_bootstrap(bootstrap)


def test_validate_bootstrap_rejects_damaged_file(tmp_path: Path):
    bootstrap = tmp_path / "bootstrap.ini"
    bootstrap.write_text("damaged", encoding="utf-8")

    with pytest.raises(RuntimeError, match="LibreOffice installation is damaged"):
        validate_bootstrap(bootstrap)
