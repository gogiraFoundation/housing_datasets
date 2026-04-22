"""Build Lane A (LA-wide) and Lane B (region-wide) housing market snapshot Parquet files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any
import pandas as pd

from housing_data.atomic_io import write_parquet_atomic

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_data.median_price_la import latest_median_price_existing_la, latest_median_price_new_la
from housing_data.price_earnings_snapshot import (
    price_earnings_la_median_snapshot,
    price_earnings_newbuild_workplace_la_median_snapshot,
    price_earnings_residence_la_median_snapshot,
)


def _load_aggregate_module():
    path = _REPO / "joins" / "aggregate_la_supply_to_region.py"
    spec = importlib.util.spec_from_file_location("aggregate_la_supply_to_region", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_agg_mod = _load_aggregate_module()
aggregate = _agg_mod.aggregate
lookup_from_mainfuel_2a = _agg_mod.lookup_from_mainfuel_2a
_DEFAULT_PROCESSED = _REPO / "data" / "processed"
_DEFAULT_REF = _REPO / "data" / "reference"


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def _vacant_second_homes_la_wide(
    processed_dir: Path, edition: str
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Headline vacant + second-home counts per LAD from ONS Census 2021 table 1a (LAD rows only)."""
    processed_dir = Path(processed_dir)
    path = processed_dir / f"ons_vacant_second_homes_{edition}_1a_tidy.parquet"
    if not path.is_file():
        return pd.DataFrame(), {
            "skipped": True,
            "reason": "missing_parquet",
            "path": path.name,
        }
    df = pd.read_parquet(path)
    sub = df[df["geography_level"].astype(str) == "local_authority_district"].copy()
    if sub.empty:
        return pd.DataFrame(), {
            "skipped": True,
            "reason": "no_lad_rows",
            "edition": edition,
        }
    sub["lad_code"] = sub["area_code"].map(_norm_lad)
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    wide = sub.pivot_table(
        index="lad_code",
        columns="dwelling_group",
        values="value",
        aggfunc="first",
    )
    wide = wide.rename(
        columns={
            "vacant": "vacant_dwellings_count",
            "second_home": "second_home_dwellings_count",
        }
    )
    out = wide.reset_index()
    for col in ("vacant_dwellings_count", "second_home_dwellings_count"):
        if col not in out.columns:
            out[col] = pd.NA
    meta = {
        "skipped": False,
        "edition": edition,
        "source_table": "1a",
        "caveat": (
            "ONS Census 2021 headline counts (table 1a), local authority district geography — "
            "not a rate; no denominator joined here."
        ),
    }
    return out[["lad_code", "vacant_dwellings_count", "second_home_dwellings_count"]], meta


def _safe_col(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(s).strip()).strip("_").lower()


def _load_lookup(processed_dir: Path, mainfuel_edition: str, ref_csv: Path | None) -> pd.DataFrame:
    if ref_csv is not None and ref_csv.is_file():
        lu = pd.read_csv(ref_csv)
        lu["lad_code"] = lu["lad_code"].map(_norm_lad)
        return lu
    mf2a_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2a_tidy.parquet"
    if not mf2a_path.is_file():
        raise FileNotFoundError(f"Missing main fuel 2a and no LAD lookup CSV: {mf2a_path}")
    mf2a = pd.read_parquet(mf2a_path)
    return lookup_from_mainfuel_2a(mf2a)


def _latest_financial_year(hb: pd.DataFrame) -> str | None:
    from ons_housebuilding_country_periods import preferred_period_order

    years = preferred_period_order(hb["financial_year"])
    return years[-1] if years else None


