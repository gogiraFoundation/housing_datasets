"""Streamlit: ONS house price to residence-based earnings ratio (England and Wales)."""

from __future__ import annotations

import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_price_residence_earnings_ratio_config import (
    DATASET_PAGE,
    PRICE_RESIDENCE_EARNINGS_RATIO_DATA_SHEETS,
    PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS,
)
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


_TABLE_HELP = {
    "1a": "1a — Median house price (£), country / region",
    "1b": "1b — Median residence-based earnings (£), country / region",
    "1c": "1c — Median price / median earnings ratio, country / region",
    "2a": "2a — Lower quartile house price (£), country / region",
    "2b": "2b — Lower quartile residence-based earnings (£), country / region",
    "2c": "2c — Lower quartile price / earnings ratio, country / region",
    "3a": "3a — Median house price (£), county (England)",
    "3b": "3b — Median residence-based earnings (£), county (England)",
    "3c": "3c — Median price / median earnings ratio, county (England)",
    "4a": "4a — Lower quartile house price (£), county (England)",
    "4b": "4b — Lower quartile residence-based earnings (£), county (England)",
    "4c": "4c — Lower quartile price / earnings ratio, county (England)",
    "5a": "5a — Median house price (£), local authority",
    "5b": "5b — Median residence-based earnings (£), local authority",
    "5c": "5c — Median price / median earnings ratio, local authority",
    "6a": "6a — Lower quartile house price (£), local authority",
    "6b": "6b — Lower quartile residence-based earnings (£), local authority",
    "6c": "6c — Lower quartile price / earnings ratio, local authority",
}


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_price_residence_earnings_ratio_{edition}_{table}_tidy.parquet"


def _label_column(df: pd.DataFrame) -> str | None:
    for prefer in (
        "local_authority_name",
        "name",
        "country_region_name",
    ):
        if prefer in df.columns:
            return prefer
    for c in df.columns:
        if c.endswith("_name"):
            return c
    return None


def _period_sort_series(period_label: pd.Series) -> pd.Series:
    """Parse period labels for chart ordering (earnings years vs year-ending-Sep vs aggregate)."""

    def one(x: object) -> pd.Timestamp:
        s = str(x).strip()
        if s == "5-Year Average":
            return pd.Timestamp("2099-12-31", tz=None)
        m = re.match(r"Year ending Sep (\d{4})", s)
        if m:
            y = int(m.group(1))
            return pd.Timestamp(year=y, month=9, day=30)
        if re.match(r"^\d{4}$", s):
            return pd.Timestamp(year=int(s), month=6, day=15)
        return pd.NaT

    return period_label.map(one)


def _y_title(component: str) -> str:
    if component == "house_price":
        return "House price (£)"
    if component == "earnings":
        return "Gross annual residence-based earnings (£)"
    return "Ratio (house price ÷ earnings)"


def main() -> None:
    st.set_page_config(page_title="Price / residence earnings", layout="wide")
    st.title("House price to residence-based earnings ratio")
    st.caption(
        "ONS affordability tables: **median** and **lower quartile** house prices and earnings, "
        "and **ratios**, for country / region, county (England), and local authority. "
        "Ratios use **gross annual residence-based** earnings. "
        "Run `python ons_price_residence_earnings_ratio_etl.py --edition current`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[ONS dataset page]({DATASET_PAGE})")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(PRICE_RESIDENCE_EARNINGS_RATIO_DATA_SHEETS),
        format_func=lambda t: _TABLE_HELP.get(t, t),
    )
    include_five_year = st.sidebar.checkbox(
        "Include “5-Year Average” column (ratio tables only)",
        value=False,
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_price_residence_earnings_ratio_etl.py --edition "
            + edition
            + "\n# or: python ons_price_residence_earnings_ratio_etl.py --transform-only -i workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    view["value"] = pd.to_numeric(view["value"], errors="coerce")
    if not include_five_year:
        view = view[view["period_label"].astype(str).str.strip() != "5-Year Average"]

    label_col = _label_column(view)
    if label_col:
        names = sorted(view[label_col].dropna().astype(str).unique())
        default_n = min(5, len(names))
        pick = st.sidebar.multiselect(label_col.replace("_", " ").title(), options=names, default=names[:default_n])
        view = view[view[label_col].isin(pick)] if pick else view

    view["period_sort"] = _period_sort_series(view["period_label"])
    view_chart = view[view["period_sort"].notna()].copy()
    component = str(view["component"].iloc[0]) if len(view) else "ratio"
    y_title = _y_title(component)

    st.subheader("Time series")
    if view_chart.empty:
        st.info("No rows to chart after filters (try widening geography selection or including 5-year average).")
    else:
        enc: dict = {
            "x": alt.X("period_sort:T", title="Period"),
            "y": alt.Y("value:Q", title=y_title),
        }
        tip = ["period_label", "value", "geography_level", "percentile", "component", "table_id"]
        if label_col:
            enc["color"] = alt.Color(f"{label_col}:N")
            tip.append(label_col)
        else:
            enc["color"] = alt.value("steelblue")
        ch = alt.Chart(view_chart).mark_line(point=True).encode(**enc, tooltip=tip).properties(height=400)
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    show = view.drop(columns=["period_sort"], errors="ignore")
    st.dataframe(show, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(show), 40)))

    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"price_residence_earnings_ratio_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
