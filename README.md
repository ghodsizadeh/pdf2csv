# PDF to CSV Converter

[![PyPI version](https://badge.fury.io/py/pdf2csv.svg)](https://pypi.org/project/pdf2csv/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
<!-- [![Downloads](https://pepy.tech/badge/pdf2csv)](https://pepy.tech/project/pdf2csv) -->
<a href="https://pypi.org/project/pdf2csv" target="_blank">
    <img src="https://img.shields.io/pypi/v/pdf2csv?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/pdf2csv" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/pdf2csv.svg?color=%2334D058" alt="Supported Python versions">
</a>
<a href="https://codecov.io/gh/ghodsizadeh/pdf2csv" target="_blank">
    <img src="https://codecov.io/gh/ghodsizadeh/pdf2csv/branch/main/graph/badge.svg" alt="codecov">
</a>
</p>
This project provides a tool to convert tables from PDF files into CSV or XLSX format using the Docling library. It extracts tables from PDFs and saves them as CSV or XLSX files, optionally reversing text for right-to-left languages.

## How It Works

1. **PDF Input**: Provide the path to the PDF file you want to convert.
2. **Table Extraction**: The tool uses Docling's `DocumentConverter` to extract tables from the PDF.
3. **DataFrame Conversion**: Each extracted table is converted into a pandas DataFrame.
4. **Optional Text Reversal**: If the `rtl` option is enabled, text in the DataFrame is reversed.
5. **CSV/XLSX Output**: The DataFrames are saved as CSV or XLSX files in the specified output directory.

## Dependencies

This project heavily depends on the [Docling](https://github.com/docling/docling) library for PDF table extraction. Ensure you have it installed before running the converter.

## CLI Usage

You can use the CLI tool to convert PDF files to CSV or XLSX:

```sh
pdf2csv convert-cli <pdf_path> --output-dir <output_dir> --output-format <csv|xlsx> --rtl --verbose
```

Example:

```sh
pdf2csv convert-cli example.pdf --output-dir ./output --output-format xlsx --rtl --verbose
```

## With uvx

You can use the CLI tool with `uvx`:

```sh
uvx pdf2csv convert-cli <pdf_path> --output-dir <output_dir> --output-format <csv|xlsx> --rtl --verbose
```

Example:

```sh
uvx pdf2csv convert-cli example.pdf --output-dir ./output --output-format xlsx --rtl --verbose
```

## Python Usage

You can also use the converter directly in your Python code:

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
- [ ] Convert datatype to numeric
- [ ]
