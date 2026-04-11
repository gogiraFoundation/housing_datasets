"""Streamlit: ONS main fuel / central heating (England and Wales) — tidy Parquet from ons_mainfuel_etl.py."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_mainfuel_config import DATASET_PAGE, MAINFUEL_DATA_SHEETS, MAINFUEL_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_mainfuel_{edition}_{table}_tidy.parquet"


def load_mainfuel_table(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def main() -> None:
    st.set_page_config(page_title="Main fuel — central heating", layout="wide")
    st.title("Main fuel type / central heating (England and Wales)")
    st.caption(
        "ONS statistics on main fuel or method of heating. "
        "Outputs come from `python ons_mainfuel_etl.py` → `data/processed/ons_mainfuel_*_*_tidy.parquet`."
    )

    st.divider()
    ogl_attribution_expander()
    st.markdown(
        f"[Dataset page (ONS)]({DATASET_PAGE}) · Housing Analysis team · typical release: March each year."
    )

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(MAINFUEL_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({MAINFUEL_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(MAINFUEL_DATA_SHEETS),
        format_func=lambda t: {
            "1a": "1a — By country or region",
            "1b": "1b — Existing vs new dwellings",
            "1c": "1c — By property type",
            "2a": "2a — By local authority",
            "2b": "2b — By MSOA",
            "3a": "3a — By property type (alt)",
            "3b": "3b — By property type (alt 2)",
        }.get(t, t),
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_mainfuel_etl.py --edition "
            + edition
            + "\n# or: python ons_mainfuel_etl.py --transform-only -i path/to/workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_mainfuel_table(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    if "country_or_region_name" in view.columns:
        view["country_or_region_name"] = view["country_or_region_name"].astype(str).str.strip()
        regions = sorted(view["country_or_region_name"].dropna().astype(str).unique())
        pick = st.sidebar.multiselect(
            "Country or region",
            options=regions,
            default=[regions[0]] if regions else [],
            help="Empty = show all rows.",
        )
        view = view[view["country_or_region_name"].isin(pick)] if pick else view
    elif "local_authority_district_name" in view.columns:
        view["local_authority_district_name"] = view["local_authority_district_name"].astype(str).str.strip()
        top_n = st.sidebar.slider("Top LAs by first fuel value (chart)", 5, 40, 15)
        gas = view[view["fuel_or_method"].astype(str).str.contains("Mains gas", case=False, na=False)]
        if not gas.empty:
            gas = gas.copy()
            gas["value"] = pd.to_numeric(gas["value"], errors="coerce")
            agg = (
                gas.groupby("local_authority_district_name", observed=True)["value"]
                .mean()
                .sort_values(ascending=False)
                .head(top_n)
            )
            ch = (
                alt.Chart(agg.reset_index())
                .mark_bar()
                .encode(
                    x=alt.X("value:Q", title="Value (%)"),
                    y=alt.Y("local_authority_district_name:N", sort="-x", title="Local authority"),
                )
                .properties(height=min(400, 24 * len(agg)))
            )
            st.subheader("Bar chart (mains gas — 2a)")
            st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_mainfuel_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
