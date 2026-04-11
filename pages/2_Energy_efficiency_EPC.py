"""Streamlit: ONS energy efficiency — Individual EPC Bands (tidy Parquet from ons_epc_etl.py)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_epc_config import DATASET_PAGE, EPC_DATA_SHEETS, EPC_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_epc_bands_{edition}_{table}_tidy.parquet"


def load_epc_table(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def _chart_for_dimensional_table(view: pd.DataFrame, dimension_col: str, chart_title: str) -> alt.Chart:
    """Build grouped line chart for 1b/1c/1d tables across EPC bands."""
    chart_df = view.copy()
    chart_df["epc_band"] = chart_df["epc_band"].astype(str)
    chart_df["percentage"] = pd.to_numeric(chart_df["percentage"], errors="coerce")
    chart_df = chart_df.dropna(subset=["percentage"])
    return (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("epc_band:N", title="EPC band", sort=list("ABCDEFG")),
            y=alt.Y("percentage:Q", title="% of dwellings"),
            color=alt.Color(f"{dimension_col}:N", title=chart_title),
            tooltip=[
                "country_or_region_name",
                alt.Tooltip(f"{dimension_col}:N", title=chart_title),
                "epc_band",
                alt.Tooltip("percentage", format=".2f"),
            ],
        )
        .properties(height=360)
    )


def main() -> None:
    st.set_page_config(page_title="Energy efficiency — EPC bands", layout="wide")
    st.title("Energy efficiency: Individual EPC bands (England and Wales)")
    st.caption(
        "ONS statistics on the distribution of dwellings across EPC rating bands (A–G). "
        "Outputs come from `python ons_epc_etl.py` → `data/processed/ons_epc_bands_*_*_tidy.parquet`."
    )

    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE}) · Housing Analysis team · typical release: October each year.")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(EPC_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({EPC_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(EPC_DATA_SHEETS),
        format_func=lambda t: {
            "1a": "1a — Bands by country and region",
            "1b": "1b — Bands by property type",
            "1c": "1c — Bands by property age",
            "1d": "1d — Bands for new vs existing dwellings",
        }[t],
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_epc_etl.py --edition " + edition + "\n# or: python ons_epc_etl.py --transform-only -i path/to/workbook.xlsx --edition " + edition,
            language="bash",
        )
        return

    df = load_epc_table(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    df = df.copy()
    df["country_or_region_name"] = df["country_or_region_name"].astype(str).str.strip()
    regions = sorted(df["country_or_region_name"].dropna().astype(str).unique())
    pick = st.sidebar.multiselect(
        "Country or region",
        options=regions,
        default=[regions[0]] if regions else [],
        help="Empty = show all rows in the table below.",
    )
    view = df[df["country_or_region_name"].isin(pick)] if pick else df

    if view.empty:
        st.info("No rows for the selected regions.")
        return

    st.subheader("Band profile (chart)")
    if table == "1a" and len(pick) == 1:
        one = view.copy()
        ch = (
            alt.Chart(one)
            .mark_bar()
            .encode(
                x=alt.X("epc_band:N", title="EPC band", sort=list("ABCDEFG")),
                y=alt.Y("percentage:Q", title="% of dwellings"),
                tooltip=["country_or_region_name", "epc_band", alt.Tooltip("percentage", format=".2f")],
            )
            .properties(height=320)
        )
        st.altair_chart(ch, width=ST_WIDTH)
    elif table == "1a" and len(pick) > 1:
        ch = (
            alt.Chart(view)
            .mark_line(point=True)
            .encode(
                x=alt.X("epc_band:N", sort=list("ABCDEFG")),
                y=alt.Y("percentage:Q", title="% of dwellings"),
                color="country_or_region_name:N",
                tooltip=["country_or_region_name", "epc_band", alt.Tooltip("percentage", format=".2f")],
            )
            .properties(height=360)
        )
        st.altair_chart(ch, width=ST_WIDTH)
    elif table == "1a" and not pick:
        st.caption("Select one or more regions in the sidebar to draw the EPC band chart.")
    elif table == "1b":
        st.altair_chart(
            _chart_for_dimensional_table(view, "property_type", "Property type"),
            width=ST_WIDTH,
        )
    elif table == "1c":
        st.altair_chart(
            _chart_for_dimensional_table(view, "property_age_band", "Property age band"),
            width=ST_WIDTH,
        )
    elif table == "1d":
        st.altair_chart(
            _chart_for_dimensional_table(view, "dwelling_age_class", "Dwelling class"),
            width=ST_WIDTH,
        )
    else:
        st.caption("No chart available for this table selection.")

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_epc_bands_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
