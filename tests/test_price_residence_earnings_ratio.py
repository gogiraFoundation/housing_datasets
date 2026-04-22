"""Tests for ONS house price to residence-based earnings ratio ETL (reuses workplace transform)."""

from __future__ import annotations

import pandas as pd

from ons_price_earnings_ratio_etl import table_meta, transform_sheet


def test_table_meta_matches_workplace_layout() -> None:
    assert table_meta("1a") == ("region", "median", "house_price")
    assert table_meta("5c") == ("local_authority", "median", "ratio")


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
    assert "code" in tidy.columns
    assert "name" in tidy.columns
