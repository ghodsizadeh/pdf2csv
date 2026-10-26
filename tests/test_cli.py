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


@pytest.mark.parametrize("command", ["convert", "convert-cli"])
@pytest.mark.parametrize("name", ["english_pages", "farsi_pages"])
@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_cli_exports_english_and_farsi(command, name, output_format, tmp_path):
    path = ROOT / "examples" / f"{name}.pdf"
    result = CliRunner().invoke(
        app, [command, str(path), "-o", str(tmp_path), "-f", output_format]
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


@pytest.mark.parametrize("option", ["--max-pages", "--max-bytes"])
@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_limits_require_positive_integers(option, value, tmp_path, monkeypatch):
    def unexpected_conversion(*args, **kwargs):
        pytest.fail("Usage errors must not run conversion")

    monkeypatch.setattr("pdf2csv.cli.convert", unexpected_conversion)
    destination = tmp_path / "output"
    result = CliRunner().invoke(
        app, ["convert", "input.pdf", "-o", str(destination), option, value]
    )
    assert result.exit_code == 2
    assert not destination.exists()


def test_limits_are_forwarded_with_one_extraction(tmp_path, monkeypatch):
    calls = []

    def fake_convert(*args, **kwargs):
        calls.append((args, kwargs))
        return [pd.DataFrame({"name": ["value"]})]

    monkeypatch.setattr("pdf2csv.cli.convert", fake_convert)
    result = CliRunner().invoke(
        app,
        [
            "convert",
            "input.pdf",
            "-o",
            str(tmp_path),
            "--max-pages",
            "7",
            "--max-bytes",
            "1024",
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls == [
        (
            ("input.pdf",),
            {
                "output_dir": None,
                "rtl": False,
                "output_format": "csv",
                "max_pages": 7,
                "max_bytes": 1024,
            },
        )
    ]
    assert (tmp_path / "input-table-1.csv").read_text() == "name\nvalue\n"


@pytest.mark.parametrize("option,value", [("--max-pages", "1"), ("--max-bytes", "1")])
def test_input_limit_exceeded_fails_without_output(option, value, tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "convert",
            str(ROOT / "examples/english_pages.pdf"),
            "-o",
            str(tmp_path),
            option,
            value,
        ],
    )
    assert result.exit_code == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("strict", [False, True])
def test_empty_results_are_successful_unless_strict(
    strict, tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr("pdf2csv.cli.convert", lambda *args, **kwargs: [])
    destination = tmp_path / "output"
    args = ["convert", "input.pdf", "-o", str(destination)]
    if strict:
        args.append("--fail-on-empty")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == (1 if strict else 0), result.output
    assert not destination.exists()
    if strict:
        assert "No tables were found" in caplog.text


@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
@pytest.mark.parametrize("collision", ["file", "directory", "dangling-symlink"])
def test_known_collision_preserves_all_outputs(
    output_format, collision, tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(
        "pdf2csv.cli.convert",
        lambda *args, **kwargs: [pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]})],
    )
    existing = tmp_path / f"input-table-2.{output_format}"
    if collision == "file":
        existing.write_bytes(b"previous export")
    elif collision == "directory":
        existing.mkdir()
    else:
        existing.symlink_to(tmp_path / "missing")
    result = CliRunner().invoke(
        app, ["convert", "input.pdf", "-o", str(tmp_path), "-f", output_format]
    )
    assert result.exit_code == 1
    assert not (tmp_path / f"input-table-1.{output_format}").exists()
    assert "--overwrite" in caplog.text
    if collision == "file":
        assert existing.read_bytes() == b"previous export"
    elif collision == "directory":
        assert existing.is_dir()
    else:
        assert existing.is_symlink()
        assert not existing.exists()


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_writes_exact_destinations_only(
    overwrite, output_format, tmp_path, monkeypatch
):
    frame = pd.DataFrame({"a": [42]})
    monkeypatch.setattr("pdf2csv.cli.convert", lambda *args, **kwargs: [frame])
    unrelated = tmp_path / f"input-table-2.{output_format}"
    unrelated.write_text("keep", encoding="utf-8")
    destination = tmp_path / f"input-table-1.{output_format}"
    if overwrite:
        destination.write_text("replace", encoding="utf-8")
    args = ["convert", "input.pdf", "-o", str(tmp_path), "-f", output_format]
    if overwrite:
        args.append("--overwrite")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    saved = (
        pd.read_csv(destination)
        if output_format == "csv"
        else pd.read_excel(destination)
    )
    pd.testing.assert_frame_equal(saved, frame)
    assert unrelated.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("expected_error", [False, True])
def test_tracebacks_are_only_logged_in_verbose_mode(
    verbose, expected_error, monkeypatch, caplog
):
    from pdf2csv.errors import Pdf2CsvError

    def fail(*args, **kwargs):
        raise (
            Pdf2CsvError("conversion failed")
            if expected_error
            else RuntimeError("failed")
        )

    monkeypatch.setattr("pdf2csv.cli.convert", fail)
    args = ["convert", "input.pdf"]
    if verbose:
        args.append("--verbose")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert bool(caplog.records[-1].exc_info) is verbose
