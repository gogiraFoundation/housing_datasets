"""Latest rolling-period median price (existing) per LA from HPSSA-style tidy frame."""

from __future__ import annotations

import pandas as pd

from housing_data.geo_ids import norm_lad


def latest_median_price_existing_la(med: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Return one row per LA for the latest ``period_label`` in table 2a (all types). Columns: lad_code, la_name, value, period_label."""
    m = med[
        (med["table_id"].astype(str) == "2a")
        & (med["property_band"].astype(str) == "all")
        & (med["geography_level"].astype(str) == "local_authority")
    ].copy()
    if m.empty:
        return pd.DataFrame(), None
    m["period_sort"] = pd.to_datetime(
        m["period_label"].astype(str).str.replace("^Year ending ", "", regex=True),
        format="%b %Y",
        errors="coerce",
    )
    latest = m["period_sort"].max()
    if pd.isna(latest):
        return pd.DataFrame(), None
    last = m[m["period_sort"] == latest].copy()
    last["lad_code"] = last["local_authority_code"].map(norm_lad)
    pl = str(last["period_label"].iloc[0])
    out = pd.DataFrame(
        {
            "lad_code": last["lad_code"],
            "la_name": last["local_authority_name"].astype(str),
            "value": pd.to_numeric(last["median_price_gbp"], errors="coerce"),
            "period_label": last["period_label"].astype(str),
        }
    )
    return out, pl


def latest_median_price_new_la(med: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Latest rolling-period median price (new build) per LA from HPSSA-style tidy (table 2a, all types)."""
    m = med[
        (med["table_id"].astype(str) == "2a")
        & (med["property_band"].astype(str) == "all")
        & (med["geography_level"].astype(str) == "local_authority")
    ].copy()
    if m.empty:
        return pd.DataFrame(), None
    m["period_sort"] = pd.to_datetime(
        m["period_label"].astype(str).str.replace("^Year ending ", "", regex=True),
        format="%b %Y",
        errors="coerce",
    )
    latest = m["period_sort"].max()
    if pd.isna(latest):
        return pd.DataFrame(), None
    last = m[m["period_sort"] == latest].copy()
    last["lad_code"] = last["local_authority_code"].map(norm_lad)
    pl = str(last["period_label"].iloc[0])
    out = pd.DataFrame(
        {
            "lad_code": last["lad_code"],
            "la_name": last["local_authority_name"].astype(str),
            "value": pd.to_numeric(last["median_price_gbp"], errors="coerce"),
            "period_label": last["period_label"].astype(str),
        }
    )
    return out, pl
