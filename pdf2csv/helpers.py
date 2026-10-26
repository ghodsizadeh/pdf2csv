"""DataFrame cleanup for extracted tables."""

from __future__ import annotations

import pandas as pd

# Persian (۰-۹) and Arabic-Indic (٠-٩) digits, plus the unicode minus sign.
_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩−", "01234567890123456789-")


def _normalize_token(value: object) -> object:
    if not isinstance(value, str):
        return value
    return value.translate(_DIGIT_TRANSLATION).strip()


def _coerce_column(series: pd.Series) -> pd.Series:
    """Convert a column when every non-empty cell is numeric."""
    if pd.api.types.is_numeric_dtype(series):
        return series

    normalized = series.map(_normalize_token)
    nonempty = normalized.map(lambda value: isinstance(value, str) and value != "")
    if not bool(nonempty.any()):
        return series

    converted = pd.to_numeric(normalized.where(nonempty), errors="coerce")
    if bool(converted[nonempty].notna().all()):
        return converted
    return series


def ensure_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with columns of pure numbers stored as numbers.

    A column is converted only when every non-empty cell parses as a number.
    Mixed text columns are left unchanged. Persian and Arabic-Indic digits are
    accepted.
    """
    coerced = [_coerce_column(df.iloc[:, index]) for index in range(df.shape[1])]
    if not coerced:
        return df.copy()
    result = pd.concat(coerced, axis=1)
    result.columns = df.columns
    return result
