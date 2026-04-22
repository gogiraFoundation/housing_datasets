"""Tests for ONS national park HPSSA (sales and prices) ETL."""

from __future__ import annotations

import pandas as pd

from ons_national_park_hpssa_etl import transform_sheet


def test_transform_sales_all_types():
    df = pd.DataFrame(
        [
            ["E26", "Park A", 10.0, 11.0],
        ],
        columns=["Area Code", "Area Name", "Year ending Dec 1995", "Year ending Mar 1996"],
    )
    tidy = transform_sheet(df, "1a")
    assert len(tidy) == 2
    assert tidy["measure"].iloc[0] == "sales_count"
    assert tidy["property_band"].iloc[0] == "all"
    assert tidy["geography_level"].iloc[0] == "national_park"
    assert "area_code" in tidy.columns


def test_transform_median_detached():
    df = pd.DataFrame(
        [["E26", "Park A", 100000.0, 101000.0]],
        columns=["Area Code", "Area Name", "Year ending Dec 1995", "Year ending Mar 1996"],
    )
    tidy = transform_sheet(df, "2b")
    assert tidy["measure"].iloc[0] == "median_price_gbp"
    assert tidy["property_band"].iloc[0] == "detached"
