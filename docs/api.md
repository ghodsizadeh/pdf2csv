# Python extraction API

`convert()` still returns one pandas DataFrame per table, with the first row as
column labels and wholly numeric columns inferred by default. `extract_document()`
returns those frames together with the extracted strings and source metadata.
Neither function writes files unless `convert(output_dir=...)` is used.

```python
from pdf2csv import extract_document

result = extract_document("report.pdf", numeric="preserve")
for table in result.tables:
    print(table.page_number, table.bbox, table.method)
    print(table.rows)       # All extracted rows, including the first row.
    print(table.dataframe)  # Header/numeric/dtype options apply here only.
    for warning in table.warnings:
        print(warning.code, warning.message)
for warning in result.warnings:
    print(warning.page_number, warning.code, warning.message)
```

`ExtractionResult` has `source` (a Path), `tables`, and page-level `warnings`.
Each `ExtractedTable` has `rows` (`list[list[str]]`), `dataframe`, `page_number`,
`bbox`, `method`, and table-level `warnings`. The first source page is 1, even
when only later pages are selected. Tables follow document order, then top to
bottom and left to right within each page. `method` is `"ruled"` for a table
rebuilt from strokes or `"text"` for the text-alignment fallback.

The bounding box is `(x0, top, x1, bottom)` in PDF points (72 points per inch),
using pdfplumber's absolute page coordinates measured from the top-left.
Cropping retains this coordinate system. Raw rows retain extracted text before
header promotion, numeric conversion, or dtype conversion. They reflect existing
extraction cleanup, including joined header bands, normalized whitespace and
removed empty rows/columns; they are not a record of every original PDF glyph.
Changing a DataFrame does not change its table's raw rows.

Ruled tables use the physical cell boundaries, including partial row separators.
Row-spanning labels are repeated across their covered output rows; body text
spanning columns is emitted once in the leftmost covered column. Partial
subcolumns are retained, so a shared header can produce duplicate labels.
Full-width leading titles and trailing annotation bands are excluded. Stacked
headers are joined when there is evidence of the data boundary; otherwise rows
remain separate and receive an `ambiguous_header` warning. Different sections
within one connected grid are not automatically split into separate schemas;
repeated section headers remain rows.
These rules are geometric cleanup, not semantic interpretation of arbitrary
merged cells. Validate nested or irregular layouts against the PDF.

## Page selection and crops

```python
result = extract_document(
    "report.pdf",
    pages=[2, 4],
    crop={2: (40, 100, 550, 700), 4: (40, 80, 550, 600)},
)
# Or apply the same crop to every selected page:
result = extract_document("report.pdf", pages=[2, 4], crop=(40, 100, 550, 700))
```

`pages=None` selects every page. Otherwise, pass a non-empty sequence of positive,
1-based document page numbers. Duplicates are removed and output follows document
order regardless of selection order. Out-of-range pages are errors.

`crop=None` uses the whole page. A four-coordinate crop applies to every selected
page; a mapping applies a crop only to its specified pages. Mapping keys must
refer to selected pages. Crops require finite numeric coordinates, positive width
and height, and must fit inside the source page. Provide enough area to include
the complete table strokes and text.

`max_bytes` defaults to 50 MiB and `max_pages` to 100. These limits apply to the
entire input document, including when a subset of pages is selected. Both are
positive integers. Encrypted PDFs are rejected, and image-only pages need OCR
before this extractor can read them.

## Headers, numbers, and dtypes

```python
# Retain a headerless table's first row as data, with integer column labels:
result = extract_document("codes.pdf", header=None, numeric="preserve")

# Keep identifier strings such as "0012", while inferring other numeric columns:
result = extract_document("codes.pdf", dtypes={"Identifier": "string"})

# For headerless tables, dtype keys are integer DataFrame column labels:
result = extract_document("codes.pdf", header=None, dtypes={0: "string"})
```

`header=0` (default) uses the first extracted row as column labels. Empty labels
receive `column_1`, `column_2`, etc. `header=None` uses every row as data. Other
header positions are not supported.

`numeric="infer"` (default) converts a column only when every non-empty value is
numeric, including Persian and Arabic-Indic digits. This can remove leading
zeroes. `numeric="preserve"` retains strings exactly as extracted, including
empty strings and digit scripts.

`dtypes` maps DataFrame column labels to pandas dtypes. Explicit dtype conversion
uses the raw strings and overrides numeric inference for those columns. Missing
or duplicate/ambiguous column labels, invalid dtypes, and failed conversions raise
`Pdf2CsvError`. Explicit conversion follows pandas `astype` behavior, including
its handling of empty strings and non-ASCII digits; use numeric inference first
and then your own pandas conversion for custom normalization policies. The same
dtype mapping applies to every table, so heterogeneous tables may be easier to
convert individually from `rows`.

Warnings report observed conditions: `no_tables` for a selected page/crop with no
detected tables, `empty_header` for generated labels, `duplicate_header` for
duplicate final labels, `ambiguous_header` for uncertain grouped headers, and
`schema_change` when repeated headers or changing column value types suggest
different sections. For `schema_change`, column labels may be wrong for some rows;
review the source before using them. These heuristics can miss changes or produce
false alarms. They do not estimate confidence or claim that every table was detected.
`convert()` logs table warnings, and the CLI shows them with table and page numbers;
page-level `no_tables` warnings are available through `extract_document()`.

## DataFrame wrapper and exports

```python
from pdf2csv import convert, export_frames

frames = convert(
    "report.pdf",
    pages=[2],
    table_header=None,  # Corresponds to extract_document(header=None).
    numeric="preserve",
    output_dir="output",
    export_kwargs={"index": False, "header": False, "encoding": "utf-8"},
)

# Or export already extracted frames without reading the PDF again:
paths = export_frames(frames, "report.pdf", "reviewed-output", overwrite=False, index=False)
```

`convert()` accepts the same extraction options as `extract_document()`, except
that `table_header` controls extraction headers. Its legacy `header=False` keyword
continues to control only the pandas CSV/Excel writer. Writer arguments can be
passed through `export_kwargs` or legacy extra keyword arguments such as
`index=False`; duplicate keys across both forms are rejected. Extraction and
writer settings are independent.

`export_frames()` writes `<pdf-stem>-table-1.csv` or `.xlsx`, followed by the
remaining tables in sequence, and returns their Paths. Both it and `convert()`
preserve the existing overwrite behavior by default. With `overwrite=False`,
all destination names are checked before writing; any existing file, directory,
or symlink (including dangling symlinks) raises `FileExistsError`. A directory at
any destination is rejected before writing even with overwriting enabled. Empty
frame lists do not create an output directory. This preflight does not make file
writes atomic against concurrent writers or guarantee rollback for I/O failures.
