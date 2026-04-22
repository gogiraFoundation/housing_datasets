"""Tests for ONS vacant dwellings and second homes (Census 2021) ETL."""

from __future__ import annotations

import pandas as pd

from ons_vacant_second_homes_etl import infer_geography_level, transform_sheet, transform_sheet_1abc


def test_infer_geography_level():
    assert infer_geography_level("K04000001") == "england_and_wales"
    assert infer_geography_level("E92000001") == "country"
    assert infer_geography_level("W92000004") == "country"
    assert infer_geography_level("E12000001") == "region"
    assert infer_geography_level("E06000001") == "local_authority_district"
    assert infer_geography_level("W06000001") == "local_authority_district"
    assert infer_geography_level("E02000001") == "msoa"
    assert infer_geography_level("E01000001") == "lsoa"


def test_transform_1a_headline():
    df = pd.DataFrame(
        [
            ["K04000001", "England and Wales", 100, 20],
        ],
        columns=["area_code", "area_name", "Vacant dwellings", "Second homes (with no usual residents)"],
    )
    tidy = transform_sheet_1abc(df, "1a")
    assert len(tidy) == 2
    assert set(tidy["dwelling_group"]) == {"vacant", "second_home"}
    assert tidy.loc[tidy["dwelling_group"] == "vacant", "value"].iloc[0] == 100
    assert tidy["geography_level"].iloc[0] == "england_and_wales"


def test_transform_1a_suppressed_counts():
    df = pd.DataFrame(
        [
            ["E02000002", "X", 80, "c"],
        ],
        columns=["area_code", "area_name", "Vacant dwellings", "Second homes (with no usual residents)"],
    )
    tidy = transform_sheet_1abc(df, "1b")
    second = tidy.loc[tidy["dwelling_group"] == "second_home", "value"].iloc[0]
    assert pd.isna(second)


def test_transform_sheet2_accommodation():
    df = pd.DataFrame(
        [
            ["E92000001", "England", 10, 20, 30, 40, 5],
        ],
        columns=[
            "Area Code",
            "Area Name",
            "Detached whole house or bungalow",
            "Semi-detached whole house or bungalow",
            "Terraced (including end-terrace) whole house or bungalow",
            "Flat, maisonette or apartment",
            "A caravan or other mobile or temporary structure",
        ],
    )
    df = df.rename(columns={"Area Code": "area_code", "Area Name": "area_name"})
    tidy = transform_sheet(df, "2")
    assert len(tidy) == 5
    assert tidy["dwelling_group"].eq("vacant").all()
    assert tidy["breakdown_type"].eq("accommodation_type").all()
    assert "detached_whole_house_or_bungalow" in set(tidy["breakdown_label"])
