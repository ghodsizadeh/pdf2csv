"""The CLI must distinguish conversion failures from successful exports."""

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from pdf2csv import convert
from pdf2csv.cli import app

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("filename", ["missing.pdf", "encrypted.pdf"])
def test_bad_input_exits_nonzero(filename, tmp_path, caplog):
    result = CliRunner().invoke(
        app, ["convert-cli", str(ROOT / "tests/assets" / filename), "-o", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert caplog.records[-1].levelname == "ERROR"
    assert not list(tmp_path.iterdir())


def test_unreadable_pdf_exits_nonzero(tmp_path, caplog):
    path = tmp_path / "bad.pdf"
    path.write_text("not a PDF", encoding="utf-8")
    result = CliRunner().invoke(app, ["convert-cli", str(path)])
    assert result.exit_code == 1
    assert "parse" in caplog.text


def test_output_write_failure_exits_nonzero(tmp_path, caplog):
    destination = tmp_path / "already-a-file"
    destination.write_text("keep this content", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        ["convert-cli", str(ROOT / "examples/farsi_ruled.pdf"), "-o", str(destination)],
    )
    assert result.exit_code == 1
    assert "Error during PDF conversion" in caplog.text
    assert destination.read_text(encoding="utf-8") == "keep this content"


def test_unsupported_output_format_is_a_usage_error(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "convert-cli",
            str(ROOT / "examples/farsi_ruled.pdf"),
            "-o",
            str(tmp_path),
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["english_pages", "farsi_pages"])
@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_cli_exports_english_and_farsi(name, output_format, tmp_path):
    path = ROOT / "examples" / f"{name}.pdf"
    result = CliRunner().invoke(
        app, ["convert-cli", str(path), "-o", str(tmp_path), "-f", output_format]
    )
    assert result.exit_code == 0, result.output
    for index, expected in enumerate(convert(path), 1):
        saved_path = tmp_path / f"{name}-table-{index}.{output_format}"
        saved = (
            pd.read_csv(saved_path)
            if output_format == "csv"
            else pd.read_excel(saved_path)
        )
        pd.testing.assert_frame_equal(saved, expected)
