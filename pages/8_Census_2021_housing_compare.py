"""Streamlit: Census 2021 LA population vs ONS LA house-building (indicative rates)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_census2021_config import BULLETIN_URL, POPULATION_DERIVED_STEM, human_dataset_page
from ons_housebuilding_la_config import DATASET_PAGE as HB_LA_DATASET_PAGE, HOUSEBUILDING_LA_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def _load_pop(path: str) -> pd.DataFrame:
    return load_processed_parquet(path)


def _load_hb(path: str) -> pd.DataFrame:
    return load_processed_parquet(path)


def main() -> None:
    st.set_page_config(page_title="Census 2021 vs house building (LA)", layout="wide")
    st.title("Census 2021 population vs local-authority house building")
    st.caption(
        "Joins **Census 2021** usual-resident population (from TS008 sex table, summed per LA) to **ONS UK house building by local authority**."
    )
    st.divider()
    with st.expander("Methodology"):
        st.markdown(
            "**Methodology:** Census population is a **point-in-time** estimate (21 March 2021). House-building figures are **flows** by **financial year**. "
            "Ratios such as completions per 1,000 residents are **indicative** supply intensity, not a formal demographic rate. "
            "Scotland and Northern Ireland appear in the house-building dataset but **not** in England-and-Wales Census population—expect missing population for those rows."
        )
    ogl_attribution_expander()
    st.markdown(
        f"[Census 2021 unrounded bulletin (ONS)]({BULLETIN_URL}) · "
        f"[TS008 Sex (ONS)]({human_dataset_page('TS008', '2021', 4)}) · "
        f"[House building by LA (ONS)]({HB_LA_DATASET_PAGE})"
    )

    pop_path = PROCESSED_DIR / f"{POPULATION_DERIVED_STEM}.parquet"
    if not pop_path.is_file():
        st.warning(f"No file `{pop_path.name}`. Run: `python ons_census2021_etl.py --dataset sex_ts008`")
        return

    edition = st.sidebar.selectbox(
        "House-building edition",
        options=list(HOUSEBUILDING_LA_EDITIONS.keys()),
        format_func=lambda k: f"{k} ({HOUSEBUILDING_LA_EDITIONS[k].label})",
        index=0,
    )
    hb_path = PROCESSED_DIR / f"ons_housebuilding_la_{edition}_tidy.parquet"
    if not hb_path.is_file():
        st.warning(f"No tidy house-building file `{hb_path.name}`. Run `python ons_housebuilding_la_etl.py --edition {edition}`.")
        return

    pop = _load_pop(str(pop_path))
    hb = _load_hb(str(hb_path))
    st.sidebar.success(f"Population: `{pop_path.name}` ({len(pop):,} LAs) · House building: `{hb_path.name}` ({len(hb):,} rows)")

    hb = hb.copy()
    hb["financial_year"] = hb["financial_year"].astype(str)
    hb["dwellings"] = pd.to_numeric(hb["dwellings"], errors="coerce")
    years = sorted(hb["financial_year"].dropna().unique().tolist())
    fy = st.sidebar.selectbox("Financial year (for rates)", options=years, index=len(years) - 1)

    sub = hb[hb["financial_year"] == fy].copy()
    wide = sub.pivot_table(
        index=["Local Authority Code", "Local Authority Name", "Region or Country Name"],
        columns="measure",
        values="dwellings",
        aggfunc="sum",
        observed=False,
    ).reset_index()
    for col in ("starts", "completions"):
        if col not in wide.columns:
            wide[col] = pd.NA

    pop2 = pop.copy()
    pop2["lad_code"] = pop2["lad_code"].map(_norm_lad)
    wide["lad_code"] = wide["Local Authority Code"].map(_norm_lad)

    merged = wide.merge(
        pop2[["lad_code", "population", "lad_name"]],
        on="lad_code",
        how="left",
        suffixes=("", "_census"),
    )
    merged["population"] = pd.to_numeric(merged["population"], errors="coerce")
    merged["completions_per_1000_pop"] = merged["completions"] / merged["population"] * 1000.0
    merged["starts_per_1000_pop"] = merged["starts"] / merged["population"] * 1000.0

    metric = st.sidebar.radio("Rate to show", options=["completions_per_1000_pop", "starts_per_1000_pop"], format_func=lambda x: x.replace("_", " ").title())
    top_n = st.sidebar.slider("Top N (bar chart)", min_value=5, max_value=50, value=15, step=1)
    exclude_na = st.sidebar.checkbox("Exclude rows without Census population", value=True)

    view = merged.copy()
    if exclude_na:
        view = view[view["population"].notna() & (view["population"] > 0)]

    st.subheader(f"Financial year {fy}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows (after filters)", f"{len(view):,}")
    c2.metric("Median " + metric.replace("_", " "), f"{view[metric].median(skipna=True):.2f}" if view[metric].notna().any() else "—")
    c3.metric("Census year", "2021")

    top = view.sort_values(metric, ascending=False).head(top_n)
    bar = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("Local Authority Name:N", sort="-y", title="Local authority"),
            y=alt.Y(f"{metric}:Q", title="Per 1,000 Census 2021 residents"),
            tooltip=[
                "Local Authority Name",
                "Region or Country Name",
                alt.Tooltip("population", format=",.0f", title="Population (2021)"),
                alt.Tooltip("completions", format=",.0f"),
                alt.Tooltip("starts", format=",.0f"),
                alt.Tooltip(metric, format=".2f"),
            ],
        )
        .properties(height=420)
    )
    st.altair_chart(bar, width=ST_WIDTH)

    scatter = (
        alt.Chart(view[view["population"].notna()].head(5000))
        .mark_circle(size=60, opacity=0.5)
        .encode(
            x=alt.X("population:Q", title="Census 2021 population"),
            y=alt.Y(f"{metric}:Q", title="Per 1,000 population"),
            tooltip=["Local Authority Name", "population", metric],
        )
        .properties(height=340)
    )
    st.altair_chart(scatter, width=ST_WIDTH)

    st.subheader("Table data")
    show = view[
        [
            "Local Authority Code",
            "Local Authority Name",
            "Region or Country Name",
            "starts",
            "completions",
            "population",
            "starts_per_1000_pop",
            "completions_per_1000_pop",
        ]
    ].sort_values("completions", ascending=False, na_position="last")
    st.dataframe(show, width=ST_WIDTH, height=min(650, 120 + 28 * min(len(show), 25)))

    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download table as CSV",
        data=csv_bytes,
        file_name=f"census2021_housebuilding_compare_{edition}_{fy.replace('/', '-')}.csv",
        mime="text/csv",
    )


main()
