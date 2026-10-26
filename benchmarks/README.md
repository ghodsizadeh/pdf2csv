# Extractor comparison

This is a small **regression benchmark**, not a general PDF accuracy claim. The
labelled corpus (`corpus.json`) contains seven generated English/Farsi examples
and the original Farsi rainfall PDF: eight PDFs, ten pages and thirteen tables.
It covers disconnected grids, mixed ruled/borderless tables, page order, shaped
Farsi, mixed-script numbers and a real multi-band header. It does not cover scans,
arbitrary report layouts or the full Unicode bidirectional algorithm.

## Reproduce

Run each engine in a separate environment, from the repository root:

```sh
uv run --locked python benchmarks/run.py --engine offline --runs 3 --output /tmp/offline.json

uv venv --python 3.12 /tmp/pdf2csv-docling-bench
uv pip compile --python 3.12 benchmarks/docling-requirements.txt -o /tmp/docling-resolved.txt
uv pip sync --python /tmp/pdf2csv-docling-bench/bin/python /tmp/docling-resolved.txt
HF_HOME=/tmp/pdf2csv-docling-models /tmp/pdf2csv-docling-bench/bin/python benchmarks/run.py \
  --engine docling --runs 3 --output /tmp/docling.json
```

The optional Docling run requires internet/model weights and substantially more
disk space. Its constraints preserve `main` (`388c172`)'s historical dependency
versions. The sole override is SciPy 1.17.1: the original SciPy 1.15.0 macOS ARM
wheel failed to load its PROPACK shared library on this machine. This historical
stack includes a yanked pypdfium2 wheel; **use it only for isolated comparison,
not production**. Normal application installation never installs Docling.

Both engines have OCR disabled. Docling uses the old package's numeric cleanup
and explicit RTL string reversal for Farsi inputs; this is not a comparison
against an untranslated raw Docling dataframe. One converter is reused for all
Docling files to measure warm throughput, unlike the old package which recreated
it per file. The complete old CLI, file validation and export are not timed.

The script records import/constructor time separately, every conversion time,
median per-document time and process-wide peak RSS (Unix). First-conversion
measurements include model loading and any downloads. Cache state is not
controlled, so these numbers do **not** measure a clean installation's startup.

Correctness compares tables, headers, rows and columns in document order. Numeric
storage dtype, equivalent digit scripts, presentation forms and whitespace are
normalized; word/digit order is not. Missing or extra cells are penalized. A
conversion/postprocessing error is recorded explicitly, scores zero, and makes
the command exit nonzero without preventing other documents from being tested.

## Recorded local run

macOS ARM64, CPython 3.12.6, three conversions per PDF. Full versions, individual
samples and errors are checked in under `results/`.

| Metric | Offline extractor | Docling 2.14.0 baseline |
| --- | ---: | ---: |
| Exact tables | 13 / 13 | 7 / 13 |
| Matching positional cells, including headers | 162 / 162 | 113 / 164 |
| Peak process RSS | 95.6 MiB | 797.4 MiB |
| Conversion/postprocessing errors | 0 | 1 |

| PDF | Offline median (ms) | Docling median (ms) |
| --- | ---: | ---: |
| English stacked | 3.65 | 757.48 |
| English side-by-side | 3.52 | 728.72 |
| English mixed | 3.57 | 728.63 |
| English multipage | 3.75 | 1046.92 |
| Farsi ruled | 4.62 | 574.29 |
| Farsi borderless | 4.79 | 563.15 (postprocessing error) |
| Farsi multipage | 7.36 | 1138.39 |
| Original Farsi rainfall | 99.70 | 971.41 |

The old RTL cleanup fails on the borderless Farsi table's non-string headers.
Other strict mismatches include changed headers/word order and mixed-table
structure. These results support the lightweight extractor **for this corpus**;
a larger independent collection of real English/Farsi documents is still needed
before making broad accuracy or performance promises. Docling also supports
use cases, particularly scanned documents, that this extractor deliberately does
not support.
