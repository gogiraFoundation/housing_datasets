"""Streamlit: ONS median price paid by administrative geography (all, existing, or newly built dwellings)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_median_price_admin_config import (
    ALL_DATASET_PAGE,
    EXISTING_DATASET_PAGE,
    MEDIAN_PRICE_ALL_ADMIN_EDITIONS,
    MEDIAN_PRICE_ADMIN_DATA_SHEETS,
    MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS,
    MEDIAN_PRICE_NEW_ADMIN_EDITIONS,
    NEW_DATASET_PAGE,
)
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _expected_parquet_path(edition: str, table: str, *, dwelling: str) -> Path:
    prefix = {
        "all": "ons_median_price_all_admin",
        "existing": "ons_median_price_existing_admin",
        "new": "ons_median_price_new_admin",
    }[dwelling]
    return PROCESSED_DIR / f"{prefix}_{edition}_{table}_tidy.parquet"


def _label_column(df: pd.DataFrame) -> str | None:
    """Pick a human-readable geography column for filtering."""
    for prefer in (
        "local_authority_name",
        "county_unitary_authority_name",
        "combined_authority_name",
        "region_country_name",
        "area_name",
    ):
        if prefer in df.columns:
            return prefer
    for c in df.columns:
        if c.endswith("_name"):
            return c
    return None


def main() -> None:
    st.set_page_config(page_title="Median price — admin geographies", layout="wide")
    st.title("Median house prices — administrative geographies")
    st.caption(
        "ONS **HPSSA-style** tables: median price paid by region, local authority, county, or combined authority. "
        "Run `python ons_median_price_admin_etl.py --dataset all|existing|new --edition <key>`."
    )
    st.divider()
    ogl_attribution_expander()
    st.info(
        "**Coverage vs legacy explorer:** this workbook uses **rolling-year quarters** and current HPSSA-style "
        "admin geographies (see edition notes). For **1995–2013 LA medians** from the static legacy workbook only, "
        "use **House Price Explorer** in the sidebar — definitions differ; do not chain the series without documentation."
    )
    st.markdown(
        f"[All dwellings (ONS)]({ALL_DATASET_PAGE}) · [Existing dwellings (ONS)]({EXISTING_DATASET_PAGE}) · [Newly built dwellings (ONS)]({NEW_DATASET_PAGE})"
    )

    dwelling = st.sidebar.radio(
        "Dwelling type",
        options=("all", "existing", "new"),
        format_func=lambda x: {
            "all": "All dwellings",
            "existing": "Existing dwellings",
            "new": "Newly built dwellings",
        }[x],
        horizontal=True,
    )
    editions = {
        "all": MEDIAN_PRICE_ALL_ADMIN_EDITIONS,
        "existing": MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS,
        "new": MEDIAN_PRICE_NEW_ADMIN_EDITIONS,
    }[dwelling]
    edition = st.sidebar.selectbox(
        "Edition",
        options=list(editions.keys()),
        format_func=lambda k: f"{k} ({editions[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(MEDIAN_PRICE_ADMIN_DATA_SHEETS),
        format_func=lambda t: {
            "1a": "1a — By region / country (all types)",
            "1b": "1b — Detached",
            "1c": "1c — Semi-detached",
            "1d": "1d — Terraced",
            "1e": "1e — Flats / maisonettes",
            "2a": "2a — By local authority (all types)",
            "2b": "2b — LA — detached",
            "2c": "2c — LA — semi-detached",
            "2d": "2d — LA — terraced",
            "2e": "2e — LA — flats",
            "3a": "3a — By county / unitary (all types)",
            "3b": "3b — County — detached",
            "3c": "3c — County — semi-detached",
            "3d": "3d — County — terraced",
            "3e": "3e — County — flats",
            "4a": "4a — Combined authorities (all types)",
            "4b": "4b — Combined — detached",
            "4c": "4c — Combined — semi-detached",
            "4d": "4d — Combined — terraced",
            "4e": "4e — Combined — flats",
        }.get(t, t),
    )

    path = _expected_parquet_path(edition, table, dwelling=dwelling)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_median_price_admin_etl.py --dataset "
            + dwelling
            + " --edition "
            + edition
            + "\n# or: python ons_median_price_admin_etl.py --transform-only -i workbook.xlsx --dataset "
            + dwelling
            + " --edition "
            + edition,
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    view["median_price_gbp"] = pd.to_numeric(view["median_price_gbp"], errors="coerce")

    label_col = _label_column(view)
    if label_col:
        names = sorted(view[label_col].dropna().astype(str).unique())
        pick = st.sidebar.multiselect(label_col.replace("_", " ").title(), options=names, default=names[: min(3, len(names))])
        view = view[view[label_col].isin(pick)] if pick else view

    view["period_sort"] = pd.to_datetime(
        view["period_label"].astype(str).str.replace("^Year ending ", "", regex=True),
        format="%b %Y",
        errors="coerce",
    )
    enc: dict = {
        "x": alt.X("period_sort:T", title="Period (rolling year)"),
        "y": alt.Y("median_price_gbp:Q", title="Median price (£)"),
    }
    tip = ["period_label", "median_price_gbp", "geography_level", "property_band"]
    if label_col:
        enc["color"] = alt.Color(f"{label_col}:N")
        tip.append(label_col)
    else:
        enc["color"] = alt.value("steelblue")
    ch = alt.Chart(view).mark_line(point=True).encode(**enc, tooltip=tip).properties(height=400)
    st.subheader("Time series")
    st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    show = view.drop(columns=["period_sort"], errors="ignore")
    st.dataframe(show, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(show), 40)))

    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"median_price_admin_{dwelling}_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
