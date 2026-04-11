"""Tests for country house-building filters (API helpers)."""

from __future__ import annotations

import pandas as pd

from housing_data.housebuilding_country import filter_housebuilding_country, prepare_housebuilding_country_df


def test_filter_country_period_and_measure() -> None:
    df = pd.DataFrame(
        {
            "table_id": ["t1", "t1", "t1"],
            "country_name": ["England", "England", "Wales"],
            "frequency": ["annual_financial_year"] * 3,
            "period": ["2009-2010", "2010-2011", "2009-2010"],
            "measure": ["starts", "starts", "starts"],
            "sector": ["All Dwellings"] * 3,
            "dwellings": [100, 200, 50],
        }
    )
    df = prepare_housebuilding_country_df(df)
    view, span = filter_housebuilding_country(
        df,
        period_min="2009-2010",
        period_max="2009-2010",
        measures=["starts"],
        country_names=["England"],
    )
    assert len(view) == 1
    assert view.iloc[0]["country_name"] == "England"
    assert span == ["2009-2010"]
