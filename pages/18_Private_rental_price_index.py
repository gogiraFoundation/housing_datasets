"""Streamlit: ONS private rental price index (PRPI) with cross-dataset analytics."""

from __future__ import annotations

import re
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_price_earnings_ratio_config import PRICE_EARNINGS_RATIO_EDITIONS
from ons_private_rental_index_config import DATASET_PAGE, PRIVATE_RENTAL_INDEX_EDITIONS
from ons_uk_hpi_monthly_config import UK_HPI_MONTHLY_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_PRPI_DEFAULT = "v41"
_HPI_DEFAULT = "march2026"
_PE_DEFAULT = "current"
_REGION_NAME_MAP = {
    "East": "East of England",
    "East Midlands": "East Midlands",
    "London": "London",
    "North East": "North East",
    "North West": "North West",
    "South East": "South East",
    "South West": "South West",
    "West Midlands": "West Midlands",
    "Yorkshire and The Humber": "Yorkshire and The Humber",
    "England": "England",
    "Wales": "Wales",
    "Scotland": "Scotland",
    "Northern Ireland [note 3]": "Northern Ireland",
    "Great Britain": "Great Britain",
    "United Kingdom": "United Kingdom",
}


def _parse_prpi_month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%b-%y", errors="coerce")


def _parse_hpi_month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%b %Y", errors="coerce")


def _with_query_default(key: str, default: str) -> str:
    qp = st.query_params
    return str(qp.get(key, default))


def _set_query(**pairs: str) -> None:
    qp = dict(st.query_params)
    qp.update({k: str(v) for k, v in pairs.items()})
    st.query_params.clear()
    st.query_params.update(qp)


def _rebase(sub: pd.DataFrame, value_col: str, by: str, base_month: pd.Timestamp) -> pd.DataFrame:
    out = sub.copy()
    out["base_val"] = out.groupby(by)[value_col].transform(
        lambda x: x[out.loc[x.index, "period"] == base_month].iloc[0]
        if (out.loc[x.index, "period"] == base_month).any()
        else np.nan
    )
    out["rebased_100"] = out[value_col] / out["base_val"] * 100.0
    return out.drop(columns=["base_val"])


