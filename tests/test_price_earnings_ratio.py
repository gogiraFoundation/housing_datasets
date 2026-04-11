"""Tests for ONS house price to workplace-based earnings ratio ETL."""

from __future__ import annotations

import pandas as pd

from ons_price_earnings_ratio_etl import table_meta, transform_sheet


def test_table_meta() -> None:
    assert table_meta("1a") == ("region", "median", "house_price")
    assert table_meta("2c") == ("region", "lower_quartile", "ratio")
    assert table_meta("3b") == ("county", "median", "earnings")
    assert table_meta("6a") == ("local_authority", "lower_quartile", "house_price")


def test_transform_region_two_id_cols() -> None:
    df = pd.DataFrame(
        [
            ["K1", "Region A", 100.0, 110.0],
        ],
        columns=["Code", "Name", "Year ending Sep 2020", "Year ending Sep 2021"],
    )
    tidy = transform_sheet(df, "1a")
    assert len(tidy) == 2
    assert tidy["geography_level"].iloc[0] == "region"
    assert tidy["percentile"].iloc[0] == "median"
    assert tidy["component"].iloc[0] == "house_price"
    assert "code" in tidy.columns
    assert "name" in tidy.columns


def test_transform_la_four_id_cols() -> None:
    df = pd.DataFrame(
        [
            ["R1", "North", "E01", "LA1", 2.5, 2.6],
        ],
        columns=[
            "Country/Region code",
            "Country/Region name",
            "Local authority code",
            "Local authority name",
            "1997",
            "1998",
        ],
    )
    tidy = transform_sheet(df, "5c")
    assert len(tidy) == 2
    assert tidy["geography_level"].iloc[0] == "local_authority"
    assert tidy["component"].iloc[0] == "ratio"
    assert tidy["local_authority_name"].iloc[0] == "LA1"
