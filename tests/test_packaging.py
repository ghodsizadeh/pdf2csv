"""Smoke tests for the installed package, not just the locked environment."""

from importlib.metadata import requires
import subprocess
import sys

from packaging.requirements import Requirement


def test_imported_libraries_are_direct_dependencies():
    dependencies = {Requirement(item).name for item in requires("pdf2csv")}
    assert {"click", "openpyxl", "pandas", "pdfplumber", "typer"} <= dependencies


def test_installed_cli_starts():
    result = subprocess.run(
        [sys.executable, "-m", "pdf2csv.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "convert-cli" in result.stdout
