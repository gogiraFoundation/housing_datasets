"""Offline CSV fixture for Census TS008-style columns (pins expected shape)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ons_census2021_etl import normalize_census_csv


def test_normalize_census_fixture_file() -> None:
    p = Path(__file__).resolve().parent / "fixtures" / "census_ts008_sample.csv"
    df = pd.read_csv(p)
    out = normalize_census_csv(df)
    assert len(out) == 2
    assert out["lad_code"].iloc[0] == "E06000001"
