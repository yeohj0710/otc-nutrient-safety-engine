from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


DEFAULT_PROGRAM = Path(r"C:\Program Files\LibreOffice\program")
REQUIRED_BOOTSTRAP_KEYS = ("[Bootstrap]", "ProductKey=LibreOffice", "UserInstallation=")


def find_libreoffice_console(program_dir: Path = DEFAULT_PROGRAM) -> Path:
    launcher = program_dir / "soffice.com"
    if not launcher.is_file():
        raise FileNotFoundError(f"LibreOffice console launcher not found: {launcher}")
    return launcher


def validate_bootstrap(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"LibreOffice installation is damaged: {path}") from exc
    if not all(key in text for key in REQUIRED_BOOTSTRAP_KEYS):
        raise RuntimeError(
            f"LibreOffice installation is damaged: {path}. "
            "Run: winget install --id TheDocumentFoundation.LibreOffice --exact --force"
        )


def render_docx(source: Path, destination: Path, program_dir: Path = DEFAULT_PROGRAM) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if source.suffix.lower() != ".docx" or not source.is_file():
        raise FileNotFoundError(f"DOCX not found: {source}")

    validate_bootstrap(program_dir / "bootstrap.ini")
    launcher = find_libreoffice_console(program_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="otc-lo-") as raw_temp:
        temp = Path(raw_temp)
        input_copy = temp / "input.docx"
        output_dir = temp / "output"
        profile_dir = temp / "profile"
        output_dir.mkdir()
        profile_dir.mkdir()
        shutil.copy2(source, input_copy)
        profile_uri = profile_dir.as_uri()
        command = [
            str(launcher),
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_copy),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        generated = output_dir / "input.pdf"
        if result.returncode or not generated.is_file() or generated.stat().st_size == 0:
            detail = (result.stdout + "\n" + result.stderr).strip()
            raise RuntimeError(f"LibreOffice conversion failed ({result.returncode}): {detail}")
        shutil.copy2(generated, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX to PDF safely on Windows.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    output = render_docx(args.source, args.destination)
    print(f"rendered={output} size={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
