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

_FIXED_AXIS_LABELS: dict[str, str] = {
    "starts_per_1000": "Starts per 1,000 population",
    "supply_starts": "Starts (dwellings)",
    "population": "Population (Census 2021)",
    "median_price_existing_gbp": "Median price existing (£)",
    "median_price_new_gbp": "Median price new build (£)",
    "pe_affordability_ratio": "Price / earnings ratio (workplace)",
    "pe_res_affordability_ratio": "Price / earnings ratio (residence-based)",
    "pe_newbuild_affordability_ratio": "New-build price / workplace earnings ratio",
    "pe_median_price_gbp": "Median house price — workplace series (£)",
    "pe_res_median_price_gbp": "Median house price — residence series (£)",
    "pe_newbuild_median_price_gbp": "Median new-build price (£)",
}


def _meta_path(stem: str) -> Path:
    return PROCESSED_DIR / f"{stem}.meta.json"


def _numeric_axis_columns(view: pd.DataFrame) -> list[str]:
    skip = {
        "lad_code",
        "region_code",
        "la_name",
        "region_name",
        "supply_financial_year",
        "median_price_period_label",
        "median_price_new_period_label",
    }
    out: list[str] = []
    for c in view.columns:
        if c in skip:
            continue
        if pd.api.types.is_numeric_dtype(view[c]):
            out.append(c)
    return sorted(set(out))


