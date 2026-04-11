"""Tests for median energy efficiency score ETL."""

from __future__ import annotations

import pandas as pd

from ons_median_eescore_etl import melt_median_sheet


def test_melt_1a():
    cols = ["Country or region code", "Country or region name", "All dwellings"]
    body = pd.DataFrame([["E92000001", "England", 69.0]], columns=cols)
    tidy = melt_median_sheet(body, "1a")
    assert len(tidy) == 1
    assert tidy["median_score"].iloc[0] == 69.0
    assert tidy["measure_label"].iloc[0] == "All dwellings"


def test_melt_2a():
    cols = [
        "Region code",
        "Region name",
        "Local authority district code",
        "Local authority district name",
        "All Dwellings",
    ]
    body = pd.DataFrame([["E12000001", "North East", "E06000001", "Hartlepool", 65.0]], columns=cols)
    tidy = melt_median_sheet(body, "2a")
    assert len(tidy) == 1
    assert tidy["local_authority_district_code"].iloc[0] == "E06000001"
    assert tidy["median_score"].iloc[0] == 65.0
