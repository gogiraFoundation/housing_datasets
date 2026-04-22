"""Streamlit: short policy-style narrative — supply vs stock efficiency (explicit period labels)."""

from __future__ import annotations

import re

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_ee_fiveyear_config import EE_FIVEYEAR_EDITIONS
from ons_housebuilding_la_config import HOUSEBUILDING_LA_EDITIONS
from ons_mainfuel_config import MAINFUEL_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def main() -> None:
    st.set_page_config(page_title="Housing + energy narrative", layout="wide")
    st.title("Housing supply and energy performance (England and Wales)")
    st.caption(
        "Each section uses a **different time basis**. Read the subtitle before interpreting charts."
    )
    st.divider()
    ogl_attribution_expander()

    with st.sidebar.expander("Data editions", expanded=True):
        hb_ed = st.selectbox(
            "House building edition",
            list(HOUSEBUILDING_LA_EDITIONS.keys()),
            format_func=lambda k: HOUSEBUILDING_LA_EDITIONS[k].label,
        )
        ee_ed = st.selectbox(
            "Five-year rolling edition",
            list(EE_FIVEYEAR_EDITIONS.keys()),
            format_func=lambda k: EE_FIVEYEAR_EDITIONS[k].label,
        )
        mf_ed = st.selectbox(
            "Main fuel edition (LA snapshot)",
            list(MAINFUEL_EDITIONS.keys()),
            format_func=lambda k: MAINFUEL_EDITIONS[k].label,
        )

    hb_path = PROCESSED_DIR / f"ons_housebuilding_la_{hb_ed}_tidy.parquet"
    ee_path = PROCESSED_DIR / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet"
    mf_path = PROCESSED_DIR / f"ons_mainfuel_{mf_ed}_2a_tidy.parquet"

    st.subheader("1. Supply — ONS house building by local authority")
    st.caption(
        f"**Period:** financial years in the LA dataset · **Edition:** {HOUSEBUILDING_LA_EDITIONS[hb_ed].label}"
    )
    if not hb_path.is_file():
        st.warning(f"Missing `{hb_path.name}`. Run: `python ons_housebuilding_la_etl.py --edition {hb_ed}`")
    else:
        hb = load_processed_parquet(str(hb_path))
        eng = hb[hb["Local Authority Code"].astype(str).str.startswith("E")].copy()
        by = (
            eng.groupby("financial_year", observed=True, dropna=False)["dwellings"]
            .sum(min_count=1)
            .reset_index()
            .sort_values("financial_year")
        )
        ch = (
            alt.Chart(by)
            .mark_line(point=True)
            .encode(
                x=alt.X("financial_year:N", title="Financial year"),
                y=alt.Y("dwellings:Q", title="Dwellings (England LAs summed)"),
            )
            .properties(height=280)
        )
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("2. Stock — share of dwellings EPC band C or above (rolling windows)")
    st.caption(
        f"**Period:** five-year rolling windows ending in the edition · **Table 1c** · **Edition:** {EE_FIVEYEAR_EDITIONS[ee_ed].label}"
    )
    if not ee_path.is_file():
        st.warning(f"Missing `{ee_path.name}`. Run: `python ons_ee_fiveyear_etl.py --edition {ee_ed}`")
    else:
        ee = load_processed_parquet(str(ee_path))
        sub = ee[ee["country_or_region_name"].astype(str).isin(["England", "Wales"])].copy()
        sub = sub[sub["measure_breakdown"].astype(str).str.strip() == "All"]
        def _rk(s: str) -> int:
            m = re.match(r"^Q2 (\d{4})", str(s).strip())
            return int(m.group(1)) if m else 0

        periods = sorted(sub["rolling_period"].astype(str).unique(), key=_rk)
        ch = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("rolling_period:N", title="Rolling period", sort=periods),
                y=alt.Y("value:Q", title="Share (%)"),
                color="country_or_region_name:N",
            )
            .properties(height=320)
        )
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("3. Heating — mains gas (LA snapshot, not aligned to financial year)")
    st.caption(
        f"**Period:** snapshot for the main fuel workbook · **Table 2a** · **Edition:** {MAINFUEL_EDITIONS[mf_ed].label}"
    )
    if not mf_path.is_file():
        st.warning(f"Missing `{mf_path.name}`. Run: `python ons_mainfuel_etl.py --edition {mf_ed}`")
    else:
        mf = load_processed_parquet(str(mf_path))
        gas = mf[mf["fuel_or_method"].astype(str).str.contains("Mains gas", case=False, na=False)] if "fuel_or_method" in mf.columns else mf.iloc[0:0]
        if gas.empty:
            st.info("No mains gas rows found in 2a; check fuel labels in the tidy file.")
        else:
            top = (
                gas.sort_values("value", ascending=False)
                .head(15)[["local_authority_district_name", "value"]]
                .rename(columns={"value": "pct_mains_gas"})
            )
            st.dataframe(top, width=ST_WIDTH)

    st.caption(
        "See `joins/README.md` for geography join rules. "
        "Do not treat the sections above as one harmonised time series without explicit alignment."
    )

    snap_p = PROCESSED_DIR / "joined_la_housing_market_snapshot.parquet"
    reg_p = PROCESSED_DIR / "region_housing_market_snapshot.parquet"
    with st.expander("Explore: starts per 1,000 vs regional rolling EPC C+ (Lane A + Lane B)"):
        st.caption(
            "**Y-axis is region-attributed:** five-year rolling EPC C+ % is published at region level only; "
            "each LA is shown with its parent region’s latest rolling value — not an LA-level EPC estimate."
        )
        if not snap_p.is_file() or not reg_p.is_file():
            st.info("Build `joined_la_housing_market_snapshot.parquet` and `region_housing_market_snapshot.parquet` to enable this chart.")
        else:
            la = load_processed_parquet(str(snap_p))
            reg = load_processed_parquet(str(reg_p))
            if "ee_epc_c_plus_pct" not in reg.columns or "region_name" not in la.columns:
                st.info("Snapshot files do not contain expected region EPC columns.")
            else:
                la = la.copy()
                la["population"] = pd.to_numeric(la.get("population"), errors="coerce")
                la["supply_starts"] = pd.to_numeric(la.get("supply_starts"), errors="coerce")
                la["starts_per_1000"] = np.where(
                    la["population"].notna() & (la["population"] > 0),
                    la["supply_starts"] / la["population"] * 1000.0,
                    np.nan,
                )
                rsub = reg[["region_name", "ee_epc_c_plus_pct"]].drop_duplicates(subset=["region_name"])
                plot = la.merge(rsub, on="region_name", how="inner")
                plot = plot.dropna(subset=["starts_per_1000", "ee_epc_c_plus_pct"])
                if plot.empty:
                    st.info("No overlapping rows after merge.")
                else:
                    chx = (
                        alt.Chart(plot)
                        .mark_circle(size=50, opacity=0.65)
                        .encode(
                            x=alt.X("starts_per_1000:Q", title="Starts per 1,000 population (Lane A)"),
                            y=alt.Y(
                                "ee_epc_c_plus_pct:Q",
                                title="EPC C+ % (five-year rolling — region value)",
                            ),
                            tooltip=["lad_code", "la_name", "region_name", "starts_per_1000", "ee_epc_c_plus_pct"],
                        )
                        .properties(height=380)
                    )
                    st.altair_chart(chx, width=ST_WIDTH)


main()
