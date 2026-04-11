"""ONS house building by local authority: tidy data prep, filters, and reference Altair charts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd


def processed_parquet_path(repo_root: Path, edition: str) -> Path:
    return repo_root / "data" / "processed" / f"ons_housebuilding_la_{edition}_tidy.parquet"


def load_housebuilding_la_parquet(path: Path | str) -> pd.DataFrame:
    return pd.read_parquet(path)


def prepare_housebuilding_la_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["financial_year"] = out["financial_year"].astype(str)
    out["dwellings"] = pd.to_numeric(out["dwellings"], errors="coerce").astype("float64")
    return out


def sorted_financial_years(series: pd.Series) -> list[str]:
    return sorted(series.dropna().astype(str).unique().tolist())


def filter_housebuilding_la(
    df: pd.DataFrame,
    *,
    financial_year_min: str | None = None,
    financial_year_max: str | None = None,
    measures: list[str] | None = None,
    regions: list[str] | None = None,
    local_authorities: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Return filtered view and the ordered list of financial years (for chart sort)."""
    all_years = sorted_financial_years(df["financial_year"])
    if not all_years:
        return df.iloc[0:0].copy(), []

    y_min = financial_year_min or all_years[0]
    y_max = financial_year_max or all_years[-1]
    if all_years.index(y_min) > all_years.index(y_max):
        y_min, y_max = y_max, y_min
    year_span = [
        y
        for y in all_years
        if all_years.index(y_min) <= all_years.index(y) <= all_years.index(y_max)
    ]

    view = df[df["financial_year"].isin(year_span)]
    if measures:
        view = view[view["measure"].isin(measures)]
    if regions:
        view = view[view["Region or Country Name"].isin(regions)]
    if local_authorities:
        view = view[view["Local Authority Name"].isin(local_authorities)]

    return view, all_years


def line_by_year_chart(
    view: pd.DataFrame,
    *,
    year_order: list[str],
    height: int = 340,
) -> alt.Chart:
    by_year = view.groupby(
        ["financial_year", "measure"],
        as_index=False,
        observed=False,
    )["dwellings"].sum(min_count=1)
    return (
        alt.Chart(by_year)
        .mark_line(point=True)
        .encode(
            x=alt.X("financial_year:N", title="Financial year", sort=year_order),
            y=alt.Y("dwellings:Q", title="Dwellings (sum)"),
            color=alt.Color("measure:N", title="Measure"),
            tooltip=["financial_year", "measure", alt.Tooltip("dwellings", format=",.0f")],
        )
        .properties(height=height)
    )


def chart_to_vega_lite(chart: alt.Chart) -> dict[str, Any]:
    return chart.to_dict()
