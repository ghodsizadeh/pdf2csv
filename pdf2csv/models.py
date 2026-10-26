"""Structured table extraction results and their source coordinates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class ExtractionWarning:
    """An observed extraction condition, with a stable machine-readable code."""

    code: str
    message: str
    page_number: int | None = None


@dataclass
class ExtractedTable:
    """A table's extracted strings, source location, and optional DataFrame.

    ``rows`` includes the first row, regardless of header or numeric settings.
    Coordinates are PDF points from the page's top-left, as in pdfplumber.
    """

    rows: list[list[str]]
    page_number: int
    bbox: BBox
    method: Literal["ruled", "text"]
    warnings: list[ExtractionWarning] = field(default_factory=list)
    dataframe: pd.DataFrame | None = None


@dataclass
class ExtractionResult:
    """Tables in document reading order and warnings for the selected pages."""

    source: Path
    tables: list[ExtractedTable]
    warnings: list[ExtractionWarning] = field(default_factory=list)
