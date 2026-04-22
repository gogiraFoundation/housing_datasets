"""Tests for ONS Index of Private Housing Rental Prices CSV tidy transform."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from ons_private_rental_index_etl import transform_csv


def _minimal_csv_text() -> str:
    return (
        "v4_1,Data Marking,mmm-yy,Time,administrative-geography,Geography,"
        "index-and-year-change,IndexAndYearChange\n"
        "105.8,,Jul-17,Jul-17,E92000001,England,index,Index\n"
        "1.3,,Jul-17,Jul-17,W92000004,Wales,year-on-year-change,Year-on-year change\n"
        "[x],,Jul-17,Jul-17,K03000001,Great Britain,index,Index\n"
    )


def test_transform_csv_shape_and_columns():
    df = pd.read_csv(io.StringIO(_minimal_csv_text()))
    tidy = transform_csv(df)
    assert len(tidy) == 3
    assert list(tidy.columns) == [
        "geography_code",
        "geography_name",
        "variable",
        "variable_label",
        "time_period",
        "month_label",
        "value",
        "data_marking",
    ]
    assert tidy["geography_name"].tolist() == ["England", "Wales", "Great Britain"]
    assert tidy["variable"].tolist() == ["index", "year-on-year-change", "index"]


def test_transform_csv_coerces_numeric_and_bracket_x():
    df = pd.read_csv(io.StringIO(_minimal_csv_text()))
    tidy = transform_csv(df)
    assert pd.isna(tidy["value"].iloc[2])
    assert tidy["value"].iloc[0] == 105.8
    assert tidy["value"].iloc[1] == 1.3


def test_transform_csv_unknown_columns_raises():
    bad = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(ValueError, match="Unexpected CSV columns"):
        transform_csv(bad)
