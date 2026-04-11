"""ONS house building by country: tidy prep and optional filters for the HTTP API."""

from __future__ import annotations

import pandas as pd

from ons_housebuilding_country_periods import preferred_period_order


def prepare_housebuilding_country_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["period"] = out["period"].astype(str)
    out["dwellings"] = pd.to_numeric(out["dwellings"], errors="coerce").astype("float64")
    return out


def filter_housebuilding_country(
    df: pd.DataFrame,
    *,
    period_min: str | None = None,
    period_max: str | None = None,
    measures: list[str] | None = None,
    country_names: list[str] | None = None,
    sectors: list[str] | None = None,
    frequencies: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Filter country-level house-building tidy data; return view and ordered period labels."""
    all_periods = preferred_period_order(df["period"])
    if not all_periods:
        return df.iloc[0:0].copy(), []

    p_min = period_min or all_periods[0]
    p_max = period_max or all_periods[-1]
    if all_periods.index(p_min) > all_periods.index(p_max):
        p_min, p_max = p_max, p_min
    i0, i1 = all_periods.index(p_min), all_periods.index(p_max)
    span = [p for p in all_periods if i0 <= all_periods.index(p) <= i1]

    view = df[df["period"].isin(span)]
    if measures:
        view = view[view["measure"].astype(str).str.lower().isin([m.lower() for m in measures])]
    if country_names:
        view = view[view["country_name"].isin(country_names)]
    if sectors:
        view = view[view["sector"].astype(str).isin(sectors)]
    if frequencies:
        view = view[view["frequency"].astype(str).isin(frequencies)]

    return view, span
