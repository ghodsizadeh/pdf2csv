"""Convert PDF tables to data frames and optional CSV or Excel files."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from pdf2csv.errors import Pdf2CsvError
from pdf2csv.extract import extract_tables
from pdf2csv.helpers import ensure_numeric_columns

_log = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 100
_OUTPUT_FORMATS = ("csv", "xlsx")


def convert(
    pdf_path: str,
    output_dir: str | None = None,
    rtl: bool = False,
    output_format: Literal["csv", "xlsx"] = "csv",
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
    **kwargs: Any,
) -> list[pd.DataFrame]:
    """Extract tables from a PDF.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF file.
    output_dir:
        Directory where each table is written. Nothing is written when omitted.
    rtl:
        Force right-to-left glyph order inside cells. Arabic and Hebrew are
        detected even when this is false. Columns stay in left-to-right page
        order, and digits are not reversed.
    output_format:
        ``csv`` or ``xlsx``. Used only when ``output_dir`` is set.
    max_bytes:
        Reject PDFs larger than this many bytes.
    max_pages:
        Reject PDFs with more pages than this.
    **kwargs:
        Forwarded to ``DataFrame.to_csv`` or ``DataFrame.to_excel``.

    Returns
    -------
    list[pd.DataFrame]
        One frame per table. The first row of each table becomes the columns.

    Raises
    ------
    FileNotFoundError
        If ``pdf_path`` does not exist.
    Pdf2CsvError
        If the file is not a readable PDF within the size and page limits.
    """
    started = time.time()
    path = _validated_pdf(pdf_path, max_bytes)
    if output_dir is not None and output_format not in _OUTPUT_FORMATS:
        raise Pdf2CsvError(f"Unsupported output format: {output_format}")

    tables = extract_tables(path, rtl=rtl, max_pages=max_pages)
    frames = [_frame_from_rows(table) for table in tables]
    if not frames:
        _log.warning("No tables were found in %s. Returning empty list.", path)
        return frames

    output_path = _prepare_output_dir(output_dir)
    if output_path is not None:
        for index, frame in enumerate(frames, start=1):
            _write_frame(frame, output_path, path.stem, index, output_format, kwargs)

    _log.debug(
        "Finished processing %s in %.2f seconds. Extracted %s tables.",
        path,
        time.time() - started,
        len(frames),
    )
    return frames


def _validated_pdf(pdf_path: str, max_bytes: int) -> Path:
    if max_bytes < 1:
        raise Pdf2CsvError("max_bytes must be a positive number of bytes")

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not path.is_file():
        raise Pdf2CsvError(f"PDF path is not a file: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise Pdf2CsvError(f"Not a PDF file: {pdf_path}")

    size = path.stat().st_size
    if size == 0:
        raise Pdf2CsvError(f"PDF file is empty: {pdf_path}")
    if size > max_bytes:
        raise Pdf2CsvError(
            f"PDF is {size} bytes, which exceeds the limit of {max_bytes} bytes"
        )
    return path


def _prepare_output_dir(output_dir: str | None) -> Path | None:
    if output_dir is None:
        return None
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _log.debug("Created/verified output directory: %s", output_path)
    return output_path


def _frame_from_rows(rows: list[list[str]]) -> pd.DataFrame:
    header, *body = rows
    columns = [
        name if name else f"column_{index + 1}" for index, name in enumerate(header)
    ]
    frame = pd.DataFrame(body, columns=columns)
    return ensure_numeric_columns(frame)


def _write_frame(
    frame: pd.DataFrame,
    output_dir: Path,
    stem: str,
    index: int,
    output_format: str,
    kwargs: dict[str, Any],
) -> None:
    if output_format == "csv":
        destination = output_dir / f"{stem}-table-{index}.csv"
        frame.to_csv(destination, **kwargs)
        _log.info("Saved CSV table #%s to: %s", index, destination)
        return

    destination = output_dir / f"{stem}-table-{index}.xlsx"
    frame.to_excel(destination, engine="openpyxl", **kwargs)
    _log.info("Saved XLSX table #%s to: %s", index, destination)
