"""Structured extraction and explicitly separated conversion/export options."""

from pathlib import Path

import pandas as pd
import pytest

from pdf2csv import Pdf2CsvError, convert, export_frames, extract_document
from pdf2csv.converter import _frame_from_rows

ASSETS = Path(__file__).parent / "assets"
EXAMPLES = Path(__file__).parents[1] / "examples"


def test_metadata_preserves_rows_and_document_coordinates():
    result = extract_document(ASSETS / "simple_table.pdf")
    table = result.tables[0]
    assert result.source == ASSETS / "simple_table.pdf"
    assert table.page_number == 1
    assert table.method == "ruled"
    assert len(table.bbox) == 4
    assert table.bbox[0] < table.bbox[2]
    assert table.bbox[1] < table.bbox[3]
    assert table.rows[0] == ["City", "2020", "2021"]
    assert table.rows[1] == ["Amsterdam", "10", "12"]
    assert table.dataframe.iloc[0, 1] == 10
    table.dataframe.iloc[0, 1] = 99
    assert table.rows[1][1] == "10"
    assert not table.warnings
    assert not result.warnings


def test_text_method_identifies_borderless_table():
    table = extract_document(ASSETS / "borderless_table.pdf").tables[0]
    assert table.method == "text"
    assert table.rows == [["Name", "Score"], ["Ada", "10"], ["Grace", "12"]]


def test_headerless_table_retains_first_row():
    result = extract_document(
        ASSETS / "simple_table.pdf", header=None, numeric="preserve"
    )
    table = result.tables[0]
    assert list(table.dataframe.columns) == [0, 1, 2]
    assert table.dataframe.values.tolist() == table.rows
    pd.testing.assert_frame_equal(
        convert(ASSETS / "simple_table.pdf", table_header=None, numeric="preserve")[0],
        table.dataframe,
    )


def test_numeric_preserve_and_dtypes_keep_leading_zeroes():
    rows = [["id", "amount"], ["0012", "۱۲"], ["0003", "۳"]]
    assert _frame_from_rows(rows)["id"].tolist() == [12, 3]
    preserved = _frame_from_rows(rows, numeric="preserve")
    assert preserved.values.tolist() == rows[1:]
    controlled = _frame_from_rows(rows, dtypes={"id": "string"})
    assert controlled["id"].tolist() == ["0012", "0003"]
    assert controlled["amount"].tolist() == [12, 3]
    assert str(controlled["id"].dtype) == "string"
    assert rows[1] == ["0012", "۱۲"]


def test_public_numeric_and_dtype_options():
    path = ASSETS / "simple_table.pdf"
    assert (
        extract_document(path, numeric="preserve").tables[0].dataframe.iloc[0, 1]
        == "10"
    )
    frame = convert(path, dtypes={"2020": "string"})[0]
    assert frame.iloc[0, 1] == "10"
    assert frame.iloc[0, 2] == 12


def test_selected_pages_keep_document_order_and_numbers():
    path = EXAMPLES / "english_pages.pdf"
    result = extract_document(path, pages=[2, 1, 2])
    assert [table.page_number for table in result.tables] == [1, 2]
    assert [table.rows[0][0] for table in result.tables] == ["Name 1", "Name 2"]
    selected = extract_document(path, pages=[2])
    assert [table.page_number for table in selected.tables] == [2]
    pd.testing.assert_frame_equal(
        convert(path, pages=[2])[0], selected.tables[0].dataframe
    )
    with pytest.raises(Pdf2CsvError, match="exceeds the limit"):
        extract_document(path, pages=[1], max_pages=1)


def test_crop_uses_page_coordinates_and_preserves_metadata():
    path = EXAMPLES / "english_side_by_side.pdf"
    full = extract_document(path)
    assert len(full.tables) == 2
    box = full.tables[0].bbox
    table = extract_document(path, crop=box).tables[0]
    assert table.bbox == box
    assert table.rows == full.tables[0].rows
    assert table.method == "ruled"
    result = extract_document(
        EXAMPLES / "english_pages.pdf", pages=[2], crop={2: (0, 0, 595, 800)}
    )
    assert result.tables[0].page_number == 2


def test_warning_reports_page_with_no_tables():
    result = extract_document(ASSETS / "simple_table.pdf", crop=(0, 0, 20, 20))
    assert not result.tables
    assert [(warning.code, warning.page_number) for warning in result.warnings] == [
        ("no_tables", 1)
    ]


