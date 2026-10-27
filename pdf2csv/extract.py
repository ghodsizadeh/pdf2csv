"""Extract ruled PDF tables without a layout model.

Ruled tables are rebuilt from axis-aligned strokes. Glyphs are read from their
positions, using directional runs to reconstruct common Arabic and Hebrew layouts.
Pages with no ruling fall back to pdfplumber's text alignment.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSException
from pdfplumber.utils.exceptions import PdfminerException

from pdf2csv.errors import Pdf2CsvError
from pdf2csv.models import BBox, ExtractedTable, ExtractionWarning

SNAP = 3.0
_RULE_SNAP = 1.0
MIN_SEGMENT = 8.0
THIN = 1.75
_JUSTIFICATION_OVERLAP = 0.35

_RTL_RE = re.compile(
    r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
_WHITESPACE_RE = re.compile(r"\s+")

_TEXT_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": SNAP,
    "join_tolerance": SNAP,
    "intersection_tolerance": SNAP,
    "min_words_vertical": 2,
    "min_words_horizontal": 1,
    # Keep a cell's explicit spaces within one word. Otherwise aligned RTL
    # phrases can introduce a false column boundary through their digits.
    "text_keep_blank_chars": True,
}


@dataclass
class _Rule:
    pos: float
    start: float
    end: float
    length: float

    @property
    def span(self) -> float:
        return self.end - self.start


@dataclass
class _Grid:
    xs: list[float]
    ys: list[float]
    vertical: list[_Rule]
    horizontal: list[_Rule]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.xs[0], self.ys[0], self.xs[-1], self.ys[-1])


def _from_pdfminer(exc: PdfminerException) -> Pdf2CsvError:
    inner = exc.args[0] if exc.args else exc
    if isinstance(inner, (PDFPasswordIncorrect, PDFEncryptionError)):
        return Pdf2CsvError("PDF is encrypted")
    if isinstance(inner, BaseException):
        return Pdf2CsvError(f"Could not parse PDF: {inner}")
    return Pdf2CsvError(f"Could not parse PDF: {exc}")


def extract_tables(
    pdf_path: Path,
    *,
    rtl: bool,
    max_pages: int,
) -> list[list[list[str]]]:
    """Return tables as rows of strings (compatibility wrapper)."""
    tables, _ = extract_table_results(pdf_path, rtl=rtl, max_pages=max_pages)
    return [table.rows for table in tables]


def extract_table_results(
    pdf_path: Path,
    *,
    rtl: bool,
    max_pages: int,
    pages: Sequence[int] | None = None,
    crop: BBox | Mapping[int, BBox] | None = None,
) -> tuple[list[ExtractedTable], list[ExtractionWarning]]:
    """Extract strings and source metadata without DataFrame transformations."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise Pdf2CsvError("max_pages must be a positive integer")
    selected, crops = _selection_options(pages, crop)

    try:
        pdf_handle = pdfplumber.open(pdf_path)
    except PDFPasswordIncorrect as exc:
        raise Pdf2CsvError("PDF is encrypted") from exc
    except PDFEncryptionError as exc:
        raise Pdf2CsvError("PDF is encrypted") from exc
    except PdfminerException as exc:
        raise _from_pdfminer(exc) from exc
    except (PDFSyntaxError, PSException) as exc:
        raise Pdf2CsvError(f"Could not parse PDF: {exc}") from exc

    with pdf_handle as pdf:
        if pdf.doc.encryption is not None:
            raise Pdf2CsvError("PDF is encrypted")
        page_count = len(pdf.pages)
        if page_count > max_pages:
            raise Pdf2CsvError(
                f"PDF has {page_count} pages, which exceeds the limit of {max_pages}"
            )
        if selected is None:
            selected = list(range(1, page_count + 1))
        if any(number > page_count for number in selected):
            raise Pdf2CsvError(
                f"pages contains a page beyond the document's {page_count} pages"
            )
        if isinstance(crops, dict) and any(number > page_count for number in crops):
            raise Pdf2CsvError(
                f"crop contains a page beyond the document's {page_count} pages"
            )

        # Validate all crop bounds before doing any extraction.
        page_regions = []
        for number in selected:
            page = pdf.pages[number - 1]
            box = crops.get(number) if isinstance(crops, dict) else crops
            if box is not None:
                x0, y0, x1, y1 = page.bbox
                if not (x0 <= box[0] < box[2] <= x1 and y0 <= box[1] < box[3] <= y1):
                    raise Pdf2CsvError(f"crop is outside the bounds of page {number}")
                page = page.crop(box)
            page_regions.append((number, page))

        tables: list[ExtractedTable] = []
        warnings: list[ExtractionWarning] = []
        for number, page in page_regions:
            page_tables = _table_details_on_page(page, rtl=rtl, page_number=number)
            page_tables.sort(key=lambda item: (item.bbox[1], item.bbox[0]))
            if not page_tables:
                warnings.append(
                    ExtractionWarning(
                        "no_tables", "No tables were detected on this page.", number
                    )
                )
            tables.extend(page_tables)
    return tables, warnings


