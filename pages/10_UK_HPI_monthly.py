"""Streamlit: ONS UK House Price Index — monthly price statistics (tidy Parquet from ons_uk_hpi_monthly_etl.py)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_uk_hpi_monthly_config import DATASET_PAGE, UK_HPI_DATA_SHEETS, UK_HPI_MONTHLY_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_TIME_SHEETS = frozenset({"1", "2", "3", "7"})
_SPLIT_SHEETS = frozenset({"4", "5", "6"})
_LA_SHEETS = frozenset({"8", "9", "10", "11"})

_SHEET_HELP = {
    "1": "Indices — countries and regions",
    "2": "Average price (£) — countries and regions",
    "3": "Annual % change — countries and regions",
    "4": "FTB vs former owner — level (£) and annual %",
    "5": "New vs pre-owned — level (£) and annual %",
    "6": "Cash vs mortgage — level (£) and annual %",
    "7": "Monthly % change — countries and regions",
    "8": "England local authorities (snapshot)",
    "9": "Wales local authorities (snapshot)",
    "10": "Scotland local authorities (snapshot)",
    "11": "Northern Ireland local authorities (snapshot)",
}


def _expected_parquet_path(edition: str, sheet: str) -> Path:
    return PROCESSED_DIR / f"ons_uk_hpi_monthly_{edition}_{sheet}_tidy.parquet"


def _parse_time_period(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%b %Y", errors="coerce")


def main() -> None:
    st.set_page_config(page_title="UK HPI — monthly", layout="wide")
    st.title("UK House Price Index — monthly price statistics")
    st.caption(
        "ONS UK HPI monthly workbook → `python ons_uk_hpi_monthly_etl.py` → "
        "`data/processed/ons_uk_hpi_monthly_*_*_tidy.parquet`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE})")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(UK_HPI_MONTHLY_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({UK_HPI_MONTHLY_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Worksheet",
        options=list(UK_HPI_DATA_SHEETS),
        format_func=lambda t: f"{t} — {_SHEET_HELP.get(t, t)}",
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_uk_hpi_monthly_etl.py --edition " + edition + "\n"
            "# or: python ons_uk_hpi_monthly_etl.py --transform-only -i path/to/workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()

    if table in _TIME_SHEETS:
        view["period"] = _parse_time_period(view["time_period"])
        geos = sorted(view["geography"].dropna().astype(str).unique())
        pick = st.sidebar.multiselect("Geography", options=geos, default=geos[: min(3, len(geos))])
        sub = view[view["geography"].isin(pick)] if pick else view
        ch = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("period:T", title="Month"),
                y=alt.Y("value:Q", title="Value"),
                color=alt.Color("geography:N"),
                tooltip=["time_period", "geography", "value"],
            )
            .properties(height=400)
        )
        st.subheader("Time series")
        st.altair_chart(ch, width=ST_WIDTH)

    elif table in _SPLIT_SHEETS:
        blocks = sorted(view["table_block"].dropna().astype(str).unique())
        blk = st.sidebar.selectbox("Block", options=blocks, index=0)
        sub = view[view["table_block"].astype(str) == blk]
        series_list = sorted(sub["series"].dropna().astype(str).unique())
        spick = st.sidebar.multiselect("Series", options=series_list, default=series_list)
        sub = sub[sub["series"].isin(spick)] if spick else sub
        sub = sub.copy()
        sub["period"] = _parse_time_period(sub["time_period"])
        ch = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("period:T", title="Month"),
                y=alt.Y("value:Q", title="Value"),
                color=alt.Color("series:N"),
                tooltip=["time_period", "table_block", "series", "value"],
            )
            .properties(height=400)
        )
        st.subheader("Time series")
        st.altair_chart(ch, width=ST_WIDTH)

    elif table in _LA_SHEETS:
        metrics = sorted(view["metric"].dropna().astype(str).unique())
        met = st.sidebar.selectbox("Metric", options=metrics, index=0)
        sub = view[view["metric"].astype(str) == met].copy()
        sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
        top_n = st.sidebar.slider("Top LAs by value (chart)", 5, 50, 15)
        agg = sub.nlargest(top_n, "value")
        ch = (
            alt.Chart(agg)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title=str(met)),
                y=alt.Y("area_name:N", sort="-x", title="Area"),
                tooltip=["country_group", "area_code", "area_name", "metric", "value"],
            )
            .properties(height=min(480, 24 * len(agg)))
        )
        st.subheader("Bar chart (top by selected metric)")
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_uk_hpi_monthly_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
