"""Convert PDF tables to data frames and optional CSV or Excel files."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from pdf2csv.errors import Pdf2CsvError
from pdf2csv.extract import extract_table_results
from pdf2csv.helpers import ensure_numeric_columns
from pdf2csv.models import BBox, ExtractionResult, ExtractionWarning

_log = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 100
_OUTPUT_FORMATS = ("csv", "xlsx")


def extract_document(
    pdf_path: str | Path,
    *,
    rtl: bool = False,
    pages: Sequence[int] | None = None,
    crop: BBox | Mapping[int, BBox] | None = None,
    header: Literal[0] | None = 0,
    numeric: Literal["infer", "preserve"] = "infer",
    dtypes: Mapping[Any, Any] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> ExtractionResult:
    """Extract tables, raw strings, source locations, and observed warnings.

    ``pages`` uses document page numbers starting at 1, returned in document
    order. ``crop`` is a page-coordinate bbox or a mapping from page numbers to
    bboxes. ``header=None`` keeps the first row as data. ``numeric='preserve'``
    retains cell strings; the default infers wholly numeric columns. Explicit
    ``dtypes`` map DataFrame column labels to pandas dtypes and use raw strings,
    so a string dtype preserves leading zeroes even with numeric inference.
    """
    _validate_frame_options(header, numeric, dtypes)
    path = _validated_pdf(pdf_path, max_bytes)
    tables, warnings = extract_table_results(
        path, rtl=rtl, max_pages=max_pages, pages=pages, crop=crop
    )
    for table in tables:
        table.dataframe = _frame_from_rows(
            table.rows, header=header, numeric=numeric, dtypes=dtypes
        )
        if header == 0:
            labels = table.rows[0]
            if any(not label for label in labels):
                table.warnings.append(
                    ExtractionWarning(
                        "empty_header",
                        "Empty header cells received generated column names.",
                        table.page_number,
                    )
                )
            if table.dataframe.columns.has_duplicates:
                table.warnings.append(
                    ExtractionWarning(
                        "duplicate_header",
                        "The DataFrame contains duplicate column labels.",
                        table.page_number,
                    )
                )
    return ExtractionResult(path, tables, warnings)


def convert(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    rtl: bool = False,
    output_format: Literal["csv", "xlsx"] = "csv",
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
    pages: Sequence[int] | None = None,
    crop: BBox | Mapping[int, BBox] | None = None,
    table_header: Literal[0] | None = 0,
    numeric: Literal["infer", "preserve"] = "infer",
    dtypes: Mapping[Any, Any] | None = None,
    export_kwargs: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> list[pd.DataFrame]:
    """Return one DataFrame per table and optionally export CSV or XLSX files.

    Extraction options match :func:`extract_document`; ``table_header`` corresponds
    to its ``header`` argument. The default promotes the first
    row to column labels and infers numeric columns, preserving legacy output.
    ``export_kwargs`` is passed only to pandas' writer; legacy extra keyword
    arguments remain supported. Use ``export_kwargs={"header": False}`` to omit
    CSV/Excel headers independently of extraction's ``table_header`` option.
    """
    started = time.time()
    if output_dir is not None and output_format not in _OUTPUT_FORMATS:
        raise Pdf2CsvError(f"Unsupported output format: {output_format}")
    writer_kwargs = _export_options(export_kwargs, kwargs)
    result = extract_document(
        pdf_path,
        rtl=rtl,
        pages=pages,
        crop=crop,
        header=table_header,
        numeric=numeric,
        dtypes=dtypes,
        max_bytes=max_bytes,
        max_pages=max_pages,
    )
    for number, table in enumerate(result.tables, 1):
        for warning in table.warnings:
            _log.warning(
                "Table %s (page %s): %s: %s",
                number,
                table.page_number,
                warning.code,
                warning.message,
            )
    frames = [table.dataframe for table in result.tables]
    if not frames:
        _log.warning("No tables were found in %s. Returning empty list.", result.source)
        return frames
    if output_dir is not None:
        export_frames(frames, result.source, output_dir, output_format, **writer_kwargs)
    _log.debug(
        "Finished processing %s in %.2f seconds. Extracted %s tables.",
        result.source,
        time.time() - started,
        len(frames),
    )
    return frames


def export_frames(
    frames: Sequence[pd.DataFrame],
    pdf_path: str | Path,
    output_dir: str | Path,
    output_format: Literal["csv", "xlsx"] = "csv",
    *,
    overwrite: bool = True,
    **kwargs: Any,
) -> list[Path]:
    """Write frames with standard filenames, preflighting all collisions.

    With ``overwrite=False``, existing files, directories and symlinks at any
    destination cause ``FileExistsError`` before any table is written.
    """
    if output_format not in _OUTPUT_FORMATS:
        raise Pdf2CsvError(f"Unsupported output format: {output_format}")
    if not isinstance(overwrite, bool):
        raise Pdf2CsvError("overwrite must be a boolean")
    output_path = Path(output_dir)
    stem = Path(pdf_path).stem
    destinations = [
        output_path / f"{stem}-table-{number}.{output_format}"
        for number in range(1, len(frames) + 1)
    ]
    if not overwrite:
        for destination in destinations:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"Output already exists: {destination}")
    for destination in destinations:
        if destination.is_dir():
            raise IsADirectoryError(f"Output path is a directory: {destination}")
    if not frames:
        return destinations
    _prepare_output_dir(output_path)
    for number, frame in enumerate(frames, 1):
        _write_frame(frame, output_path, stem, number, output_format, kwargs)
    return destinations


def _export_options(export_kwargs, legacy_kwargs):
    if export_kwargs is not None and not isinstance(export_kwargs, Mapping):
        raise Pdf2CsvError("export_kwargs must be a mapping")
    options = dict(export_kwargs or {})
    duplicates = options.keys() & legacy_kwargs.keys()
    if duplicates:
        raise Pdf2CsvError(
            f"Export options specified twice: {', '.join(sorted(duplicates))}"
        )
    options.update(legacy_kwargs)
    if any(not isinstance(key, str) for key in options):
        raise Pdf2CsvError("export_kwargs keys must be strings")
    return options


def _validate_frame_options(header, numeric, dtypes):
    if header is not None and (
        isinstance(header, bool) or not isinstance(header, int) or header != 0
    ):
        raise Pdf2CsvError("header must be 0 (first row) or None (no header)")
    if numeric not in ("infer", "preserve"):
        raise Pdf2CsvError("numeric must be 'infer' or 'preserve'")
    if dtypes is not None:
        if not isinstance(dtypes, Mapping):
            raise Pdf2CsvError("dtypes must map column labels to pandas dtypes")
        for dtype in dtypes.values():
            try:
                pd.api.types.pandas_dtype(dtype)
            except (TypeError, ValueError) as exc:
                raise Pdf2CsvError(f"Invalid pandas dtype: {dtype!r}") from exc


def _validated_pdf(pdf_path: str | Path, max_bytes: int) -> Path:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise Pdf2CsvError("max_bytes must be a positive integer number of bytes")

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


def _prepare_output_dir(output_dir: str | Path | None) -> Path | None:
    if output_dir is None:
        return None
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _log.debug("Created/verified output directory: %s", output_path)
    return output_path


def _frame_from_rows(
    rows: list[list[str]],
    *,
    header: Literal[0] | None = 0,
    numeric: Literal["infer", "preserve"] = "infer",
    dtypes: Mapping[Any, Any] | None = None,
) -> pd.DataFrame:
    if header is None:
        frame = pd.DataFrame(rows)
    else:
        names, *body = rows
        columns = [
            name if name else f"column_{index + 1}" for index, name in enumerate(names)
        ]
        frame = pd.DataFrame(body, columns=columns)
    raw = frame
    if numeric == "infer":
        frame = ensure_numeric_columns(frame)
    else:
        frame = frame.copy()
    for column, dtype in (dtypes or {}).items():
        positions = [
            index for index, label in enumerate(raw.columns) if label == column
        ]
        if not positions:
            raise Pdf2CsvError(f"dtype column not found: {column!r}")
        if len(positions) > 1:
            raise Pdf2CsvError(f"dtype column is ambiguous: {column!r}")
        index = positions[0]
        try:
            frame.isetitem(index, raw.iloc[:, index].astype(dtype))
        except (TypeError, ValueError, OverflowError) as exc:
            raise Pdf2CsvError(
                f"Could not convert column {column!r} to {dtype!r}: {exc}"
            ) from exc
    return frame


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
