"""Tests for ONS house building by local authority ETL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from ons_housebuilding_la_etl import clean_wide, melt_with_measure, transform_workbook


def _write_workbook_like_ons(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for title, df in sheets.items():
        ws = wb.create_sheet(title)
        for _ in range(5):
            ws.append([None])
        ws.append(list(df.columns))
        for _, row in df.iterrows():
            ws.append(row.tolist())
    wb.save(path)


def _minimal_block() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["[r]", "North East", "E06000001", "Hartlepool", 10, 20],
            ["[r]", "North East", "E06000002", "Middlesbrough", 30, "[x]"],
        ],
        columns=[
            "Revised",
            "Region or Country Name",
            "Local Authority Code",
            "Local Authority Name",
            "2009-2010",
            "2010-2011",
        ],
    )


def test_clean_wide_normalises_headers() -> None:
    raw = _minimal_block()
    out = clean_wide(raw)
    assert list(out.columns[:4]) == [
        "Region Type",
        "Region or Country Name",
        "Local Authority Code",
        "Local Authority Name",
    ]


def test_clean_wide_invalid_year_raises() -> None:
    raw = _minimal_block().rename(columns={"2010-2011": "FY 2010/11"})
    with pytest.raises(ValueError, match="Unexpected year column"):
        clean_wide(raw)


def test_melt_with_measure_contains_metric_and_nullable_ints() -> None:
    tidy = melt_with_measure(clean_wide(_minimal_block()), measure="starts")
    assert set(tidy["measure"]) == {"starts"}
    assert tidy["dwellings"].dtype == pd.Int64Dtype()
    assert tidy["dwellings"].isna().sum() == 1


def test_transform_workbook_writes_outputs(tmp_path: Path) -> None:
    xlsx = tmp_path / "wb.xlsx"
    _write_workbook_like_ons(
        xlsx,
        {
            "UK_Starts": _minimal_block(),
            "UK_Completions": _minimal_block(),
        },
    )
    out = tmp_path / "out"
    tidy = transform_workbook(xlsx, out, edition_key="test", write_parquet=True, verbose=False)
    assert set(tidy["measure"].astype(str).unique()) == {"starts", "completions"}
    assert (out / "ons_housebuilding_la_test_tidy.csv").is_file()
    assert (out / "ons_housebuilding_la_test_tidy.parquet").is_file()
