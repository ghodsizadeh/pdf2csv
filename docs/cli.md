# Command-line guide

Use `convert` to extract each detected table to a separate CSV or Excel file:

```sh
pdf2csv convert report.pdf -o output
pdf2csv convert report.pdf -o output -f xlsx
uvx pdf2csv convert report.pdf -o output
```

`convert-cli` remains an alias with the same arguments and behavior. Run
`pdf2csv convert --help` for all options.

| Option | Default | Behavior |
| --- | --- | --- |
| `--output-dir`, `-o` | `.` | Directory for output files; created if tables are found. |
| `--output-format`, `-f` | `csv` | `csv` or `xlsx`. |
| `--rtl` / `--no-rtl` | `--no-rtl` | Force RTL glyph ordering; Arabic and Hebrew detection remains automatic. |
| `--max-pages` | `100` | Maximum number of pages in the input PDF; must be a positive integer. |
| `--max-bytes` | `52428800` | Maximum input PDF size in bytes (50 MiB); must be a positive integer. |
| `--fail-on-empty` | Off | Exit with an error when no tables are detected. |
| `--overwrite` | Off | Allow replacing files at the planned output destinations. |
| `--verbose`, `-v` | Off | Enable debug logging and tracebacks on conversion errors. |

Files use the input stem and a table number, such as `report-table-1.csv` and
`report-table-2.csv`. The CLI omits the dataframe index. Each detected table is
written independently; tables continued across pages are not combined.

Table warnings are logged with the output table number and source page. In
particular, `schema_change` means column labels may not apply to every row, and
`ambiguous_header` means uncertain header rows were retained as data. Review
warned output against the PDF. Warnings do not prevent export or guarantee that
other problems were detected.

Existing destinations are protected by default. After extracting the tables,
the CLI checks every planned destination before writing any files. An existing
file, directory, or symlink at one of those destinations causes an error;
unrelated files in the output directory are allowed. Use `--overwrite` when
replacing a previous export is intentional:

```sh
pdf2csv convert report.pdf -o output --overwrite
```

This preflight prevents partial output from an already known collision. Other
write failures can still leave output from tables written before the failure.
Avoid concurrent writers targeting the same output filenames.

To adjust input limits or require at least one table:

```sh
pdf2csv convert report.pdf -o output --max-pages 200 --max-bytes 104857600
pdf2csv convert report.pdf -o output --fail-on-empty
```

The page limit applies to the entire PDF. These options limit accepted input
size, not extraction time or memory use. Image-only scans still need OCR before
pdf2csv can extract their text tables.

Exit codes are `0` for success, `1` for conversion or write errors (including
protected output collisions and empty results with `--fail-on-empty`), and `2`
for invalid arguments. Without `--fail-on-empty`, no detected tables is a
successful result and creates no output directory.