def _selection_options(pages, crop):
    selected = None
    if pages is not None:
        if isinstance(pages, (str, bytes)) or not isinstance(pages, Sequence):
            raise Pdf2CsvError(
                "pages must be a non-empty sequence of 1-based page numbers"
            )
        if not pages or any(
            isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in pages
        ):
            raise Pdf2CsvError(
                "pages must be a non-empty sequence of 1-based page numbers"
            )
        selected = sorted(set(pages))
    if isinstance(crop, Mapping):
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in crop):
            raise Pdf2CsvError("crop page numbers must be positive integers")
        if selected is not None and any(n not in selected for n in crop):
            raise Pdf2CsvError("crop page numbers must be included in pages")
        return selected, {number: _validated_box(box) for number, box in crop.items()}
    return selected, None if crop is None else _validated_box(crop)


def _validated_box(box) -> BBox:
    if isinstance(box, (str, bytes)) or not isinstance(box, Sequence) or len(box) != 4:
        raise Pdf2CsvError(
            "crop must contain four finite coordinates (x0, top, x1, bottom)"
        )
    if any(
        isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
        for n in box
    ):
        raise Pdf2CsvError(
            "crop must contain four finite coordinates (x0, top, x1, bottom)"
        )
    if box[0] >= box[2] or box[1] >= box[3]:
        raise Pdf2CsvError("crop must have positive width and height")
    return tuple(float(n) for n in box)


def _tables_on_page(
    page, *, rtl: bool
) -> list[tuple[tuple[float, float, float, float], list[list[str]]]]:
    return [
        (table.bbox, table.rows)
        for table in _table_details_on_page(page, rtl=rtl, page_number=page.page_number)
    ]


def _table_details_on_page(
    page, *, rtl: bool, page_number: int
) -> list[ExtractedTable]:
    vertical, horizontal = _rules_from_page(page)
    grids = _grids(vertical, horizontal)
    rendered: list[ExtractedTable] = []
    for grid in grids:
        bbox, rows, ambiguous_header = _render_grid(page, grid, rtl)
        if rows:
            table = ExtractedTable(rows, page_number, bbox, "ruled")
            if ambiguous_header:
                table.warnings.append(
                    ExtractionWarning(
                        "ambiguous_header",
                        "A grouped header may span additional rows; those rows were retained as data. Review against the PDF.",
                        page_number,
                    )
                )
            if _has_schema_change(rows):
                table.warnings.append(
                    ExtractionWarning(
                        "schema_change",
                        "Column contents or a repeated header suggest that this table changes schema. Review against the PDF before using the column labels.",
                        page_number,
                    )
                )
            rendered.append(table)
    ruled_boxes = [table.bbox for table in rendered]
    for region in _text_regions(page, ruled_boxes):
        for bbox, rows in _borderless_tables(region, rtl=rtl):
            rendered.append(ExtractedTable(rows, page_number, bbox, "text"))
    return rendered


