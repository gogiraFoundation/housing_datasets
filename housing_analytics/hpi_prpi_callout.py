"""Reusable PRPI vs UK HPI index comparison (no Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_REGION_NAME_MAP: dict[str, str] = {
    "East": "East of England",
    "East Midlands": "East Midlands",
    "London": "London",
    "North East": "North East",
    "North West": "North West",
    "South East": "South East",
    "South West": "South West",
    "West Midlands": "West Midlands",
    "Yorkshire and The Humber": "Yorkshire and The Humber",
    "England": "England",
    "Wales": "Wales",
    "Scotland": "Scotland",
    "Northern Ireland [note 3]": "Northern Ireland",
    "Great Britain": "Great Britain",
    "United Kingdom": "United Kingdom",
}


def buy_vs_rent_spread_caption(
    processed_dir: Path,
    *,
    prpi_edition: str = "v41",
    hpi_edition: str = "march2026",
    geography_name: str = "Great Britain",
) -> str | None:
    """One-line caption: cumulative growth spread (HPI minus PRPI) from first overlapping month to latest.

    Both series are rebased to 100 at the first month where both have index values for ``geography_name``.
    ``processed_dir`` is the ``data/processed`` directory (same as ``streamlit_io.PROCESSED_DIR``).
    """
    prpi_path = Path(processed_dir) / f"ons_private_rental_index_{prpi_edition}_tidy.parquet"
    hpi_path = Path(processed_dir) / f"ons_uk_hpi_monthly_{hpi_edition}_1_tidy.parquet"
    if not prpi_path.is_file() or not hpi_path.is_file():
        return None
    prpi = pd.read_parquet(prpi_path)
    prpi = prpi[prpi["variable"].astype(str) == "index"].copy()
    prpi["period"] = pd.to_datetime(prpi["month_label"].astype(str), format="%b-%y", errors="coerce")
    prpi["value"] = pd.to_numeric(prpi["value"], errors="coerce")
    prpi = prpi.dropna(subset=["period", "value"])
    prpi = prpi[prpi["geography_name"].astype(str) == geography_name]
    if prpi.empty:
        return None

    hpi = pd.read_parquet(hpi_path)
    hpi["period"] = pd.to_datetime(hpi["time_period"].astype(str), format="%b %Y", errors="coerce")
    hpi["value"] = pd.to_numeric(hpi["value"], errors="coerce")
    hpi["geo_m"] = hpi["geography"].astype(str).map(_REGION_NAME_MAP).fillna(hpi["geography"].astype(str))
    hpi = hpi.dropna(subset=["period", "value"])
    hpi = hpi[hpi["geo_m"].astype(str) == geography_name]
    if hpi.empty:
        return None

    j = prpi[["period", "value"]].merge(hpi[["period", "value"]], on="period", how="inner", suffixes=("_prpi", "_hpi"))
    j = j.sort_values("period")
    if len(j) < 2:
        return None
    first = j.iloc[0]
    last = j.iloc[-1]
    if float(first["value_prpi"]) == 0 or float(first["value_hpi"]) == 0:
        return None
    rb_prpi = float(last["value_prpi"]) / float(first["value_prpi"]) * 100.0
    rb_hpi = float(last["value_hpi"]) / float(first["value_hpi"]) * 100.0
    spread = (rb_hpi - 100.0) - (rb_prpi - 100.0)
    last_m = last["period"]
    label = last_m.strftime("%b %Y") if pd.notna(last_m) else str(last["period"])
    return (
        f"**Buy vs rent (indexed):** from first overlapping month to **{label}** ({geography_name}), "
        f"cumulative growth spread (HPI minus PRPI) ≈ **{spread:+.1f} percentage points** "
        f"(rebased series; not sterling levels)."
    )
