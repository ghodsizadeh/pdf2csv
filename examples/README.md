# English and Farsi example PDFs

These are real born-digital PDFs with text glyphs and vector rules, not images or
mocked parser objects. Tests read the checked-in PDF bytes through the public
Python API and CLI, including CSV/XLSX round trips.

## English

| PDF | Expected tables | Purpose |
| --- | ---: | --- |
| [english_stacked.pdf](english_stacked.pdf) | 2 | Same-width tables separated vertically |
| [english_close_stacked.pdf](english_close_stacked.pdf) | 2 | Only 20 points of space between tables |
| [english_side_by_side.pdf](english_side_by_side.pdf) | 2 | Collinear rules must not bridge a horizontal gap |
| [english_rectangles.pdf](english_rectangles.pdf) | 1 | Cell borders drawn as rectangles |
| [english_mixed_stacked.pdf](english_mixed_stacked.pdf) | 2 | Ruled table above a borderless table |
| [english_mixed_reverse.pdf](english_mixed_reverse.pdf) | 2 | Borderless table above a ruled table |
| [english_mixed_side_by_side.pdf](english_mixed_side_by_side.pdf) | 2 | Ruled and borderless tables on the same row |
| [english_borderless_stacked.pdf](english_borderless_stacked.pdf) | 2 | Separate borderless tables |
| [english_pages.pdf](english_pages.pdf) | 2 | Page 1 table is lower than page 2 table |

Each table has headers `Name 1` (or `Name 2`) and `Score`, and rows `Ada, 10` and
`Grace, 12`. The numbered header identifies the table's intended document order.

## فارسی / Farsi

| PDF | Expected tables | Purpose |
| --- | ---: | --- |
| [farsi_ruled.pdf](farsi_ruled.pdf) | 1 | Shaped Farsi text, mixed RTL/number cells |
| [farsi_borderless.pdf](farsi_borderless.pdf) | 1 | Right-aligned text without rules |
| [farsi_mixed.pdf](farsi_mixed.pdf) | 2 | The same data in ruled and borderless tables |
| [farsi_pages.pdf](farsi_pages.pdf) | 2 | Page ordering, headers `شهر اول` / `شهر دوم` |

Physical left-to-right columns are `شهر`, `جمعیت`, `توضیح`. Expected logical data:

| شهر | جمعیت (numeric output) | توضیح |
| --- | ---: | --- |
| تهران | 123 | سلام ۱۲۳ |
| شیراز | 456 | سلام ٤٥٦ |
| تبریز | 789 | سلام 789 |

The source population cells deliberately use Persian (`۱۲۳`), Arabic-Indic
(`٤٥٦`) and ASCII (`789`) digits. Description cells retain their original digit
scripts and spacing. The examples use the embedded Noto Naskh Arabic font, Arabic
shaping and Unicode bidi layout to produce readable Farsi, including ligatures.
This is a controlled fixture set, not a substitute for testing arbitrary PDFs.
The original real Farsi rainfall PDF remains at `tests/assets/rtl_test.pdf`.

## Try and regenerate

From the repository root:

```sh
uv run --locked pdf2csv convert-cli examples/english_pages.pdf -o /tmp/english-csv
uv run --locked pdf2csv convert-cli examples/farsi_ruled.pdf -o /tmp/farsi-xlsx -f xlsx
uv run --locked --group examples python examples/generate.py
uv run --locked pytest -q
```

ReportLab, arabic-reshaper and python-bidi are **generation-only** dependencies in
`--group examples`; normal conversion and tests do not need them. `invariant=1`
makes generation deterministic, and CI verifies the PDFs have no regeneration
diff. The font is bundled so generation requires no system font or font download.

`fonts/NotoNaskhArabic-Regular.ttf` comes from the
[Noto font project](https://github.com/notofonts/noto-fonts/tree/main/hinted/ttf/NotoNaskhArabic),
and is distributed under the [SIL Open Font License 1.1](fonts/LICENSE), with the
Noto Project copyright notice included there. It is embedded in the Farsi PDFs.
