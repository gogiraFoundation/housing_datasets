"""Tests for ONS house price per m² / per room ETL."""

from __future__ import annotations

import pandas as pd

from ons_house_m2_room_etl import transform_sheet


def test_table1_region_melt():
    df = pd.DataFrame(
        [
            ["E12000001", "North East", 100.0, 110.0],
        ],
        columns=["Area code", "Region Name", 2004.0, 2005.0],
    )
    tidy = transform_sheet(df, "Table1")
    assert len(tidy) == 2
    assert set(tidy["year"].astype(int).tolist()) == {2004, 2005}
    assert tidy["metric"].iloc[0] == "price_per_sqm"
    assert tidy["geography_level"].iloc[0] == "region"


def test_table7_la_melt():
    df = pd.DataFrame(
        [
            ["E12000001", "North East", "E06000001", "Hartlepool", 1.0, 2.0],
        ],
        columns=["Region code", "Region name", "LA code", "LA name", 2004.0, 2005.0],
    )
    tidy = transform_sheet(df, "Table7")
    assert len(tidy) == 2
    assert tidy["la_name"].iloc[0] == "Hartlepool"
    assert tidy["metric"].iloc[0] == "price_per_room"