def _hb_latest_snapshot(hb: pd.DataFrame, latest_fy: str) -> pd.DataFrame:
    sub = hb[hb["financial_year"].astype(str) == latest_fy].copy()
    sub["lad_code"] = sub["Local Authority Code"].map(_norm_lad)
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    agg = (
        sub.groupby(["lad_code", "measure"], observed=True, dropna=False)["dwellings"]
        .sum(min_count=1)
        .reset_index()
    )
    wide = agg.pivot(index="lad_code", columns="measure", values="dwellings")
    wide = wide.rename(columns={c: f"supply_{_safe_col(c)}" for c in wide.columns})
    wide = wide.reset_index()
    wide["supply_financial_year"] = latest_fy
    return wide


def _median_la_latest(
    med: pd.DataFrame,
    *,
    median_edition: str,
) -> tuple[pd.DataFrame, str | None]:
    """Latest rolling-period row per LA from `2a` (all property types)."""
    df, pl = latest_median_price_existing_la(med)
    if df.empty:
        return pd.DataFrame(), None
    out = df.rename(
        columns={
            "la_name": "median_la_name",
            "value": "median_price_existing_gbp",
            "period_label": "median_price_period_label",
        }
    )
    out["median_price_admin_edition"] = median_edition
    return out, pl


def _pivot_mf(mf: pd.DataFrame, prefix: str) -> pd.DataFrame:
    mf = mf.copy()
    mf["lad_code"] = mf["local_authority_district_code"].map(_norm_lad)
    mf["value"] = pd.to_numeric(mf["value"], errors="coerce")
    if "dwelling_class" in mf.columns:
        mf["fuel_key"] = (
            mf["dwelling_class"].astype(str).fillna("") + "_|_" + mf["fuel_or_method"].astype(str)
        )
    else:
        mf["fuel_key"] = mf["fuel_or_method"].astype(str)
    pv = mf.pivot_table(index="lad_code", columns="fuel_key", values="value", aggfunc="first")
    pv = pv.rename(columns={c: f"{prefix}_{_safe_col(c)}" for c in pv.columns})
    return pv.reset_index()


def _hpi_england_wide(hpi: pd.DataFrame) -> pd.DataFrame:
    hpi = hpi.copy()
    hpi["lad_code"] = hpi["area_code"].map(_norm_lad)
    pv = hpi.pivot_table(index="lad_code", columns="metric", values="value", aggfunc="first")
    pv = pv.rename(
        columns={
            "Average Price (£)": "hpi_avg_price_gbp",
            "Annual percentage change": "hpi_annual_pct_change",
        }
    )
    return pv.reset_index()


def _canonical_geo(name: object) -> str:
    s = str(name).strip()
    mapping = {
        "East": "East of England",
        "Northern Ireland [note 3]": "Northern Ireland",
    }
    return mapping.get(s, s)


def _region_hpi_prpi_growth(processed_dir: Path, *, hpi_edition: str, prpi_edition: str) -> pd.DataFrame:
    hpi_path = processed_dir / f"ons_uk_hpi_monthly_{hpi_edition}_1_tidy.parquet"
    prpi_path = processed_dir / f"ons_private_rental_index_{prpi_edition}_tidy.parquet"
    if not hpi_path.is_file() or not prpi_path.is_file():
        return pd.DataFrame(
            columns=[
                "region_name",
                "hpi_growth_overlap_pct",
                "prpi_growth_overlap_pct",
                "hpi_minus_prpi_growth_pp",
            ]
        )

    hpi = pd.read_parquet(hpi_path).copy()
    hpi["period"] = pd.to_datetime(hpi["time_period"].astype(str), format="%b %Y", errors="coerce")
    hpi["value"] = pd.to_numeric(hpi["value"], errors="coerce")
    hpi["region_name"] = hpi["geography"].map(_canonical_geo)
    hpi = hpi.dropna(subset=["period", "value", "region_name"])[["region_name", "period", "value"]]
    hpi = hpi.rename(columns={"value": "hpi_index"})

    prpi = pd.read_parquet(prpi_path)
    prpi = prpi[prpi["variable"].astype(str) == "index"].copy()
    prpi["period"] = pd.to_datetime(prpi["month_label"].astype(str), format="%b-%y", errors="coerce")
    prpi["value"] = pd.to_numeric(prpi["value"], errors="coerce")
    prpi["region_name"] = prpi["geography_name"].map(_canonical_geo)
    prpi = prpi.dropna(subset=["period", "value", "region_name"])[["region_name", "period", "value"]]
    prpi = prpi.rename(columns={"value": "prpi_index"})

    joined = hpi.merge(prpi, on=["region_name", "period"], how="inner")
    rows: list[dict[str, Any]] = []
    for geo, sub in joined.groupby("region_name", observed=True):
        sub = sub.sort_values("period")
        if len(sub) < 2:
            continue
        first = sub.iloc[0]
        last = sub.iloc[-1]
        if float(first["hpi_index"]) == 0 or float(first["prpi_index"]) == 0:
            continue
        hpi_growth = (float(last["hpi_index"]) / float(first["hpi_index"]) - 1.0) * 100.0
        prpi_growth = (float(last["prpi_index"]) / float(first["prpi_index"]) - 1.0) * 100.0
        rows.append(
            {
                "region_name": geo,
                "hpi_growth_overlap_pct": hpi_growth,
                "prpi_growth_overlap_pct": prpi_growth,
                "hpi_minus_prpi_growth_pp": hpi_growth - prpi_growth,
            }
        )
    return pd.DataFrame(rows)


