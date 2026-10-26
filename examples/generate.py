"""Regenerate deterministic example PDFs: uv run --group examples python examples/generate.py."""

from pathlib import Path

from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent
PAGE_SIZE = (640, 800)


def draw_table(pdf, rows, *, left=40, top=80, ruled=True, rectangles=False):
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
    pdf.setFont("Helvetica", 12)
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            pdf.drawString(
                left + col * col_width + 10,
                PAGE_SIZE[1] - top - row * row_height - 23,
                str(value),
            )


def english_examples():
    rows = [["Name", "Score"], ["Ada", "10"], ["Grace", "12"]]
    layouts = {
        "english_stacked.pdf": [{"top": 80}, {"top": 350}],
        "english_close_stacked.pdf": [{"top": 80}, {"top": 205}],
        "english_side_by_side.pdf": [{"left": 40}, {"left": 340}],
        "english_rectangles.pdf": [{"rectangles": True}],
    }
    for filename, positions in layouts.items():
        pdf = canvas.Canvas(str(ROOT / filename), pagesize=PAGE_SIZE, invariant=1)
        for number, position in enumerate(positions, 1):
            table = [[f"Name {number}", "Score"], *rows[1:]]
            draw_table(pdf, table, **position)
        pdf.save()


if __name__ == "__main__":
    english_examples()
