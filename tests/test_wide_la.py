"""Tests for shared wide LA table helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from housing_data.wide_la import LA_ID_COLUMNS, clean_wide_la_housing


def _minimal_wide_rows():
    return [
        ["R", "England", "E09000001", "Westminster", 10, 20],
        ["R", "England", "E09000002", "Camden", 30, 40],
    ]


def _minimal_columns():
    return [
        "Revised",
        "Region or Country Name",
        "Local Authority Code",
        "Local Authority Name",
        "2009-2010",
        "2010-2011",
    ]


def test_clean_wide_la_housing_renames_ids_and_validates_years() -> None:
    df = pd.DataFrame(_minimal_wide_rows(), columns=_minimal_columns())
    wide = clean_wide_la_housing(df)
    assert list(wide.columns[:4]) == LA_ID_COLUMNS
    assert list(wide.columns[4:]) == ["2009-2010", "2010-2011"]
    assert len(wide) == 2


def test_clean_wide_la_housing_too_few_columns_raises() -> None:
    df = pd.DataFrame([[1, 2, 3]], columns=["a", "b", "c"])
    with pytest.raises(ValueError, match="at least 4"):
        clean_wide_la_housing(df)


def test_clean_wide_la_housing_bad_year_column_raises() -> None:
    cols = _minimal_columns().copy()
    cols[-1] = "not-a-year"
    df = pd.DataFrame(_minimal_wide_rows(), columns=cols)
    with pytest.raises(ValueError, match="Unexpected year column"):
        clean_wide_la_housing(df)
