"""Streamlit: ONS house price per m² and per room (England and Wales, 2004–2016)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_house_m2_room_config import DATASET_PAGE, HOUSE_M2_DATA_SHEETS, HOUSE_M2_ROOM_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_TABLE_HELP = {
    "Table1": "Price per m² — country/region — houses and flats",
    "Table2": "Price per m² — region — flats only",
    "Table3": "Price per m² — region — excluding flats",
    "Table4": "Price per room — region — houses and flats",
    "Table5": "Price per room — region — flats only",
    "Table6": "Price per room — region — excluding flats",
    "Table7": "Price per room — local authority — houses and flats",
    "Table8": "Price per room — local authority — flats only",
    "Table9": "Price per room — local authority — excluding flats",
    "Table10": "Price per m² — local authority — houses and flats",
    "Table11": "Price per m² — local authority — flats only",
    "Table12": "Price per m² — local authority — excluding flats",
}


def _expected_parquet_path(edition: str, table: str) -> Path:
    return PROCESSED_DIR / f"ons_house_m2_room_{edition}_{table}_tidy.parquet"


def _normalize_for_altair(df: pd.DataFrame) -> pd.DataFrame:
    """Altair/Streamlit cannot infer types for nullable Arrow/pandas extension dtypes; use plain objects."""
    out = df.copy()
    for col in ("la_name", "region_name"):
        if col not in out.columns:
            continue
        out[col] = out[col].map(lambda x: "" if pd.isna(x) else str(x)).astype(object)
    if "year" in out.columns:
        out["year"] = pd.to_numeric(out["year"], errors="coerce")
        if out["year"].notna().all():
            out["year"] = out["year"].astype(np.int64)
    if "value" in out.columns:
        out["value"] = pd.to_numeric(out["value"], errors="coerce").astype(np.float64)
    return out


def main() -> None:
    st.set_page_config(page_title="House price per m² / room", layout="wide")
    st.title("House price per square metre and per room (England and Wales)")
    st.caption(
        "Annual series for **2004–2016** (legacy ONS release). "
        "Run `python ons_house_m2_room_etl.py` → `data/processed/ons_house_m2_room_*_Table*_tidy.parquet`."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE})")

    edition = st.sidebar.selectbox(
        "Edition",
        options=list(HOUSE_M2_ROOM_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({HOUSE_M2_ROOM_EDITIONS[k].label})",
        index=0,
    )
    table = st.sidebar.selectbox(
        "Table",
        options=list(HOUSE_M2_DATA_SHEETS),
        format_func=lambda t: f"{t} — {_TABLE_HELP.get(t, t)}",
    )

    path = _expected_parquet_path(edition, table)
    if not path.is_file():
        st.warning(f"No tidy file at `{path.name}`.")
        st.code(
            "python ons_house_m2_room_etl.py --edition "
            + edition
            + "\n# or: python ons_house_m2_room_etl.py --transform-only -i path/to/priceperareadata.xls --edition "
            + edition,
            language="bash",
        )
        return

    df = load_processed_parquet(str(path))
    st.sidebar.success(f"Loaded `{path.name}` ({len(df):,} rows)")

    view = df.copy()
    view["value"] = pd.to_numeric(view["value"], errors="coerce")

    geo_level = ""
    if len(view) and view["geography_level"].notna().any():
        geo_level = str(view["geography_level"].dropna().iloc[0])
    if not geo_level and "la_name" in view.columns:
        geo_level = "local_authority"
    if geo_level == "region":
        names = sorted(view["region_name"].dropna().astype(str).unique())
        pick = st.sidebar.multiselect("Region", options=names, default=names[: min(3, len(names))])
        view = view[view["region_name"].isin(pick)] if pick else view
        color_enc = alt.Color("region_name:N")
        x_title = "Year"
    else:
        la = sorted(view["la_name"].dropna().astype(str).unique())
        top_n = st.sidebar.slider("Top LAs by latest year value (chart)", 5, 40, 15)
        latest_year = int(view["year"].max()) if view["year"].notna().any() else None
        pick_la: list[str] = []
        if latest_year is not None:
            last = view[view["year"] == latest_year].copy()
            order = last.groupby("la_name", observed=True)["value"].mean().sort_values(ascending=False)
            pick_la = list(order.head(top_n).index)
        default_la = pick_la if pick_la else la[: min(3, len(la))]
        pick_names = st.sidebar.multiselect("Local authority", options=la, default=default_la)
        view = view[view["la_name"].isin(pick_names)] if pick_names else view
        color_enc = alt.Color("la_name:N")
        x_title = "Year"

    if view.empty:
        st.warning("No rows after filters — adjust sidebar selections.")
        return

    chart_df = _normalize_for_altair(view)
    tooltips: list[alt.Tooltip] = [
        alt.Tooltip("table_id:N", title="Table"),
        alt.Tooltip("metric:N", title="Metric"),
        alt.Tooltip("dwelling_segment:N", title="Segment"),
        alt.Tooltip("year:O", title="Year"),
        alt.Tooltip("value:Q", title="Value", format=",.2f"),
    ]
    if "region_name" in chart_df.columns:
        tooltips.append(alt.Tooltip("region_name:N", title="Region"))
    if "la_name" in chart_df.columns:
        tooltips.append(alt.Tooltip("la_name:N", title="Local authority"))

    ch = (
        alt.Chart(chart_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("year:O", title=x_title),
            y=alt.Y("value:Q", title="£ per m² or per room (ONS definition)"),
            color=color_enc,
            tooltip=tooltips,
        )
        .properties(height=400)
    )
    st.subheader("Time series")
    st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Data")
    st.dataframe(view, width=ST_WIDTH, height=min(600, 120 + 35 * min(len(view), 40)))

    csv_bytes = view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered view as CSV",
        data=csv_bytes,
        file_name=f"ons_house_m2_room_{edition}_{table}_filtered.csv",
        mime="text/csv",
    )


main()
