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


def complex_report_examples():
    """Synthetic Word-style layouts; no user-supplied report is bundled."""

    def new(filename):
        return canvas.Canvas(str(ROOT / filename), pagesize=PAGE_SIZE, invariant=1)

    def h(pdf, left, right, top):
        pdf.setFillColorRGB(0, 0, 0)
        pdf.rect(left, PAGE_SIZE[1] - top - 0.24, right - left, 0.48, stroke=0, fill=1)

    def v(pdf, x, top, bottom):
        pdf.setFillColorRGB(0, 0, 0)
        pdf.rect(x - 0.24, PAGE_SIZE[1] - bottom, 0.48, bottom - top, stroke=0, fill=1)

    def text(pdf, x, top, value, angle=0):
        arabic = any("\u0600" <= c <= "\u06ff" for c in value)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("NotoNaskhArabic" if arabic else "Helvetica", 10)
        visual = get_display(arabic_reshaper.reshape(value)) if arabic else value
        pdf.saveState()
        pdf.translate(x, PAGE_SIZE[1] - top)
        pdf.rotate(angle)
        pdf.drawCentredString(0, -3, visual)
        pdf.restoreState()

    pdf = new("word_shading_and_title.pdf")
    xs, ys = [50, 180, 300, 440], [80, 110, 140, 170, 200, 230]
    rows = [
        ["Name", "Score", "Team"],
        ["Ada", "10", "Blue"],
        ["Grace", "12", "Green"],
        ["Linus", "14", "Red"],
    ]
    # Cell fills and inset text-line fills must not become grid boundaries.
    for top, bottom in zip(ys, ys[1:]):
        pdf.setFillColorRGB(0.85, 0.9, 0.95)
        pdf.rect(
            xs[0], PAGE_SIZE[1] - bottom, xs[-1] - xs[0], bottom - top, stroke=0, fill=1
        )
        for left, right in zip(xs, xs[1:]):
            pdf.rect(
                left + 5,
                PAGE_SIZE[1] - top - 25,
                right - left - 10,
                10,
                stroke=0,
                fill=1,
            )
    for y in ys:
        h(pdf, xs[0], xs[-1], y)
    for x in xs:
        v(pdf, x, ys[0] if x in (xs[0], xs[-1]) else ys[1], ys[-1])
    text(pdf, 245, 95, "Regional statistics")
    for row, top in zip(rows, ys[1:]):
        for value, left, right in zip(row, xs, xs[1:]):
            text(pdf, (left + right) / 2, top + 15, value)
    pdf.save()

    pdf = new("partial_rules_rowspan.pdf")
    xs, ys = [50, 170, 230, 350], [80, 110, 140, 170, 200]
    for y in (ys[0], ys[1], ys[-1]):
        h(pdf, xs[0], xs[-1], y)
    for y in ys[2:-1]:
        h(pdf, xs[0], xs[1], y)
        h(pdf, xs[2], xs[-1], y)
    for x in xs:
        v(pdf, x, ys[0], ys[-1])
    for value, left, right in zip(["Name", "Unit", "Amount"], xs, xs[1:]):
        text(pdf, (left + right) / 2, 95, value)
    for name, amount, top in [
        ("Ada", "10", 125),
        ("Grace", "12", 155),
        ("Linus", "14", 185),
    ]:
        text(pdf, 110, top, name)
        text(pdf, 290, top, amount)
    text(pdf, 200, 155, "kWh", 90)
    pdf.showPage()
    xs, ys = [50, 170, 230, 350, 450], [80, 110, 140, 170, 195]
    for y in ys:
        h(pdf, xs[0], xs[-1], y)
    for x in [xs[0], xs[-1]]:
        v(pdf, x, ys[0], ys[-1])
    for x in [170, 350]:
        v(pdf, x, 80, 170)
    v(pdf, 230, 140, 170)
    for x, value in [(110, "Name"), (260, "Details"), (400, "Amount")]:
        text(pdf, x, 95, value)
    for x, value in [(110, "Ada"), (260, "Combined label"), (400, "10")]:
        text(pdf, x, 125, value)
    for x, value in [(110, "Grace"), (200, "Left"), (290, "Right"), (400, "12")]:
        text(pdf, x, 155, value)
    text(pdf, 250, 182, "Source: synthetic fixture")
    pdf.save()

    pdf = new("quarter_turn_text.pdf")
    xs, ys = [50, 180, 310, 460], [80, 160, 240, 320]
    rows = [
        ["Case", "Value", "Text"],
        ["One", "-21.7", "سلام ۱۲۳"],
        ["Two", "1015", "سلام ٤٥٦"],
    ]
    for angle in [0, 90, 180, 270]:
        for y in ys:
            h(pdf, xs[0], xs[-1], y)
        for x in xs:
            v(pdf, x, ys[0], ys[-1])
        for row, top, bottom in zip(rows, ys, ys[1:]):
            for value, left, right in zip(row, xs, xs[1:]):
                text(pdf, (left + right) / 2, (top + bottom) / 2, value, angle)
        pdf.showPage()
    pdf.save()

    pdf = new("frame_touching_tables.pdf")
    pdf.setStrokeColorRGB(0, 0, 0.5)
    for margin in [12, 18]:
        pdf.rect(
            margin, margin, PAGE_SIZE[0] - 2 * margin, PAGE_SIZE[1] - 2 * margin, fill=0
        )
    for xs, top in [([50, 300, 622], 100), ([50, 180, 310], 400)]:
        rows = [["Name", "Score"], ["Ada", "10"], ["Grace", "12"]]
        for y in [top, top + 35, top + 70, top + 105]:
            h(pdf, xs[0], xs[-1], y)
        for x in xs:
            v(pdf, x, top, top + 105)
        for row, offset in zip(rows, [17, 52, 87]):
            for value, left, right in zip(row, xs, xs[1:]):
                text(pdf, (left + right) / 2, top + offset, value)
    pdf.save()

    pdf = new("borderless_prose.pdf")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 750, "Annual report 101")
    for i, line in enumerate(
        [
            "This is a paragraph about annual operating performance.",
            "Its indents align with other lines without forming columns.",
            "The totals increased compared with the previous reporting period.",
            "These notes explain the reasons for the observed changes.",
        ]
    ):
        pdf.drawString(50 + 10 * (i % 2), 650 - 24 * i, line)
    pdf.drawCentredString(270, 410, "Separate heading, rather than a data row")
    pdf.drawRightString(500, 120, "Prepared by the statistics department")
    pdf.showPage()
    pdf.setFont("Helvetica", 14)
    phrase = "Annual operating performance and statistics report"
    center = 50 + pdfmetrics.stringWidth(phrase, "Helvetica", 14) / 2
    pdf.drawString(50, 680, "Bulletin")
    pdf.drawCentredString(center, 680, "101")
    pdf.drawString(50, 650, phrase)
    pdf.showPage()
    for top, row in [
        (100, ["Section", "Author"]),
        (360, ["Introduction", "Statistics division"]),
    ]:
        for x, value in zip([80, 260], row):
            text(pdf, x, top, value)
    pdf.save()

    pdf = new("borderless_text_only.pdf")
    for i, row in enumerate(
        [["Name", "State"], ["Alpha", "Enabled"], ["Beta", "Disabled"]]
    ):
        for x, value in zip([60, 220], row):
            text(pdf, x, 100 + 30 * i, value)
    pdf.save()

    pdf = new("ambiguous_grouped_header.pdf")
    xs, ys = [50, 150, 250, 350, 450], [80, 110, 140, 170, 200]
    for y in ys:
        h(pdf, xs[0], xs[-1], y)
    for x in [50, 250, 450]:
        v(pdf, x, ys[0], ys[-1])
    for x in [150, 350]:
        v(pdf, x, ys[1], ys[-1])
    text(pdf, 150, 95, "Group A")
    text(pdf, 350, 95, "Group B")
    for top, row in zip(
        [125, 155, 185],
        [
            ["A1", "B1", "C1", "D1"],
            ["A2", "B2", "C2", "D2"],
            ["A3", "B3", "C3", "D3"],
        ],
    ):
        for value, left, right in zip(row, xs, xs[1:]):
            text(pdf, (left + right) / 2, top, value)
    pdf.save()

    pdf = new("schema_change.pdf")
    rows = [
        ["Share", "Amount", "Category"],
        ["20", "400", "Steam"],
        ["30", "600", "Gas"],
        ["1000", "Thermal", "Capacity"],
        ["2000", "Hydro", "Capacity"],
        ["Value", "Description", "Category"],
        ["3000", "Generation", "Energy"],
    ]
    draw_table(pdf, rows)
    pdf.save()


if __name__ == "__main__":
    english_examples()
    borderless_wide_examples()
    farsi_examples()
    complex_report_examples()
