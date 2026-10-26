from pathlib import Path

import pandas as pd
import pytest

from typer.testing import CliRunner

from pdf2csv import Pdf2CsvError, convert
from pdf2csv.cli import app

ASSETS = Path(__file__).parent / "assets"
LEFT_HEADER = "درصد اختلاف نسبت به ميانگين بلندمدت"
RIGHT_HEADER = "حوضه آبریز اصلی"


@pytest.fixture
def rtl_pdf() -> Path:
    return ASSETS / "rtl_test.pdf"


def test_rtl_convert(rtl_pdf: Path):
    frames = convert(rtl_pdf, rtl=True)
    assert len(frames) == 1
    frame = frames[0]
    assert list(frame.columns)[0] == LEFT_HEADER
    assert list(frame.columns)[-1] == RIGHT_HEADER
    assert len(frame.columns) == 6
    assert len(frame) == 10
    assert frame.iloc[0, 0] == -44
    assert frame.iloc[0, -1] == "ارس"

    without_flag = convert(rtl_pdf, rtl=False)
    assert list(without_flag[0].columns) == list(frame.columns)
    assert without_flag[0].iloc[0, 0] == -44
    assert without_flag[0].iloc[0, -1] == "ارس"


def test_borderless_table_uses_text_alignment():
    frames = convert(ASSETS / "borderless_table.pdf")
    assert len(frames) == 1
    frame = frames[0]
    assert list(frame.columns) == ["Name", "Score"]
    assert frame.iloc[0, 0] == "Ada"
    assert frame.iloc[0, 1] == 10
    assert frame.iloc[1, 0] == "Grace"
    assert frame.iloc[1, 1] == 12


def test_simple_table_and_csv_roundtrip(tmp_path: Path):
    frames = convert(
        ASSETS / "simple_table.pdf",
        output_dir=tmp_path,
        output_format="csv",
        index=False,
    )
    assert len(frames) == 1
    frame = frames[0]
    assert list(frame.columns) == ["City", "2020", "2021"]
    assert frame.iloc[0, 0] == "Amsterdam"
    assert frame.iloc[0, 1] == 10
    assert frame.iloc[1, 2] == 9

    saved = pd.read_csv(tmp_path / "simple_table-table-1.csv")
    assert list(saved.columns) == ["City", "2020", "2021"]
    assert saved.iloc[0, 0] == "Amsterdam"
    assert saved.iloc[0, 1] == 10


def test_xlsx_roundtrip(rtl_pdf: Path, tmp_path: Path):
    frames = convert(
        rtl_pdf,
        output_dir=tmp_path,
        rtl=True,
        output_format="xlsx",
        index=False,
    )
    saved = pd.read_excel(tmp_path / "rtl_test-table-1.xlsx")
    assert list(saved.columns) == list(frames[0].columns)
    assert saved.iloc[0, 0] == -44
    assert len(saved) == 10


def test_missing_pdf():
    with pytest.raises(FileNotFoundError):
        convert(ASSETS / "missing.pdf")


def test_rejects_non_pdf(tmp_path: Path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(Pdf2CsvError, match="Not a PDF"):
        convert(notes)


def test_rejects_oversized_pdf(rtl_pdf: Path):
    with pytest.raises(Pdf2CsvError, match="exceeds the limit"):
        convert(rtl_pdf, max_bytes=1024)


def test_rejects_too_many_pages():
    with pytest.raises(Pdf2CsvError, match="exceeds the limit of 1"):
        convert(ASSETS / "two_pages.pdf", max_pages=1)


def test_rejects_encrypted_pdf():
    with pytest.raises(Pdf2CsvError, match="encrypted"):
        convert(ASSETS / "encrypted.pdf")


def test_rejects_unreadable_pdf(tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not really a pdf")
    with pytest.raises(Pdf2CsvError, match="parse"):
        convert(bad)


def test_cli_writes_csv(tmp_path: Path):
    result = CliRunner().invoke(
        app,
        [
            "convert-cli",
            str(ASSETS / "simple_table.pdf"),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    saved = pd.read_csv(tmp_path / "simple_table-table-1.csv")
    assert saved.iloc[0, 0] == "Amsterdam"
    assert saved.iloc[0, 1] == 10


def test_numeric_columns_keep_mixed_text():
    from pdf2csv.helpers import ensure_numeric_columns

    frame = pd.DataFrame({"value": ["۱۲", "۳"], "label": ["12", "ارس"]})
    converted = ensure_numeric_columns(frame)
    assert converted.iloc[0, 0] == 12
    assert converted.iloc[1, 0] == 3
    assert converted.iloc[1, 1] == "ارس"
