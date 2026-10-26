# PDF to CSV Converter
<p>
<a href="https://pypi.org/project/pdf2csv" target="_blank">
    <img src="https://img.shields.io/pypi/v/pdf2csv?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/pdf2csv" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/pdf2csv.svg?color=%2334D058" alt="Supported Python versions">
</a>
<a href="https://codecov.io/gh/ghodsizadeh/pdf2csv" target="_blank">
    <img src="https://codecov.io/gh/ghodsizadeh/pdf2csv/branch/main/graph/badge.svg" alt="codecov">
</a>
<a>
    <img src="https://img.shields.io/github/license/ghodsizadeh/pdf2csv" alt="License">
</a>
    <img src="https://img.shields.io/github/stars/ghodsizadeh/pdf2csv" alt="Stars">
    <img src="https://img.shields.io/github/issues/ghodsizadeh/pdf2csv" alt="Issues">
    <!-- downloads -->
    <img src="https://img.shields.io/pypi/dm/pdf2csv" alt="Downloads">


</p>

<img src='./docs/logo.webp' style="display: block; margin: auto; width: 400px; height: auto; box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1); border-radius: 35px;
padding:40px">


This project extracts tables from PDF files and saves them as CSV or XLSX. It reads the vector drawing in the PDF: ruling lines become the grid, and each cell is rebuilt from the glyphs inside it. There is no layout model, no OCR, and no download at runtime.

Python 3.12 or newer is required.

## How It Works

1. **PDF Input**: Provide the path to a born-digital PDF. By default the file must be an unencrypted `.pdf`, at most 50 MiB, and at most 100 pages.
2. **Table Extraction**: Connected ruled lines are snapped into separate grids. Text alignment finds borderless tables outside those grids, including on mixed pages.
3. **DataFrame Conversion**: The first row of each table becomes the column names. A column becomes numeric only when every non-empty cell is a number.
4. **Right-to-left text**: Arabic and Hebrew glyphs are put back into reading order. Digits are left as written. `--rtl` also treats a mixed cell as right-to-left when any of those letters are present, not only when they are the majority. Columns stay in left-to-right page order.
5. **CSV/XLSX Output**: Each table is saved in page order, then top-to-bottom and left-to-right within the page. Files are named `<pdf-stem>-table-1.csv` (or `.xlsx`), and so on. Tables on different pages are not automatically stitched together.

Scanned pages and other image-only PDFs are not supported. Those files have no text glyphs to read. See [migration notes and limitations](docs/migration-0.3.md) before upgrading from the Docling-based version.

## Installation

Requires Python 3.12+.

```sh
pip install pdf2csv
```

To use this branch before its release to PyPI, install the checkout instead:

```sh
pip install .
# Or use the locked development environment:
uv sync --locked
```

## CLI Usage

```sh
pdf2csv convert-cli <pdf_path> --output-dir <output_dir> --output-format <csv|xlsx> --rtl --verbose
```

Example:

```sh
pdf2csv convert-cli example.pdf --output-dir ./output --output-format xlsx --rtl --verbose
```

## With uvx

```sh
uvx pdf2csv convert-cli <pdf_path> --output-dir <output_dir> --output-format <csv|xlsx> --rtl --verbose
```

Example:

```sh
uvx pdf2csv convert-cli example.pdf --output-dir ./output --output-format xlsx --rtl --verbose
```

## Python Usage

```python
from pdf2csv.converter import convert

pdf_path = "example.pdf"
output_dir = "./output"
rtl = True
output_format = "xlsx"

dfs = convert(pdf_path, output_dir=output_dir, rtl=rtl, output_format=output_format, index=False)
for df in dfs:
    print(df)
```

## English and Farsi examples

The repository includes [13 generated example PDFs](examples/README.md), including
shaped Farsi with embedded fonts, mixed digit scripts, multiple tables and pages:

```sh
uv run --locked pdf2csv convert-cli examples/english_pages.pdf -o /tmp/pdf2csv-english
uv run --locked pdf2csv convert-cli examples/farsi_ruled.pdf -o /tmp/pdf2csv-farsi -f xlsx
```

Arabic/Farsi detection is automatic; `--no-rtl` does not turn it off. `--rtl`
forces the RTL interpretation when a cell mixes mostly Latin text with RTL text.
Columns always stay in physical left-to-right page order.

## Development and verification

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked --group examples python examples/generate.py
```

CI tests Python 3.12–3.14, minimum/latest dependency installations and reproducible
PDF generation. See [the measured Docling comparison](benchmarks/README.md) for
methodology, raw results and limitations; the small regression corpus is not a
general-purpose PDF accuracy guarantee.

The CLI exits with `0` on success (including no tables), `1` on conversion or
write errors, and `2` for invalid command-line arguments.
