"""Tests for ONS UK HPI monthly ETL."""

from __future__ import annotations

import pandas as pd

from ons_uk_hpi_monthly_etl import transform_la_sheet, transform_split_sheet, transform_time_sheet


def test_time_sheet_melt():
    df = pd.DataFrame(
        [
            ["Jan 2011", 1.0, 2.0],
            ["Feb 2011", 3.0, 4.0],
        ],
        columns=["Time period", "England", "Wales"],
    )
    tidy = transform_time_sheet(df, "1")
    assert len(tidy) == 4
    assert set(tidy["geography"]) == {"England", "Wales"}


def test_split_sheet_two_blocks():
    df = pd.DataFrame(
        [
            ["Jan 2012", 100, 200, None, "Jan 2012", 1.0, 2.0],
        ],
        columns=[
            "Time period",
            "First time buyer",
            "Former owner occupier",
            "Unnamed: 3",
            "Time period.1",
            "First time buyer.1",
            "Former owner occupier.1",
        ],
    )
    tidy = transform_split_sheet(df, "4")
    assert set(tidy["table_block"]) == {"level_gbp", "annual_pct_change"}
    assert len(tidy[tidy["table_block"] == "level_gbp"]) == 2


def test_la_sheet_melt():
    df = pd.DataFrame(
        [
            ["E09000001", "City of London", 500.0, 1.0],
        ],
        columns=["AreaCode", "RegionName", "Average Price (£)", "Annual percentage change"],
    )
    tidy = transform_la_sheet(df, "8")
    assert len(tidy) == 2
    assert set(tidy["metric"]) == {"Average Price (£)", "Annual percentage change"}
    assert tidy["country_group"].iloc[0] == "England"
