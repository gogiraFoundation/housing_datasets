"""Tests for UK housing starts Excel pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from uk_local_authority_housing_data import (
    ID_COL_NAMES,
    clean_wide,
    melt_to_tidy,
    run_pipeline,
)


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


def _write_minimal_workbook(path: Path) -> None:
    df = pd.DataFrame(_minimal_wide_rows(), columns=_minimal_columns())
    df.to_excel(path, sheet_name="UK_Starts", index=False)


def test_clean_wide_renames_ids_and_validates_years():
    df = pd.DataFrame(_minimal_wide_rows(), columns=_minimal_columns())
    wide = clean_wide(df)
    assert list(wide.columns[:4]) == ID_COL_NAMES
    assert list(wide.columns[4:]) == ["2009-2010", "2010-2011"]
    assert len(wide) == 2


def test_clean_wide_too_few_columns_raises():
    df = pd.DataFrame([[1, 2, 3]], columns=["a", "b", "c"])
    with pytest.raises(ValueError, match="at least 4"):
        clean_wide(df)


def test_clean_wide_bad_year_column_raises():
    cols = _minimal_columns().copy()
    cols[-1] = "not-a-year"
    df = pd.DataFrame(_minimal_wide_rows(), columns=cols)
    with pytest.raises(ValueError, match="Unexpected year column"):
        clean_wide(df)


def test_melt_to_tidy_shape_and_columns():
    df = pd.DataFrame(_minimal_wide_rows(), columns=_minimal_columns())
    wide = clean_wide(df)
    tidy = melt_to_tidy(wide)
    assert len(tidy) == 4
    assert set(tidy["financial_year"]) == {"2009-2010", "2010-2011"}
    assert list(tidy.columns) == ID_COL_NAMES + ["financial_year", "starts"]
    # melt orders by value_vars (years) then id order within each year
    assert tidy["starts"].tolist() == [10, 30, 20, 40]


def test_run_pipeline_writes_csv_and_parquet(tmp_path: Path):
    xlsx = tmp_path / "mini.xlsx"
    out = tmp_path / "processed"
    _write_minimal_workbook(xlsx)
    wide, tidy = run_pipeline(
        xlsx,
        out,
        sheet_name="UK_Starts",
        skiprows=0,
        write_parquet=True,
        verbose=False,
    )
    assert wide.shape[0] == 2
    assert (out / "uk_housing_starts_wide.csv").is_file()
    assert (out / "uk_housing_starts_tidy.csv").is_file()
    assert (out / "uk_housing_starts_tidy.parquet").is_file()
    roundtrip = pd.read_parquet(out / "uk_housing_starts_tidy.parquet")
    pd.testing.assert_frame_equal(tidy.reset_index(drop=True), roundtrip.reset_index(drop=True))


def test_run_pipeline_skip_parquet(tmp_path: Path):
    xlsx = tmp_path / "mini.xlsx"
    out = tmp_path / "processed"
    _write_minimal_workbook(xlsx)
    run_pipeline(xlsx, out, sheet_name="UK_Starts", skiprows=0, write_parquet=False, verbose=False)
    assert not (out / "uk_housing_starts_tidy.parquet").is_file()
