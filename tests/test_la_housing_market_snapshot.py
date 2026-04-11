"""Tests for joins/build_la_housing_market_snapshot.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


def _minimal_hb(tmp: Path) -> None:
    df = pd.DataFrame(
        {
            "Region Type": ["a", "a"],
            "Region or Country Name": ["NE", "NE"],
            "Local Authority Code": ["E06000001", "E06000001"],
            "Local Authority Name": ["Hartlepool", "Hartlepool"],
            "financial_year": ["2023-2024", "2023-2024"],
            "measure": ["starts", "completions"],
            "dwellings": [10.0, 8.0],
        }
    )
    df.to_parquet(tmp / "ons_housebuilding_la_testhb_tidy.parquet", index=False)


def _minimal_mf2a2b(tmp: Path) -> None:
    rows = []
    for sheet, dc in [("2a", None), ("2b", "Existing")]:
        for fuel, val in [("Mains gas", 80.0), ("Electricity", 10.0)]:
            row = {
                "table_id": sheet,
                "region_code": "E12000001",
                "region_name": "North East",
                "local_authority_district_code": "E06000001",
                "local_authority_district_name": "Hartlepool",
                "fuel_or_method": fuel,
                "value": val,
            }
            if dc:
                row["dwelling_class"] = dc
            rows.append(row)
    mf = pd.DataFrame(rows)
    mf2a = mf[mf["table_id"] == "2a"].drop(columns=["dwelling_class"], errors="ignore")
    mf2b = mf[mf["table_id"] == "2b"]
    mf2a.to_parquet(tmp / "ons_mainfuel_testmf_2a_tidy.parquet", index=False)
    mf2b.to_parquet(tmp / "ons_mainfuel_testmf_2b_tidy.parquet", index=False)


def _minimal_median_2a(tmp: Path) -> None:
    df = pd.DataFrame(
        {
            "table_id": ["2a", "2a"],
            "dwelling_class": ["existing", "existing"],
            "geography_level": ["local_authority", "local_authority"],
            "property_band": ["all", "all"],
            "region_country_code": ["E12000001", "E12000001"],
            "region_country_name": ["NE", "NE"],
            "local_authority_code": ["E06000001", "E06000001"],
            "local_authority_name": ["Hartlepool", "Hartlepool"],
            "period_label": ["Year ending Sep 2024", "Year ending Sep 2025"],
            "median_price_gbp": [100000.0, 110000.0],
        }
    )
    df.to_parquet(tmp / "ons_median_price_existing_admin_testmed_2a_tidy.parquet", index=False)


def _minimal_pe_5abc(tmp: Path, edition: str = "testpe") -> None:
    """Minimal LA rows for 5a/5b/5c sharing calendar year 2025."""
    common = dict(
        geography_level="local_authority",
        country_region_code="E92000001",
        country_region_name="England",
        local_authority_code="E06000001",
        local_authority_name="Hartlepool",
    )
    sheets = [
        ("5a", "house_price", "median", "Year ending Sep 2025", 200000.0),
        ("5b", "earnings", "median", "2025", 40000.0),
        ("5c", "ratio", "median", "2025", 5.0),
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
        df.to_parquet(tmp / f"ons_price_earnings_ratio_{edition}_{sid}_tidy.parquet", index=False)


def _minimal_census_pop(tmp: Path) -> None:
    df = pd.DataFrame(
        {
            "lad_code": ["E06000001"],
            "lad_name": ["Hartlepool"],
            "population": [92000],
            "year": [2021],
        }
    )
    df.to_parquet(tmp / "census2021_la_population_2021.parquet", index=False)


def _minimal_epc_ee(tmp: Path) -> None:
    epc = pd.DataFrame(
        {
            "table_id": ["1a"] * 6,
            "country_or_region_code": ["E12000001"] * 6,
            "country_or_region_name": ["North East"] * 6,
            "epc_band": ["A", "B", "C", "D", "E", "F"],
            "percentage": [1.0, 2.0, 38.0, 30.0, 20.0, 9.0],
        }
    )
    epc.to_parquet(tmp / "ons_epc_bands_testepc_1a_tidy.parquet", index=False)
    ee = pd.DataFrame(
        {
            "table_id": ["1c"] * 2,
            "country_or_region_name": ["North East", "North East"],
            "country_or_region_code": ["E12000001", "E12000001"],
            "measure_breakdown": ["All", "All"],
            "rolling_period": ["Q2 2008 to Q1 2013", "Q2 2019 to Q1 2024"],
            "value": [40.0, 59.0],
        }
    )
    ee.to_parquet(tmp / "ons_ee_fiveyear_testee_1c_tidy.parquet", index=False)


def test_build_lane_a_smoke(tmp_path: Path) -> None:
    sys_path_insert = _REPO
    import sys

    if str(sys_path_insert) not in sys.path:
        sys.path.insert(0, str(sys_path_insert))

    from joins.build_la_housing_market_snapshot import build_lane_a

    _minimal_hb(tmp_path)
    _minimal_mf2a2b(tmp_path)
    _minimal_median_2a(tmp_path)

    la, meta = build_lane_a(
        tmp_path,
        housebuilding_edition="testhb",
        mainfuel_edition="testmf",
        median_existing_edition="testmed",
        uk_hpi_edition=None,
        ref_csv=None,
    )
    assert "lad_code" in la.columns
    assert "E06000001" in set(la["lad_code"].astype(str))
    assert meta["supply_financial_year"] == "2023-2024"
    assert meta["median_price_period_label"] == "Year ending Sep 2025"
    assert la["median_price_existing_gbp"].iloc[0] == 110000.0


def test_region_population_by_region_sums(tmp_path: Path) -> None:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    from joins.build_la_housing_market_snapshot import region_population_by_region

    _minimal_census_pop(tmp_path)
    _minimal_mf2a2b(tmp_path)
    df, meta = region_population_by_region(tmp_path, mainfuel_edition="testmf")
    assert not meta.get("skipped")
    assert len(df) == 1
    assert df["region_population_census2021"].iloc[0] == 92000
    assert int(df["region_population_year"].iloc[0]) == 2021


def test_build_lane_a_price_earnings_merge(tmp_path: Path) -> None:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    from joins.build_la_housing_market_snapshot import build_lane_a

    _minimal_hb(tmp_path)
    _minimal_mf2a2b(tmp_path)
    _minimal_median_2a(tmp_path)
    _minimal_pe_5abc(tmp_path, edition="testpe")

    la, meta = build_lane_a(
        tmp_path,
        housebuilding_edition="testhb",
        mainfuel_edition="testmf",
        median_existing_edition="testmed",
        uk_hpi_edition=None,
        ref_csv=None,
        price_earnings_edition="testpe",
    )
    row = la[la["lad_code"] == "E06000001"].iloc[0]
    assert row["pe_median_price_gbp"] == 200000.0
    assert row["pe_workplace_earnings_gbp"] == 40000.0
    assert row["pe_affordability_ratio"] == 5.0
    assert int(row["pe_snapshot_year"]) == 2025
    assert meta["price_earnings"]["pe_snapshot_year"] == 2025


def test_build_lane_b_smoke(tmp_path: Path) -> None:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))

    from joins.build_la_housing_market_snapshot import build_lane_b

    _minimal_hb(tmp_path)
    _minimal_mf2a2b(tmp_path)
    _minimal_epc_ee(tmp_path)
    _minimal_census_pop(tmp_path)

    reg, meta = build_lane_b(
        tmp_path,
        housebuilding_edition="testhb",
        mainfuel_edition="testmf",
        epc_edition="testepc",
        ee_edition="testee",
    )
    assert "region_supply_starts" in reg.columns
    ne = reg[reg["region_code"] == "E12000001"]
    assert not ne.empty
    assert ne["epc_pct_bands_abc"].iloc[0] == pytest.approx(41.0)
    assert meta["ee_rolling_period"] is not None
    assert ne["region_population_census2021"].iloc[0] == 92000
