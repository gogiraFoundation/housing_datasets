"""Tests for ONS median price by administrative geography ETL."""

from __future__ import annotations

import pandas as pd

from ons_median_price_admin_etl import transform_sheet


def test_transform_region_two_cols():
    df = pd.DataFrame(
        [
            ["X1", "Region A", 100.0, 110.0],
        ],
        columns=["Area Code", "Area Name", "Year ending Dec 1995", "Year ending Mar 1996"],
    )
    tidy = transform_sheet(df, "1a", dwelling_class="existing")
    assert len(tidy) == 2
    assert "area_code" in tidy.columns
    assert tidy["geography_level"].iloc[0] == "region"


def test_transform_la_four_cols():
    df = pd.DataFrame(
        [
            ["R1", "North", "E01", "LA1", 1.0, 2.0],
        ],
        columns=[
            "Region/Country code",
            "Region/Country name",
            "Local authority code",
            "Local authority name",
            "Year ending Dec 1995",
            "Year ending Mar 1996",
        ],
    )
    tidy = transform_sheet(df, "2a", dwelling_class="existing")
    assert len(tidy) == 2
    assert "local_authority_name" in tidy.columns


def test_transform_marks_all_dwellings_class():
    df = pd.DataFrame(
        [["X1", "Region A", 100.0]],
        columns=["Area Code", "Area Name", "Year ending Dec 1995"],
    )
    tidy = transform_sheet(df, "1a", dwelling_class="all_dwellings")
    assert tidy["dwelling_class"].iloc[0] == "all_dwellings"
