# Changelog

## 0.3.0rc1

First release candidate of the offline extractor rewrite. This is a prerelease;
validate it against your own PDFs before replacing an existing installation.

### Changed

- Replace Docling and its model downloads with pdfplumber-based vector and glyph
  extraction. Ordinary conversion has no model downloads or runtime network use.
- Require Python 3.12 or newer; test Python 3.12, 3.13 and 3.14.
- Extract separate ruled and borderless tables, including mixed pages and
  conservatively detected neighboring borderless tables.
- Reconstruct common Arabic/Farsi/Hebrew directional runs while preserving Latin
  identifiers and digit runs. Columns retain physical left-to-right page order.
- Provide `extract_document()` with raw rows, DataFrames, page numbers, bounding
  boxes, methods and observed warnings. Add page/crop selection, headerless
  extraction, numeric preservation and explicit pandas dtypes.
- Add `pdf2csv convert`, retaining `convert-cli` as an alias. Add input-limit
  controls, `--fail-on-empty`, and explicit `--overwrite` for existing CLI exports.
- Return nonzero CLI exit codes for conversion/write failures and report concise
  errors, with tracebacks available through `--verbose`.

### Compatibility and limitations

- Scanned/image-only PDFs have no readable glyphs and require external OCR.
- The Python `convert()` wrapper retains default header promotion, numeric
  inference and overwrite behavior. Its legacy `header=False` controls export;
  `table_header=None` controls headerless extraction.
- Default input limits are 50 MiB and 100 pages. Encrypted PDFs are rejected.
- Each table is independent; tables continuing across pages are not stitched.
- Borderless layouts and complex bidirectional text remain heuristic. Some
  logical bidi strings paint identical glyphs, so original ordering is ambiguous.
- Output preflight detects existing destinations but does not provide atomic
  writes, rollback after I/O failures, or protection against concurrent writers.

See [migration guidance](docs/migration-0.3.md), [the Python API](docs/api.md),
[the CLI guide](docs/cli.md), and [benchmark scope](benchmarks/README.md).
