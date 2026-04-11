"""Tests for ONS house building by country ETL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from ons_housebuilding_country_etl import _melt_table, transform_workbook


def _write_wb(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for name, df in sheets.items():
        ws = wb.create_sheet(name)
        for _ in range(5):
            ws.append([None])
        ws.append(list(df.columns))
        for _, row in df.iterrows():
            ws.append(row.tolist())
    wb.save(path)


def _mini_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["", "Jan - Mar 2000", 100, 80, 10, 10, 120, 90, 20, 10],
            ["", "Apr - Jun 2000", "[x1]", 70, 20, 5, 110, 85, 15, 10],
        ],
        columns=[
            "Revised",
            "Period",
            "Started - All Dwellings",
            "Started - Private Enterprise",
            "Started - Housing Associations",
            "Started - Local Authorities",
            "Completed - All Dwellings",
            "Completed - Private Enterprise",
            "Completed - Housing Associations",
            "Completed - Local Authorities",
        ],
    )


def test_melt_table_parses_measure_sector():
    tidy = _melt_table(_mini_sheet(), "1a")
    assert set(tidy["measure"]) == {"started", "completed"}
    assert "All Dwellings" in set(tidy["sector"])
    assert tidy["dwellings"].dtype == pd.Int64Dtype()


def test_transform_workbook_outputs(tmp_path: Path):
    wb = tmp_path / "wb.xlsx"
    sheets = {k: _mini_sheet() for k in ("1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "2c", "2d", "2e", "3a", "3b", "3c", "3d", "3e")}
    _write_wb(wb, sheets)
    out = tmp_path / "out"
    tidy = transform_workbook(wb, out, edition_key="test", write_parquet=True, verbose=False)
    assert (out / "ons_housebuilding_country_test_tidy.csv").is_file()
    assert (out / "ons_housebuilding_country_test_tidy.parquet").is_file()
    assert {"quarterly", "annual_financial_year", "annual_calendar_year"} <= set(tidy["frequency"])
