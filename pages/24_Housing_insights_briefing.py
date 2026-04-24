"""Streamlit: Housing insights briefing — multi-dataset hero KPIs and tabbed story beats."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from housing_analytics.insights_briefing import (
    DEFAULT_PE_ANCHOR_YEARS,
    DEFAULT_SUPPLY_COMPARE_FY,
    PRESET_CUSTOM,
    PRESET_LONDON_COMMUTER,
    PRESET_NATIONAL,
    PRESET_NORTH,
    REGION_COLOR_DOMAIN,
    REGION_COLOR_RANGE,
    build_insights_payload,
    insights_inputs_snapshot,
)
from ons_census2021_config import POPULATION_DERIVED_STEM
from ons_ee_fiveyear_config import DATASET_PAGE as EE_DATASET_PAGE, EE_FIVEYEAR_EDITIONS
from ons_epc_config import DATASET_PAGE as EPC_DATASET_PAGE, EPC_EDITIONS
from ons_housebuilding_country_config import DATASET_PAGE as HB_COUNTRY_DATASET_PAGE, HOUSEBUILDING_COUNTRY_EDITIONS
from ons_housebuilding_la_config import DATASET_PAGE as HB_LA_DATASET_PAGE, HOUSEBUILDING_LA_EDITIONS
from ons_median_price_admin_config import EXISTING_DATASET_PAGE, MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS
from ons_price_earnings_ratio_config import DATASET_PAGE as PE_DATASET_PAGE, PRICE_EARNINGS_RATIO_EDITIONS
from ons_uk_hpi_monthly_config import DATASET_PAGE as HPI_DATASET_PAGE, UK_HPI_MONTHLY_EDITIONS
from streamlit_io import PROCESSED_DIR
from streamlit_page_helpers import ogl_attribution_expander, render_missing_or_empty


def _select_index(options: list[str], *, default_key: str) -> int:
    try:
        return options.index(default_key)
    except ValueError:
        return 0


def _insights_inputs_snapshot_mtiles(
    processed_root: str,
    *,
    pe_ed: str,
    hb_la_ed: str,
    hb_country_ed: str,
    hpi_ed: str,
    median_ed: str,
    epc_ed: str,
    ee_ed: str,
) -> str:
    return insights_inputs_snapshot(
        Path(processed_root),
        pe_ed=pe_ed,
        hb_la_ed=hb_la_ed,
        hb_country_ed=hb_country_ed,
        hpi_ed=hpi_ed,
        median_ed=median_ed,
        epc_ed=epc_ed,
        ee_ed=ee_ed,
        census_stem=POPULATION_DERIVED_STEM,
    )


@st.cache_data
def _housing_insights_payload(
    processed_root: str,
    pe_ed: str,
    hb_la_ed: str,
    hb_country_ed: str,
    hpi_ed: str,
    median_ed: str,
    epc_ed: str,
    ee_ed: str,
    preset: str,
    custom_regions_tuple: tuple[str, ...],
    horizon_years: int,
    pe_anchor_years_key: str,
    inputs_snapshot: str,
) -> dict[str, Any]:
    _ = inputs_snapshot
    pe_anchor: tuple[int, int] | None = DEFAULT_PE_ANCHOR_YEARS if pe_anchor_years_key == "anchor" else None
    return build_insights_payload(
        processed_root,
        pe_ed=pe_ed,
        hb_la_ed=hb_la_ed,
        hb_country_ed=hb_country_ed,
        hpi_ed=hpi_ed,
        median_ed=median_ed,
        epc_ed=epc_ed,
        ee_ed=ee_ed,
        census_stem=POPULATION_DERIVED_STEM,
        preset=preset,
        custom_regions=custom_regions_tuple,
        horizon_years=horizon_years,
        pe_anchor_years=pe_anchor,
        supply_compare_fy=DEFAULT_SUPPLY_COMPARE_FY,
    )


def _render_tab_findings(payload: dict[str, Any], tab_key: str, *, title: str = "Key findings — this section") -> None:
    fbt = payload.get("findings_by_tab")
    if not isinstance(fbt, dict):
        return
    lines = fbt.get(tab_key) or []
    if not lines:
        return
    st.subheader(title)
    for line in lines:
        st.markdown(f"- {line}")


def _render_table_caps(df: pd.DataFrame, *, cap: int = 15) -> None:
    if df is None or df.empty:
        st.info("No rows for this selection.")
        return
    st.dataframe(df.head(cap), width=ST_WIDTH, height=min(420, 120 + 28 * min(cap, len(df))))
    if len(df) > cap:
        with st.expander("Show up to 50 rows"):
            st.dataframe(df.head(50), width=ST_WIDTH, height=min(600, 120 + 26 * min(50, len(df))))


def _parse_inputs_snapshot(snapshot: str) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for token in str(snapshot).split("|"):
        parts = token.split(":")
        if len(parts) != 3:
            continue
        name, mtime_ns, size = parts
        if mtime_ns == "missing":
            continue
        try:
            out[name] = (int(mtime_ns), int(size))
        except ValueError:
            continue
    return out


def main() -> None:
    st.set_page_config(page_title="Housing insights briefing", layout="wide")
    st.title("Housing insights briefing")
    st.caption(
        "One-page read of affordability, entry pressure, regional ratios, supply, and EPC context — "
        "built from tidy Parquet under `data/processed/` (no live ONS fetch)."
    )

    if "insights_horizon_years" not in st.session_state:
        st.session_state.insights_horizon_years = 5

    with st.sidebar:
        st.subheader("Briefing preset")
        preset = st.radio(
            "Geography preset",
            options=[PRESET_NATIONAL, PRESET_LONDON_COMMUTER, PRESET_NORTH, PRESET_CUSTOM],
            format_func=lambda k: {
                PRESET_NATIONAL: "National (England & Wales)",
                PRESET_LONDON_COMMUTER: "London commuter belt",
                PRESET_NORTH: "North of England",
                PRESET_CUSTOM: "Custom regions",
            }[k],
            index=0,
        )
        custom_regions: tuple[str, ...] = ()
        if preset == PRESET_CUSTOM:
            custom_regions = tuple(
                st.multiselect(
                    "Regions",
                    options=sorted(REGION_COLOR_DOMAIN),
                    default=["London", "South East"],
                )
            )

        st.subheader("Horizon (shared)")
        pe_win = st.radio(
            "Calendar window for price/earnings LA tables (5a–5c)",
            options=("anchor", "rolling"),
            index=0,
            format_func=lambda x: (
                f"Anchor **{DEFAULT_PE_ANCHOR_YEARS[0]}–{DEFAULT_PE_ANCHOR_YEARS[1]}** when both years exist in data"
                if x == "anchor"
                else "Rolling only: last N calendar years in file"
            ),
            horizontal=False,
        )
        hz = st.radio(
            "N when using rolling window",
            options=(5, 10),
            index=0 if st.session_state.insights_horizon_years == 5 else 1,
            format_func=lambda x: f"Last {x} years",
            horizontal=True,
            disabled=(pe_win == "anchor"),
        )
        st.session_state.insights_horizon_years = int(hz)
        top_n = st.radio(
            "Top N rows/charts (LA-heavy views)",
            options=(10, 25, 50),
            index=1,
            horizontal=True,
        )
        quick_regions = tuple(
            st.multiselect(
                "Quick region filter (charts/tables only)",
                options=sorted(REGION_COLOR_DOMAIN),
                default=[],
                help="Optional extra filter on top of preset. Leave empty to keep all preset regions.",
            )
        )

        st.subheader("Data vintages")
        _pe_opts = list(PRICE_EARNINGS_RATIO_EDITIONS.keys())
        _hb_la_opts = list(HOUSEBUILDING_LA_EDITIONS.keys())
        _hb_c_opts = list(HOUSEBUILDING_COUNTRY_EDITIONS.keys())
        _hpi_opts = list(UK_HPI_MONTHLY_EDITIONS.keys())
        _med_opts = list(MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS.keys())
        _epc_opts = list(EPC_EDITIONS.keys())
        _ee_opts = list(EE_FIVEYEAR_EDITIONS.keys())
        pe_ed = st.selectbox(
            "Price / earnings (ONS)",
            options=_pe_opts,
            index=_select_index(_pe_opts, default_key="current"),
            format_func=lambda k: PRICE_EARNINGS_RATIO_EDITIONS[k].label,
        )
        hb_la_ed = st.selectbox(
            "House building (LA)",
            options=_hb_la_opts,
            index=_select_index(_hb_la_opts, default_key="fye_march2025"),
            format_func=lambda k: HOUSEBUILDING_LA_EDITIONS[k].label,
        )
        median_ed = st.selectbox(
            "Median price admin (watchlist)",
            options=_med_opts,
            index=_select_index(_med_opts, default_key="current"),
            format_func=lambda k: MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS[k].label,
        )
        epc_ed = st.selectbox(
            "EPC bands",
            options=_epc_opts,
            index=_select_index(_epc_opts, default_key="march2025"),
            format_func=lambda k: EPC_EDITIONS[k].label,
        )
        with st.expander("Advanced/optional vintages", expanded=False):
            st.caption("These vintages are tracked for provenance but do not currently drive hero KPIs on this page.")
            hb_country_ed = st.selectbox(
                "House building (country)",
                options=_hb_c_opts,
                index=_select_index(_hb_c_opts, default_key="current"),
                format_func=lambda k: HOUSEBUILDING_COUNTRY_EDITIONS[k].label,
            )
            hpi_ed = st.selectbox(
                "UK HPI monthly",
                options=_hpi_opts,
                index=_select_index(_hpi_opts, default_key="march2026"),
                format_func=lambda k: UK_HPI_MONTHLY_EDITIONS[k].label,
            )
            ee_ed = st.selectbox(
                "Energy efficiency rolling",
                options=_ee_opts,
                index=_select_index(_ee_opts, default_key="march2025"),
                format_func=lambda k: EE_FIVEYEAR_EDITIONS[k].label,
            )

    snap = _insights_inputs_snapshot_mtiles(
        str(PROCESSED_DIR),
        pe_ed=pe_ed,
        hb_la_ed=hb_la_ed,
        hb_country_ed=hb_country_ed,
        hpi_ed=hpi_ed,
        median_ed=median_ed,
        epc_ed=epc_ed,
        ee_ed=ee_ed,
    )
    payload = _housing_insights_payload(
        str(PROCESSED_DIR),
        pe_ed,
        hb_la_ed,
        hb_country_ed,
        hpi_ed,
        median_ed,
        epc_ed,
        ee_ed,
        preset,
        custom_regions,
        st.session_state.insights_horizon_years,
        str(pe_win),
        snap,
    )
    meta = payload["meta"]
    hero = payload["hero"]
    tables: dict[str, pd.DataFrame] = payload["tables"]

    st.markdown(
        f"**Scope:** {meta['preset_label']} · workplace-based earnings where used · "
        f"**Data** loaded from `data/processed/`. {meta['horizon_label']} {meta['editions']}"
    )
    readiness = payload.get("data_readiness") or {}
    if isinstance(readiness, dict):
        st.caption(
            "Data readiness: "
            f"required {int(readiness.get('required_loaded', 0))}/{int(readiness.get('required_total', 0))} · "
            f"active {int(readiness.get('active_loaded', 0))}/{int(readiness.get('active_total', 0))} · "
            f"optional {int(readiness.get('optional_loaded', 0))}/{int(readiness.get('optional_total', 0))}"
        )
    sigs = _parse_inputs_snapshot(snap)
    fresh_keys = [
        f"ons_price_earnings_ratio_{pe_ed}_5c_tidy.parquet",
        f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet",
        f"ons_epc_bands_{epc_ed}_1a_tidy.parquet",
    ]
    fresh_bits: list[str] = []
    for key in fresh_keys:
        rec = sigs.get(key)
        if rec is None:
            continue
        ts = datetime.fromtimestamp(rec[0] / 1_000_000_000, tz=timezone.utc).strftime("%Y-%m-%d")
        fresh_bits.append(f"`{key}` ({ts})")
    if fresh_bits:
        st.caption("Freshness (mtime UTC): " + " · ".join(fresh_bits))
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v_end = hero.get("ew_ratio_end")
        d_lbl = hero.get("ew_ratio_delta_str")
        st.metric(
            label="England & Wales median P/E ratio (table 1c)",
            value=f"{v_end:.2f}" if v_end is not None else "—",
            delta=d_lbl if d_lbl else None,
            help="ONS table 1c, region row England and Wales; delta label includes baseline calendar year.",
        )
    with c2:
        n_ep = hero.get("entry_pressure_n")
        st.metric(
            label="LAs: Δ lower-quartile price > Δ median price",
            value=f"{int(n_ep)}" if n_ep is not None else "—",
            help=hero.get("entry_pressure_caption", ""),
        )
    with c3:
        sr = hero.get("supply_region")
        sd = hero.get("supply_delta")
        sf0, sf1 = hero.get("supply_fy0"), hero.get("supply_fy1")
        if sr and sd is not None and sf0 and sf1:
            st.metric(
                label=f"Largest Δ regional starts ({sf0} → {sf1})",
                value=sr,
                delta=f"{sd:+.0f} dwellings vs {sf0}",
            )
        else:
            st.metric(label="Largest Δ regional starts", value="—")
    with c4:
        br, wr = hero.get("epc_best_region"), hero.get("epc_worst_region")
        bp, wp = hero.get("epc_best_pct"), hero.get("epc_worst_pct")
        if br and wr and bp is not None and wp is not None:
            st.metric(label="EPC A–C share — best region", value=f"{br} ({bp:.1f}%)")
            st.caption(f"Lowest regional A–C share: **{wr}** ({wp:.1f}%).")
        else:
            st.metric(label="EPC A–C share — best region", value="—")

    tab_labels = {
        "affordability": "Affordability",
        "entry": "Entry barrier",
        "regions": "Regions",
        "supply": "Supply & liquidity",
        "energy": "Energy & equity",
    }
    reg_scale = alt.Scale(domain=REGION_COLOR_DOMAIN, range=REGION_COLOR_RANGE)

    t1, t2, t3, t4, t5 = st.tabs(list(tab_labels.values()))

    with t1:
        st.caption(
            "Explore underlying series on **Median price (admin)** and **Price / earnings ratio** "
            "(sidebar multipage)."
        )
        try:
            st.page_link("pages/12_Median_price_admin.py", label="Median price (admin)")
            st.page_link("pages/14_House_price_earnings_ratio.py", label="Price / earnings ratio")
        except Exception:
            st.markdown(
                "- `pages/12_Median_price_admin.py`\n"
                "- `pages/14_House_price_earnings_ratio.py`"
            )
        rdf = tables.get("affordability_region")
        if quick_regions and isinstance(rdf, pd.DataFrame) and not rdf.empty:
            rdf = rdf[rdf["region"].isin(quick_regions)]
        if isinstance(rdf, pd.DataFrame) and not rdf.empty:
            st.markdown("**By region** (median of LAs in scope)")
            ch_r = (
                alt.Chart(rdf)
                .mark_circle(size=140, opacity=0.9)
                .encode(
                    x=alt.X("delta_median_price:Q", title="Δ Median house price (£) — regional median of LAs"),
                    y=alt.Y("delta_ratio:Q", title="Δ Price / earnings ratio — regional median of LAs"),
                    color=alt.Color("region:N", scale=reg_scale, title="Region"),
                    tooltip=["region", "delta_median_price", "delta_ratio"],
                )
                .properties(height=380)
            )
            st.altair_chart(ch_r, width=ST_WIDTH)
        df = tables["affordability"]
        if quick_regions and not df.empty:
            df = df[df["region"].isin(quick_regions)]
        blocked = render_missing_or_empty(
            payload["missing"],
            "affordability",
            is_empty=df.empty and (not isinstance(rdf, pd.DataFrame) or rdf.empty),
            empty_message="No rows for current selection. Affordability charts need tables 5a-5c for the selected horizon.",
        )
        if not blocked and not df.empty:
            with st.expander("Local authorities (same horizon)", expanded=False):
                top_df = df.sort_values("delta_ratio", ascending=False).head(int(top_n))
                ch = (
                    alt.Chart(top_df)
                    .mark_circle(size=70, opacity=0.75)
                    .encode(
                        x=alt.X("delta_median_price:Q", title="Δ Median house price (£)"),
                        y=alt.Y("delta_ratio:Q", title="Δ Price / earnings ratio"),
                        color=alt.Color("region:N", scale=reg_scale, title="Region"),
                        tooltip=["la_name", "region", "delta_median_price", "delta_ratio", "delta_earnings"],
                    )
                    .properties(height=380)
                )
                st.altair_chart(ch, width=ST_WIDTH)
                _render_table_caps(df.sort_values("delta_ratio", ascending=False), cap=int(top_n))
        with st.expander("Method & caveats"):
            st.markdown(
                "- House prices use year-ending-September rolling periods; earnings are ASHE workplace gross for a calendar year.\n"
                "- England & Wales local authorities only where published.\n"
                "- Colours follow a fixed regional palette so charts stay comparable across presets."
            )
        st.subheader("Executive summary")
        for line in payload.get("findings_overview") or []:
            st.markdown(f"- {line}")
        _render_tab_findings(payload, "affordability", title="Key findings — affordability")

    with t2:
        st.caption(
            "Entry pressure is **not** an ONS FTB definition. "
            "Optional watchlist lines use HPSSA table 2a (`pages/12_Median_price_admin.py`)."
        )
        edf = tables["entry"]
        if quick_regions and not edf.empty:
            edf = edf[edf["region"].isin(quick_regions)]
        blocked = render_missing_or_empty(
            payload["missing"],
            "entry",
            is_empty=edf.empty,
            empty_message="No rows for current selection. Entry chart needs tables 5a and 6a.",
        )
        if not blocked and not edf.empty:
            top = edf.head(int(top_n))
            ch = (
                alt.Chart(top)
                .mark_bar()
                .encode(
                    x=alt.X("entry_gap:Q", title="Δ6a lower-quartile price − Δ5a median price (£)"),
                    y=alt.Y("la_name:N", sort="-x", title=""),
                    color=alt.Color("region:N", scale=reg_scale),
                    tooltip=["la_name", "region", "entry_gap", "delta_lq_price", "delta_median_price"],
                )
                .properties(height=min(520, 120 + 18 * len(top)))
            )
            st.altair_chart(ch, width=ST_WIDTH)
        _render_table_caps(edf, cap=int(top_n))
        wl = payload.get("entry_watchlist")
        if not isinstance(wl, pd.DataFrame):
            wl = pd.DataFrame()
        if not wl.empty:
            st.subheader("Watchlist — median price (existing), table 2a")
            ch2 = (
                alt.Chart(wl)
                .mark_line(point=True)
                .encode(
                    x=alt.X("ay:O", title="Year (Dec-ending)"),
                    y=alt.Y("median_price_gbp:Q", title="Median price (£)"),
                    color=alt.Color("local_authority_name:N", title="LA"),
                    tooltip=["local_authority_name", "ay", "median_price_gbp"],
                )
                .properties(height=280)
                .facet("local_authority_name:N", columns=2)
            )
            st.altair_chart(ch2, width=ST_WIDTH)
        with st.expander("Method & caveats"):
            st.markdown(
                "- 6a vs 5a compares lower-quartile stock prices with median stock prices; interpretation is contextual.\n"
                "- Watchlist LAs are fixed in code for reproducibility."
            )
        _render_tab_findings(payload, "entry")

    with t3:
        st.caption(
            "Regional **price/earnings ratios** (ONS table 1c) indexed to 100 in the first calendar year of the horizon. "
            "See `pages/14_House_price_earnings_ratio.py` for full charts."
        )
        rdf = tables["regions"]
        if quick_regions and not rdf.empty:
            rdf = rdf[rdf["region"].isin(quick_regions)]
        blocked = render_missing_or_empty(
            payload["missing"],
            "regions",
            is_empty=rdf.empty,
            empty_message="No rows for current selection. Regional series needs table 1c with region rows for the horizon.",
        )
        if not blocked and not rdf.empty:
            ch = (
                alt.Chart(rdf)
                .mark_line(point=True)
                .encode(
                    x=alt.X("pe_year:O", title="Calendar year"),
                    y=alt.Y("index_norm:Q", title="Index (first horizon year = 100)"),
                    color=alt.Color("region:N", scale=reg_scale),
                    tooltip=["region", "pe_year", alt.Tooltip("value", format=".2f", title="Ratio"), "index_norm"],
                )
                .properties(height=380)
            )
            st.altair_chart(ch, width=ST_WIDTH)
        _render_table_caps(rdf.drop(columns=["index_norm"], errors="ignore"))
        with st.expander("Method & caveats"):
            st.markdown(
                "- Mixes published ratio definitions across years; not a forecast.\n"
                "- Wales and English regions use the same indexing within the selected window."
            )
        _render_tab_findings(payload, "regions")

    with t4:
        st.caption(
            f"{payload.get('supply_note', '')} "
            "Regime-style language belongs in captions only — not causal claims."
        )
        try:
            st.page_link("pages/15_Housing_market_comparator.py", label="Housing market comparator (joined snapshot)")
        except Exception:
            st.caption("Comparator: `pages/15_Housing_market_comparator.py`.")
        sdf = tables["supply"]
        if quick_regions and not sdf.empty:
            sdf = sdf[sdf["region"].isin(quick_regions)]
        blocked = render_missing_or_empty(
            payload["missing"],
            "supply",
            is_empty=sdf.empty,
            empty_message="No rows for current selection. Supply bars need LA house-building Parquet.",
        )
        if not blocked and not sdf.empty:
            ch = (
                alt.Chart(sdf)
                .mark_bar()
                .encode(
                    x=alt.X("dwellings:Q", title="Dwellings (sum of LAs)"),
                    y=alt.Y("region:N", title="", sort="-x"),
                    color=alt.Color("measure:N", title=""),
                    row=alt.Row("financial_year:N", title="FY"),
                )
                .properties(height=120)
            )
            st.altair_chart(ch, width=ST_WIDTH)
        _render_table_caps(sdf, cap=int(top_n))
        with st.expander("Method & caveats"):
            st.markdown(
                "- Financial years differ from calendar years used in price/earnings tables.\n"
                "- Regional sums exclude Scotland and Northern Ireland rows in the LA file."
            )
        _render_tab_findings(payload, "supply")

    with t5:
        st.caption(
            "EPC band distribution (table 1a). Rolling energy efficiency statistics use different periods — "
            f"see [EE dataset]({EE_DATASET_PAGE})."
        )
        raw = payload.get("energy_stack_raw")
        if not isinstance(raw, pd.DataFrame):
            raw = pd.DataFrame()
        if quick_regions and not raw.empty:
            raw = raw[raw["country_or_region_name"].isin(quick_regions)]
        blocked = render_missing_or_empty(
            payload["missing"],
            "energy",
            is_empty=raw.empty,
            empty_message="No rows for current selection. EPC stacked profile needs `ons_epc_bands_*_1a_tidy.parquet`.",
        )
        if not blocked and not raw.empty:
            ch = (
                alt.Chart(raw)
                .mark_bar()
                .encode(
                    x=alt.X("percentage:Q", title="% of dwellings", stack="zero"),
                    y=alt.Y("country_or_region_name:N", title="Region", sort="-x"),
                    color=alt.Color("epc_band:N", title="Band", sort=list("ABCDEFG")),
                    tooltip=["country_or_region_name", "epc_band", alt.Tooltip("percentage", format=".2f")],
                )
                .properties(height=min(520, 200 + 22 * raw["country_or_region_name"].nunique()))
            )
            st.altair_chart(ch, width=ST_WIDTH)
        st.markdown("**Regional A–C share (ranking)**")
        epc_table = tables["energy"]
        if quick_regions and not epc_table.empty:
            epc_table = epc_table[epc_table["region"].isin(quick_regions)]
        _render_table_caps(epc_table, cap=int(top_n))
        jf = payload.get("joined_preview")
        if not isinstance(jf, pd.DataFrame):
            jf = pd.DataFrame()
        if not jf.empty:
            st.caption("Preview from `joined_la_housing_market_snapshot.parquet` (optional build).")
            st.dataframe(jf, width=ST_WIDTH, height=220)
        with st.expander("Method & caveats"):
            st.markdown(
                "- EPC percentages are stock modelled estimates, not certificates per dwelling.\n"
                "- A–C share sums published band percentages; small rounding differences may occur."
            )
        _render_tab_findings(payload, "energy")

    st.divider()
    ogl_attribution_expander()
    st.markdown(
        f"- [Price / earnings (ONS)]({PE_DATASET_PAGE})\n"
        f"- [House building LA]({HB_LA_DATASET_PAGE}) · [House building UK indicators]({HB_COUNTRY_DATASET_PAGE})\n"
        f"- [UK HPI monthly]({HPI_DATASET_PAGE})\n"
        f"- [Median price existing (admin)]({EXISTING_DATASET_PAGE})\n"
        f"- [EPC bands]({EPC_DATASET_PAGE}) · [Energy efficiency rolling]({EE_DATASET_PAGE})\n"
        f"- Census 2021 population: `{POPULATION_DERIVED_STEM}.parquet`"
    )

    export_choice = st.selectbox(
        "Export CSV — choose section",
        options=list(tab_labels.keys()),
        format_func=lambda k: tab_labels[k],
    )
    ex_df = tables.get(export_choice)
    if not isinstance(ex_df, pd.DataFrame):
        ex_df = pd.DataFrame()
    if ex_df.empty:
        st.caption("No rows to export for this section.")
    else:
        st.download_button(
            label=f"Download `{export_choice}` table as CSV",
            data=ex_df.to_csv(index=False).encode("utf-8"),
            file_name=f"housing_insights_{export_choice}.csv",
            mime="text/csv",
        )


main()
