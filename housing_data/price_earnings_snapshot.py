"""Latest common-year price/earnings snapshot per LA (ONS tables 5a–5c)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from housing_data.geo_ids import norm_lad
from housing_data.periods import pe_year_from_period


def price_earnings_la_median_snapshot(
    processed_dir: Path,
    edition: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Latest calendar year common to LA sheets 5a/5b/5c (median price, earnings, ratio)."""
    processed_dir = Path(processed_dir)
    paths = {s: processed_dir / f"ons_price_earnings_ratio_{edition}_{s}_tidy.parquet" for s in ("5a", "5b", "5c")}
    if not all(p.is_file() for p in paths.values()):
        return pd.DataFrame(), {
            "skipped": True,
            "reason": "missing_one_or_more_parquet",
            "paths": {k: str(v) for k, v in paths.items()},
        }

    dfs: dict[str, pd.DataFrame] = {}
    year_sets: list[set[int]] = []
    for s in ("5a", "5b", "5c"):
        df = pd.read_parquet(paths[s])
        sub = df[df["geography_level"].astype(str) == "local_authority"].copy()
        sub["pe_year"] = sub["period_label"].map(pe_year_from_period)
        sub = sub[sub["pe_year"].notna()]
        dfs[s] = sub
        year_sets.append({int(x) for x in sub["pe_year"].dropna().unique()})

    common = year_sets[0] & year_sets[1] & year_sets[2]
    if not common:
        return pd.DataFrame(), {"skipped": True, "reason": "no_common_year_across_5a_5b_5c"}

    snapshot_year = max(common)

    def _col_for_sheet(sheet: str, value_name: str) -> pd.DataFrame:
        sy = int(snapshot_year)
        pey = pd.to_numeric(dfs[sheet]["pe_year"], errors="coerce")
        sub = dfs[sheet][pey.notna() & (pey == sy)].copy()
        sub["lad_code"] = sub["local_authority_code"].map(norm_lad)
        sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
        out = sub[["lad_code", "value"]].drop_duplicates(subset=["lad_code"], keep="first")
        return out.rename(columns={"value": value_name})

    pe = _col_for_sheet("5a", "pe_median_price_gbp")
    pe = pe.merge(_col_for_sheet("5b", "pe_workplace_earnings_gbp"), on="lad_code", how="outer")
    pe = pe.merge(_col_for_sheet("5c", "pe_affordability_ratio"), on="lad_code", how="outer")
    pe["pe_snapshot_year"] = snapshot_year
    pe["price_earnings_edition"] = edition

    sy = int(snapshot_year)

    def _period_label_one(df: pd.DataFrame) -> pd.Series:
        pey = pd.to_numeric(df["pe_year"], errors="coerce")
        return df[pey.notna() & (pey == sy)]["period_label"].drop_duplicates().head(1)

    pl_a = _period_label_one(dfs["5a"])
    pl_b = _period_label_one(dfs["5b"])
    pl_c = _period_label_one(dfs["5c"])

    meta = {
        "skipped": False,
        "price_earnings_edition": edition,
        "pe_snapshot_year": snapshot_year,
        "pe_period_label_median_house_price": str(pl_a.iloc[0]) if len(pl_a) else None,
        "pe_period_label_earnings": str(pl_b.iloc[0]) if len(pl_b) else None,
        "pe_period_label_ratio": str(pl_c.iloc[0]) if len(pl_c) else None,
        "caveat": (
            "House prices use a year-ending-September rolling period; earnings are ASHE workplace gross "
            "for a calendar year (ONS methodology). Ratio columns use the same paired year label as published."
        ),
    }
    return pe, meta


def latest_affordability_ratio_la_only(processed_dir: Path, edition: str) -> tuple[pd.DataFrame, str | None, int | None]:
    """LA affordability ratio from 5c using same common-year rule as full snapshot."""
    pe, meta = price_earnings_la_median_snapshot(processed_dir, edition)
    if pe.empty or meta.get("skipped"):
        return pd.DataFrame(), None, None
    y = int(meta["pe_snapshot_year"])
    path_5c = Path(processed_dir) / f"ons_price_earnings_ratio_{edition}_5c_tidy.parquet"
    d5 = pd.read_parquet(path_5c)
    d5 = d5[d5["geography_level"].astype(str) == "local_authority"].copy()
    d5["lad_code"] = d5["local_authority_code"].map(norm_lad)
    d5["py"] = d5["period_label"].map(pe_year_from_period)
    py_num = pd.to_numeric(d5["py"], errors="coerce")
    d5 = d5[py_num.notna() & (py_num == float(y))]
    names = d5[["lad_code", "local_authority_name"]].drop_duplicates(subset=["lad_code"])
    out = pe[["lad_code", "pe_affordability_ratio"]].merge(names, on="lad_code", how="left")
    out = out.rename(columns={"pe_affordability_ratio": "value", "local_authority_name": "la_name"})
    pl = meta.get("pe_period_label_ratio")
    out["period_label"] = pl or ""
    return out, pl, y