def _text_regions(page, ruled_boxes):
    """Find text bands outside ruled tables, without bridging large row gaps."""

    def outside_tables(obj):
        if obj.get("object_type") != "char":
            return True
        x = (obj["x0"] + obj["x1"]) / 2
        y = (obj["top"] + obj["bottom"]) / 2
        return not any(
            x0 - SNAP <= x <= x1 + SNAP and y0 - SNAP <= y <= y1 + SNAP
            for x0, y0, x1, y1 in ruled_boxes
        )

    remaining = page.filter(outside_tables)
    if not remaining.chars:
        return
    spans: list[list[float]] = []
    for char in sorted(remaining.chars, key=lambda char: char["top"]):
        if spans and char["top"] <= spans[-1][1] + 2:
            spans[-1][1] = max(spans[-1][1], char["bottom"])
        else:
            spans.append([char["top"], char["bottom"]])
    gaps = [bottom[0] - top[1] for top, bottom in zip(spans, spans[1:])]
    threshold = max(
        3 * _median(char["size"] for char in remaining.chars),
        1.8 * _median(gaps) if gaps else 0,
    )
    start, end = spans[0]
    x0, y0, x1, y1 = page.bbox
    for top, bottom in spans[1:]:
        if top - end > threshold:
            yield from _horizontal_text_regions(
                remaining.crop((x0, max(y0, start - 1), x1, min(y1, end + 1)))
            )
            start = top
        end = bottom
    yield from _horizontal_text_regions(
        remaining.crop((x0, max(y0, start - 1), x1, min(y1, end + 1)))
    )


def _horizontal_text_regions(page):
    """Split only unusually wide gutters between repeated text columns.

    A pair of adjacent borderless tables can be indistinguishable from one
    four-column table. Require two columns on each side, three aligned rows,
    and a gutter substantially wider than ordinary column spacing. Ambiguous
    or sparse layouts remain a single region.
    """
    words = page.extract_words(keep_blank_chars=True)
    if not words:
        return
    occupied: list[list[float]] = []
    for word in sorted(words, key=lambda word: word["x0"]):
        if occupied and word["x0"] <= occupied[-1][1] + SNAP:
            occupied[-1][1] = max(occupied[-1][1], word["x1"])
        else:
            occupied.append([word["x0"], word["x1"]])
    gaps = [right[0] - left[1] for left, right in zip(occupied, occupied[1:])]
    minimum = 10 * _median(char["size"] for char in page.chars)
    cuts = []
    for index, gap in enumerate(gaps):
        if index < 1 or index > len(gaps) - 2 or gap < minimum:
            continue
        neighbors = [gaps[index - 1], gaps[index + 1]]
        if gap < 1.5 * max(neighbors):
            continue
        cut = (occupied[index][1] + occupied[index + 1][0]) / 2
        left_rows = _unique([word["top"] for word in words if word["x1"] < cut])
        right_rows = _unique([word["top"] for word in words if word["x0"] > cut])
        shared = sum(
            any(abs(left - right) <= SNAP for right in right_rows) for left in left_rows
        )
        if shared >= 3:
            cuts.append(cut)
    x0, y0, x1, y1 = page.bbox
    for left, right in zip([x0, *cuts], [*cuts, x1]):
        yield page.crop((left, y0, right, y1))


def _borderless_tables(page, *, rtl: bool):
    rendered = []
    for table in page.find_tables(_TEXT_SETTINGS):
        # In a real borderless table the inferred column separators should
        # pass through whitespace, not through complete text phrases.
        # Repeated paragraph indents alone can otherwise invent columns.
        words = page.extract_words(keep_blank_chars=True)
        x0, top, x1, bottom = table.bbox
        words = [w for w in words if top <= (w["top"] + w["bottom"]) / 2 <= bottom]
        baselines = _unique([w["top"] for w in words])
        font_size = _median(c["size"] for c in page.chars)
        if any(b - a > 4 * font_size for a, b in zip(baselines, baselines[1:])):
            continue
        cuts = _unique([x for cell in table.cells for x in (cell[0], cell[2])])
        if any(w["x0"] + 1 < cut < w["x1"] - 1 for cut in cuts[1:-1] for w in words):
            continue
        rows: list[list[str]] = []
        for row in table.rows:
            rows.append(
                [
                    ""
                    if cell is None
                    else _text_in_box(page, cell[0], cell[1], cell[2], cell[3], rtl)
                    for cell in row.cells
                ]
            )
        rows = _drop_empty(rows)
        if len(rows) >= 2 and len(rows[0]) >= 2:
            rendered.append((tuple(table.bbox), rows))
    return rendered


