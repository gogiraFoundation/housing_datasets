"""Streamlit: ONS House Price Statistics for Small Areas by national park."""

from __future__ import annotations

import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_median_price_admin_config import MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS
from ons_national_park_hpssa_config import (
    DATASET_PAGE,
    NATIONAL_PARK_HPSSA_DATA_SHEETS,
    NATIONAL_PARK_HPSSA_EDITIONS,
)
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_TABLE_HELP = {
    "1a": "1a — Sales count (all types)",
    "1b": "1b — Sales count — detached",
    "1c": "1c — Sales count — semi-detached",
    "1d": "1d — Sales count — terraced",
    "1e": "1e — Sales count — flats / maisonettes",
    "2a": "2a — Median price (all types)",
    "2b": "2b — Median price — detached",
    "2c": "2c — Median price — semi-detached",
    "2d": "2d — Median price — terraced",
    "2e": "2e — Median price — flats / maisonettes",
    "3a": "3a — Lower quartile price (all types)",
    "3b": "3b — Lower quartile price — detached",
    "3c": "3c — Lower quartile price — semi-detached",
    "3d": "3d — Lower quartile price — terraced",
    "3e": "3e — Lower quartile price — flats / maisonettes",
}


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_national_park_hpssa_{edition}_{table}_tidy.parquet"


def _period_sort_series(period_label: pd.Series) -> pd.Series:
    def one(x: object) -> pd.Timestamp:
        s = str(x).strip()
        m = re.match(r"^Year ending (.+) (\d{4})$", s)
        if not m:
            return pd.NaT
        mon, year = m.group(1), int(m.group(2))
        return pd.to_datetime(f"{mon} {year}", format="%b %Y", errors="coerce")

    return period_label.map(one)


def _y_title(measure: str) -> str:
    if measure == "sales_count":
        return "Number of sales"
    if measure == "median_price_gbp":
        return "Median price (£)"
    return "Lower quartile price (£)"


def main() -> None:
    st.set_page_config(page_title="National park — sales & prices", layout="wide")
    st.title("National parks — property sales and prices (HPSSA)")
    st.caption(
        "ONS **House Price Statistics for Small Areas by national park**: rolling-quarter annual series "
        "for **sales counts** (tables 1a–1e), **median** price paid (2a–2e), and **lower quartile** price (3a–3e). "
        "Run `python ons_national_park_hpssa_etl.py --edition yearendingseptember2025`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[ONS dataset page]({DATASET_PAGE})")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(NATIONAL_PARK_HPSSA_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({NATIONAL_PARK_HPSSA_EDITIONS[k].label})",
        index=max(0, list(NATIONAL_PARK_HPSSA_EDITIONS).index("yearendingseptember2025")),
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(NATIONAL_PARK_HPSSA_DATA_SHEETS),
        format_func=lambda t: _TABLE_HELP.get(t, t),
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            f"python ons_national_park_hpssa_etl.py --edition {edition}\n"
            f"# or: python ons_national_park_hpssa_etl.py --transform-only -i workbook.xlsx --edition {edition}",
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    view["value"] = pd.to_numeric(view["value"], errors="coerce")
    name_col = "area_name" if "area_name" in view.columns else None
    if name_col:
        parks = sorted(view[name_col].dropna().astype(str).unique())
        pick = st.sidebar.multiselect("National park", options=parks, default=parks[: min(4, len(parks))])
        view = view[view[name_col].isin(pick)] if pick else view

    view["period_sort"] = _period_sort_series(view["period_label"])
    view_chart = view[view["period_sort"].notna()].copy()
    measure = str(view["measure"].iloc[0]) if len(view) else "sales_count"

    st.subheader("Time series")
    if view_chart.empty:
        st.info("No rows to chart after filters.")
    else:
        enc: dict = {
            "x": alt.X("period_sort:T", title="Period (rolling year)"),
            "y": alt.Y("value:Q", title=_y_title(measure)),
        }
        tip = ["period_label", "value", "measure", "property_band", "table_id"]
        if name_col:
            enc["color"] = alt.Color(f"{name_col}:N")
            tip.append(name_col)
        else:
            enc["color"] = alt.value("steelblue")
        ch = alt.Chart(view_chart).mark_line(point=True).encode(**enc, tooltip=tip).properties(height=400)
        st.altair_chart(ch, width=ST_WIDTH)

    with st.expander("Regional median context (HPSSA admin — not national parks)"):
        st.caption(
            "Compare park-level HPSSA small-area series to **administrative region** medians from the separate "
            "median-price-admin workbook. Geographies and property concepts differ; use as context only."
        )
        med_ed = st.selectbox(
            "Median price (existing) edition",
            options=list(MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS.keys()),
            format_func=lambda k: MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS[k].label,
            key="np_med_ed",
        )
        med_path = PROCESSED_DIR / f"ons_median_price_existing_admin_{med_ed}_2a_tidy.parquet"
        if not med_path.is_file():
            st.info(f"Missing `{med_path.name}`. Run `python ons_median_price_admin_etl.py --dataset existing --edition {med_ed}`.")
        else:
            med = load_processed_parquet(str(med_path))
            price_col = (
                "median_price_gbp"
                if "median_price_gbp" in med.columns
                else ("value" if "value" in med.columns else None)
            )
            if price_col is None:
                st.info("Median admin file has no `median_price_gbp` or `value` column.")
            else:
                med = med[
                    (med["geography_level"].astype(str) == "region")
                    & (med["table_id"].astype(str) == "2a")
                    & (med["property_band"].astype(str).str.lower() == "all")
                ].copy()
                if "region_country_name" not in med.columns:
                    st.info("Median admin file has no region rows in expected layout.")
                else:
                    regions = sorted(med["region_country_name"].dropna().astype(str).unique())
                    pick_r = st.selectbox("Reference region", options=regions, key="np_ref_region")
                    subm = med[med["region_country_name"].astype(str) == pick_r].copy()
                    subm[price_col] = pd.to_numeric(subm[price_col], errors="coerce")
                    subm["period_sort"] = _period_sort_series(subm["period_label"])
                    subm = subm[subm["period_sort"].notna()]
                    if subm.empty:
                        st.info("No median rows for this region.")
                    else:
                        cm = (
                            alt.Chart(subm)
                            .mark_line(color="#666", strokeDash=[4, 2], point=True)
                            .encode(
                                x=alt.X("period_sort:T", title="Period"),
                                y=alt.Y(f"{price_col}:Q", title="Median price existing (£)"),
                                tooltip=["period_label", price_col],
                            )
                            .properties(height=260, title=f"Admin median — {pick_r}")
                        )
                        st.altair_chart(cm, width=ST_WIDTH)

    st.subheader("Data")
    show = view.drop(columns=["period_sort"], errors="ignore")
    st.dataframe(show, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(show), 40)))

    st.download_button(
        label="Download filtered view as CSV",
        data=show.to_csv(index=False).encode("utf-8"),
        file_name=f"national_park_hpssa_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