@pytest.mark.parametrize(
    "options,match",
    [
        ({"pages": []}, "pages"),
        ({"pages": [0]}, "pages"),
        ({"pages": [True]}, "pages"),
        ({"pages": "1"}, "pages"),
        ({"pages": [1.5]}, "pages"),
        ({"pages": [2]}, "beyond"),
        ({"crop": (1, 2, 3)}, "four finite"),
        ({"crop": (0, 0, float("nan"), 10)}, "four finite"),
        ({"crop": (0, 0, True, 10)}, "four finite"),
        ({"crop": (10, 10, 0, 20)}, "positive width"),
        ({"crop": (-1, 0, 10, 10)}, "outside"),
        ({"crop": {0: (0, 0, 10, 10)}}, "page numbers"),
        ({"crop": {2: (0, 0, 10, 10)}}, "beyond"),
        ({"pages": [1], "crop": {2: (0, 0, 10, 10)}}, "included"),
        ({"header": 1}, "header"),
        ({"header": False}, "header"),
        ({"numeric": "guess"}, "numeric"),
        ({"dtypes": "string"}, "dtypes"),
        ({"dtypes": {"City": "not-a-dtype"}}, "dtype"),
        ({"dtypes": {"missing": str}}, "column not found"),
        ({"dtypes": {"City": "int64"}}, "Could not convert"),
        ({"max_pages": True}, "positive integer"),
        ({"max_pages": 0}, "positive integer"),
        ({"max_bytes": 0}, "positive integer"),
    ],
)
def test_invalid_extraction_options(options, match):
    with pytest.raises(Pdf2CsvError, match=match):
        extract_document(ASSETS / "simple_table.pdf", **options)


def test_empty_and_duplicate_headers_have_observed_warnings(monkeypatch):
    from pdf2csv.models import ExtractedTable

    table = ExtractedTable(
        [["", "column_1"], ["001", "002"]], 1, (0, 0, 10, 10), "ruled"
    )
    monkeypatch.setattr(
        "pdf2csv.converter.extract_table_results", lambda *a, **kw: ([table], [])
    )
    result = extract_document(ASSETS / "simple_table.pdf")
    assert [warning.code for warning in result.tables[0].warnings] == [
        "empty_header",
        "duplicate_header",
    ]
    with pytest.raises(Pdf2CsvError, match="ambiguous"):
        extract_document(ASSETS / "simple_table.pdf", dtypes={"column_1": str})


def test_export_options_are_separate_from_extraction(tmp_path):
    frames = convert(
        ASSETS / "simple_table.pdf",
        output_dir=tmp_path,
        numeric="preserve",
        export_kwargs={"header": False, "index": False},
    )
    saved = tmp_path / "simple_table-table-1.csv"
    assert saved.read_text().splitlines()[0] == "Amsterdam,10,12"
    assert list(frames[0].columns) == ["City", "2020", "2021"]
    with pytest.raises(Pdf2CsvError, match="specified twice"):
        convert(ASSETS / "simple_table.pdf", index=False, export_kwargs={"index": True})
    with pytest.raises(Pdf2CsvError, match="mapping"):
        convert(ASSETS / "simple_table.pdf", export_kwargs="index")


def test_export_preflights_every_destination_before_writing(tmp_path):
    frames = [pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]})]
    second = tmp_path / "source-table-2.csv"
    second.write_text("keep me")
    with pytest.raises(FileExistsError, match="source-table-2.csv"):
        export_frames(frames, "source.pdf", tmp_path, overwrite=False)
    assert not (tmp_path / "source-table-1.csv").exists()
    assert second.read_text() == "keep me"
    paths = export_frames(frames, "source.pdf", tmp_path, index=False)
    assert paths == [tmp_path / "source-table-1.csv", second]
    assert second.read_text() == "b\n2\n"


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_export_preflight_rejects_nonfile_destinations(tmp_path, kind):
    destination = tmp_path / "source-table-1.csv"
    if kind == "directory":
        destination.mkdir()
    else:
        destination.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        export_frames(
            [pd.DataFrame({"a": [1]})], "source.pdf", tmp_path, overwrite=False
        )


def test_empty_export_does_not_create_directory(tmp_path):
    destination = tmp_path / "missing"
    assert export_frames([], "source.pdf", destination) == []
    assert not destination.exists()


def test_legacy_writer_header_option(tmp_path):
    frames = convert(
        ASSETS / "simple_table.pdf", output_dir=tmp_path, header=False, index=False
    )
    assert list(frames[0].columns) == ["City", "2020", "2021"]
    assert (tmp_path / "simple_table-table-1.csv").read_text().splitlines()[
        0
    ] == "Amsterdam,10,12"


def test_extract_submodule_remains_importable():
    import pdf2csv.extract as module

    assert callable(module.extract_tables)


def test_overwrite_preflights_directory_before_changing_other_files(tmp_path):
    first = tmp_path / "source-table-1.csv"
    first.write_text("preserve this")
    (tmp_path / "source-table-2.csv").mkdir()
    frames = [pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]})]
    with pytest.raises(IsADirectoryError):
        export_frames(frames, "source.pdf", tmp_path, overwrite=True)
    assert first.read_text() == "preserve this"


def test_headerless_dtype_keys_use_integer_column_labels():
    frame = _frame_from_rows(
        [["0012", "1"], ["0003", "2"]], header=None, dtypes={0: "string"}
    )
    assert frame[0].tolist() == ["0012", "0003"]
    assert frame[1].tolist() == [1, 2]