def _render_grid(
    page,
    grid: _Grid,
    rtl: bool,
) -> tuple[tuple[float, float, float, float], list[list[str]], bool]:
    # Ignore a full-width title/blank band before the column labels. Combine
    # genuinely stacked column headers until most leaf columns are separated.
    start = 0
    bands = list(zip(grid.ys, grid.ys[1:]))
    while start < len(bands) - 1 and len(_column_cuts(grid, *bands[start])) == 2:
        start += 1
    stop = start
    while stop < len(bands) - 1:
        if len(_column_cuts(grid, *bands[stop])) >= max(
            3, math.ceil(0.75 * len(grid.xs))
        ):
            break
        stop += 1
    ambiguous_header = False
    if stop > start:
        candidate = _band_values(page, grid, *bands[stop], rtl)
        following = (
            _band_values(page, grid, *bands[stop + 1], rtl)
            if stop + 1 < len(bands)
            else []
        )
        evidence = sum(
            bool(a) and not _numeric_token(a) and _numeric_token(b)
            for a, b in zip(candidate, following)
        )
        if evidence < min(2, len(candidate)):
            # Geometry alone cannot tell a subheader from the first data row.
            # Preserve uncertain rows and let the caller review them.
            stop = start
            ambiguous_header = True
    top, bottom = bands[start][0], bands[stop][1]
    header = _headers(page, grid, rtl, top=top, bottom=bottom)
    rows = [header]
    body = bands[stop + 1 :]
    # Full-width annotation bands at the bottom are not data records.
    while body and len(_column_cuts(grid, *body[-1])) == 2:
        body.pop()
    for top, bottom in body:
        row = []
        for left, right in zip(grid.xs, grid.xs[1:]):
            box = _cell_box(grid, (left + right) / 2, (top + bottom) / 2)
            # Row-spanning labels repeat; a column-spanning label belongs to
            # its leftmost leaf column, rather than inventing duplicate data.
            row.append(
                "" if box[0] < left - _RULE_SNAP else _text_in_box(page, *box, rtl)
            )
        rows.append(row)
    return grid.bbox, _drop_empty(rows), ambiguous_header


def _band_values(page, grid, top, bottom, rtl):
    return [
        _text_in_box(page, left, top, right, bottom, rtl)
        for left, right in zip(grid.xs, grid.xs[1:])
    ]


def _numeric_token(value):
    value = value.strip().replace("−", "-").replace(",", "")
    if not value:
        return False
    try:
        return math.isfinite(float(value))
    except ValueError:
        return False


def _has_schema_change(rows):
    """Flag observable schema changes without claiming to infer their meaning."""
    if len(rows) < 4:
        return False
    header = rows[0]
    for row in rows[1:]:
        matches = sum(bool(a) and a == b for a, b in zip(header, row))
        if matches >= 2:
            return True
    for column in zip(*rows[1:]):
        kinds = [_numeric_token(value) for value in column if value.strip()]
        for index in range(2, len(kinds) - 1):
            if kinds[index - 2 : index] == [True, True] and kinds[
                index : index + 2
            ] == [False, False]:
                return True
    return False


def _cell_box(grid, x, y):
    """Find the actual ruled cell around a grid slot, including spans."""
    x0, y0, x1, y1 = grid.bbox
    hs = [
        h.pos
        for h in grid.horizontal
        if h.start - _RULE_SNAP <= x <= h.end + _RULE_SNAP
    ]
    vs = [
        v.pos for v in grid.vertical if v.start - _RULE_SNAP <= y <= v.end + _RULE_SNAP
    ]
    return (
        max([x0, *(v for v in vs if v < x)]),
        max([y0, *(h for h in hs if h < y)]),
        min([x1, *(v for v in vs if v > x)]),
        min([y1, *(h for h in hs if h > y)]),
    )


def _column_cuts(grid, top, bottom):
    return _unique(
        [
            grid.xs[0],
            grid.xs[-1],
            *(
                v.pos
                for v in grid.vertical
                if grid.xs[0] < v.pos < grid.xs[-1]
                and _overlap(v.start, v.end, top, bottom) >= 0.5 * (bottom - top)
            ),
        ],
        tolerance=_RULE_SNAP,
    )


