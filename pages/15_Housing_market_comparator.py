"""Streamlit: two-lane housing market comparator (LA snapshot vs region snapshot)."""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_LA_STEM = "joined_la_housing_market_snapshot"
_REG_STEM = "region_housing_market_snapshot"


def _meta_path(stem: str) -> Path:
    return PROCESSED_DIR / f"{stem}.meta.json"


def main() -> None:
    st.set_page_config(page_title="Housing market comparator", layout="wide")
    st.title("Housing market comparator (two lanes)")
    st.caption(
        "**Lane A** — local authorities: supply, Census population (where available), median price (HPSSA), optional **price/earnings** (ONS tables 5a–5c), main fuel pivots, optional HPI. "
        "**Lane B** — regions: aggregated supply, EPC band shares, five-year rolling EPC C+, **Census population summed to region**."
    )
    st.divider()
    ogl_attribution_expander()
    with st.expander("How to build snapshot files"):
        st.markdown(
            "Run `python joins/build_la_housing_market_snapshot.py` "
            "→ `data/processed/joined_la_housing_market_snapshot.parquet` and "
            "`region_housing_market_snapshot.parquet`."
        )

    lane = st.sidebar.radio("Lane", ("A — Local authority", "B — Region"), horizontal=True)

    la_path = PROCESSED_DIR / f"{_LA_STEM}.parquet"
    reg_path = PROCESSED_DIR / f"{_REG_STEM}.parquet"

    if lane.startswith("A"):
        if not la_path.is_file():
            st.warning(f"Missing `{la_path.name}`. Run `python joins/build_la_housing_market_snapshot.py`.")
            return
        df = load_processed_parquet(str(la_path))
        meta = {}
        mp = _meta_path(_LA_STEM)
        if mp.is_file():
            meta = json.loads(mp.read_text(encoding="utf-8"))
        st.subheader("Lane A — Local authority snapshot")
        if meta:
            st.caption(
                f"Supply FY: **{meta.get('supply_financial_year', '—')}** · "
                f"Median price period: **{meta.get('median_price_period_label', '—')}** · "
                f"Editions: HB `{meta.get('housebuilding_edition')}`, "
                f"fuel `{meta.get('mainfuel_edition')}`, "
                f"median `{meta.get('median_existing_admin_edition')}`"
                + (f", HPI `{meta.get('uk_hpi_edition')}`" if meta.get("uk_hpi_edition") else "")
            )
            if meta.get("caveat"):
                st.info(meta["caveat"])

        view = df.copy()
        view["population"] = pd.to_numeric(view.get("population"), errors="coerce")
        view["supply_starts"] = pd.to_numeric(view.get("supply_starts"), errors="coerce")
        view["median_price_existing_gbp"] = pd.to_numeric(view.get("median_price_existing_gbp"), errors="coerce")
        view["starts_per_1000"] = np.where(
            view["population"].notna() & (view["population"] > 0),
            view["supply_starts"] / view["population"] * 1000.0,
            np.nan,
        )

        xopt = st.sidebar.selectbox(
            "X axis",
            options=["starts_per_1000", "supply_starts", "population"],
            format_func=lambda x: {
                "starts_per_1000": "Starts per 1,000 population",
                "supply_starts": "Starts (dwellings)",
                "population": "Population (Census 2021)",
            }[x],
        )
        yopt = st.sidebar.selectbox("Y axis", options=["median_price_existing_gbp"], format_func=lambda x: "Median price existing (£)")

        plot_df = view.dropna(subset=[xopt, yopt], how="any")
        if not plot_df.empty:
            ch = (
                alt.Chart(plot_df)
                .mark_circle(size=60)
                .encode(
                    x=alt.X(f"{xopt}:Q", title=xopt.replace("_", " ")),
                    y=alt.Y(f"{yopt}:Q", title="Median price (£)"),
                    tooltip=["lad_code", "la_name", "region_name", xopt, yopt, "supply_financial_year"],
                )
                .properties(height=420)
            )
            st.altair_chart(ch, width=ST_WIDTH)

        st.subheader("Data")
        st.dataframe(view, width=ST_WIDTH, height=min(560, 120 + 28 * min(len(view), 35)))
        st.download_button(
            "Download Lane A as CSV",
            data=view.to_csv(index=False).encode("utf-8"),
            file_name=f"{_LA_STEM}.csv",
            mime="text/csv",
        )
        return

    if not reg_path.is_file():
        st.warning(f"Missing `{reg_path.name}`. Run `python joins/build_la_housing_market_snapshot.py`.")
        return
    df = load_processed_parquet(str(reg_path))
    meta = {}
    mp = _meta_path(_REG_STEM)
    if mp.is_file():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    st.subheader("Lane B — Region snapshot")
    if meta:
        st.caption(
            f"Supply FY: **{meta.get('supply_financial_year', '—')}** · "
            f"EE rolling: **{meta.get('ee_rolling_period', '—')}** · "
            f"EPC `{meta.get('epc_edition')}`, EE `{meta.get('ee_fiveyear_edition')}`"
        )
        if meta.get("caveat"):
            st.info(meta["caveat"])

    view = df.copy()
    ch = (
        alt.Chart(view)
        .mark_bar()
        .encode(
            x=alt.X("ee_epc_c_plus_pct:Q", title="EPC C+ share (five-year rolling, %)"),
            y=alt.Y("region_name:N", sort="-x", title="Region"),
            tooltip=[
                "region_name",
                "region_supply_starts",
                "region_supply_completions",
                "epc_pct_bands_abc",
                "ee_epc_c_plus_pct",
            ],
        )
        .properties(height=min(400, 28 * len(view)))
    )
    st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(560, 120 + 28 * min(len(view), 25)))
    st.download_button(
        "Download Lane B as CSV",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name=f"{_REG_STEM}.csv",
        mime="text/csv",
    )


main()
