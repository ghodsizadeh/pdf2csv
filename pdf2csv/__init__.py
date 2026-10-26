"""pdf2csv - Extract tables from PDF files into CSV or Excel."""

__version__ = "0.3.0"

from pdf2csv.converter import convert
from pdf2csv.errors import Pdf2CsvError

__all__ = ["Pdf2CsvError", "convert"]
