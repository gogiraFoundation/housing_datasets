from __future__ import annotations

import math
from datetime import date, timezone

import pandas as pd

from housing_api.data_access import dataframe_to_json_records


def test_dataframe_to_json_records_null_and_nan() -> None:
    df = pd.DataFrame({"a": [1.0, float("nan")], "b": ["x", None]})
    rows = dataframe_to_json_records(df)
    assert rows[0]["a"] == 1.0
    assert rows[1]["a"] is None
    assert rows[1]["b"] is None


def test_dataframe_to_json_records_datetime() -> None:
    ts = pd.Timestamp("2024-01-15 12:30:00", tz=timezone.utc)
    df = pd.DataFrame({"t": [ts]})
    rows = dataframe_to_json_records(df)
    assert "2024-01-15" in rows[0]["t"]


def test_dataframe_to_json_records_date() -> None:
    df = pd.DataFrame({"d": [date(2023, 6, 1)]})
    rows = dataframe_to_json_records(df)
    assert rows[0]["d"] == "2023-06-01"


def test_dataframe_to_json_records_json_serializable() -> None:
    import json

    df = pd.DataFrame({"x": [1, 2], "y": [math.nan, 3.0]})
    rows = dataframe_to_json_records(df)
    json.dumps(rows)
