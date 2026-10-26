"""RTL regressions include shaped text in real, embedded-font Farsi PDFs."""

from pathlib import Path

import pandas as pd
import pytest

from pdf2csv import convert
from pdf2csv.extract import _logical_tokens

EXAMPLES = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize("digits", ["123", "۱۲۳", "١٢٣", "۱۲.۳", "-۱۲۳"])
@pytest.mark.parametrize("force_rtl", [False, True])
def test_rtl_numbers_and_separating_spaces(digits, force_rtl):
    assert _logical_tokens(list(f"{digits} مالس"), force_rtl) == f"سلام {digits}"
    assert _logical_tokens(list(f"مالس {digits}"), force_rtl) == f"{digits} سلام"


def test_ltr_phrase_in_an_rtl_line():
    assert _logical_tokens(list("123 ABC مالس"), True) == "سلام 123 ABC"


def test_parentheses_around_numbers_and_rtl_words():
    assert _logical_tokens(list("(۱۲۳) مالس"), False) == "سلام (۱۲۳)"
    assert _logical_tokens(list("(مالس)"), False) == "(سلام)"
    # Existing PDFs may already map mirrored brackets to logical code points.
    assert _logical_tokens(list(")مالس("), False) == "(سلام)"


def test_existing_farsi_pdf_keeps_logical_parentheses():
    frame = convert(EXAMPLES.parent / "tests/assets/rtl_test.pdf", rtl=True)[0]
    assert list(frame.columns)[2:5] == [
        "ارتفاع بارندگی (ميليمتر) ميانگين بلند مدت",
        "ارتفاع بارندگی (ميليمتر) سال آبی گذشته",
        "ارتفاع بارندگی (ميليمتر) سال آبی جاری",
    ]


def test_ligature_is_not_reversed_inside_its_glyph():
    assert _logical_tokens(["لا", "م"], False) == "ملا"
    assert _logical_tokens(["\ufefb", "م"], False) == "ملا"


@pytest.mark.parametrize("name", ["farsi_ruled", "farsi_borderless"])
@pytest.mark.parametrize("rtl", [False, True])
def test_farsi_pdf_text_and_numeric_columns(name, rtl):
    frames = convert(EXAMPLES / f"{name}.pdf", rtl=rtl)
    assert len(frames) == 1
    expected = pd.DataFrame(
        {
            "شهر": ["تهران", "شیراز", "تبریز"],
            "جمعیت": [123, 456, 789],
            "توضیح": ["سلام ۱۲۳", "سلام ٤٥٦", "سلام 789"],
        }
    )
    pd.testing.assert_frame_equal(frames[0], expected)


def test_farsi_ruled_and_borderless_tables_are_both_found():
    frames = convert(EXAMPLES / "farsi_mixed.pdf")
    assert len(frames) == 2
    expected = convert(EXAMPLES / "farsi_ruled.pdf")[0]
    for frame in frames:
        pd.testing.assert_frame_equal(frame, expected)


@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_farsi_export_roundtrip(output_format, tmp_path):
    frames = convert(
        EXAMPLES / "farsi_ruled.pdf",
        output_dir=tmp_path,
        output_format=output_format,
        index=False,
    )
    destination = tmp_path / f"farsi_ruled-table-1.{output_format}"
    saved = (
        pd.read_csv(destination)
        if output_format == "csv"
        else pd.read_excel(destination)
    )
    pd.testing.assert_frame_equal(saved, frames[0])
