# Migrating from 0.2.x (Docling) to 0.3

Version 0.3 replaces the model-based Docling pipeline with deterministic vector
and glyph extraction using pdfplumber. This is an intentional change of scope,
not a drop-in replacement for every document Docling can process.

## Compatibility changes

| Area | 0.3 behavior |
| --- | --- |
| Python | Requires 3.12+; Python 3.10 and 3.11 are no longer supported. CI covers 3.12–3.14. |
| OCR | No OCR or layout-model downloads. Scanned/image-only tables are not supported. |
| PDF input | Local, nonempty files with a `.pdf` extension; encrypted PDFs are rejected even if they open without a password. |
| Limits | Defaults to 50 MiB and 100 pages. Override with Python's `max_bytes`/`max_pages` or the CLI's `--max-bytes`/`--max-pages`. |
| Headers | The first detected row becomes column names. Blank names become `column_1`, etc. Use `extract_document(header=None)` or `convert(table_header=None)` for headerless tables. |
| RTL | Arabic/Farsi/Hebrew detection is automatic. `rtl=True` prefers RTL interpretation in mixed text; Latin text at both ends still anchors an LTR paragraph. Latin identifiers and digit runs retain their written order. |
| Column order | Physical left-to-right page order, even in Farsi documents. |
| Table order | Page order, then top-to-bottom/left-to-right on each page. Each table is independent; continued tables are not stitched. |
| Numeric cleanup | A column becomes numeric only when all nonempty cells are numbers. Persian and Arabic-Indic digits are accepted; mixed text remains text. Use `numeric="preserve"` to keep strings or explicit `dtypes` to protect identifiers. |
| Errors | Invalid inputs raise `Pdf2CsvError` (missing paths raise `FileNotFoundError`). Export failures propagate rather than being silently swallowed. |
| CLI errors | Conversion/write errors exit `1`; argument errors exit `2`. No detected tables is a successful empty result unless `--fail-on-empty` is set. |

If you need OCR or complex semantic layout interpretation, keep the older version
in a separate environment or use Docling directly. Do not feed a scanned file to
0.3 and interpret an empty result as proof that the document contains no tables.

## Python API

The `convert` import and common arguments are unchanged:

```python
from pdf2csv import Pdf2CsvError, convert

try:
    frames = convert(
        "report.pdf",
        output_dir="output",
        output_format="xlsx",
        max_bytes=100 * 1024 * 1024,
        max_pages=200,
        index=False,
    )
except (FileNotFoundError, Pdf2CsvError) as error:
    print(f"Invalid input: {error}")
```

Limits must be positive. Increasing them does not bound CPU use or decompressed
PDF memory: do not treat input byte/page validation as sandboxing untrusted PDFs.

When `output_dir` is omitted, nothing is written. Writer keyword arguments such
as `index=False` are forwarded to pandas. As before, the Python API otherwise
uses pandas' default of exporting the dataframe index; the CLI always omits it.
The Python API overwrites existing output filenames by default. The CLI protects
existing output files and requires `--overwrite` to replace them; it checks every
planned destination before writing any tables. `convert` is the preferred command,
and `convert-cli` remains an alias. See the [CLI guide](cli.md).

## Known limitations

- Text alignment is heuristic and may confuse aligned prose with tables.
- Rotated text, arbitrary merged body cells, unusual font mappings, complex
  bidirectional nesting and irregular/broken grids are not universally supported.
- Different logical bidirectional strings can paint identical glyphs, so their
  original word/number order cannot always be recovered. Borderless gutter
  splitting is conservative and cannot distinguish every neighboring table.
- Empty rows/columns are trimmed; a detected table needs at least two nonempty
  columns and a body row.
- Numeric-looking identifiers (for example zero-padded account numbers) may become
  numbers. Validate schema-sensitive exports before consuming them downstream.

Review the [English/Farsi examples](../examples/README.md) and
[benchmark scope](../benchmarks/README.md), and test your own PDFs before upgrading.