def _axis_label(col: str) -> str:
    return _FIXED_AXIS_LABELS.get(col, col.replace("_", " "))


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

    qp = st.query_params
    lane_default = str(qp.get("lane", "A"))
    lane_options = ("A — Local authority", "B — Region")
    lane = st.sidebar.radio(
        "Lane",
        lane_options,
        index=0 if lane_default.upper().startswith("A") else 1,
        horizontal=True,
    )
    st.query_params["lane"] = "A" if lane.startswith("A") else "B"

    la_path = PROCESSED_DIR / f"{_LA_STEM}.parquet"
    reg_path = PROCESSED_DIR / f"{_REG_STEM}.parquet"

    if lane.startswith("A"):
        if not la_path.is_file():
            st.warning(f"Missing `{la_path.name}`. Run `python joins/build_la_housing_market_snapshot.py`.")
            return
        df = load_processed_parquet(str(la_path))
        reg_df = load_processed_parquet(str(reg_path)) if reg_path.is_file() else None
        meta: dict = {}
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

        axis_candidates = _numeric_axis_columns(view)
        preferred_x = ["starts_per_1000", "supply_starts", "population"]
        x_options = [c for c in preferred_x if c in axis_candidates] + [c for c in axis_candidates if c not in preferred_x]
        if not x_options:
            x_options = ["starts_per_1000"]
        q_lad = str(qp.get("lad", "")).strip().upper()
        lad_list = sorted(view["lad_code"].dropna().astype(str).str.upper().unique())
        default_x = str(qp.get("x", "starts_per_1000"))
        if default_x not in x_options:
            default_x = x_options[0]
        default_y = str(qp.get("y", "median_price_existing_gbp"))
        preferred_y = [
            "median_price_existing_gbp",
            "median_price_new_gbp",
            "pe_affordability_ratio",
            "pe_res_affordability_ratio",
            "pe_newbuild_affordability_ratio",
        ]
        y_options = [c for c in preferred_y if c in axis_candidates] + [c for c in axis_candidates if c not in preferred_y]
        if not y_options:
            y_options = axis_candidates[:1] if axis_candidates else ["starts_per_1000"]
        if default_y not in y_options:
            default_y = y_options[0]

        xopt = st.sidebar.selectbox(
            "X axis",
            options=x_options,
            index=max(0, x_options.index(default_x) if default_x in x_options else 0),
            format_func=_axis_label,
        )
        yopt = st.sidebar.selectbox(
            "Y axis",
            options=y_options,
            index=max(0, y_options.index(default_y) if default_y in y_options else 0),
            format_func=_axis_label,
        )
        st.query_params["x"] = xopt
        st.query_params["y"] = yopt

        focus_idx = 0
        if lad_list and q_lad and q_lad in lad_list:
            focus_idx = lad_list.index(q_lad) + 1
        focus_lad = st.sidebar.selectbox(
            "Focus LA (links Lane B)",
            options=(["—"] + lad_list) if lad_list else ["—"],
            index=min(focus_idx, len(lad_list)),
            format_func=lambda x: "—" if x == "—" else str(x),
        )
        if focus_lad != "—":
            st.query_params["lad"] = str(focus_lad)
            rmatch = view.loc[view["lad_code"].astype(str).str.upper() == str(focus_lad), "region_name"]
            if not rmatch.empty:
                st.query_params["region"] = str(rmatch.iloc[0])
        else:
            if "lad" in st.query_params:
                del st.query_params["lad"]

        if focus_lad != "—" and reg_df is not None and not reg_df.empty:
            rn = view.loc[view["lad_code"].astype(str).str.upper() == str(focus_lad), "region_name"]
            if not rn.empty:
                region_name = str(rn.iloc[0])
                brow = reg_df[reg_df["region_name"].astype(str) == region_name]
                if not brow.empty:
                    br = brow.iloc[0]
                    st.subheader("Parent region (Lane B)")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Region", region_name)
                    c2.metric("Supply starts (FY)", f"{br.get('region_supply_starts', float('nan')):,.0f}" if pd.notna(br.get("region_supply_starts")) else "—")
                    c3.metric("HPI growth (overlap %)", f"{float(br['hpi_growth_overlap_pct']):.2f}" if pd.notna(br.get("hpi_growth_overlap_pct")) else "—")
                    c4.metric("PRPI growth (overlap %)", f"{float(br['prpi_growth_overlap_pct']):.2f}" if pd.notna(br.get("prpi_growth_overlap_pct")) else "—")
                    if pd.notna(br.get("hpi_minus_prpi_growth_pp")):
                        st.caption(f"HPI minus PRPI growth (percentage points): **{float(br['hpi_minus_prpi_growth_pp']):+.2f}** (same overlapping months as join script).")

        with st.expander("Period / edition alignment (focused LA or first row)"):
            if focus_lad != "—":
                row_lad = str(focus_lad).strip().upper()
            elif len(view):
                row_lad = str(view.iloc[0]["lad_code"]).strip().upper()
            else:
                row_lad = ""
            row = view[view["lad_code"].astype(str).str.upper() == row_lad].head(1) if row_lad else view.head(0)
            pe = meta.get("price_earnings") or {}
            rows = [
                {"Field": "Supply financial year", "Value": meta.get("supply_financial_year", "—")},
                {"Field": "Median price (existing) period", "Value": meta.get("median_price_period_label", "—")},
                {"Field": "Workplace P/E snapshot year", "Value": str(pe.get("pe_snapshot_year", "—"))},
                {"Field": "Workplace P/E period (ratio sheet)", "Value": str(pe.get("pe_period_label_ratio", "—"))},
            ]
            mn = meta.get("median_new_build") or {}
            if not mn.get("skipped"):
                rows.append({"Field": "Median new-build period", "Value": str(mn.get("median_price_new_period_label", "—"))})
            pr = meta.get("price_earnings_residence") or {}
            if not pr.get("skipped"):
                rows.append({"Field": "Residence P/E snapshot year", "Value": str(pr.get("snapshot_year", "—"))})
                rows.append({"Field": "Residence P/E period (ratio)", "Value": str(pr.get("period_label_ratio", "—"))})
            nb = meta.get("price_earnings_newbuild_workplace") or {}
            if not nb.get("skipped"):
                rows.append({"Field": "New-build P/E snapshot year", "Value": str(nb.get("snapshot_year", "—"))})
                rows.append({"Field": "New-build P/E period (ratio)", "Value": str(nb.get("period_label_ratio", "—"))})
            if not row.empty:
                r0 = row.iloc[0]
                rows.append({"Field": "LA code (row)", "Value": str(r0.get("lad_code", "—"))})
                rows.append(
                    {
                        "Field": "Median new-build on row",
                        "Value": str(r0.get("median_price_new_period_label", "—"))
                        + " / £"
                        + str(r0.get("median_price_new_gbp", "—")),
                    }
                )
            st.dataframe(pd.DataFrame(rows), width=ST_WIDTH, hide_index=True)

        plot_df = view.dropna(subset=[xopt, yopt], how="any")
        if not plot_df.empty:
            ch = (
                alt.Chart(plot_df)
                .mark_circle(size=60)
                .encode(
                    x=alt.X(f"{xopt}:Q", title=_axis_label(xopt)),
                    y=alt.Y(f"{yopt}:Q", title=_axis_label(yopt)),
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
    metric_options = {
        "ee_epc_c_plus_pct": "EPC C+ share (five-year rolling, %)",
        "epc_pct_bands_abc": "EPC A-C share (snapshot, %)",
        "region_supply_starts": "Supply starts (latest FY)",
        "hpi_growth_overlap_pct": "HPI growth over overlap window (%)",
        "prpi_growth_overlap_pct": "PRPI growth over overlap window (%)",
        "hpi_minus_prpi_growth_pp": "HPI minus PRPI growth (pp)",
    }
    available_metrics = [k for k in metric_options if k in view.columns]
    q_metric = str(qp.get("metric", "ee_epc_c_plus_pct"))
    metric = st.sidebar.selectbox(
        "Region metric",
        options=available_metrics,
        index=max(0, available_metrics.index(q_metric) if q_metric in available_metrics else 0),
        format_func=lambda k: metric_options[k],
    )
    st.query_params["metric"] = metric

    regions_sorted = sorted(view["region_name"].dropna().astype(str).unique())
    q_region = str(qp.get("region", "")).strip()
    hl_index = 0
    if q_region and q_region in regions_sorted:
        hl_index = regions_sorted.index(q_region) + 1
    highlight_region = st.sidebar.selectbox(
        "Highlight region",
        options=["—"] + regions_sorted,
        index=hl_index,
        format_func=lambda x: "—" if x == "—" else str(x),
    )
    if highlight_region != "—":
        st.query_params["region"] = str(highlight_region)
    else:
        if "region" in st.query_params:
            del st.query_params["region"]

    view_plot = view.copy()
    if highlight_region != "—":
        view_plot["_bar_opacity"] = np.where(view_plot["region_name"].astype(str) == highlight_region, 1.0, 0.35)
    else:
        view_plot["_bar_opacity"] = 1.0

    tooltip_cols = [
        c
        for c in [
            "region_name",
            "region_supply_starts",
            "region_supply_completions",
            "epc_pct_bands_abc",
            "ee_epc_c_plus_pct",
            "hpi_growth_overlap_pct",
            "prpi_growth_overlap_pct",
            "hpi_minus_prpi_growth_pp",
        ]
        if c in view_plot.columns
    ]
    ch = (
        alt.Chart(view_plot)
        .mark_bar()
        .encode(
            x=alt.X(f"{metric}:Q", title=metric_options[metric]),
            y=alt.Y("region_name:N", sort="-x", title="Region"),
            opacity=alt.Opacity("_bar_opacity:Q", legend=None),
            tooltip=tooltip_cols,
        )
        .properties(height=min(400, 28 * len(view_plot)))
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
