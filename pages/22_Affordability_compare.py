"""Streamlit: compare workplace, residence-based, and new-build affordability ratios (table 1c)."""

from __future__ import annotations

import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_price_earnings_ratio_config import PRICE_EARNINGS_RATIO_EDITIONS
from ons_price_newbuild_workplace_earnings_ratio_config import NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS
from ons_price_residence_earnings_ratio_config import PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _path_workplace(ed: str) -> Path:
    return PROCESSED_DIR / f"ons_price_earnings_ratio_{ed}_1c_tidy.parquet"


def _path_residence(ed: str) -> Path:
    return PROCESSED_DIR / f"ons_price_residence_earnings_ratio_{ed}_1c_tidy.parquet"


def _path_newbuild(ed: str) -> Path:
    return PROCESSED_DIR / f"ons_price_newbuild_workplace_earnings_ratio_{ed}_1c_tidy.parquet"


def _label_column(df: pd.DataFrame) -> str | None:
    for prefer in ("local_authority_name", "name", "country_region_name"):
        if prefer in df.columns:
            return prefer
    for c in df.columns:
        if c.endswith("_name"):
            return c
    return None


def _period_sort_series(period_label: pd.Series) -> pd.Series:
    def one(x: object) -> pd.Timestamp:
        s = str(x).strip()
        if s == "5-Year Average":
            return pd.Timestamp("2099-12-31", tz=None)
        m = re.match(r"Year ending Sep (\d{4})", s)
        if m:
            return pd.Timestamp(year=int(m.group(1)), month=9, day=30)
        if re.match(r"^\d{4}$", s):
            return pd.Timestamp(year=int(s), month=6, day=15)
        return pd.NaT

    return period_label.map(one)


def _prep(df: pd.DataFrame, *, family: str) -> pd.DataFrame:
    out = df.copy()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out[out["period_label"].astype(str).str.strip() != "5-Year Average"]
    out["period_sort"] = _period_sort_series(out["period_label"])
    out = out[out["period_sort"].notna()]
    out["family"] = family
    return out


def main() -> None:
    st.set_page_config(page_title="Affordability compare", layout="wide")
    st.title("Affordability compare — workplace vs residence vs new build")
    st.caption(
        "Aligns **table 1c** (price to earnings ratio) across three ONS families already in this repo: "
        "workplace-based stock, residence-based stock, and **new build** vs workplace earnings. "
        "Interpretation: commuter vs local earnings base, and new build vs wider stock — not a single harmonised definition."
    )
    st.divider()
    ogl_attribution_expander()

    c1, c2, c3 = st.columns(3)
    ed_w = c1.selectbox(
        "Workplace P/E edition",
        options=list(PRICE_EARNINGS_RATIO_EDITIONS.keys()),
        format_func=lambda k: PRICE_EARNINGS_RATIO_EDITIONS[k].label,
    )
    ed_r = c2.selectbox(
        "Residence P/E edition",
        options=list(PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS.keys()),
        format_func=lambda k: PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS[k].label,
    )
    ed_n = c3.selectbox(
        "New-build / workplace edition",
        options=list(NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS.keys()),
        format_func=lambda k: NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS[k].label,
    )

    pw, pr, pn = _path_workplace(ed_w), _path_residence(ed_r), _path_newbuild(ed_n)
    missing = [p.name for p in (pw, pr, pn) if not p.is_file()]
    if missing:
        st.warning(f"Missing tidy file(s): {', '.join(missing)}. Run the matching `ons_*_etl.py` scripts.")
        return

    df_w = _prep(load_processed_parquet(str(pw)), family="Workplace (stock)")
    df_r = _prep(load_processed_parquet(str(pr)), family="Residence (stock)")
    df_n = _prep(load_processed_parquet(str(pn)), family="New build / workplace")

    geo_levels = sorted(
        set(df_w["geography_level"].dropna().astype(str).unique())
        & set(df_r["geography_level"].dropna().astype(str).unique())
        & set(df_n["geography_level"].dropna().astype(str).unique())
    )
    _pref = "country_region" if "country_region" in geo_levels else geo_levels[0]
    level = st.sidebar.selectbox(
        "Geography level",
        options=geo_levels,
        index=geo_levels.index(_pref) if _pref in geo_levels else 0,
    )

    sub_w = df_w[df_w["geography_level"].astype(str) == level]
    sub_r = df_r[df_r["geography_level"].astype(str) == level]
    sub_n = df_n[df_n["geography_level"].astype(str) == level]

    lw, lr, ln = _label_column(sub_w), _label_column(sub_r), _label_column(sub_n)
    if not lw or not lr or not ln:
        st.error("Could not detect geography name columns in one or more datasets.")
        return

    names_w = set(sub_w[lw].dropna().astype(str).unique())
    names_r = set(sub_r[lr].dropna().astype(str).unique())
    names_n = set(sub_n[ln].dropna().astype(str).unique())
    common_names = sorted(names_w & names_r & names_n)
    if not common_names:
        st.info("No geography names in common across all three 1c tables at this level.")
        return

    pick = st.sidebar.selectbox("Geography", options=common_names)
    tw = sub_w[sub_w[lw].astype(str) == pick][["period_sort", "period_label", "value", "family"]].rename(
        columns={"value": "ratio"}
    )
    tr = sub_r[sub_r[lr].astype(str) == pick][["period_sort", "period_label", "value", "family"]].rename(
        columns={"value": "ratio"}
    )
    tn = sub_n[sub_n[ln].astype(str) == pick][["period_sort", "period_label", "value", "family"]].rename(
        columns={"value": "ratio"}
    )
    long = pd.concat([tw, tr, tn], ignore_index=True).sort_values("period_sort")
    if long.empty:
        st.info("No rows for this geography.")
        return

    st.subheader(f"Ratio time series — {pick}")
    ch = (
        alt.Chart(long)
        .mark_line(point=True)
        .encode(
            x=alt.X("period_sort:T", title="Period"),
            y=alt.Y("ratio:Q", title="Price / earnings ratio"),
            color=alt.Color("family:N", title="Series"),
            tooltip=["family", "period_label", alt.Tooltip("ratio:Q", format=".2f")],
        )
        .properties(height=400)
    )
    st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data (long)")
    st.dataframe(long, width=ST_WIDTH, height=min(480, 120 + 24 * min(len(long), 25)))
    st.download_button(
        "Download aligned long table (CSV)",
        data=long.to_csv(index=False).encode("utf-8"),
        file_name="affordability_compare_1c_long.csv",
        mime="text/csv",
    )


main()
