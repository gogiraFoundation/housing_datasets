"""Unit tests for ``housing_analytics.insights_briefing``."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from housing_analytics.insights_briefing import (
    PRESET_LONDON_COMMUTER,
    PRESET_NATIONAL,
    admin_year_from_period,
    build_insights_payload,
    common_pe_years,
    entry_pressure_count,
    hb_region_supply_change_between,
    horizon_year_bounds_from_common_years,
    insights_inputs_snapshot,
    la_pe_horizon_table,
    preset_region_filter,
)


def test_admin_year_from_period() -> None:
    assert admin_year_from_period("Year ending Dec 2020") == 2020
    assert admin_year_from_period("nope") is None


def test_horizon_year_bounds_from_common_years() -> None:
    assert horizon_year_bounds_from_common_years(range(2018, 2025), 5) == (2020, 2024)
    assert horizon_year_bounds_from_common_years([2022], 5) == (2022, 2022)


def test_preset_region_filter() -> None:
    assert preset_region_filter(PRESET_NATIONAL, ()) is None
    f = preset_region_filter(PRESET_LONDON_COMMUTER, ())
    assert f is not None and "London" in f
    assert preset_region_filter("custom", ("London",)) == frozenset({"London"})


def _synthetic_pe_la(
    *,
    lad: str,
    la_name: str,
    region: str,
    y0: int,
    y1: int,
    v5a_y0: float,
    v5a_y1: float,
    v5b_y0: float,
    v5b_y1: float,
    v5c_y0: float,
    v5c_y1: float,
    v6a_y0: float,
    v6a_y1: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = dict(
        table_id="x",
        geography_level="local_authority",
        percentile="median",
        local_authority_code=lad,
        local_authority_name=la_name,
        country_region_code="E12000001",
        country_region_name=region,
    )

    def sheet(component: str, pairs: list[tuple[int, float]]) -> pd.DataFrame:
        rows = []
        for y, val in pairs:
            rows.append(
                {
                    **base,
                    "component": component,
                    "period_label": str(y),
                    "value": val,
                }
            )
        return pd.DataFrame(rows)

    d5a = sheet(
        "house_price",
        [(y0, v5a_y0), (y1, v5a_y1)],
    )
    d5b = sheet("earnings", [(y0, v5b_y0), (y1, v5b_y1)])
    d5c = sheet("ratio", [(y0, v5c_y0), (y1, v5c_y1)])
    d6 = sheet("house_price", [(y0, v6a_y0), (y1, v6a_y1)])
    for d in (d5a, d5b, d5c, d6):
        d["pe_year"] = d["period_label"].astype(int)
        d["lad_code"] = d["local_authority_code"].str.strip().str.upper()
        d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d5a, d5b, d5c, d6


def test_common_pe_years_and_la_pe_horizon_table() -> None:
    d5a, d5b, d5c, _ = _synthetic_pe_la(
        lad="E06000001",
        la_name="Alpha",
        region="North East",
        y0=2020,
        y1=2024,
        v5a_y0=100_000,
        v5a_y1=120_000,
        v5b_y0=30_000,
        v5b_y1=32_000,
        v5c_y0=3.0,
        v5c_y1=3.5,
        v6a_y0=80_000,
        v6a_y1=115_000,
    )
    assert common_pe_years(d5a, d5b, d5c) == {2020, 2024}
    out = la_pe_horizon_table(d5a, d5b, d5c, 2020, 2024, None)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["delta_median_price"] == pytest.approx(20_000)
    assert row["delta_earnings"] == pytest.approx(2000)
    assert row["delta_ratio"] == pytest.approx(0.5)


def test_entry_pressure_count() -> None:
    """LA1: LQ grows more than median -> counts. LA2: opposite -> does not count."""
    d5a1, d5b1, d5c1, d6a1 = _synthetic_pe_la(
        lad="E1",
        la_name="High LQ pressure",
        region="London",
        y0=2020,
        y1=2024,
        v5a_y0=400_000,
        v5a_y1=410_000,
        v5b_y0=40_000,
        v5b_y1=41_000,
        v5c_y0=10,
        v5c_y1=10,
        v6a_y0=200_000,
        v6a_y1=280_000,
    )
    d5a2, d5b2, d5c2, d6a2 = _synthetic_pe_la(
        lad="E2",
        la_name="Calm",
        region="London",
        y0=2020,
        y1=2024,
        v5a_y0=200_000,
        v5a_y1=250_000,
        v5b_y0=35_000,
        v5b_y1=36_000,
        v5c_y0=5,
        v5c_y1=6,
        v6a_y0=150_000,
        v6a_y1=160_000,
    )
    d5a = pd.concat([d5a1, d5a2], ignore_index=True)
    d5b = pd.concat([d5b1, d5b2], ignore_index=True)
    d5c = pd.concat([d5c1, d5c2], ignore_index=True)
    d6a = pd.concat([d6a1, d6a2], ignore_index=True)
    assert entry_pressure_count(d5a, d6a, 2020, 2024) == 1


def test_la_pe_horizon_table_respects_preset() -> None:
    d5a, d5b, d5c, _ = _synthetic_pe_la(
        lad="E1",
        la_name="Lon",
        region="London",
        y0=2020,
        y1=2024,
        v5a_y0=1,
        v5a_y1=2,
        v5b_y0=1,
        v5b_y1=2,
        v5c_y0=1,
        v5c_y1=2,
        v6a_y0=1,
        v6a_y1=2,
    )
    d5a_n, d5b_n, d5c_n, _ = _synthetic_pe_la(
        lad="E2",
        la_name="NE",
        region="North East",
        y0=2020,
        y1=2024,
        v5a_y0=1,
        v5a_y1=2,
        v5b_y0=1,
        v5b_y1=2,
        v5c_y0=1,
        v5c_y1=2,
        v6a_y0=1,
        v6a_y1=2,
    )
    d5a = pd.concat([d5a, d5a_n], ignore_index=True)
    d5b = pd.concat([d5b, d5b_n], ignore_index=True)
    d5c = pd.concat([d5c, d5c_n], ignore_index=True)
    allow = preset_region_filter(PRESET_LONDON_COMMUTER, ())
    assert allow is not None
    out = la_pe_horizon_table(d5a, d5b, d5c, 2020, 2024, allow)
    assert set(out["region"]) == {"London"}


def test_hb_region_supply_change_between() -> None:
    rows: list[dict] = []
    for fy, reg, d in (
        ("2020-2021", "North East", 100.0),
        ("2020-2021", "London", 200.0),
        ("2024-2025", "North East", 110.0),
        ("2024-2025", "London", 250.0),
    ):
        rows.append(
            {"financial_year": fy, "Region or Country Name": reg, "measure": "starts", "dwellings": d}
        )
    hb = pd.DataFrame(rows)
    reg, delta, f0, f1 = hb_region_supply_change_between(
        hb, "2020-2021", "2024-2025", measure="starts", region_allow=None
    )
    assert reg == "London"
    assert delta == pytest.approx(50.0)
    assert f0 == "2020-2021" and f1 == "2024-2025"


def test_build_insights_payload_empty_dir_no_raise(tmp_path: Path) -> None:
    out = build_insights_payload(
        tmp_path,
        pe_ed="missing",
        hb_la_ed="missing",
        hb_country_ed="missing",
        hpi_ed="missing",
        median_ed="missing",
        epc_ed="missing",
        ee_ed="missing",
        census_stem="census2021_la_population_2021",
        preset=PRESET_NATIONAL,
        custom_regions=(),
        horizon_years=5,
    )
    assert set(out["missing"].keys()) == {"affordability", "entry", "regions", "supply", "energy"}
    assert set(out["findings_by_tab"].keys()) == {"affordability", "entry", "regions", "supply", "energy"}
    assert out["tables"]["affordability"].empty
    snap = insights_inputs_snapshot(
        tmp_path,
        pe_ed="x",
        hb_la_ed="x",
        hb_country_ed="x",
        hpi_ed="x",
        median_ed="x",
        epc_ed="x",
        ee_ed="x",
        census_stem="census2021_la_population_2021",
    )
    assert "missing" in snap
