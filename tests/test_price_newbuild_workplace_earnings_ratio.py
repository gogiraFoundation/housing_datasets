"""Tests for new-build workplace price/earnings ETL (reuses workplace ratio transform)."""

from __future__ import annotations

import pandas as pd

from ons_price_earnings_ratio_etl import transform_sheet


def test_transform_sheet_newbuild_workbook_layout():
    df = pd.DataFrame(
        [["K1", "Region A", 100.0, 110.0]],
        columns=["Code", "Name", "Year ending Sep 2020", "Year ending Sep 2021"],
    )
    tidy = transform_sheet(df, "1a")
    assert len(tidy) == 2
    assert tidy["component"].iloc[0] == "house_price"
