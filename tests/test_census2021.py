"""Tests for Census 2021 CMD CSV normalization and LA population derivation (offline)."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from ons_census2021_config import CENSUS_DATASETS, POPULATION_DERIVED_STEM
from ons_census2021_etl import normalize_census_csv, write_la_population_2021


def test_normalize_census_csv_ts008_style() -> None:
    raw = """Lower tier local authorities Code,Lower tier local authorities,Sex (2 categories) Code,Sex (2 categories),Observation
E06000001,Hartlepool,1,Female,47653
E06000001,Hartlepool,2,Male,44685
"""
    df = pd.read_csv(io.StringIO(raw))
    out = normalize_census_csv(df)
    assert list(out.columns[:2]) == ["lad_code", "lad_name"]
    assert "sex_2_categories_code" in out.columns
    assert out["observation"].iloc[0] == 47653
    assert out["lad_code"].iloc[0] == "E06000001"


def test_normalize_census_csv_three_columns() -> None:
    raw = """Lower Tier Local Authorities Code,Lower Tier Local Authorities,Observation
E06000001,Hartlepool,40930
"""
    df = pd.read_csv(io.StringIO(raw))
    out = normalize_census_csv(df)
    assert set(out.columns) >= {"lad_code", "lad_name", "observation"}
    assert out["observation"].iloc[0] == 40930


def test_normalize_rejects_non_observation_last_col() -> None:
    raw = """A,B,C
1,2,3
"""
    df = pd.read_csv(io.StringIO(raw))
    with pytest.raises(ValueError, match="Observation"):
        normalize_census_csv(df)


def test_population_from_sex_tidy() -> None:
    raw = """Lower tier local authorities Code,Lower tier local authorities,Sex (2 categories) Code,Sex (2 categories),Observation
E06000001,Hartlepool,1,Female,10
E06000001,Hartlepool,2,Male,20
E06000002,X,1,Female,5
E06000002,X,2,Male,5
"""
    df = pd.read_csv(io.StringIO(raw))
    tidy = normalize_census_csv(df)
    tidy["dataset_id"] = "TS008"
    tidy["census_year"] = 2021
    tmp = Path(tempfile.mkdtemp())
    pop = write_la_population_2021(tidy, tmp, write_parquet=False, verbose=False)
    assert len(pop) == 2
    row = pop.set_index("lad_code").loc["E06000001"]
    assert int(row["population"]) == 30
    assert int(row["year"]) == 2021


def test_census_config_keys() -> None:
    assert "sex_ts008" in CENSUS_DATASETS
    assert CENSUS_DATASETS["sex_ts008"].dataset_id == "TS008"
    assert POPULATION_DERIVED_STEM == "census2021_la_population_2021"
