"""Streamlit: ONS house building by local authority (starts + completions)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from housing_data.housebuilding_la import (
    filter_housebuilding_la,
    line_by_year_chart,
    prepare_housebuilding_la_df,
    sorted_financial_years,
)
from ons_housebuilding_la_config import DATASET_PAGE, HOUSEBUILDING_LA_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

def _expected_parquet_filename(edition: str) -> str:
    return f"ons_housebuilding_la_{edition}_tidy.parquet"


def load_table(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def main() -> None:
    st.set_page_config(page_title="House building by local authority", layout="wide")
    st.title("House building by local authority: starts and completions (UK)")
    st.caption(
        "ONS annual local-authority house building dataset. Outputs come from "
        "`python ons_housebuilding_la_etl.py` → "
        "`data/processed/ons_housebuilding_la_*_tidy.parquet`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE}) · Housing Analysis team")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(HOUSEBUILDING_LA_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({HOUSEBUILDING_LA_EDITIONS[k].label})",
        index=0,
    )

    filename = _expected_parquet_filename(edition)
    path = PROCESSED_DIR / filename
    if not path.is_file():
        st.warning(f"No tidy file at `{filename}` in `{PROCESSED_DIR}`.")
        st.code(
            "python ons_housebuilding_la_etl.py --edition "
            + edition
            + "\n# or: python ons_housebuilding_la_etl.py --transform-only -i path/to/workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_table(filename)
    st.sidebar.success(f"Loaded `{filename}` ({len(df):,} rows)")

    df = prepare_housebuilding_la_df(df)

    all_years = sorted_financial_years(df["financial_year"])
    regions = sorted(df["Region or Country Name"].dropna().astype(str).unique())
    las = sorted(df["Local Authority Name"].dropna().astype(str).unique())

    metric_pick = st.sidebar.multiselect(
        "Measure",
        options=["starts", "completions"],
        default=["starts", "completions"],
    )
    region_pick = st.sidebar.multiselect(
        "Region or country",
        options=regions,
        default=[],
    )
    la_pick = st.sidebar.multiselect(
        "Local authority",
        options=las,
        default=[],
    )
    y_min = st.sidebar.selectbox("Financial year from", options=all_years, index=0)
    y_max = st.sidebar.selectbox("Financial year to", options=all_years, index=len(all_years) - 1)
    if all_years.index(y_min) > all_years.index(y_max):
        y_min, y_max = y_max, y_min

    view, _ = filter_housebuilding_la(
        df,
        financial_year_min=y_min,
        financial_year_max=y_max,
        measures=metric_pick if metric_pick else None,
        regions=region_pick if region_pick else None,
        local_authorities=la_pick if la_pick else None,
    )

    if view.empty:
        st.info("No rows for the current filters.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total dwellings", int(view["dwellings"].sum(skipna=True)))
    c2.metric("Local authorities in view", f"{view['Local Authority Name'].nunique():,}")
    c3.metric("Financial years in view", f"{view['financial_year'].nunique():,}")

    line = line_by_year_chart(view, year_order=all_years)
    st.altair_chart(line, width=ST_WIDTH)

    st.subheader("Filtered data")
    st.dataframe(view, width=ST_WIDTH, height=min(650, 120 + 30 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_housebuilding_la_{edition}_filtered.csv",
        mime="text/csv",
    )


main()
