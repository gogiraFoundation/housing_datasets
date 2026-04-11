"""Streamlit: ONS house building by country (starts + completions)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_housebuilding_country_config import DATASET_PAGE, HOUSEBUILDING_COUNTRY_EDITIONS
from ons_housebuilding_country_periods import preferred_period_order
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _expected_parquet_path(edition: str) -> Path:
    return PROCESSED_DIR / f"ons_housebuilding_country_{edition}_tidy.parquet"


def load_table(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def main() -> None:
    st.set_page_config(page_title="House building by country", layout="wide")
    st.title("House building by country: starts and completions (UK)")
    st.caption(
        "ONS country-level starts/completions dataset (quarterly and annual). "
        "Outputs come from `python ons_housebuilding_country_etl.py` → "
        "`data/processed/ons_housebuilding_country_*_tidy.parquet`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE}) · Housing Analysis team")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(HOUSEBUILDING_COUNTRY_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({HOUSEBUILDING_COUNTRY_EDITIONS[k].label})",
        index=0,
    )
    path = _expected_parquet_path(edition)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_housebuilding_country_etl.py --edition "
            + edition
            + "\n# or: python ons_housebuilding_country_etl.py --transform-only -i path/to/workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_table(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    countries = sorted(df["country_name"].dropna().astype(str).unique())
    freqs = sorted(df["frequency"].dropna().astype(str).unique())
    measures = sorted(df["measure"].dropna().astype(str).unique())
    sectors = sorted(df["sector"].dropna().astype(str).unique())

    pick_country = st.sidebar.multiselect("Country", countries, default=["United Kingdom"])
    pick_freq = st.sidebar.multiselect("Frequency", freqs, default=freqs)
    pick_measure = st.sidebar.multiselect("Measure", measures, default=measures)
    pick_sector = st.sidebar.multiselect("Sector", sectors, default=["All Dwellings"] if "All Dwellings" in sectors else [])

    view = df.copy()
    if pick_country:
        view = view[view["country_name"].isin(pick_country)]
    if pick_freq:
        view = view[view["frequency"].isin(pick_freq)]
    if pick_measure:
        view = view[view["measure"].isin(pick_measure)]
    if pick_sector:
        view = view[view["sector"].isin(pick_sector)]

    view["dwellings"] = pd.to_numeric(view["dwellings"], errors="coerce")
    if view.empty:
        st.info("No rows for the current filters.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total dwellings", int(view["dwellings"].sum(skipna=True)))
    c2.metric("Periods in view", f"{view['period'].nunique():,}")
    c3.metric("Countries in view", f"{view['country_name'].nunique():,}")

    plot = view.dropna(subset=["dwellings"]).copy()
    plot["series"] = plot["country_name"] + " | " + plot["measure"] + " | " + plot["sector"] + " | " + plot["frequency"]
    if not plot.empty:
        period_order = preferred_period_order(plot["period"])
        ch = (
            alt.Chart(plot)
            .mark_line(point=False)
            .encode(
                x=alt.X("period:N", title="Period", sort=period_order),
                y=alt.Y("dwellings:Q", title="Dwellings"),
                color=alt.Color("series:N", title="Series"),
                tooltip=["country_name", "frequency", "period", "measure", "sector", alt.Tooltip("dwellings", format=",.0f")],
            )
            .properties(height=400)
        )
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Filtered data")
    st.dataframe(view, width=ST_WIDTH, height=min(650, 120 + 30 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_housebuilding_country_{edition}_filtered.csv",
        mime="text/csv",
    )


main()
