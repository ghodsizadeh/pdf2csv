import pandas as pd


def ensure_numeric_columns(df: pd.DataFrame, errors: str = "coerce") -> pd.DataFrame:
    """
    Ensure all columns which are numbers are considered as numeric.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to process.
    errors : str, optional
        How to handle errors during numeric conversion. Options are 'ignore', 'coerce', and 'raise'.
        Defaults to 'coerce'.

    Returns
    -------
    pd.DataFrame
        The processed DataFrame with numeric columns converted.
    """
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df
