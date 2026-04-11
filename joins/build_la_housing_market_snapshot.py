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

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_data.median_price_la import latest_median_price_existing_la
from housing_data.price_earnings_snapshot import price_earnings_la_median_snapshot


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

    meta = {
        "lane": "A_local_authority",
        "housebuilding_edition": housebuilding_edition,
        "mainfuel_edition": mainfuel_edition,
        "median_existing_admin_edition": median_existing_edition,
        "uk_hpi_edition": hpi_edition_used,
        "supply_financial_year": latest_fy,
        "median_price_period_label": med_pl,
        "price_earnings": pe_extra,
        "caveat": (
            "Main fuel is a snapshot for the workbook reference period; supply is by financial year. "
            "Population is Census 2021 (England & Wales LAs) where present. "
            "Median price is from HPSSA existing admin table 2a (all dwelling types), latest rolling year in file. "
            "HPI sheet 8 (optional) is England LA snapshot only. "
            "Price/earnings columns (when present) use the latest calendar year common to ONS tables 5a–5c; "
            "see price_earnings.caveat in this metadata."
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

    la_df, la_meta = build_lane_a(
        out_dir,
        housebuilding_edition=args.housebuilding_edition,
        mainfuel_edition=args.mainfuel_edition,
        median_existing_edition=args.median_existing_edition,
        uk_hpi_edition=hpi_ed,
        ref_csv=args.lad_lookup_csv if args.lad_lookup_csv.is_file() else None,
        price_earnings_edition=pe_ed,
        skip_price_earnings=args.skip_price_earnings,
    )

    reg_df, reg_meta = build_lane_b(
        out_dir,
        housebuilding_edition=args.housebuilding_edition,
        mainfuel_edition=args.mainfuel_edition,
        epc_edition=args.epc_edition,
        ee_edition=args.ee_edition,
    )

    la_pq = out_dir / f"{args.la_stem}.parquet"
    la_meta_path = out_dir / f"{args.la_stem}.meta.json"
    reg_pq = out_dir / f"{args.region_stem}.parquet"
    reg_meta_path = out_dir / f"{args.region_stem}.meta.json"

    la_df.to_parquet(la_pq, index=False)
    combined_la = {**la_meta, "output_path": str(la_pq.resolve().relative_to(repo_root))}
    la_meta_path.write_text(json.dumps(combined_la, indent=2), encoding="utf-8")

    reg_df.to_parquet(reg_pq, index=False)
    combined_reg = {**reg_meta, "output_path": str(reg_pq.resolve().relative_to(repo_root))}
    reg_meta_path.write_text(json.dumps(combined_reg, indent=2), encoding="utf-8")

    print(f"Wrote {la_pq}")
    print(f"Wrote {la_meta_path}")
    print(f"Wrote {reg_pq}")
    print(f"Wrote {reg_meta_path}")


if __name__ == "__main__":
    main()
