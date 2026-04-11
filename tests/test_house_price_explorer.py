"""Tests for ONS House Price Explorer ETL."""

from __future__ import annotations

import pandas as pd

from ons_house_price_explorer_etl import (
    transform_price_or_count_totals,
    transform_type_price_snapshot,
)


def test_price_data_melt():
    df = pd.DataFrame(
        [["A", "E1", 10, 20]],
        columns=["LA Name", "LA Code", "1995", "1996"],
    )
    tidy = transform_price_or_count_totals(df, "1. Price Data", table_kind="median_price")
    assert len(tidy) == 2
    assert set(tidy["year"].astype(int).tolist()) == {1995, 1996}


def test_type_price_snapshot():
    df = pd.DataFrame(
        [["E1", "LA1", 100, 200]],
        columns=["LA Code", "LA Name", "DET", "SEM"],
    )
    tidy = transform_type_price_snapshot(df, "4.Type Price Data")
    assert len(tidy) == 2
    assert set(tidy["property_type"]) == {"DET", "SEM"}
