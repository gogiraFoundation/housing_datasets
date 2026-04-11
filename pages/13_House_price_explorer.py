"""Streamlit: ONS House Price Explorer (legacy LA workbook, 1995–2013)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_house_price_explorer_config import (
    DATASET_PAGE,
    HOUSE_PRICE_EXPLORER_DATA_SHEETS,
    HOUSE_PRICE_EXPLORER_EDITIONS,
    HOUSE_PRICE_EXPLORER_SHEET_SLUGS,
)
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _expected_parquet_path(edition: str, sheet: str) -> Path:
    slug = HOUSE_PRICE_EXPLORER_SHEET_SLUGS[sheet]
    return PROCESSED_DIR / f"ons_house_price_explorer_{edition}_{slug}_tidy.parquet"


def main() -> None:
    st.set_page_config(page_title="House Price Explorer", layout="wide")
    st.title("House Price Explorer (legacy)")
    st.caption(
        "ONS **1995–2013** local authority median prices and sale counts; static workbook. "
        "Run `python ons_house_price_explorer_etl.py --edition current`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE})")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(HOUSE_PRICE_EXPLORER_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({HOUSE_PRICE_EXPLORER_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Sheet",
        options=list(HOUSE_PRICE_EXPLORER_DATA_SHEETS),
        format_func=lambda t: {
            "1. Price Data": "1 — Median price by LA (annual)",
            "2. Count Data Totals": "2 — Sale counts (totals by LA)",
            "3. Count Data": "3 — Sale counts by type and year",
            "4.Type Price Data": "4 — Median price by LA and property type (snapshot)",
        }.get(t, t),
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_house_price_explorer_etl.py --edition " + edition,
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    kind = view["table_kind"].iloc[0] if len(view) else ""

    if kind in ("median_price", "sale_count_total") and "year" in view.columns:
        view["year"] = pd.to_numeric(view["year"], errors="coerce")
        las = sorted(view["la_name"].dropna().astype(str).unique())
        pick = st.sidebar.multiselect("Local authority", options=las, default=las[: min(5, len(las))])
        sub = view[view["la_name"].isin(pick)] if pick else view
        ytitle = "Median price (£)" if kind == "median_price" else "Sales count"
        ch = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y("value:Q", title=ytitle),
                color=alt.Color("la_name:N"),
                tooltip=["la_name", "la_code", "year", "value", "table_kind"],
            )
            .properties(height=400)
        )
        st.subheader("Time series")
        st.altair_chart(ch, width=ST_WIDTH)

    elif kind == "count_by_type" and "year" in view.columns:
        las = sorted(view["la_name"].dropna().astype(str).unique())
        pick = st.sidebar.multiselect("Local authority", options=las, default=las[: min(3, len(las))])
        sub = view[view["la_name"].isin(pick)] if pick else view
        props = sorted(sub["property_type"].dropna().unique())
        pp = st.sidebar.multiselect("Property type", options=props, default=props[:4])
        sub = sub[sub["property_type"].isin(pp)] if pp else sub
        ch = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y("value:Q", title="Count"),
                color=alt.Color("property_type:N"),
                strokeDash=alt.StrokeDash("la_name:N"),
                tooltip=["la_name", "year", "property_type", "value"],
            )
            .properties(height=400)
        )
        st.subheader("Counts by type")
        st.altair_chart(ch, width=ST_WIDTH)

    elif kind == "median_by_type_snapshot":
        sub = view.copy()
        sub["median_price_gbp"] = pd.to_numeric(sub["median_price_gbp"], errors="coerce")
        top_n = st.sidebar.slider("Top LAs by max median (chart)", 5, 40, 15)
        mx = sub.groupby("la_name", observed=True)["median_price_gbp"].max().sort_values(ascending=False)
        pick = list(mx.head(top_n).index)
        sub = sub[sub["la_name"].isin(pick)]
        ch = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x=alt.X("median_price_gbp:Q", title="Median (£)"),
                y=alt.Y("la_name:N", sort="-x", title="Local authority"),
                color=alt.Color("property_type:N"),
                tooltip=["la_name", "property_type", "median_price_gbp"],
            )
            .properties(height=min(480, 24 * len(sub["la_name"].unique())))
        )
        st.subheader("Median by property type (snapshot)")
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_house_price_explorer_{edition}_{HOUSE_PRICE_EXPLORER_SHEET_SLUGS[table]}_filtered.csv",
        mime="text/csv",
    )


main()