def region_population_by_region(
    processed_dir: Path,
    *,
    mainfuel_edition: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Sum Census 2021 LA population to ONS region (England / Wales / English regions)."""
    processed_dir = Path(processed_dir)
    pop_path = processed_dir / "census2021_la_population_2021.parquet"
    mf2a_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2a_tidy.parquet"
    if not pop_path.is_file() or not mf2a_path.is_file():
        return pd.DataFrame(), {"skipped": True, "reason": "missing_census_or_mainfuel_2a"}

    pop = pd.read_parquet(pop_path)
    pop["lad_code"] = pop["lad_code"].map(_norm_lad)
    pop["population"] = pd.to_numeric(pop["population"], errors="coerce")
    year_val = pd.to_numeric(pop["year"], errors="coerce").dropna()
    census_year = int(year_val.iloc[0]) if len(year_val) else None

    mf2a = pd.read_parquet(mf2a_path)
    lookup = lookup_from_mainfuel_2a(mf2a)
    m = pop.merge(lookup[["lad_code", "region_code", "region_name"]], on="lad_code", how="inner")
    agg = (
        m.groupby(["region_code", "region_name"], observed=True, dropna=False)["population"]
        .sum(min_count=1)
        .reset_index()
        .rename(columns={"population": "region_population_census2021"})
    )
    if census_year is not None:
        agg["region_population_year"] = census_year
    meta = {
        "skipped": False,
        "census_year": census_year,
        "caveat": (
            "Population is summed over LAs mapped to region via main fuel 2a; Census is England and Wales LAs — "
            "UK region rows without mapped LAs have null population."
        ),
    }
    return agg, meta


def build_lane_a(
    processed_dir: Path,
    *,
    housebuilding_edition: str,
    mainfuel_edition: str,
    median_existing_edition: str,
    uk_hpi_edition: str | None,
    ref_csv: Path | None = None,
    price_earnings_edition: str | None = None,
    skip_price_earnings: bool = False,
    median_new_admin_edition: str | None = None,
    price_residence_earnings_edition: str | None = None,
    price_newbuild_workplace_edition: str | None = None,
    vacant_second_homes_edition: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    processed_dir = Path(processed_dir)
    hb_path = processed_dir / f"ons_housebuilding_la_{housebuilding_edition}_tidy.parquet"
    mf2a_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2a_tidy.parquet"
    mf2b_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2b_tidy.parquet"
    med_path = processed_dir / f"ons_median_price_existing_admin_{median_existing_edition}_2a_tidy.parquet"

    for p, label in (
        (hb_path, "house building LA"),
        (mf2a_path, "main fuel 2a"),
        (mf2b_path, "main fuel 2b"),
        (med_path, "median price existing admin 2a"),
    ):
        if not p.is_file():
            raise FileNotFoundError(f"Missing {label}: {p}")

    lookup = _load_lookup(processed_dir, mainfuel_edition, ref_csv)
    base = lookup[["lad_code", "region_code", "region_name", "local_authority_district_name"]].copy()
    base = base.rename(columns={"local_authority_district_name": "la_name"})

    hb = pd.read_parquet(hb_path)
    latest_fy = _latest_financial_year(hb)
    if latest_fy is None:
        raise ValueError("No financial_year in house building LA parquet.")
    hb_snap = _hb_latest_snapshot(hb, latest_fy)

    out = base.merge(hb_snap, on="lad_code", how="left")

    pop_path = processed_dir / "census2021_la_population_2021.parquet"
    if pop_path.is_file():
        pop = pd.read_parquet(pop_path)
        pop["lad_code"] = pop["lad_code"].map(_norm_lad)
        pop["population"] = pd.to_numeric(pop["population"], errors="coerce")
        out = out.merge(pop[["lad_code", "population"]], on="lad_code", how="left")

    med = pd.read_parquet(med_path)
    med_rows, med_pl = _median_la_latest(med, median_edition=median_existing_edition)
    if not med_rows.empty:
        out = out.merge(med_rows, on="lad_code", how="left")

    mf2a = pd.read_parquet(mf2a_path)
    mf2b = pd.read_parquet(mf2b_path)
    p2a = _pivot_mf(mf2a, "mf2a")
    p2b = _pivot_mf(mf2b, "mf2b")
    out = out.merge(p2a, on="lad_code", how="left")
    out = out.merge(p2b, on="lad_code", how="left")

    hpi_edition_used: str | None = None
    if uk_hpi_edition:
        hpi_path = processed_dir / f"ons_uk_hpi_monthly_{uk_hpi_edition}_8_tidy.parquet"
        if hpi_path.is_file():
            hpi = pd.read_parquet(hpi_path)
            hw = _hpi_england_wide(hpi)
            out = out.merge(hw, on="lad_code", how="left")
            hpi_edition_used = uk_hpi_edition

    pe_extra: dict[str, Any] = {}
    if not skip_price_earnings and price_earnings_edition:
        pe_rows, pe_extra = price_earnings_la_median_snapshot(processed_dir, price_earnings_edition)
        if not pe_rows.empty:
            out = out.merge(pe_rows, on="lad_code", how="left")

    median_new_meta: dict[str, Any] = {"skipped": True}
    if median_new_admin_edition:
        med_new_path = processed_dir / f"ons_median_price_new_admin_{median_new_admin_edition}_2a_tidy.parquet"
        if med_new_path.is_file():
            med_new = pd.read_parquet(med_new_path)
            new_rows, new_pl = latest_median_price_new_la(med_new)
            median_new_meta = {
                "skipped": False,
                "median_new_admin_edition": median_new_admin_edition,
                "median_price_new_period_label": new_pl,
            }
            if not new_rows.empty:
                new_only = new_rows.rename(
                    columns={"value": "median_price_new_gbp", "period_label": "median_price_new_period_label"}
                )[["lad_code", "median_price_new_gbp", "median_price_new_period_label"]]
                out = out.merge(new_only, on="lad_code", how="left")
        else:
            median_new_meta = {"skipped": True, "reason": "missing_parquet", "path": str(med_new_path.name)}

    pe_res_meta: dict[str, Any] = {"skipped": True}
    if price_residence_earnings_edition:
        res_rows, pe_res_meta = price_earnings_residence_la_median_snapshot(
            processed_dir, price_residence_earnings_edition
        )
        if not res_rows.empty and not pe_res_meta.get("skipped"):
            out = out.merge(res_rows, on="lad_code", how="left")

    pe_nb_meta: dict[str, Any] = {"skipped": True}
    if price_newbuild_workplace_edition:
        nb_rows, pe_nb_meta = price_earnings_newbuild_workplace_la_median_snapshot(
            processed_dir, price_newbuild_workplace_edition
        )
        if not nb_rows.empty and not pe_nb_meta.get("skipped"):
            out = out.merge(nb_rows, on="lad_code", how="left")

    vacant_meta: dict[str, Any] = {"skipped": True}
    if vacant_second_homes_edition:
        vac_wide, vacant_meta = _vacant_second_homes_la_wide(
            processed_dir, vacant_second_homes_edition
        )
        if not vac_wide.empty and not vacant_meta.get("skipped"):
            out = out.merge(vac_wide, on="lad_code", how="left")

    meta = {
        "lane": "A_local_authority",
        "housebuilding_edition": housebuilding_edition,
        "mainfuel_edition": mainfuel_edition,
        "median_existing_admin_edition": median_existing_edition,
        "uk_hpi_edition": hpi_edition_used,
        "supply_financial_year": latest_fy,
        "median_price_period_label": med_pl,
        "price_earnings": pe_extra,
        "median_new_build": median_new_meta,
        "price_earnings_residence": pe_res_meta,
        "price_earnings_newbuild_workplace": pe_nb_meta,
        "vacant_second_homes": vacant_meta,
        "caveat": (
            "Main fuel is a snapshot for the workbook reference period; supply is by financial year. "
            "Population is Census 2021 (England & Wales LAs) where present. "
            "Median price (existing) is from HPSSA existing admin table 2a (all dwelling types), latest rolling year in file; "
            "optional median new-build uses the new-dwellings admin 2a file when present (also rolling-year). "
            "HPI sheet 8 (optional) is England LA snapshot only. "
            "Workplace price/earnings columns (when present) use the latest calendar year common to ONS tables 5a–5c; "
            "optional residence-based and new-build workplace families use the same common-year rule on their own 5a–5c tables. "
            "Optional vacant/second-home headline counts (Census 2021 table 1a) are counts only — see vacant_second_homes in metadata. "
            "See price_earnings.* and related keys in this metadata."
        ),
    }
    return out, meta


def build_lane_b(
    processed_dir: Path,
    *,
    housebuilding_edition: str,
    mainfuel_edition: str,
    epc_edition: str,
    ee_edition: str,
    uk_hpi_edition: str = "march2026",
    prpi_edition: str = "v41",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from ons_housebuilding_country_periods import preferred_period_order

    processed_dir = Path(processed_dir)
    epc_path = processed_dir / f"ons_epc_bands_{epc_edition}_1a_tidy.parquet"
    ee_path = processed_dir / f"ons_ee_fiveyear_{ee_edition}_1c_tidy.parquet"
    for p, label in ((epc_path, "EPC 1a"), (ee_path, "EE five-year 1c")):
        if not p.is_file():
            raise FileNotFoundError(f"Missing {label}: {p}")

    agg = aggregate(processed_dir, housebuilding_edition, mainfuel_edition)
    agg = agg.dropna(subset=["region_code"])
    fy_order = preferred_period_order(agg["financial_year"])
    latest_fy = fy_order[-1] if fy_order else None
    if latest_fy is None:
        raise ValueError("No financial_year in house-building aggregate.")
    sub = agg[agg["financial_year"].astype(str) == latest_fy].copy()
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    sup = sub.pivot(
        index=["region_code", "region_name"],
        columns="measure",
        values="dwellings",
    )
    sup = sup.rename(columns={c: f"region_supply_{_safe_col(c)}" for c in sup.columns})
    sup = sup.reset_index()
    sup["supply_financial_year"] = latest_fy

    epc = pd.read_parquet(epc_path)
    epc["percentage"] = pd.to_numeric(epc["percentage"], errors="coerce")
    epc["band_u"] = epc["epc_band"].astype(str).str.upper()
    epc_bc = (
        epc[epc["band_u"] == "C"][["country_or_region_code", "percentage"]]
        .rename(columns={"percentage": "epc_pct_band_c"})
    )
    epc_abc = (
        epc[epc["band_u"].isin(["A", "B", "C"])]
        .groupby("country_or_region_code", observed=True)["percentage"]
        .sum(min_count=1)
        .reset_index()
        .rename(columns={"percentage": "epc_pct_bands_abc"})
    )

    out = sup.merge(epc_bc, left_on="region_code", right_on="country_or_region_code", how="left")
    out = out.drop(columns=["country_or_region_code"], errors="ignore")
    out = out.merge(epc_abc, left_on="region_code", right_on="country_or_region_code", how="left")
    out = out.drop(columns=["country_or_region_code"], errors="ignore")

    ee = pd.read_parquet(ee_path)
    ee = ee[ee["measure_breakdown"].astype(str).str.strip() == "All"].copy()
    ee["value"] = pd.to_numeric(ee["value"], errors="coerce")
    rps = preferred_period_order(ee["rolling_period"])
    latest_rp = rps[-1] if rps else None
    if latest_rp is None:
        raise ValueError("No rolling_period in EE 1c.")
    ee_last = ee[ee["rolling_period"].astype(str) == latest_rp].copy()
    ee_last = ee_last.rename(
        columns={
            "value": "ee_epc_c_plus_pct",
            "country_or_region_code": "region_code_ee",
        }
    )[["region_code_ee", "ee_epc_c_plus_pct", "rolling_period"]]

    out = out.merge(ee_last, left_on="region_code", right_on="region_code_ee", how="left")
    out = out.drop(columns=["region_code_ee"], errors="ignore")
    overlap_growth = _region_hpi_prpi_growth(processed_dir, hpi_edition=uk_hpi_edition, prpi_edition=prpi_edition)
    if not overlap_growth.empty:
        out = out.merge(overlap_growth, on="region_name", how="left")

    rp, rp_meta = region_population_by_region(processed_dir, mainfuel_edition=mainfuel_edition)
    if not rp.empty:
        rp_cols = ["region_code", "region_population_census2021"]
        if "region_population_year" in rp.columns:
            rp_cols.append("region_population_year")
        out = out.merge(rp[rp_cols], on="region_code", how="left")

    meta = {
        "lane": "B_region",
        "housebuilding_edition": housebuilding_edition,
        "mainfuel_edition": mainfuel_edition,
        "epc_edition": epc_edition,
        "ee_fiveyear_edition": ee_edition,
        "uk_hpi_edition": uk_hpi_edition,
        "prpi_edition": prpi_edition,
        "supply_financial_year": latest_fy,
        "ee_rolling_period": latest_rp,
        "region_population": rp_meta,
        "caveat": (
            "Region supply is summed LA dwellings from ONS house building (UK). "
            "EPC and five-year rolling metrics are England and Wales geographies only; "
            "Scotland/NI region rows may lack EPC/EE columns. "
            "region_population_census2021 sums Census 2021 LA counts mapped via main fuel 2a (see region_population in metadata)."
        ),
    }
    return out, meta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_DEFAULT_PROCESSED,
        help="Directory for joined Parquet (default: data/processed).",
    )
    p.add_argument("--housebuilding-edition", default="fye_march2025")
    p.add_argument("--mainfuel-edition", default="march2025")
    p.add_argument("--median-existing-edition", default="yearendingseptember2025")
    p.add_argument("--uk-hpi-edition", default="march2026", help="Set empty to skip HPI join.")
    p.add_argument(
        "--price-earnings-edition",
        default="current",
        help="Edition for ons_price_earnings_ratio_* tables 5a–5c (set empty to skip).",
    )
    p.add_argument("--skip-price-earnings", action="store_true", help="Do not join price/earnings tables.")
    p.add_argument("--epc-edition", default="march2025")
    p.add_argument("--ee-edition", default="march2025")
    p.add_argument("--prpi-edition", default="v41")
    p.add_argument(
        "--median-new-admin-edition",
        default="yearendingseptember2025",
        help="Edition for ons_median_price_new_admin_* table 2a (empty = skip new-build median join).",
    )
    p.add_argument(
        "--price-residence-earnings-edition",
        default="",
        help="Edition for ons_price_residence_earnings_ratio_* 5a–5c (empty = skip).",
    )
    p.add_argument(
        "--price-newbuild-workplace-edition",
        default="",
        help="Edition for ons_price_newbuild_workplace_earnings_ratio_* 5a–5c (empty = skip).",
    )
    p.add_argument(
        "--vacant-second-homes-edition",
        default="",
        help="Edition for ons_vacant_second_homes_*_1a headline LAD counts (empty = skip).",
    )
    p.add_argument("--la-stem", default="joined_la_housing_market_snapshot")
    p.add_argument("--region-stem", default="region_housing_market_snapshot")
    p.add_argument(
        "--lad-lookup-csv",
        type=Path,
        default=_DEFAULT_REF / "lad_to_region_england.csv",
        help="Optional LAD→region CSV (default: data/reference/lad_to_region_england.csv).",
    )
    args = p.parse_args()

    out_dir = Path(args.output_dir).resolve()
    repo_root = _REPO.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    hpi_ed = None if args.uk_hpi_edition in ("", "none", "None") else str(args.uk_hpi_edition)
    pe_ed = None
    if not args.skip_price_earnings and str(args.price_earnings_edition).strip() not in ("", "none", "None"):
        pe_ed = str(args.price_earnings_edition).strip()

    def _opt_ed(s: str) -> str | None:
        t = str(s).strip()
        return None if t in ("", "none", "None") else t

    la_df, la_meta = build_lane_a(
        out_dir,
        housebuilding_edition=args.housebuilding_edition,
        mainfuel_edition=args.mainfuel_edition,
        median_existing_edition=args.median_existing_edition,
        uk_hpi_edition=hpi_ed,
        ref_csv=args.lad_lookup_csv if args.lad_lookup_csv.is_file() else None,
        price_earnings_edition=pe_ed,
        skip_price_earnings=args.skip_price_earnings,
        median_new_admin_edition=_opt_ed(args.median_new_admin_edition),
        price_residence_earnings_edition=_opt_ed(args.price_residence_earnings_edition),
        price_newbuild_workplace_edition=_opt_ed(args.price_newbuild_workplace_edition),
        vacant_second_homes_edition=_opt_ed(args.vacant_second_homes_edition),
    )

    hpi_overlap_ed = hpi_ed if hpi_ed else "march2026"
    reg_df, reg_meta = build_lane_b(
        out_dir,
        housebuilding_edition=args.housebuilding_edition,
        mainfuel_edition=args.mainfuel_edition,
        epc_edition=args.epc_edition,
        ee_edition=args.ee_edition,
        uk_hpi_edition=hpi_overlap_ed,
        prpi_edition=args.prpi_edition,
    )

    la_pq = out_dir / f"{args.la_stem}.parquet"
    la_meta_path = out_dir / f"{args.la_stem}.meta.json"
    reg_pq = out_dir / f"{args.region_stem}.parquet"
    reg_meta_path = out_dir / f"{args.region_stem}.meta.json"

    write_parquet_atomic(la_df, la_pq, index=False)
    combined_la = {**la_meta, "output_path": str(la_pq.resolve().relative_to(repo_root))}
    la_meta_path.write_text(json.dumps(combined_la, indent=2), encoding="utf-8")

    write_parquet_atomic(reg_df, reg_pq, index=False)
    combined_reg = {**reg_meta, "output_path": str(reg_pq.resolve().relative_to(repo_root))}
    reg_meta_path.write_text(json.dumps(combined_reg, indent=2), encoding="utf-8")

    print(f"Wrote {la_pq}")
    print(f"Wrote {la_meta_path}")
    print(f"Wrote {reg_pq}")
    print(f"Wrote {reg_meta_path}")


if __name__ == "__main__":
    main()
