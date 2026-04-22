"""Tests for housing_data.la_map_context."""

from __future__ import annotations

import pandas as pd

from housing_data.la_map_context import merge_lane_a_snapshot_columns, snapshot_tooltip_strings


def test_merge_lane_a_snapshot_excludes_duplicate_val_col() -> None:
    display = pd.DataFrame(
        {
            "lad_code": ["E01"],
            "la_name": ["Test"],
            "region": ["R"],
            "value": [5.0],
        }
    )
    snap = pd.DataFrame(
        {
            "lad_code": ["E01"],
            "pe_affordability_ratio": [4.0],
            "supply_starts": [10.0],
        }
    )
    out = merge_lane_a_snapshot_columns(display, snap, exclude_duplicate_of="pe_affordability_ratio")
    assert "supply_starts" in out.columns
    assert "pe_affordability_ratio" not in out.columns


def test_snapshot_tooltip_strings_formats() -> None:
    row = pd.Series(
        {
            "median_price_existing_gbp": 200_000.0,
            "median_price_period_label": "Year ending Sep 2025",
            "median_price_new_gbp": 300_000.0,
            "median_price_new_period_label": "Year ending Sep 2025",
            "supply_financial_year": "2024-2025",
            "supply_starts": 100.0,
            "supply_completions": 80.0,
            "pe_affordability_ratio": 8.5,
            "vacant_dwellings_count": 12,
            "second_home_dwellings_count": 3,
            "mf2a_mains_gas": 62.5,
        }
    )
    tw = snapshot_tooltip_strings(row, mains_gas_col="mf2a_mains_gas")
    assert "£200,000" in tw["snap_prices"]
    assert "2024-2025" in tw["snap_supply"]
    assert "mains gas" in tw["snap_fuel"].lower()
    assert "8.50" in tw["snap_more"]
