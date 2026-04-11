"""Shared wide-table helpers for ONS-style local authority house-building Excel layouts."""

from __future__ import annotations

import re

import pandas as pd

FINANCIAL_YEAR_PATTERN = re.compile(r"^\d{4}-\d{4}$")

LA_ID_COLUMNS = [
    "Region Type",
    "Region or Country Name",
    "Local Authority Code",
    "Local Authority Name",
]


def clean_wide_la_housing(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty rows/columns; standardise four ID columns; validate financial-year column names."""
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    if len(out.columns) < 4:
        raise ValueError(f"Expected at least 4 identifier columns after cleaning; got {len(out.columns)}.")

    id_rename = {out.columns[i]: LA_ID_COLUMNS[i] for i in range(4)}
    out = out.rename(columns=id_rename)

    year_renames: dict[str | int, str] = {}
    for col in list(out.columns[4:]):
        label = str(col).strip()
        if not FINANCIAL_YEAR_PATTERN.match(label):
            raise ValueError(
                f"Unexpected year column {col!r} (normalised {label!r}); expected financial year like '2009-2010'."
            )
        if label != col:
            year_renames[col] = label
    if year_renames:
        out = out.rename(columns=year_renames)

    return out
