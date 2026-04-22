"""Tests for extended price/earnings LA snapshot helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from housing_data.geo_ids import norm_lad
from housing_data.price_earnings_snapshot import (
    price_earnings_newbuild_workplace_la_median_snapshot,
    price_earnings_residence_la_median_snapshot,
)


def _minimal_pe_family(tmp: Path, stem: str, edition: str = "tfam") -> None:
    common = dict(
        geography_level="local_authority",
        country_region_code="E92000001",
        country_region_name="England",
        local_authority_code="E06000001",
        local_authority_name="Hartlepool",
    )
    sheets = [
        ("5a", "house_price", "median", "Year ending Sep 2025", 210000.0),
        ("5b", "earnings", "median", "2025", 41000.0),
        ("5c", "ratio", "median", "2025", 5.12),
    ]
    for sid, comp, pct, pl, val in sheets:
        df = pd.DataFrame(
            [
                {
                    "table_id": sid,
                    "geography_level": common["geography_level"],
                    "percentile": pct,
                    "component": comp,
                    "country_region_code": common["country_region_code"],
                    "country_region_name": common["country_region_name"],
                    "local_authority_code": common["local_authority_code"],
                    "local_authority_name": common["local_authority_name"],
                    "period_label": pl,
                    "value": val,
                }
            ]
        )
        df.to_parquet(tmp / f"{stem}_{edition}_{sid}_tidy.parquet", index=False)


def test_residence_la_snapshot(tmp_path: Path) -> None:
    _minimal_pe_family(tmp_path, "ons_price_residence_earnings_ratio", edition="tres")
    pe, meta = price_earnings_residence_la_median_snapshot(tmp_path, "tres")
    assert not meta.get("skipped")
    row = pe[pe["lad_code"] == norm_lad("E06000001")].iloc[0]
    assert row["pe_res_median_price_gbp"] == 210000.0
    assert row["pe_res_affordability_ratio"] == 5.12


def test_newbuild_la_snapshot(tmp_path: Path) -> None:
    _minimal_pe_family(tmp_path, "ons_price_newbuild_workplace_earnings_ratio", edition="tnb")
    pe, meta = price_earnings_newbuild_workplace_la_median_snapshot(tmp_path, "tnb")
    assert not meta.get("skipped")
    row = pe[pe["lad_code"] == norm_lad("E06000001")].iloc[0]
    assert row["pe_newbuild_median_price_gbp"] == 210000.0
