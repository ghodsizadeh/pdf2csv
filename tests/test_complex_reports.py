"""Read shaded, merged and rotated layouts without relying on the user PDF."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pdfplumber
import pytest

from pdf2csv import convert, extract_document
from pdf2csv.extract import _cluster, _text_in_box

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_background_rectangles_do_not_invent_cells_or_headers():
    result = extract_document(EXAMPLES / "word_shading_and_title.pdf")
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.method == "ruled"
    assert list(table.dataframe.columns) == ["Name", "Score", "Team"]
    assert table.dataframe.values.tolist() == [
        ["Ada", 10, "Blue"],
        ["Grace", 12, "Green"],
        ["Linus", 14, "Red"],
    ]
    assert not table.warnings


def test_partial_body_rules_keep_one_table_and_repeat_rowspanning_units():
    tables = extract_document(EXAMPLES / "partial_rules_rowspan.pdf", pages=[1]).tables
    assert len(tables) == 1
    assert list(tables[0].dataframe.columns) == ["Name", "Unit", "Amount"]
    assert tables[0].dataframe.values.tolist() == [
        ["Ada", "kWh", 10],
        ["Grace", "kWh", 12],
        ["Linus", "kWh", 14],
    ]


def test_partial_subcolumns_and_column_spans_preserve_text_once():
    tables = extract_document(EXAMPLES / "partial_rules_rowspan.pdf", pages=[2]).tables
    assert len(tables) == 1
    assert list(tables[0].dataframe.columns) == ["Name", "Details", "Details", "Amount"]
    assert tables[0].dataframe.values.tolist() == [
        ["Ada", "Combined label", "", 10],
        ["Grace", "Left", "Right", 12],
    ]
    assert [w.code for w in tables[0].warnings] == ["duplicate_header"]


@pytest.mark.parametrize("page", [1, 2, 3, 4])
def test_quarter_turns_preserve_numbers_signs_and_farsi(page):
    tables = extract_document(EXAMPLES / "quarter_turn_text.pdf", pages=[page]).tables
    assert len(tables) == 1
    assert list(tables[0].dataframe.columns) == ["Case", "Value", "Text"]
    assert tables[0].dataframe.values.tolist() == [
        ["One", -21.7, "سلام ۱۲۳"],
        ["Two", 1015.0, "سلام ٤٥٦"],
    ]


def test_matrix_controls_orientation_even_when_pdfminer_calls_it_upright():
    with pdfplumber.open(EXAMPLES / "quarter_turn_text.pdf") as pdf:
        page = pdf.pages[1]
        chars = [{**c, "upright": True} for c in page.chars]
        assert (
            _text_in_box(SimpleNamespace(chars=chars), 180, 160, 310, 240, False)
            == "-21.7"
        )


def test_page_frame_does_not_connect_independent_tables():
    result = extract_document(EXAMPLES / "frame_touching_tables.pdf")
    assert len(result.tables) == 2
    expected = pd.DataFrame({"Name": ["Ada", "Grace"], "Score": [10, 12]})
    for table in result.tables:
        pd.testing.assert_frame_equal(table.dataframe, expected)
    cropped = extract_document(
        EXAMPLES / "frame_touching_tables.pdf", crop=result.tables[0].bbox
    )
    assert len(cropped.tables) == 1
    pd.testing.assert_frame_equal(cropped.tables[0].dataframe, expected)


def test_prose_and_separate_headings_are_not_tables():
    assert convert(EXAMPLES / "borderless_prose.pdf") == []


def test_real_borderless_tables_need_not_contain_numbers():
    tables = convert(EXAMPLES / "borderless_text_only.pdf")
    assert len(tables) == 1
    assert list(tables[0].columns) == ["Name", "State"]
    assert tables[0].values.tolist() == [["Alpha", "Enabled"], ["Beta", "Disabled"]]


def test_rule_snapping_does_not_chain_across_neighboring_positions():
    rules = _cluster([(40, 10, 60), (41, 10, 60), (42, 10, 60)])
    assert len(rules) == 2
