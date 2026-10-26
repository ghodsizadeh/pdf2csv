"""Regenerate deterministic example PDFs: uv run --group examples python examples/generate.py."""

from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent
PAGE_SIZE = (640, 800)


def draw_table(
    pdf, rows, *, left=40, top=80, ruled=True, rectangles=False, latin_fallback=False
):
    """Draw rows in left-to-right column order using top-origin coordinates."""
    width, row_height = 260, 35
    col_width = width / len(rows[0])
    bottom = top + row_height * len(rows)
    pdf.setLineWidth(1)
    if ruled:
        if rectangles:
            for row in range(len(rows)):
                for col in range(len(rows[0])):
                    pdf.rect(
                        left + col * col_width,
                        PAGE_SIZE[1] - top - (row + 1) * row_height,
                        col_width,
                        row_height,
                    )
        else:
            for row in range(len(rows) + 1):
                y = PAGE_SIZE[1] - top - row * row_height
                pdf.line(left, y, left + width, y)
            for col in range(len(rows[0]) + 1):
                x = left + col * col_width
                pdf.line(x, PAGE_SIZE[1] - top, x, PAGE_SIZE[1] - bottom)
    farsi = any(
        "\u0600" <= char <= "\u06ff"
        for row in rows
        for value in row
        for char in str(value)
    )
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            text = str(value)
            pdf.setFont("NotoNaskhArabic" if farsi else "Helvetica", 12)
            y = PAGE_SIZE[1] - top - row * row_height - 23
            if farsi:
                visual = get_display(arabic_reshaper.reshape(text))
                right = left + (col + 1) * col_width - 10
                if latin_fallback:
                    # Noto Naskh Arabic has no Latin alphabet. Use Helvetica for
                    # ASCII glyphs so this fixture has valid text/font mappings.
                    glyphs = [
                        (char, "Helvetica" if ord(char) < 128 else "NotoNaskhArabic")
                        for char in visual
                    ]
                    x = right - sum(
                        pdfmetrics.stringWidth(char, font, 12) for char, font in glyphs
                    )
                    for char, font in glyphs:
                        pdf.setFont(font, 12)
                        pdf.drawString(x, y, char)
                        x += pdfmetrics.stringWidth(char, font, 12)
                else:
                    pdf.drawRightString(right, y, visual)
            else:
                pdf.drawString(left + col * col_width + 10, y, text)


def english_examples():
    rows = [["Name", "Score"], ["Ada", "10"], ["Grace", "12"]]
    layouts = {
        "english_stacked.pdf": [{"top": 80}, {"top": 350}],
        "english_close_stacked.pdf": [{"top": 80}, {"top": 205}],
        "english_side_by_side.pdf": [{"left": 40}, {"left": 340}],
        "english_rectangles.pdf": [{"rectangles": True}],
        "english_mixed_stacked.pdf": [{"top": 80}, {"top": 350, "ruled": False}],
        "english_mixed_reverse.pdf": [{"top": 80, "ruled": False}, {"top": 350}],
        "english_mixed_side_by_side.pdf": [{"left": 40}, {"left": 340, "ruled": False}],
        "english_borderless_side_by_side.pdf": [
            {"left": 40, "ruled": False},
            {"left": 340, "ruled": False},
        ],
        "english_borderless_stacked.pdf": [
            {"top": 80, "ruled": False},
            {"top": 350, "ruled": False},
        ],
    }
    for filename, positions in layouts.items():
        pdf = canvas.Canvas(str(ROOT / filename), pagesize=PAGE_SIZE, invariant=1)
        for number, position in enumerate(positions, 1):
            table = [[f"Name {number}", "Score"], *rows[1:]]
            draw_table(pdf, table, **position)
        pdf.save()
    pdf = canvas.Canvas(
        str(ROOT / "english_pages.pdf"), pagesize=PAGE_SIZE, invariant=1
    )
    for number, top in [(1, 450), (2, 80)]:
        draw_table(pdf, [[f"Name {number}", "Score"], *rows[1:]], top=top)
        pdf.showPage()
    pdf.save()


def borderless_wide_examples():
    # Nearby ordinary layouts: equal column spacing, then a somewhat wider
    # middle gutter. Neither is evidence of two separate tables.
    for filename, columns in [
        ("english_borderless_four_columns.pdf", [50, 180, 310, 440]),
        ("english_borderless_wide_middle.pdf", [50, 180, 355, 485]),
    ]:
        pdf = canvas.Canvas(str(ROOT / filename), pagesize=PAGE_SIZE, invariant=1)
        pdf.setFont("Helvetica", 12)
        rows = [
            ["Name", "Score", "Team", "Rank"],
            ["Ada", "10", "Blue", "1"],
            ["Grace", "12", "Green", "2"],
        ]
        for row, values in enumerate(rows):
            for x, value in zip(columns, values):
                pdf.drawString(x, PAGE_SIZE[1] - 103 - row * 35, value)
        pdf.save()


def farsi_examples():
    pdfmetrics.registerFont(
        TTFont("NotoNaskhArabic", str(ROOT / "fonts" / "NotoNaskhArabic-Regular.ttf"))
    )
    rows = [
        ["شهر", "جمعیت", "توضیح"],
        ["تهران", "۱۲۳", "سلام ۱۲۳"],
        ["شیراز", "٤٥٦", "سلام ٤٥٦"],
        ["تبریز", "789", "سلام 789"],
    ]
    for filename, ruled in [("farsi_ruled.pdf", True), ("farsi_borderless.pdf", False)]:
        pdf = canvas.Canvas(str(ROOT / filename), pagesize=PAGE_SIZE, invariant=1)
        draw_table(pdf, rows, ruled=ruled)
        pdf.save()
    pdf = canvas.Canvas(str(ROOT / "farsi_mixed.pdf"), pagesize=PAGE_SIZE, invariant=1)
    draw_table(pdf, rows)
    draw_table(pdf, rows, top=350, ruled=False)
    pdf.save()
    pdf = canvas.Canvas(str(ROOT / "farsi_pages.pdf"), pagesize=PAGE_SIZE, invariant=1)
    for label, top in [("اول", 450), ("دوم", 80)]:
        draw_table(pdf, [[f"شهر {label}", *rows[0][1:]], *rows[1:]], top=top)
        pdf.showPage()
    pdf.save()

    mixed = [
        ["Case", "Text"],
        ["anchors", "ABC سلام DEF"],
        ["number", "ABC سلام 123 DEF"],
        ["brackets", "ABC (سلام) DEF"],
        ["identifier", "سلام ABC123"],
        ["hyphen", "سلام ABC-123"],
        ["version", "سلام v1.2"],
        ["id-anchor", "ABC123 سلام DEF"],
        ["dash-anchor", "ABC-123 سلام DEF"],
        ["ver-anchor", "v1.2 سلام DEF"],
        ["ambiguous-a", "سلام 123 ABC"],
        ["ambiguous-b", "سلام ABC 123"],
        ["latin", "ABC DEF"],
    ]
    pdf = canvas.Canvas(
        str(ROOT / "mixed_direction_runs.pdf"), pagesize=PAGE_SIZE, invariant=1
    )
    draw_table(pdf, mixed, latin_fallback=True)
    pdf.save()


if __name__ == "__main__":
    english_examples()
    borderless_wide_examples()
    farsi_examples()