def _rules_from_page(page) -> tuple[list[_Rule], list[_Rule]]:
    vertical: list[tuple[float, float, float]] = []
    horizontal: list[tuple[float, float, float]] = []

    def add_box(x0: float, top: float, x1: float, bottom: float) -> None:
        width = x1 - x0
        height = bottom - top
        if width <= THIN and height >= MIN_SEGMENT:
            vertical.append(((x0 + x1) / 2, top, bottom))
        elif height <= THIN and width >= MIN_SEGMENT:
            horizontal.append(((top + bottom) / 2, x0, x1))

    # A filled cell/background rectangle has edges in pdfplumber too, even
    # when none were stroked. Word emits many such boxes behind individual
    # lines of text. Treating their outlines as rules invents rows/columns.
    for edge in page.edges:
        if edge["object_type"] != "rect_edge" and edge.get("stroke", True):
            add_box(edge["x0"], edge["top"], edge["x1"], edge["bottom"])
    for rect in page.rects:
        x0, top, x1, bottom = rect["x0"], rect["top"], rect["x1"], rect["bottom"]
        if rect.get("stroke"):
            for box in [
                (x0, top, x1, top),
                (x0, bottom, x1, bottom),
                (x0, top, x0, bottom),
                (x1, top, x1, bottom),
            ]:
                add_box(*box)
        elif rect.get("fill"):
            add_box(x0, top, x1, bottom)
    vertical, horizontal = _cluster(vertical), _cluster(horizontal)
    return _strip_decorative_frame(page, vertical, horizontal)


def _strip_decorative_frame(page, vertical, horizontal):
    """Remove repeated inset page-border strokes, retaining attached tables.

    Require parallel long strokes on all four margins so an ordinary large
    table is not mistaken for a page frame. A table may touch one frame edge;
    trim that vertical stroke to its surviving table intersections.
    """
    x0, y0, x1, y1 = getattr(page, "root_page", page).bbox
    width, height = x1 - x0, y1 - y0
    sides = [
        [v for v in vertical if v.span > 0.85 * height and v.pos < x0 + 0.1 * width],
        [v for v in vertical if v.span > 0.85 * height and v.pos > x1 - 0.1 * width],
    ]
    ends = [
        [h for h in horizontal if h.span > 0.85 * width and h.pos < y0 + 0.1 * height],
        [h for h in horizontal if h.span > 0.85 * width and h.pos > y1 - 0.1 * height],
    ]
    if any(len(side) < 2 for side in [*sides, *ends]):
        return vertical, horizontal
    left = max(v.pos for v in sides[0])
    right = min(v.pos for v in sides[1])
    top = max(h.pos for h in ends[0])
    bottom = min(h.pos for h in ends[1])
    horizontal = [
        h
        for h in horizontal
        if top + _RULE_SNAP < h.pos < bottom - _RULE_SNAP
        and _overlap(h.start, h.end, left, right) > _RULE_SNAP
    ]
    kept = []
    for v in vertical:
        if v in [*sides[0], *sides[1]]:
            contacts = [
                h.pos
                for h in horizontal
                if h.start - _RULE_SNAP <= v.pos <= h.end + _RULE_SNAP
            ]
            if len(contacts) < 2:
                continue
            start, end = min(contacts), max(contacts)
            kept.append(_Rule(v.pos, start, end, end - start))
        elif v.start >= top - _RULE_SNAP and v.end <= bottom + _RULE_SNAP:
            kept.append(v)
    return kept, horizontal


