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

1. **PDF Input**: Provide the path to a born-digital PDF. The file must be an unencrypted `.pdf`, at most 50 MB, and at most 100 pages.
2. **Table Extraction**: Ruled lines are snapped into a grid. A page with no ruling falls back to text alignment.
3. **DataFrame Conversion**: The first row of each table becomes the column names. A column becomes numeric only when every non-empty cell is a number.
4. **Right-to-left text**: Arabic and Hebrew glyphs are put back into reading order. Digits are left as written. `--rtl` forces that glyph order; columns stay in left-to-right page order.
5. **CSV/XLSX Output**: Each table is saved in the output directory.

Scanned pages and other image-only PDFs are not supported. Those files have no text glyphs to read.

## Installation

Requires Python 3.12+.

```sh
pip install pdf2csv
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

dfs = convert(pdf_path, output_dir=output_dir, rtl=rtl, output_format=output_format)
for df in dfs:
    print(df)
```

## TODO:
- [x] Convert datatype to numeric
- [x] Support for XLSX output
