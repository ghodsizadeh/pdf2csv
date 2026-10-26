---
name: pdf2csv
description: Extract born-digital PDF tables to pandas DataFrames, CSV, or XLSX with pdf2csv. Use when writing or debugging pdf2csv Python or CLI integrations, preserving identifiers, selecting pages/crops, or handling Arabic/Farsi/Hebrew tables.
---

# pdf2csv

Use these instructions with the installed pdf2csv version that supplied them.
Python 3.12+ is required. No model, OCR engine, or runtime download is involved.

## Choose the interface

- CLI: convert every detected table to an independent CSV or XLSX file.
- `extract_document`: inspect raw rows, DataFrames, source locations, and warnings.
- `convert`: return a list of DataFrames; optionally write them.
- `export_frames`: export existing frames without re-reading the PDF.

Import public APIs from `pdf2csv`. Do not use obsolete Docling-based APIs or
invent CLI flags for Python-only options. Check `pdf2csv convert --help`.

## CLI: safe export

```sh
pdf2csv convert report.pdf -o output -f csv --fail-on-empty
pdf2csv convert report.pdf -o output-xlsx -f xlsx
```

`convert-cli` is a compatibility alias. Outputs are named
`<pdf-stem>-table-1.csv` (or `.xlsx`), then numbered in document order.
The CLI omits the DataFrame index and protects existing destinations by default.
Use `--overwrite` only when replacement is explicitly intended.
Exit codes: 0 success, 1 extraction/write failure, 2 invalid arguments.
Without `--fail-on-empty`, no tables is success and creates no output directory.

## Python: inspect before exporting

```python
from pdf2csv import extract_document, export_frames

result = extract_document("report.pdf", numeric="preserve")
for warning in result.warnings:
    print(warning.page_number, warning.code, warning.message)
for table in result.tables:
    print(table.page_number, table.bbox, table.method, table.rows)
    for warning in table.warnings:
        print(warning.code, warning.message)

paths = export_frames(
    [table.dataframe for table in result.tables],
    "report.pdf",
    "output",
    overwrite=False,
    index=False,
)
```

Python exports overwrite by default for compatibility: explicitly pass
`overwrite=False` to protect existing files. Destination preflight is not an
atomic write or a rollback guarantee; avoid concurrent writers to the same names.
An empty frame list creates no output directory.

```python
from pdf2csv import convert

frames = convert(
    "report.pdf",
    pages=[2, 4],
    table_header=None,
    numeric="preserve",
    output_dir="output",
    overwrite=False,
    export_kwargs={"index": False, "header": False},
)
```

## Extraction controls and data fidelity

- `extract_document(header=0)` promotes the first row to labels by default.
  Use `header=None` for headerless data. On `convert`, the extraction option is
  `table_header=None`; its legacy `header=False` controls the writer only.
- `numeric="infer"` converts wholly numeric columns and may remove leading zeros.
  Use `numeric="preserve"` for identifiers or `dtypes={"Identifier": "string"}`.
  Headerless dtype keys are integer column labels. Explicit dtypes use raw
  strings, override inference, and follow pandas `astype` behavior.
- `pages=[2, 4]` selects positive, 1-based document pages. Results remain in
  document order. Duplicates are removed; out-of-range pages are errors.
- `crop=(x0, top, x1, bottom)` uses absolute PDF points from the page's top-left.
  A page-to-box mapping is also accepted. Boxes must fit the source page.
- Raw `table.rows` precede header/numeric/dtype conversion but already include
  extraction cleanup. `table.dataframe` contains converted data.
- Tables include `page_number`, `bbox`, `method` ("ruled" or "text"), and warnings.
  Warnings such as `no_tables`, `empty_header`, and `duplicate_header` are
  observations, not confidence scores or completeness guarantees.

## Limits and RTL

Only born-digital PDFs with text glyphs are supported. Scans need a separate OCR
workflow; do not promise OCR or perfect arbitrary-layout reconstruction.
Encrypted PDFs are rejected. Default limits are 50 MiB and 100 pages for the
entire document, even when selecting pages. Python accepts `max_bytes` and
`max_pages`; CLI accepts `--max-bytes` and `--max-pages`. These do not cap
execution time or memory.

Arabic/Farsi/Hebrew detection is automatic. Python `rtl=True` or CLI `--rtl`
prefers RTL interpretation; `--no-rtl` does not disable automatic detection.
Columns stay in physical left-to-right order. Mixed Latin/numeric/RTL text can
be ambiguous; inspect representative output against the PDF.
Tables across pages are not stitched automatically. Never claim that a successful
exit or absence of warnings proves every table was recovered.
