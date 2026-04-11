"""Streamlit: ONS energy efficiency — five-year rolling tables (tidy Parquet from ons_ee_fiveyear_etl.py)."""

from __future__ import annotations

import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_ee_fiveyear_config import DATASET_PAGE, EE_DATA_SHEETS, EE_FIVEYEAR_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_PERIOD_START_YEAR = re.compile(r"^Q2 (\d{4})")

EE_TABLE_LABELS: dict[str, str] = {
    "1a": "1a — Median energy efficiency score (all dwellings)",
    "1b": "1b — Median score by property type",
    "1c": "1c — % dwellings EPC band C or above",
    "1d": "1d — % dwellings EPC band C, by property type",
    "2a": "2a — Median CO₂ emissions (all / new / existing)",
    "2b": "2b — Median CO₂ emissions by property type",
    "3a": "3a — % community heating",
    "3b": "3b — % electricity",
    "3c": "3c — % mains gas",
    "3d": "3d — % oil",
    "3e": "3e — % other and unknown",
    "3f": "3f — % renewable (incl. heat pumps)",
    "3g": "3g — % two or more (incl. renewable)",
    "3h": "3h — % two or more (not incl. renewable)",
}


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_ee_fiveyear_{edition}_{table}_tidy.parquet"


def load_ee_table(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def _rolling_period_sort_key(period: str) -> int:
    m = _PERIOD_START_YEAR.match(str(period).strip())
    return int(m.group(1)) if m else 0


def _ordered_rolling_periods(series: pd.Series) -> list[str]:
    uniq = series.dropna().astype(str).unique()
    return sorted(uniq, key=_rolling_period_sort_key)


def main() -> None:
    st.set_page_config(page_title="Energy efficiency — five-year rolling", layout="wide")
    st.title("Energy efficiency: five-year rolling (England and Wales)")
    st.caption(
        "ONS statistics on energy efficiency, EPC band C+, CO₂ emissions, and main heating fuel "
        "over five-year rolling windows. Outputs come from `python ons_ee_fiveyear_etl.py` → "
        "`data/processed/ons_ee_fiveyear_*_*_tidy.parquet`."
    )

    st.divider()
    ogl_attribution_expander()
    st.markdown(
        f"[Dataset page (ONS)]({DATASET_PAGE}) · Housing Analysis team · typical release: October each year."
    )

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(EE_FIVEYEAR_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({EE_FIVEYEAR_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(EE_DATA_SHEETS),
        format_func=lambda t: EE_TABLE_LABELS.get(t, t),
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_ee_fiveyear_etl.py --edition "
            + edition
            + "\n# or: python ons_ee_fiveyear_etl.py --transform-only -i path/to/workbook.xlsx --edition "
            + edition,
            language="bash",
        )
        return

    df = load_ee_table(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    df = df.copy()
    df["country_or_region_name"] = df["country_or_region_name"].astype(str).str.strip()
    regions = sorted(df["country_or_region_name"].dropna().astype(str).unique())
    breakdowns = sorted(df["measure_breakdown"].dropna().astype(str).unique())

    pick_regions = st.sidebar.multiselect(
        "Country or region",
        options=regions,
        default=[regions[0]] if regions else [],
        help="Empty = all rows in the table below.",
    )
    default_breakdown: list[str] = []
    if "All" in breakdowns:
        default_breakdown = ["All"]
    pick_breakdown = st.sidebar.multiselect(
        "Measure breakdown",
        options=breakdowns,
        default=default_breakdown,
        help="Empty = all breakdowns (can be busy on the chart).",
    )

    view = df
    if pick_regions:
        view = view[view["country_or_region_name"].isin(pick_regions)]
    if pick_breakdown:
        view = view[view["measure_breakdown"].isin(pick_breakdown)]

    if view.empty:
        st.info("No rows for the current filters.")
        return

    period_order = _ordered_rolling_periods(view["rolling_period"])
    chart_df = view.copy()
    chart_df["value"] = pd.to_numeric(chart_df["value"], errors="coerce")
    chart_df = chart_df.dropna(subset=["value"])

    st.subheader("Trend (chart)")
    if chart_df.empty:
        st.caption("No numeric values to plot for the current filters.")
    elif not period_order:
        st.caption("No rolling periods in the filtered data.")
    else:
        ch = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "rolling_period:N",
                    title="Five-year rolling period",
                    sort=period_order,
                ),
                y=alt.Y("value:Q", title="Value"),
                color=alt.Color("measure_breakdown:N", title="Breakdown"),
                detail="measure_breakdown:N",
                strokeDash=alt.StrokeDash(
                    "country_or_region_name:N",
                    title="Region",
                ),
                tooltip=[
                    "country_or_region_name",
                    "measure_breakdown",
                    "rolling_period",
                    alt.Tooltip("value", format=".4f"),
                ],
            )
            .properties(height=400)
        )
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_ee_fiveyear_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
