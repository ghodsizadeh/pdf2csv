# PDF to CSV Converter

This project provides a tool to convert tables from PDF files into CSV format using the Docling library. It extracts tables from PDFs and saves them as CSV files, optionally reversing text for right-to-left languages.

## How It Works

1. **PDF Input**: Provide the path to the PDF file you want to convert.
2. **Table Extraction**: The tool uses Docling's `DocumentConverter` to extract tables from the PDF.
3. **DataFrame Conversion**: Each extracted table is converted into a pandas DataFrame.
4. **Optional Text Reversal**: If the `rtl` option is enabled, text in the DataFrame is reversed.
5. **CSV Output**: The DataFrames are saved as CSV files in the specified output directory.

## Dependencies

This project heavily depends on the [Docling](https://github.com/docling/docling) library for PDF table extraction. Ensure you have it installed before running the converter.

## TODO:
- [ ] Convert datatype to numeric
- [ ]