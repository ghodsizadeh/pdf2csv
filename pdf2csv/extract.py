"""Extract ruled PDF tables without a layout model.

Ruled tables are rebuilt from axis-aligned strokes. Glyphs are read from their
positions, so Arabic and Hebrew keep logical order and digits stay left to right.
Pages with no ruling fall back to pdfplumber's text alignment.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSException
from pdfplumber.utils.exceptions import PdfminerException

from pdf2csv.errors import Pdf2CsvError

SNAP = 3.0
MIN_SEGMENT = 8.0
THIN = 1.75
_SPAN_TOLERANCE = 12.0
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
    """Return tables as rows of strings. The first row of each table is the header."""
    if max_pages < 1:
        raise Pdf2CsvError("max_pages must be a positive number")

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

        tables: list[tuple[tuple[float, float, float, float], list[list[str]]]] = []
        for page in pdf.pages:
            tables.extend(_tables_on_page(page, rtl=rtl))

    tables.sort(key=lambda item: (item[0][1], item[0][0]))
    return [rows for _, rows in tables]


def _tables_on_page(
    page, *, rtl: bool
) -> list[tuple[tuple[float, float, float, float], list[list[str]]]]:
    vertical, horizontal = _rules_from_page(page)
    grids = _grids(vertical, horizontal)
    rendered: list[tuple[tuple[float, float, float, float], list[list[str]]]] = []
    for grid in grids:
        bbox, rows = _render_grid(page, grid, rtl)
        if rows:
            rendered.append((bbox, rows))
    ruled_boxes = [bbox for bbox, _ in rendered]
    for region in _text_regions(page, ruled_boxes):
        rendered.extend(_borderless_tables(region, rtl=rtl))
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
            yield remaining.crop((x0, max(y0, start - 1), x1, min(y1, end + 1)))
            start = top
        end = bottom
    yield remaining.crop((x0, max(y0, start - 1), x1, min(y1, end + 1)))


def _borderless_tables(page, *, rtl: bool):
    rendered = []
    for table in page.find_tables(_TEXT_SETTINGS):
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
) -> tuple[tuple[float, float, float, float], list[list[str]]]:
    header = _headers(page, grid, rtl)
    rows = [header]
    for top, bottom in zip(grid.ys[1:], grid.ys[2:]):
        rows.append(
            [
                _text_in_box(page, left, top, right, bottom, rtl)
                for left, right in zip(grid.xs, grid.xs[1:])
            ]
        )
    return grid.bbox, _drop_empty(rows)


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

    # Rectangle borders are edges too, not just thin filled rectangles.
    for edge in page.edges:
        add_box(edge["x0"], edge["top"], edge["x1"], edge["bottom"])
    return _cluster(vertical), _cluster(horizontal)


def _cluster(segments: list[tuple[float, float, float]]) -> list[_Rule]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda item: item[0])
    groups: list[list[tuple[float, float, float]]] = [[ordered[0]]]
    for segment in ordered[1:]:
        if abs(segment[0] - groups[-1][-1][0]) <= SNAP:
            groups[-1].append(segment)
        else:
            groups.append([segment])

    rules: list[_Rule] = []
    for group in groups:
        # Snap collinear strokes without bridging whitespace between tables.
        intervals: list[list[tuple[float, float, float]]] = []
        end = float("-inf")
        for segment in sorted(group, key=lambda item: item[1]):
            if not intervals or segment[1] > end + SNAP:
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
    strong = [
        rule
        for rule in horizontal
        if rule.length >= 36 and rule.length >= 0.65 * max(rule.span, 1)
    ]
    groups: list[list[_Rule]] = []
    for rule in sorted(strong, key=lambda item: item.pos):
        for group in groups:
            if _same_span(group[0], rule) and _connected_rows(
                group[-1], rule, vertical
            ):
                group.append(rule)
                break
        else:
            groups.append([rule])

    grids: list[_Grid] = []
    for group in groups:
        if len(group) < 3:
            continue
        group.sort(key=lambda item: item.pos)
        left = _median(rule.start for rule in group)
        right = _median(rule.end for rule in group)
        top = group[0].pos
        bottom = group[-1].pos
        height = bottom - top
        if height < 20 or right - left < 40:
            continue
        xs = [
            rule.pos
            for rule in vertical
            if left - SNAP <= rule.pos <= right + SNAP
            and _overlap(rule.start, rule.end, top, bottom) >= 0.45 * height
        ]
        xs = _unique(xs)
        if not xs or left < xs[0] - 8:
            xs = [left, *xs]
        if right > xs[-1] + 8:
            xs = [*xs, right]
        xs = _unique(xs)
        ys = _unique([rule.pos for rule in group])
        if len(xs) >= 3 and len(ys) >= 3:
            grids.append(_Grid(xs=xs, ys=ys, vertical=vertical, horizontal=horizontal))
    return _drop_outer(grids)


def _connected_rows(top: _Rule, bottom: _Rule, vertical: list[_Rule]) -> bool:
    """Require an actual vertical stroke across consecutive horizontal rules."""
    return any(
        top.start - SNAP <= rule.pos <= top.end + SNAP
        and rule.start <= top.pos + SNAP
        and rule.end >= bottom.pos - SNAP
        for rule in vertical
    )


def _same_span(left: _Rule, right: _Rule) -> bool:
    return (
        abs(left.start - right.start) <= _SPAN_TOLERANCE
        and abs(left.end - right.end) <= _SPAN_TOLERANCE
    )


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


def _headers(page, grid: _Grid, rtl: bool) -> list[str]:
    """Join stacked header bands, keeping labels that span several columns."""
    xs = grid.xs
    top, bottom = grid.ys[0], grid.ys[1]
    width = xs[-1] - xs[0]
    internal = [
        rule.pos
        for rule in grid.horizontal
        if top + 2 < rule.pos < bottom - 2
        and _overlap(rule.start, rule.end, xs[0], xs[-1]) >= 0.35 * width
    ]
    bands = _unique([top, *internal, bottom], tolerance=2.0)
    names: list[list[str]] = [[] for _ in range(len(xs) - 1)]
    for band_top, band_bottom in zip(bands, bands[1:]):
        cuts = [xs[0], xs[-1]]
        band_height = max(band_bottom - band_top, 1)
        for rule in grid.vertical:
            crosses = (
                _overlap(rule.start, rule.end, band_top, band_bottom)
                >= 0.45 * band_height
            )
            if xs[0] - 1 <= rule.pos <= xs[-1] + 1 and crosses:
                cuts.append(rule.pos)
        pieces: list[tuple[float, float, str]] = []
        ordered_cuts = _unique(cuts)
        for left, right in zip(ordered_cuts, ordered_cuts[1:]):
            pieces.append(
                (
                    left,
                    right,
                    _text_in_box(page, left, band_top, right, band_bottom, rtl),
                )
            )
        for index in range(len(xs) - 1):
            mid = (xs[index] + xs[index + 1]) / 2
            for left, right, text in pieces:
                if left - 0.8 <= mid <= right + 0.8 and text:
                    if not names[index] or names[index][-1] != text:
                        names[index].append(text)
                    break
    return [_collapse(" ".join(parts)) for parts in names]


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

    selected.sort(key=lambda char: char["top"])
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
    """Turn visual glyph order into logical reading order.

    Tokens are reversed for Arabic and Hebrew, but each PDF glyph keeps its own
    text. That preserves lam-alef ligatures, which pdfminer already returns in
    logical order inside a single glyph. Digit runs are then restored so a
    number painted left to right is not flipped.
    """
    # Some PDFs map shaped Arabic glyphs to presentation-form code points.
    # Normalize each glyph independently so a lam-alef ligature stays intact.
    tokens = [
        unicodedata.normalize("NFKC", token)
        if any("\ufb1d" <= char <= "\ufeff" for char in token)
        else token
        for token in tokens
    ]
    text = "".join(tokens)
    letters = [char for char in text if unicodedata.category(char).startswith("L")]
    rtl_letters = [char for char in letters if _RTL_RE.match(char)]
    mostly_rtl = bool(letters) and len(rtl_letters) / len(letters) >= 0.5
    if force_rtl and rtl_letters:
        mostly_rtl = True
    if not mostly_rtl:
        return text

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
        # Boundary spaces belong between directional runs, not inside the
        # reversal. Otherwise "123 <RTL>" becomes "<RTL>123 ".
        start, stop = index, end
        while start < stop and flipped[start].isspace():
            start += 1
        while stop > start and flipped[stop - 1].isspace():
            stop -= 1
        if any(kinds[pos] == "ltr" for pos in range(start, stop)):
            flipped[start:stop] = flipped[start:stop][::-1]
        else:
            mirrors = str.maketrans("()[]{}<>", ")(][}{><")
            flipped[start:stop] = [
                token.translate(mirrors) for token in flipped[start:stop]
            ]
        index = end
    return "".join(flipped)


def _token_kind(token: str) -> str:
    directions = {unicodedata.bidirectional(char) for char in token}
    if directions & {"R", "AL"}:
        return "rtl"
    # EN and AN include ASCII, Persian and Arabic-Indic digits. Arabic block
    # membership alone does not make a digit a right-to-left letter.
    if directions & {"L", "EN", "AN"}:
        return "ltr"
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
