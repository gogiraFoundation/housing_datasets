"""Lane A snapshot columns merged onto map tables for tooltips and CSV exports."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


# Columns merged when joined_la_housing_market_snapshot.parquet exists (subset of Lane A wide table).
_SNAPSHOT_MERGE_NAMES: tuple[str, ...] = (
    "median_price_existing_gbp",
    "median_price_period_label",
    "median_price_new_gbp",
    "median_price_new_period_label",
    "supply_starts",
    "supply_completions",
    "supply_financial_year",
    "pe_affordability_ratio",
    "vacant_dwellings_count",
    "second_home_dwellings_count",
)


def pick_mf2a_mains_gas_column(columns: list[str]) -> str | None:
    for c in columns:
        cl = c.lower()
        if cl.startswith("mf2a_") and "mains_gas" in cl:
            return c
    return None


def merge_lane_a_snapshot_columns(
    display: pd.DataFrame,
    snap: pd.DataFrame,
    *,
    exclude_duplicate_of: str | None = None,
) -> pd.DataFrame:
    """Left-merge snapshot context onto ``display`` by ``lad_code`` (does not replace ``value``)."""
    if snap.empty or "lad_code" not in display.columns:
        return display
    snap = snap.copy()
    snap["lad_code"] = snap["lad_code"].map(_norm_lad)
    extra = [c for c in _SNAPSHOT_MERGE_NAMES if c in snap.columns]
    mg = pick_mf2a_mains_gas_column(list(snap.columns))
    if mg:
        extra.append(mg)
    extra = sorted(set(extra))
    if exclude_duplicate_of and exclude_duplicate_of in extra:
        extra = [c for c in extra if c != exclude_duplicate_of]
    if not extra:
        return display
    sub = snap[["lad_code", *extra]].drop_duplicates(subset=["lad_code"], keep="first")
    to_add = [c for c in extra if c not in display.columns]
    if not to_add:
        return display
    return display.merge(sub[["lad_code", *to_add]], on="lad_code", how="left")


def _fmt_price(x: object) -> str:
    v = pd.to_numeric(x, errors="coerce")
    if pd.isna(v):
        return "—"
    return f"£{float(v):,.0f}"


def _fmt_num(x: object) -> str:
    v = pd.to_numeric(x, errors="coerce")
    if pd.isna(v):
        return "—"
    return f"{float(v):,.0f}"


def _fmt_ratio(x: object) -> str:
    v = pd.to_numeric(x, errors="coerce")
    if pd.isna(v):
        return "—"
    return f"{float(v):,.2f}"


def _fmt_str(x: object) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    s = str(x).strip()
    return s if s else "—"


def snapshot_tooltip_strings(
    row: pd.Series,
    *,
    mains_gas_col: str | None,
) -> dict[str, str]:
    """Preformatted blocks for Folium / Pydeck (4 keys)."""
    prices = (
        f"Median existing: {_fmt_price(row.get('median_price_existing_gbp'))} "
        f"({_fmt_str(row.get('median_price_period_label'))}) · "
        f"Median new: {_fmt_price(row.get('median_price_new_gbp'))} "
        f"({_fmt_str(row.get('median_price_new_period_label'))})"
    )
    supply = (
        f"Supply FY {_fmt_str(row.get('supply_financial_year'))}: "
        f"starts {_fmt_num(row.get('supply_starts'))}, "
        f"completions {_fmt_num(row.get('supply_completions'))}"
    )
    if mains_gas_col and mains_gas_col in row.index:
        fuel_lab = mains_gas_col.replace("mf2a_", "").replace("_", " ")
        fuel = f"{fuel_lab}: {_fmt_ratio(row.get(mains_gas_col))}% (main fuel 2a)"
    else:
        fuel = "Main fuel (2a): —"
    afford = f"Affordability (5c): {_fmt_ratio(row.get('pe_affordability_ratio'))}"
    vacant = (
        f"Vacant / second home (ONS 1a): {_fmt_num(row.get('vacant_dwellings_count'))} / "
        f"{_fmt_num(row.get('second_home_dwellings_count'))} (headline counts)"
    )
    more = f"{afford} · {vacant}"
    return {
        "snap_prices": prices,
        "snap_supply": supply,
        "snap_fuel": fuel,
        "snap_more": more,
    }


def region_snapshot_metric_columns(df: pd.DataFrame) -> list[str]:
    skip = {
        "region_code",
        "region_name",
        "supply_financial_year",
        "rolling_period",
    }
    out: list[str] = []
    for c in df.columns:
        if c in skip:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return sorted(set(out))
