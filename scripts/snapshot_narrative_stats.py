#!/usr/bin/env python3
"""Reproducible headline statistics for narrative alignment with processed Parquet.

Reads ``data/processed`` (or ``--processed-dir``) and prints JSON to stdout.
Intended for copy/paste into reporting; re-run after ETL or join refresh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.hpi_prpi_callout import buy_vs_rent_spread_caption


def _england_fy_starts(processed: Path) -> pd.DataFrame:
    hb = pd.read_parquet(processed / "ons_housebuilding_country_current_tidy.parquet")
    sub = hb[
        (hb["country_name"] == "England")
        & (hb["measure"] == "started")
        & (hb["frequency"] == "annual_financial_year")
    ].copy()
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    return sub.groupby("period", as_index=False)["dwellings"].sum().sort_values("period")


def _uk_fy_starts(processed: Path) -> pd.DataFrame:
    hb = pd.read_parquet(processed / "ons_housebuilding_country_current_tidy.parquet")
    sub = hb[
        (hb["country_name"] == "United Kingdom")
        & (hb["measure"] == "started")
        & (hb["frequency"] == "annual_financial_year")
    ].copy()
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    return sub.groupby("period", as_index=False)["dwellings"].sum().sort_values("period")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed",
        help="Directory containing tidy Parquet outputs.",
    )
    args = p.parse_args()
    processed = args.processed_dir.resolve()

    out: dict = {"processed_dir": str(processed)}

    la_path = processed / "joined_la_housing_market_snapshot.parquet"
    meta_path = processed / "joined_la_housing_market_snapshot.meta.json"
    if la_path.is_file():
        la = pd.read_parquet(la_path)
        pe = pd.to_numeric(la["pe_affordability_ratio"], errors="coerce")
        out["joined_la_housing_market_snapshot"] = {
            "rows": int(len(la)),
            "pe_affordability_ratio_non_null": int(pe.notna().sum()),
            "pe_affordability_ratio_gt_10": int((pe > 10).sum()),
            "pe_affordability_ratio_max": float(pe.max()) if pe.notna().any() else None,
        }
        if "median_price_existing_gbp" in la.columns and "region_name" in la.columns:
            reg = (
                la.groupby("region_name")["median_price_existing_gbp"]
                .apply(lambda s: float(pd.to_numeric(s, errors="coerce").median()))
                .sort_values()
            )
            out["median_price_existing_gbp_median_by_region"] = reg.round(0).to_dict()
    if meta_path.is_file():
        out["joined_la_meta"] = json.loads(meta_path.read_text(encoding="utf-8"))

    reg_path = processed / "region_housing_market_snapshot.parquet"
    reg_meta_path = processed / "region_housing_market_snapshot.meta.json"
    if reg_path.is_file():
        reg = pd.read_parquet(reg_path)
        out["region_housing_market_snapshot_columns"] = list(reg.columns)
    if reg_meta_path.is_file():
        out["region_meta"] = json.loads(reg_meta_path.read_text(encoding="utf-8"))

    eng = _england_fy_starts(processed)
    fy_like = eng[eng["period"].astype(str).str.contains("-", na=False)]
    out["england_starts_annual_financial_year"] = {
        "period_min": str(fy_like["period"].iloc[0]) if len(fy_like) else None,
        "period_max": str(fy_like["period"].iloc[-1]) if len(fy_like) else None,
        "2024_25_dwellings": int(fy_like[fy_like["period"] == "2024-25"]["dwellings"].iloc[0])
        if len(fy_like[fy_like["period"] == "2024-25"])
        else None,
        "2008_09_dwellings": int(fy_like[fy_like["period"] == "2008-09"]["dwellings"].iloc[0])
        if len(fy_like[fy_like["period"] == "2008-09"])
        else None,
        "2007_08_dwellings": int(fy_like[fy_like["period"] == "2007-08"]["dwellings"].iloc[0])
        if len(fy_like[fy_like["period"] == "2007-08"])
        else None,
    }

    uk = _uk_fy_starts(processed)
    uk_fy = uk[uk["period"].astype(str).str.contains("-", na=False)]
    era = uk_fy[(uk_fy["period"].astype(str) >= "2011-12") & (uk_fy["period"].astype(str) <= "2024-25")]
    if len(era):
        out["uk_starts_fy_2011_12_to_2024_25"] = {
            "financial_years": int(len(era)),
            "count_gt_200k": int((era["dwellings"] > 200_000).sum()),
        }

    ee_path = processed / "ons_ee_fiveyear_march2025_1c_tidy.parquet"
    if ee_path.is_file():
        ee = pd.read_parquet(ee_path)
        ee = ee[ee["measure_breakdown"].astype(str).str.strip() == "All"]
        eng_ee = ee[ee["country_or_region_name"].astype(str) == "England"].copy()
        eng_ee["value"] = pd.to_numeric(eng_ee["value"], errors="coerce")
        rps = sorted(eng_ee["rolling_period"].astype(str).unique())
        first, last = rps[0], rps[-1]
        v_first = float(eng_ee[eng_ee["rolling_period"] == first]["value"].iloc[0])
        v_last = float(eng_ee[eng_ee["rolling_period"] == last]["value"].iloc[0])
        out["england_ee_fiveyear_1c_all"] = {
            "edition_parquet": ee_path.name,
            "first_rolling_period": first,
            "last_rolling_period": last,
            "epc_c_plus_pct_first": v_first,
            "epc_c_plus_pct_last": v_last,
        }

    caption = buy_vs_rent_spread_caption(processed)
    out["buy_vs_rent_caption_plain"] = caption.replace("**", "") if caption else None

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