def _cluster(segments: list[tuple[float, float, float]]) -> list[_Rule]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda item: item[0])
    groups: list[list[tuple[float, float, float]]] = [[ordered[0]]]
    for segment in ordered[1:]:
        if abs(segment[0] - groups[-1][0][0]) <= _RULE_SNAP:
            groups[-1].append(segment)
        else:
            groups.append([segment])

    rules: list[_Rule] = []
    for group in groups:
        # Snap collinear strokes without bridging whitespace between tables.
        intervals: list[list[tuple[float, float, float]]] = []
        end = float("-inf")
        for segment in sorted(group, key=lambda item: item[1]):
            if not intervals or segment[1] > end + _RULE_SNAP:
                intervals.append([segment])
                end = segment[2]
            else:
                intervals[-1].append(segment)
                end = max(end, segment[2])
        for interval in intervals:
            positions = sorted(item[0] for item in interval)
            start = min(item[1] for item in interval)
            end = max(item[2] for item in interval)
            rules.append(_Rule(positions[len(positions) // 2], start, end, end - start))
    return rules


def _grids(vertical: list[_Rule], horizontal: list[_Rule]) -> list[_Grid]:
    """Join intersecting strokes, including partial rules across merged cells.

    Equal horizontal spans are not required: a row-spanning unit/description
    cell interrupts otherwise valid body separators. Keep disconnected tables
    separate by requiring actual intersections at the tighter rule tolerance.
    """
    parent = list(range(len(vertical) + len(horizontal)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for vi, v in enumerate(vertical):
        for hi, h in enumerate(horizontal, len(vertical)):
            if (
                h.start - _RULE_SNAP <= v.pos <= h.end + _RULE_SNAP
                and v.start - _RULE_SNAP <= h.pos <= v.end + _RULE_SNAP
            ):
                parent[find(vi)] = find(hi)
    groups: dict[int, tuple[list[_Rule], list[_Rule]]] = {}
    for index, rule in enumerate([*vertical, *horizontal]):
        vs, hs = groups.setdefault(find(index), ([], []))
        (vs if index < len(vertical) else hs).append(rule)
    grids = []
    for vs, hs in groups.values():
        if len(vs) < 3 or len(hs) < 3:
            continue
        top, bottom = min(h.pos for h in hs), max(h.pos for h in hs)
        height = bottom - top
        if height < 20:
            continue
        xs = _unique(
            [v.pos for v in vs if v.span >= 0.45 * height], tolerance=_RULE_SNAP
        )
        if len(xs) < 3 or xs[-1] - xs[0] < 40:
            continue
        # Retain partial internal dividers as leaf columns too, so an inset
        # subcell is not silently lost inside a wider row-spanning cell.
        xs = _unique(
            [*xs, *(v.pos for v in vs if xs[0] < v.pos < xs[-1])], tolerance=_RULE_SNAP
        )
        ys = _unique([h.pos for h in hs], tolerance=_RULE_SNAP)
        grids.append(_Grid(xs=xs, ys=ys, vertical=vs, horizontal=hs))
    return _drop_outer(grids)


def _drop_outer(grids: list[_Grid]) -> list[_Grid]:
    kept: list[_Grid] = []
    for grid in grids:
        x0, y0, x1, y1 = grid.bbox
        area = (x1 - x0) * (y1 - y0)
        contains_another = False
        for other in grids:
            if other is grid:
                continue
            ox0, oy0, ox1, oy1 = other.bbox
            other_area = (ox1 - ox0) * (oy1 - oy0)
            inside = ox0 >= x0 - 1 and oy0 >= y0 - 1 and ox1 <= x1 + 1 and oy1 <= y1 + 1
            if inside and other_area < area - 1:
                contains_another = True
                break
        if not contains_another:
            kept.append(grid)
    return kept


def _headers(page, grid: _Grid, rtl: bool, *, top=None, bottom=None) -> list[str]:
    """Join stacked header bands, keeping labels that span several columns."""
    xs = grid.xs
    top = grid.ys[0] if top is None else top
    bottom = grid.ys[1] if bottom is None else bottom
    bands = _unique(
        [top, *(y for y in grid.ys if top < y < bottom), bottom], tolerance=_RULE_SNAP
    )
    names = []
    for left, right in zip(xs, xs[1:]):
        parts = []
        seen = set()
        for band_top, band_bottom in zip(bands, bands[1:]):
            box = _cell_box(grid, (left + right) / 2, (band_top + band_bottom) / 2)
            box = (box[0], max(top, box[1]), box[2], min(bottom, box[3]))
            if box in seen:
                continue
            seen.add(box)
            text = _text_in_box(page, *box, rtl)
            if text and (not parts or parts[-1] != text):
                parts.append(text)
        names.append(_collapse(" ".join(parts)))
    return names


def _text_in_box(page, x0: float, y0: float, x1: float, y1: float, rtl: bool) -> str:
    inset = 1.0
    box = (x0 + inset, y0 + inset, x1 - inset, y1 - inset)
    if box[2] - box[0] < 4 or box[3] - box[1] < 4:
        box = (x0, y0, x1, y1)

    selected = []
    for char in page.chars:
        center_x = (char["x0"] + char["x1"]) / 2
        center_y = (char["top"] + char["bottom"]) / 2
        if (
            box[0] <= center_x <= box[2]
            and box[1] <= center_y <= box[3]
            and char["text"]
        ):
            selected.append(char)
    if not selected:
        return ""

    # Use the text matrix rather than `upright`: some Word PDFs report True
    # for glyphs whose baseline is rotated by 90 degrees.
    orientations: dict[int, list] = {}
    for char in selected:
        matrix = char.get("matrix", (1, 0, 0, 1, 0, 0))
        degrees = math.degrees(math.atan2(matrix[1], matrix[0]))
        quarter_turn = round(degrees / 90) * 90
        angle = quarter_turn if abs(degrees - quarter_turn) <= 1 else 0
        orientations.setdefault(angle % 360, []).append(char)
    parts = []
    for angle, chars in orientations.items():
        if angle:
            radians = math.radians(angle)
            cosine, sine = math.cos(radians), math.sin(radians)
            transformed = []
            for char in chars:
                points = [
                    (x * cosine - y * sine, x * sine + y * cosine)
                    for x in (char["x0"], char["x1"])
                    for y in (char["top"], char["bottom"])
                ]
                xs, ys = zip(*points)
                transformed.append(
                    {
                        **char,
                        "x0": min(xs),
                        "x1": max(xs),
                        "top": min(ys),
                        "bottom": max(ys),
                        "size": max(ys) - min(ys),
                    }
                )
            chars = transformed
        parts.append(_render_lines(chars, rtl))
    return _collapse(" ".join(parts))


def _render_lines(selected, rtl):
    selected = sorted(selected, key=lambda char: char["top"])
    lines: list[list] = [[selected[0]]]
    for char in selected[1:]:
        size = max(char["size"], 1)
        if abs(char["top"] - lines[-1][0]["top"]) <= max(2.2, size * 0.45):
            lines[-1].append(char)
        else:
            lines.append([char])

    rendered = [_logical_line(line, rtl) for line in lines]
    return _collapse(" ".join(rendered))


def _logical_line(chars: list, rtl: bool) -> str:
    ordered = sorted(chars, key=lambda char: (char["x0"] + char["x1"]) / 2)
    ordered = _drop_justification_spaces(ordered)
    tokens: list[str] = []
    previous = None
    for char in ordered:
        if previous is not None:
            gap = char["x0"] - previous["x1"]
            if (
                gap > 4
                and not previous["text"].isspace()
                and not char["text"].isspace()
            ):
                tokens.append(" ")
        tokens.append(char["text"])
        previous = char
    return _logical_tokens(tokens, rtl)


def _drop_justification_spaces(chars: list) -> list:
    """Ignore space glyphs that Word draws on top of a letter."""
    kept = []
    for index, char in enumerate(chars):
        if not char["text"].isspace():
            kept.append(char)
            continue
        previous = next(
            (item for item in reversed(chars[:index]) if not item["text"].isspace()),
            None,
        )
        nxt = next(
            (item for item in chars[index + 1 :] if not item["text"].isspace()), None
        )
        overlaps_next = (
            nxt is not None and nxt["x0"] < char["x1"] - _JUSTIFICATION_OVERLAP
        )
        overlaps_previous = (
            previous is not None
            and previous["x1"] > char["x0"] + _JUSTIFICATION_OVERLAP
        )
        if overlaps_next or overlaps_previous:
            continue
        kept.append(char)
    return kept


def _logical_tokens(tokens: list[str], force_rtl: bool) -> str:
    """Reconstruct common visual-order runs, preserving each glyph's mapping.

    Visual-to-logical bidi inversion is ambiguous. Prefer an LTR paragraph when
    Latin text anchors both ends; otherwise use the letter majority (or the RTL
    hint). Contiguous Latin/numeric phrases retain their visual order. This
    cannot recover explicit bidi controls or distinguish all logical strings
    that paint the same visual glyph sequence.
    """
    # Normalize each glyph independently, preserving logical lam-alef mappings.
    tokens = [
        unicodedata.normalize("NFKC", token)
        if any("\ufb1d" <= char <= "\ufeff" for char in token)
        else token
        for token in tokens
    ]
    kinds = [_token_kind(token) for token in tokens]
    if "rtl" not in kinds:
        return "".join(tokens)
    letters = [
        char
        for token in tokens
        for char in token
        if unicodedata.category(char).startswith("L")
    ]
    strong = [kind for kind in kinds if kind in {"rtl", "ltr"}]
    latin_anchors = strong[0] == strong[-1] == "ltr"
    mostly_rtl = sum(bool(_RTL_RE.match(char)) for char in letters) >= len(letters) / 2
    if not latin_anchors and (force_rtl or mostly_rtl):
        return _reverse_rtl_run(tokens)

    # Preserve Latin identifiers as complete words before finding RTL spans.
    # Digits/punctuation in ABC-123 must not migrate into an adjacent RTL run.
    start = 0
    for index in range(len(tokens) + 1):
        if index < len(tokens) and not tokens[index].isspace():
            continue
        if "ltr" in kinds[start:index]:
            for pos in range(start, index):
                if kinds[pos] != "rtl":
                    kinds[pos] = "ltr"
        start = index + 1

    # LTR paragraph: reconstruct only the spans between strong Latin glyphs.
    # The span may include a preceding number, e.g. ABC 123 <Arabic> DEF.
    result = []
    start = 0
    for index, kind in enumerate([*kinds, "ltr"]):
        if kind != "ltr":
            continue
        span = tokens[start:index]
        if "rtl" in kinds[start:index]:
            left = 0
            right = len(span)
            while left < right and span[left].isspace():
                left += 1
            while right > left and span[right - 1].isspace():
                right -= 1
            result.extend(span[:left])
            result.append(_reverse_rtl_run(span[left:right]))
            result.extend(span[right:])
        else:
            result.extend(span)
        if index < len(tokens):
            result.append(tokens[index])
        start = index + 1
    return "".join(result)


def _reverse_rtl_run(tokens: list[str]) -> str:
    flipped = tokens[::-1]
    kinds = [_token_kind(token) for token in flipped]
    index = 0
    while index < len(flipped):
        if kinds[index] == "rtl":
            index += 1
            continue
        end = index
        while end < len(flipped) and kinds[end] != "rtl":
            end += 1
        # Boundary spaces separate directional runs. Restore each complete
        # forward-reading phrase, including identifiers, numbers and punctuation.
        start, stop = index, end
        while start < stop and flipped[start].isspace():
            start += 1
        while stop > start and flipped[stop - 1].isspace():
            stop -= 1
        if any(kinds[pos] in {"ltr", "number"} for pos in range(start, stop)):
            flipped[start:stop] = flipped[start:stop][::-1]
        index = end
    return _balanced_brackets("".join(flipped))


def _balanced_brackets(text: str) -> str:
    """Orient reversed enclosure pairs, retaining already-logical PDF glyphs.

    PDF ToUnicode maps sometimes encode a visually mirrored bracket as its
    logical counterpart already. Blindly mirroring every bracket corrupts
    those files, so change only pairs whose closing bracket precedes opening.
    """
    chars = list(text)
    for opening, closing in [("(", ")"), ("[", "]"), ("{", "}")]:
        depth = 0
        pending = []
        for index, char in enumerate(chars):
            if char == opening:
                if pending:
                    other = pending.pop()
                    chars[other], chars[index] = opening, closing
                else:
                    depth += 1
            elif char == closing:
                if depth:
                    depth -= 1
                else:
                    pending.append(index)
    return "".join(chars)


def _token_kind(token: str) -> str:
    directions = {unicodedata.bidirectional(char) for char in token}
    if directions & {"R", "AL"}:
        return "rtl"
    # EN and AN include ASCII, Persian and Arabic-Indic digits. Arabic block
    # membership alone does not make a digit a right-to-left letter.
    if "L" in directions:
        return "ltr"
    if directions & {"EN", "AN"}:
        return "number"
    return "neutral"


def _drop_empty(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    keep = [
        index for index in range(width) if any(row[index].strip() for row in padded)
    ]
    if len(keep) < 2:
        return []
    trimmed = [[row[index] for index in keep] for row in padded]
    body = [row for row in trimmed[1:] if any(cell.strip() for cell in row)]
    if not body:
        return []
    return [trimmed[0], *body]


def _collapse(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _overlap(start: float, end: float, other_start: float, other_end: float) -> float:
    return max(0.0, min(end, other_end) - max(start, other_start))


def _median(values) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _unique(values: list[float], tolerance: float = SNAP) -> list[float]:
    ordered = sorted(values)
    if not ordered:
        return []
    unique = [ordered[0]]
    for value in ordered[1:]:
        if abs(value - unique[-1]) > tolerance:
            unique.append(value)
        else:
            unique[-1] = (unique[-1] + value) / 2
    return unique
