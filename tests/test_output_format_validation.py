"""An unsupported output format must fail even when nothing is exported."""

from pathlib import Path

import pytest

from pdf2csv import Pdf2CsvError, convert

ASSETS = Path(__file__).parent / "assets"


def test_rejects_unsupported_output_format_without_output_dir():
    with pytest.raises(Pdf2CsvError, match="Unsupported output format"):
        convert(ASSETS / "simple_table.pdf", output_dir=None, output_format="xml")