def _load_prpi(edition: str) -> pd.DataFrame:
    p = PROCESSED_DIR / f"ons_private_rental_index_{edition}_tidy.parquet"
    if not p.is_file():
        raise FileNotFoundError(p.name)
    df = load_processed_parquet(str(p)).copy()
    df["period"] = _parse_prpi_month(df["month_label"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["period", "value"])


def _load_hpi_index(edition: str) -> pd.DataFrame:
    p = PROCESSED_DIR / f"ons_uk_hpi_monthly_{edition}_1_tidy.parquet"
    if not p.is_file():
        raise FileNotFoundError(p.name)
    df = load_processed_parquet(str(p)).copy()
    df["period"] = _parse_hpi_month(df["time_period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["prpi_geography_name"] = df["geography"].astype(str).map(_REGION_NAME_MAP).fillna(df["geography"].astype(str))
    return df.dropna(subset=["period", "value"])


def _pe_period_label_to_year(period_label: pd.Series) -> pd.Series:
    """Calendar-style year for ONS affordability period_label values (wide sheet melt)."""

    def one(x: object) -> int | None:
        s = str(x).strip()
        if not s or s == "5-Year Average":
            return None
        m = re.match(r"Year ending Sep (\d{4})", s)
        if m:
            return int(m.group(1))
        if re.match(r"^\d{4}$", s):
            return int(s)
        v = pd.to_numeric(s, errors="coerce")
        if pd.isna(v):
            return None
        return int(v)

    return period_label.map(one).astype("Int64")


def _load_affordability_ratio(edition: str) -> pd.DataFrame:
    p = PROCESSED_DIR / f"ons_price_earnings_ratio_{edition}_1c_tidy.parquet"
    if not p.is_file():
        raise FileNotFoundError(p.name)
    df = load_processed_parquet(str(p)).copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "period_label" in df.columns:
        df["year"] = _pe_period_label_to_year(df["period_label"])
    elif "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    else:
        raise KeyError("Expected 'period_label' or 'year' in affordability data.")

    geo_col = None
    for prefer in ("country_region_name", "name", "local_authority_name"):
        if prefer in df.columns:
            geo_col = prefer
            break
    if geo_col is None:
        for c in df.columns:
            if str(c).endswith("_name"):
                geo_col = c
                break
    if geo_col is None:
        raise KeyError("Expected a geography name column (e.g. name, country_region_name).")
    df["country_region_name"] = df[geo_col].astype(str)

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["year", "value"])[["country_region_name", "year", "value"]]


def main() -> None:
    st.set_page_config(page_title="Private rental price index", layout="wide")
    st.title("Private rental price index (PRPI)")
    st.caption(
        "ONS private rental price index (experimental index and year-on-year change). "
        "This index measures rate of change and does not represent sterling rent levels."
    )
    st.divider()
    ogl_attribution_expander()
    st.markdown(f"[Dataset page (ONS)]({DATASET_PAGE})")

    q_prpi = _with_query_default("prpi_edition", _PRPI_DEFAULT)
    q_hpi = _with_query_default("hpi_edition", _HPI_DEFAULT)
    q_pe = _with_query_default("pe_edition", _PE_DEFAULT)
    q_geo = _with_query_default("geo", "Great Britain")

    prpi_edition = st.sidebar.selectbox(
        "PRPI edition",
        options=list(PRIVATE_RENTAL_INDEX_EDITIONS.keys()),
        index=max(0, list(PRIVATE_RENTAL_INDEX_EDITIONS).index(q_prpi) if q_prpi in PRIVATE_RENTAL_INDEX_EDITIONS else 0),
        format_func=lambda k: f"{k} ({PRIVATE_RENTAL_INDEX_EDITIONS[k].label})",
    )
    hpi_edition = st.sidebar.selectbox(
        "UK HPI edition (sheet 1)",
        options=list(UK_HPI_MONTHLY_EDITIONS.keys()),
        index=max(0, list(UK_HPI_MONTHLY_EDITIONS).index(q_hpi) if q_hpi in UK_HPI_MONTHLY_EDITIONS else 0),
        format_func=lambda k: f"{k} ({UK_HPI_MONTHLY_EDITIONS[k].label})",
    )
    pe_edition = st.sidebar.selectbox(
        "Price/earnings edition (table 1c)",
        options=list(PRICE_EARNINGS_RATIO_EDITIONS.keys()),
        index=max(0, list(PRICE_EARNINGS_RATIO_EDITIONS).index(q_pe) if q_pe in PRICE_EARNINGS_RATIO_EDITIONS else 0),
        format_func=lambda k: f"{k} ({PRICE_EARNINGS_RATIO_EDITIONS[k].label})",
    )

    _set_query(prpi_edition=prpi_edition, hpi_edition=hpi_edition, pe_edition=pe_edition)

    try:
        prpi = _load_prpi(prpi_edition)
    except FileNotFoundError as e:
        st.warning(f"Missing `{e}`. Run `python ons_private_rental_index_etl.py --edition {prpi_edition}`.")
        return

    geos = sorted(prpi["geography_name"].dropna().astype(str).unique())
    default_geo = q_geo if q_geo in geos else (geos[0] if geos else "Great Britain")
    selected_geos = st.sidebar.multiselect("Geography", geos, default=[default_geo] if default_geo in geos else geos[:1])
    variable = st.sidebar.selectbox(
        "PRPI series",
        options=["index", "year-on-year-change"],
        format_func=lambda v: "Index" if v == "index" else "Year-on-year change (%)",
    )
    if selected_geos:
        _set_query(geo=selected_geos[0])

    view = prpi[prpi["variable"].astype(str) == variable].copy()
    if selected_geos:
        view = view[view["geography_name"].isin(selected_geos)]
    if view.empty:
        st.info("No rows for the selected PRPI filters.")
        return

    st.subheader("PRPI trend")
    y_title = "Index" if variable == "index" else "Year-on-year change (%)"
    ch = (
        alt.Chart(view)
        .mark_line(point=True)
        .encode(
            x=alt.X("period:T", title="Month"),
            y=alt.Y("value:Q", title=y_title),
            color=alt.Color("geography_name:N", title="Geography"),
            tooltip=["geography_name", "month_label", alt.Tooltip("value:Q", format=".3f")],
        )
        .properties(height=360)
    )
    st.altair_chart(ch, width=ST_WIDTH)

    if variable == "index":
        periods = sorted(view["period"].dropna().unique())
        base_default = periods[0] if periods else None
        base_month = st.selectbox("Rebase month (PRPI index = 100)", options=periods, index=0 if base_default is not None else None)
        rebased = _rebase(view, "value", "geography_name", pd.Timestamp(base_month))
        st.subheader("Rebased PRPI index")
        rb = (
            alt.Chart(rebased.dropna(subset=["rebased_100"]))
            .mark_line(point=False)
            .encode(
                x=alt.X("period:T", title="Month"),
                y=alt.Y("rebased_100:Q", title="Rebased index (base month = 100)"),
                color="geography_name:N",
                tooltip=["geography_name", "month_label", alt.Tooltip("rebased_100:Q", format=".2f")],
            )
            .properties(height=320)
        )
        st.altair_chart(rb, width=ST_WIDTH)

    st.subheader("Cross-dataset analytics")
    tab_buy_rent, tab_stress = st.tabs(["Buy vs rent (indexed)", "Affordability + rent inflation"])

    with tab_buy_rent:
        try:
            hpi = _load_hpi_index(hpi_edition)
        except FileNotFoundError as e:
            st.info(f"Missing `{e}`. Run `python ons_uk_hpi_monthly_etl.py --edition {hpi_edition}` to enable this chart.")
        else:
            prpi_idx = prpi[prpi["variable"].astype(str) == "index"][["geography_name", "period", "value"]].rename(
                columns={"value": "prpi_index"}
            )
            hpi_idx = hpi[["prpi_geography_name", "period", "value"]].rename(
                columns={"prpi_geography_name": "geography_name", "value": "hpi_index"}
            )
            joined = prpi_idx.merge(hpi_idx, on=["geography_name", "period"], how="inner")
            joined = joined.dropna(subset=["prpi_index", "hpi_index"]).sort_values(["geography_name", "period"])
            if selected_geos:
                joined = joined[joined["geography_name"].isin(selected_geos)]
            if joined.empty:
                st.info("No overlapping monthly periods between PRPI and HPI for the selected geographies.")
            else:
                base = joined.groupby("geography_name", observed=True).first().reset_index()[
                    ["geography_name", "period", "prpi_index", "hpi_index"]
                ]
                base = base.rename(columns={"period": "base_period", "prpi_index": "base_prpi", "hpi_index": "base_hpi"})
                x = joined.merge(base, on="geography_name", how="left")
                x["prpi_rebased"] = x["prpi_index"] / x["base_prpi"] * 100.0
                x["hpi_rebased"] = x["hpi_index"] / x["base_hpi"] * 100.0
                x["spread_growth_pp"] = (x["hpi_rebased"] - 100.0) - (x["prpi_rebased"] - 100.0)
                x["ratio_rebased"] = x["hpi_rebased"] / x["prpi_rebased"]
                st.caption("Default view rebases both indices to each geography's first overlapping month (base = 100).")
                m = x.melt(
                    id_vars=["geography_name", "period"],
                    value_vars=["prpi_rebased", "hpi_rebased"],
                    var_name="series",
                    value_name="value",
                )
                m["series"] = m["series"].map({"prpi_rebased": "PRPI rebased", "hpi_rebased": "HPI rebased"})
                c = (
                    alt.Chart(m)
                    .mark_line(point=False)
                    .encode(
                        x=alt.X("period:T", title="Month"),
                        y=alt.Y("value:Q", title="Rebased index (first overlap month = 100)"),
                        color="series:N",
                        strokeDash="geography_name:N",
                        tooltip=["geography_name", "series", alt.Tooltip("value:Q", format=".2f")],
                    )
                    .properties(height=360)
                )
                st.altair_chart(c, width=ST_WIDTH)
                t_spread, t_ratio = st.tabs(["Cumulative growth spread", "Ratio of rebased indices"])
                with t_spread:
                    s = (
                        alt.Chart(x)
                        .mark_line(point=False)
                        .encode(
                            x="period:T",
                            y=alt.Y("spread_growth_pp:Q", title="HPI minus PRPI cumulative growth (pp)"),
                            color="geography_name:N",
                            tooltip=["geography_name", alt.Tooltip("spread_growth_pp:Q", format=".2f")],
                        )
                        .properties(height=280)
                    )
                    st.altair_chart(s, width=ST_WIDTH)
                with t_ratio:
                    r = (
                        alt.Chart(x)
                        .mark_line(point=False)
                        .encode(
                            x="period:T",
                            y=alt.Y("ratio_rebased:Q", title="HPI rebased / PRPI rebased"),
                            color="geography_name:N",
                            tooltip=["geography_name", alt.Tooltip("ratio_rebased:Q", format=".3f")],
                        )
                        .properties(height=280)
                    )
                    st.altair_chart(r, width=ST_WIDTH)

    with tab_stress:
        try:
            pe = _load_affordability_ratio(pe_edition)
        except FileNotFoundError as e:
            st.info(
                f"Missing `{e}`. Run `python ons_price_earnings_ratio_etl.py --edition {pe_edition}` "
                "to enable affordability + PRPI panel."
            )
        else:
            yoy = prpi[prpi["variable"].astype(str) == "year-on-year-change"].copy()
            yoy["year"] = yoy["period"].dt.year.astype("Int64")
            yoy_g = (
                yoy.groupby(["geography_name", "year"], observed=True)["value"]
                .mean()
                .reset_index()
                .rename(columns={"value": "prpi_yoy_avg"})
            )
            merged = yoy_g.merge(
                pe.rename(columns={"country_region_name": "geography_name", "value": "affordability_ratio"}),
                on=["geography_name", "year"],
                how="inner",
            )
            if selected_geos:
                merged = merged[merged["geography_name"].isin(selected_geos)]
            if merged.empty:
                st.info("No aligned year-level rows between PRPI YoY and affordability ratio for selected geographies.")
            else:
                st.caption("Periods differ by source; this panel aligns by calendar year and geography only.")
                p1, p2 = st.columns(2)
                with p1:
                    c1 = (
                        alt.Chart(merged)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("year:O", title="Year"),
                            y=alt.Y("affordability_ratio:Q", title="Price / earnings ratio"),
                            color="geography_name:N",
                            tooltip=["geography_name", "year", alt.Tooltip("affordability_ratio:Q", format=".2f")],
                        )
                        .properties(height=300)
                    )
                    st.altair_chart(c1, width=ST_WIDTH)
                with p2:
                    c2 = (
                        alt.Chart(merged)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("year:O", title="Year"),
                            y=alt.Y("prpi_yoy_avg:Q", title="Average PRPI YoY (%)"),
                            color="geography_name:N",
                            tooltip=["geography_name", "year", alt.Tooltip("prpi_yoy_avg:Q", format=".2f")],
                        )
                        .properties(height=300)
                    )
                    st.altair_chart(c2, width=ST_WIDTH)

    st.subheader("Filtered PRPI rows")
    table = view.sort_values(["period", "geography_name"]).copy()
    st.dataframe(table, width=ST_WIDTH, height=min(640, 120 + 30 * min(len(table), 40)))
    st.download_button(
        "Download filtered PRPI rows (CSV)",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name=f"ons_private_rental_index_{prpi_edition}_{variable}_filtered.csv",
        mime="text/csv",
    )

    st.caption(
        "Coverage note: PRPI is UK/nations/regions (not LA-level in this source). "
        "Combined charts keep period definitions visible and do not imply harmonised concepts."
    )


main()
