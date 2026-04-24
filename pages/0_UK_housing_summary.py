"""Streamlit: UK housing summary — country, region, LA supply plus EPC/Energy snapshots (explicit periods)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from ons_census2021_config import BULLETIN_URL as CENSUS_BULLETIN_URL, POPULATION_DERIVED_STEM
from ons_ee_fiveyear_config import DATASET_PAGE as EE_DATASET_PAGE, EE_FIVEYEAR_EDITIONS
from ons_epc_config import DATASET_PAGE as EPC_DATASET_PAGE, EPC_EDITIONS
from ons_housebuilding_country_config import (
    DATASET_PAGE as HB_COUNTRY_DATASET_PAGE,
    HOUSEBUILDING_COUNTRY_EDITIONS,
)
from ons_housebuilding_country_periods import preferred_period_order
from ons_housebuilding_la_config import DATASET_PAGE as HB_LA_DATASET_PAGE, HOUSEBUILDING_LA_EDITIONS
from housing_analytics.hpi_prpi_callout import buy_vs_rent_spread_caption
from housing_analytics.insights_briefing import (
    DEFAULT_PE_ANCHOR_YEARS,
    DEFAULT_SUPPLY_COMPARE_FY,
    PRESET_NATIONAL,
    build_insights_payload,
    insights_inputs_snapshot,
)
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_PERIOD_START_YEAR = re.compile(r"^Q2 (\d{4})")

FOUR_NATIONS = {"England", "Wales", "Scotland", "Northern Ireland"}

_BRIEF_PE_ED = "current"
_BRIEF_HB_LA_ED = "fye_march2025"
_BRIEF_HB_COUNTRY_ED = "current"
_BRIEF_HPI_ED = "march2026"
_BRIEF_MEDIAN_ED = "current"
_BRIEF_EPC_ED = "march2025"
_BRIEF_EE_ED = "march2025"


def _briefing_inputs_snapshot(root: Path) -> str:
    return insights_inputs_snapshot(
        root,
        pe_ed=_BRIEF_PE_ED,
        hb_la_ed=_BRIEF_HB_LA_ED,
        hb_country_ed=_BRIEF_HB_COUNTRY_ED,
        hpi_ed=_BRIEF_HPI_ED,
        median_ed=_BRIEF_MEDIAN_ED,
        epc_ed=_BRIEF_EPC_ED,
        ee_ed=_BRIEF_EE_ED,
        census_stem=POPULATION_DERIVED_STEM,
    )


@st.cache_data
def _uk_summary_briefing_payload(processed_root: str, inputs_snapshot: str) -> dict[str, Any]:
    _ = inputs_snapshot
    return build_insights_payload(
        processed_root,
        pe_ed=_BRIEF_PE_ED,
        hb_la_ed=_BRIEF_HB_LA_ED,
        hb_country_ed=_BRIEF_HB_COUNTRY_ED,
        hpi_ed=_BRIEF_HPI_ED,
        median_ed=_BRIEF_MEDIAN_ED,
        epc_ed=_BRIEF_EPC_ED,
        ee_ed=_BRIEF_EE_ED,
        census_stem=POPULATION_DERIVED_STEM,
        preset=PRESET_NATIONAL,
        custom_regions=(),
        horizon_years=5,
        pe_anchor_years=DEFAULT_PE_ANCHOR_YEARS,
        supply_compare_fy=DEFAULT_SUPPLY_COMPARE_FY,
    )


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def _summary_inputs_snapshot(
    root: Path,
    hb_country_ed: str,
    hb_la_ed: str,
    ee_ed: str,
    epc_ed: str,
) -> str:
    """Mtime/size for every Parquet/CSV this page reads so cache misses when ETL outputs change."""
    paths = (
        root / f"ons_housebuilding_country_{hb_country_ed}_tidy.parquet",
        root / f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet",
        root / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet",
        root / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet",
        root / f"{POPULATION_DERIVED_STEM}.parquet",
        root / "uk_housing_starts_tidy.parquet",
        root / "uk_housing_starts_tidy.csv",
    )
    parts: list[str] = []
    for p in paths:
        if p.is_file():
            stat = p.stat()
            parts.append(f"{p.name}:{stat.st_mtime_ns}:{stat.st_size}")
        else:
            parts.append(f"{p.name}:missing")
    return "|".join(parts)


def _sorted_fy(series: pd.Series) -> list[str]:
    return sorted(series.dropna().astype(str).unique().tolist())


def _rolling_period_sort_key(period: str) -> int:
    m = _PERIOD_START_YEAR.match(str(period).strip())
    return int(m.group(1)) if m else 0


def _ordered_rolling_periods(series: pd.Series) -> list[str]:
    uniq = series.dropna().astype(str).unique()
    return sorted(uniq, key=_rolling_period_sort_key)


def _country_fy_slice(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[
        (df["frequency"].astype(str) == "annual_financial_year")
        & (df["sector"].astype(str).str.strip() == "All Dwellings")
    ].copy()
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    return sub.dropna(subset=["dwellings"])


def _latest_fy_period(sub: pd.DataFrame) -> str | None:
    if sub.empty:
        return None
    order = preferred_period_order(sub["period"])
    return order[-1] if order else None


def _build_hpi_prpi_overlap(root: Path) -> pd.DataFrame:
    """Great Britain overlap, rebased to first overlapping month (100)."""
    prpi_path = root / "ons_private_rental_index_v41_tidy.parquet"
    hpi_path = root / "ons_uk_hpi_monthly_march2026_1_tidy.parquet"
    if not prpi_path.is_file() or not hpi_path.is_file():
        return pd.DataFrame()
    prpi = load_processed_parquet(prpi_path.relative_to(root)).copy()
    hpi = load_processed_parquet(hpi_path.relative_to(root)).copy()
    prpi = prpi[
        (prpi["variable"].astype(str) == "index")
        & (prpi["geography_name"].astype(str) == "Great Britain")
    ].copy()
    hpi = hpi[hpi["geography"].astype(str) == "Great Britain"].copy()
    if prpi.empty or hpi.empty:
        return pd.DataFrame()
    prpi["period"] = pd.to_datetime(prpi["month_label"].astype(str), format="%b-%y", errors="coerce")
    hpi["period"] = pd.to_datetime(hpi["time_period"].astype(str), format="%b %Y", errors="coerce")
    prpi["value"] = pd.to_numeric(prpi["value"], errors="coerce")
    hpi["value"] = pd.to_numeric(hpi["value"], errors="coerce")
    prpi = prpi.dropna(subset=["period", "value"])[["period", "value"]].rename(columns={"value": "prpi_index"})
    hpi = hpi.dropna(subset=["period", "value"])[["period", "value"]].rename(columns={"value": "hpi_index"})
    joined = prpi.merge(hpi, on="period", how="inner").sort_values("period")
    if joined.empty:
        return pd.DataFrame()
    base = joined.iloc[0]
    if float(base["prpi_index"]) == 0 or float(base["hpi_index"]) == 0:
        return pd.DataFrame()
    joined["prpi_rebased"] = joined["prpi_index"] / float(base["prpi_index"]) * 100.0
    joined["hpi_rebased"] = joined["hpi_index"] / float(base["hpi_index"]) * 100.0
    joined["hpi_minus_prpi"] = joined["hpi_rebased"] - joined["prpi_rebased"]
    return joined


@st.cache_data
def _summary_payload(
    processed_root: str,
    hb_country_ed: str,
    hb_la_ed: str,
    ee_ed: str,
    epc_ed: str,
    la_mode: str,
    n_years: int,
    top_n_la: int,
    include_bundled: bool,
    country_trend_years: int,
    include_census_rates: bool,
    ee_trend_n_periods: int,
    include_ee_period_trend: bool,
    include_epc_ee_scatter: bool,
    inputs_snapshot: str,
) -> dict[str, Any]:
    """Load tidy files once; return bullets and chart-ready frames.

    ``inputs_snapshot`` is part of the ``@st.cache_data`` key (must not use a leading underscore — Streamlit excludes those from hashing).
    """
    root = Path(processed_root)
    insight_cards = [
        {
            "headline": "Supply has not consistently returned to pre-crisis strength.",
            "evidence": (
                'ons_housebuilding_country_current_tidy.parquet (measure="started", '
                'frequency="annual_financial_year").'
            ),
            "caveat": (
                "Financial-year starts are flow measures; do not compare directly to calendar-year "
                "affordability without period labeling."
            ),
        },
        {
            "headline": "Affordability stress is concentrated, not uniform.",
            "evidence": (
                "joined_la_housing_market_snapshot.parquet using pe_affordability_ratio "
                "(e.g., count LAs above 10x)."
            ),
            "caveat": (
                "Workplace-based ratio follows ONS workplace earnings framework "
                "(tables 5a-5c), not residence income."
            ),
        },
        {
            "headline": "Regional house price disparities remain large.",
            "evidence": "Lane A regional summaries from median_price_existing_gbp.",
            "caveat": (
                "This is a median-of-LA medians in current join context, not population-weighted "
                "regional median."
            ),
        },
        {
            "headline": "Entry-level pressure can exceed headline median pressure in many areas.",
            "evidence": "Delta comparison logic (6a vs 5a) in housing_analytics/insights_briefing.py.",
            "caveat": "Proxy for lower-end pressure; not an official first-time-buyer metric.",
        },
        {
            "headline": "Energy efficiency has improved over rolling windows.",
            "evidence": (
                'ons_ee_fiveyear_*_1c_tidy.parquet (measure_breakdown="All"), EPC C+ trend.'
            ),
            "caveat": (
                "Overlapping windows smooth short-term movements; not annual change series."
            ),
        },
        {
            "headline": "Energy performance differs materially by region.",
            "evidence": (
                "region_housing_market_snapshot.parquet (epc_pct_bands_abc, ee_epc_c_plus_pct)."
            ),
            "caveat": (
                "Region-level signal only in this lane; avoid LA-level EPC band claims."
            ),
        },
        {
            "headline": "HPI has outgrown PRPI over overlapping periods in selected geographies.",
            "evidence": (
                "housing_analytics/hpi_prpi_callout.py indexed spread (hpi_minus_prpi logic)."
            ),
            "caveat": (
                "Rebased index spread, not sterling housing-cost comparison."
            ),
        },
        {
            "headline": "Some regions combine weaker supply with stronger affordability strain.",
            "evidence": (
                "Lane B cross-metric comparison (region_supply_starts plus affordability-linked context)."
            ),
            "caveat": "Descriptive co-movement only; no causal inference.",
        },
    ]

    path_country = root / f"ons_housebuilding_country_{hb_country_ed}_tidy.parquet"
    path_la = root / f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet"
    path_ee = root / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet"
    path_epc = root / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet"
    path_bundled_pq = root / "uk_housing_starts_tidy.parquet"
    path_bundled_csv = root / "uk_housing_starts_tidy.csv"

    out: dict[str, Any] = {
        "bullets": [],
        "insight_cards": insight_cards,
        "country_plot": None,
        "latest_country_period": None,
        "country_missing": None,
        "country_info": None,
        "la_region_frames": [],
        "la_window_label": "",
        "la_top_la": None,
        "la_y_title": "",
        "la_missing": None,
        "la_info": None,
        "ee_last": None,
        "latest_rp": None,
        "ee_missing": None,
        "epc_band_c": None,
        "epc_key_bands": None,
        "epc_missing": None,
        "bundled_reg": None,
        "bundled_missing": None,
        "bundled_year_span": 0,
        "country_ts": None,
        "country_yoy": None,
        "region_balance": None,
        "census_rates": None,
        "census_rates_note": None,
        "ee_trend_long": None,
        "epc_ee_scatter": None,
        "manifest_preview": None,
        "hpi_prpi_callout": None,
        "chart2_affordability": None,
        "chart3_regional_median": None,
        "chart4_entry_gap": None,
        "chart5_epc_spread": None,
        "chart6_hpi_prpi": None,
    }
    bullets: list[str] = out["bullets"]

    # Country
    if not path_country.is_file():
        out["country_missing"] = path_country.name
    else:
        hc = load_processed_parquet(path_country.relative_to(root))
        fy = _country_fy_slice(hc)
        latest_p = _latest_fy_period(fy)
        out["latest_country_period"] = latest_p
        if latest_p is None:
            out["country_info"] = "No annual financial year rows found."
        else:
            view = fy[fy["period"].astype(str) == latest_p].copy()
            nations = view[view["country_name"].isin(FOUR_NATIONS)]
            if nations.empty:
                out["country_info"] = "No England / Wales / Scotland / Northern Ireland rows for the latest financial year."
            else:
                plot_country = nations.copy()
                plot_country["measure_label"] = plot_country["measure"].astype(str).str.capitalize()
                out["country_plot"] = plot_country
                for m_key, label in (("started", "starts"), ("completed", "completions")):
                    subm = nations[nations["measure"].astype(str).str.lower() == m_key]
                    if not subm.empty:
                        top = subm.sort_values("dwellings", ascending=False).iloc[0]
                        bullets.append(
                            f"Among the four nations, **{top['country_name']}** had the highest **{label}** "
                            f"in **{latest_p}** ({int(top['dwellings']):,} dwellings)."
                        )

        if not fy.empty:
            order_fy = preferred_period_order(fy["period"])
            n_ts = max(3, min(int(country_trend_years), len(order_fy)))
            use_p = order_fy[-n_ts:] if len(order_fy) >= n_ts else order_fy
            ts = fy[fy["period"].isin(use_p)].copy()
            ts = ts[ts["country_name"].isin(FOUR_NATIONS)]
            ts = ts[ts["measure"].astype(str).str.lower().isin(["started", "completed"])]
            ts["measure_label"] = ts["measure"].astype(str).str.capitalize()
            ts["dwellings"] = pd.to_numeric(ts["dwellings"], errors="coerce")
            out["country_ts"] = ts.dropna(subset=["dwellings"])
            if len(order_fy) >= 2:
                p_last, p_prev = order_fy[-1], order_fy[-2]
                eng = fy[
                    (fy["country_name"].astype(str) == "England")
                    & (fy["measure"].astype(str).str.lower() == "started")
                ]
                r1 = eng[eng["period"].astype(str) == p_last]["dwellings"]
                r0 = eng[eng["period"].astype(str) == p_prev]["dwellings"]
                if len(r1) and len(r0) and pd.notna(r1.iloc[0]) and pd.notna(r0.iloc[0]) and float(r0.iloc[0]) != 0:
                    d0, d1 = float(r0.iloc[0]), float(r1.iloc[0])
                    pct = (d1 - d0) / d0 * 100.0
                    out["country_yoy"] = (p_prev, p_last, d0, d1, pct)
                    bullets.append(
                        f"**England starts** moved from **{d0:,.0f}** ({p_prev}) to **{d1:,.0f}** ({p_last}) "
                        f"({pct:+.1f}% year-on-year)."
                    )

    # LA
    if not path_la.is_file():
        out["la_missing"] = path_la.name
    else:
        la = load_processed_parquet(path_la.relative_to(root))
        la = la.copy()
        la["dwellings"] = pd.to_numeric(la["dwellings"], errors="coerce")
        la["financial_year"] = la["financial_year"].astype(str)
        all_years = _sorted_fy(la["financial_year"])
        if not all_years:
            out["la_info"] = "No financial years in LA file."
        else:
            if la_mode == "Latest financial year":
                use_years = [all_years[-1]]
                window_label = f"**{use_years[0]}**"
            else:
                use_years = all_years[-int(n_years) :] if len(all_years) >= int(n_years) else all_years
                window_label = (
                    f"mean annual total over **{use_years[0]}**–**{use_years[-1]}** ({len(use_years)} years)"
                )
            out["la_window_label"] = window_label
            sub_la = la[la["financial_year"].isin(use_years)]
            agg = (
                sub_la.groupby(["Region or Country Name", "measure"], observed=True, dropna=False)["dwellings"]
                .sum(min_count=1)
                .reset_index()
            )
            if la_mode == "Mean over last N financial years":
                agg["dwellings"] = agg["dwellings"] / len(use_years)

            for m_key, label in (("starts", "Starts"), ("completions", "Completions")):
                mdf = agg[agg["measure"].astype(str).str.lower() == m_key].copy()
                if mdf.empty:
                    continue
                mdf = mdf.sort_values("dwellings", ascending=False)
                out["la_region_frames"].append({"title": label, "df": mdf, "use_years_n": len(use_years)})
                top_r = mdf.iloc[0]
                bullets.append(
                    f"From the LA dataset ({window_label}), **{top_r['Region or Country Name']}** "
                    f"has the highest **{label.lower()}** ({float(top_r['dwellings']):,.1f} dwellings"
                    f"{', mean per year' if len(use_years) > 1 else ''})."
                )

            la_starts = sub_la[sub_la["measure"].astype(str).str.lower() == "starts"].copy()
            if not la_starts.empty:
                if la_mode == "Mean over last N financial years":
                    by_la = (
                        la_starts.groupby("Local Authority Name", observed=True, dropna=False)["dwellings"]
                        .sum(min_count=1)
                        .reset_index()
                    )
                    by_la["dwellings"] = by_la["dwellings"] / len(use_years)
                    y_title = "Mean starts per year"
                else:
                    by_la = (
                        la_starts.groupby("Local Authority Name", observed=True, dropna=False)["dwellings"]
                        .sum(min_count=1)
                        .reset_index()
                    )
                    y_title = "Starts (dwellings)"
                by_la = by_la.sort_values("dwellings", ascending=False).head(int(top_n_la))
                out["la_top_la"] = by_la
                out["la_y_title"] = y_title
                top3 = by_la.head(3)["Local Authority Name"].tolist()
                bullets.append(
                    f"Top local authorities for starts ({window_label}): **{', '.join(top3)}**."
                )

            piv = sub_la.pivot_table(
                index="Region or Country Name",
                columns="measure",
                values="dwellings",
                aggfunc="sum",
                observed=True,
            )
            if la_mode == "Mean over last N financial years" and len(use_years) > 1:
                piv = piv / len(use_years)
            piv = piv.reset_index()
            ren = {c: str(c).strip().lower() for c in piv.columns if c != "Region or Country Name"}
            piv = piv.rename(columns=ren)
            if "starts" in piv.columns and "completions" in piv.columns:
                piv["completion_to_start_ratio"] = piv["completions"] / piv["starts"].replace(0, np.nan)
                out["region_balance"] = piv.sort_values("completions", ascending=False, na_position="last")
                rb = out["region_balance"]
                if not rb.empty and rb["completion_to_start_ratio"].notna().any():
                    idx = rb["completion_to_start_ratio"].idxmax()
                    best = rb.loc[idx]
                    bullets.append(
                        f"Highest **completions-to-starts** ratio ({window_label}): **{best['Region or Country Name']}** "
                        f"({float(best['completion_to_start_ratio']):.2f}). "
                        "Values above 1 imply more completions than starts in the window (pipeline / timing effects)."
                    )

            pop_path = root / f"{POPULATION_DERIVED_STEM}.parquet"
            if include_census_rates and pop_path.is_file():
                pop = load_processed_parquet(pop_path.relative_to(root))
                pop = pop.copy()
                pop["lad_code"] = pop["lad_code"].map(_norm_lad)
                pop["population"] = pd.to_numeric(pop["population"], errors="coerce")
                la_p = sub_la.pivot_table(
                    index=["Local Authority Code", "Local Authority Name", "Region or Country Name"],
                    columns="measure",
                    values="dwellings",
                    aggfunc="sum",
                    observed=True,
                ).reset_index()
                if la_mode == "Mean over last N financial years" and len(use_years) > 1:
                    for c in la_p.columns:
                        if c not in ("Local Authority Code", "Local Authority Name", "Region or Country Name"):
                            la_p[c] = la_p[c] / len(use_years)
                ren2 = {
                    c: str(c).strip().lower()
                    for c in la_p.columns
                    if c not in ("Local Authority Code", "Local Authority Name", "Region or Country Name")
                }
                la_p = la_p.rename(columns=ren2)
                la_p["lad_code"] = la_p["Local Authority Code"].map(_norm_lad)
                jm = la_p.merge(pop[["lad_code", "population"]], on="lad_code", how="left")
                jm = jm[jm["population"].notna() & (jm["population"] > 0)]
                if not jm.empty:
                    for col in ("starts", "completions"):
                        if col not in jm.columns:
                            jm[col] = np.nan
                    cr = jm.groupby("Region or Country Name", observed=True, dropna=False).agg(
                        starts=("starts", "sum"),
                        completions=("completions", "sum"),
                        population=("population", "sum"),
                    ).reset_index()
                    cr["starts_per_1000"] = cr["starts"] / cr["population"] * 1000.0
                    cr["completions_per_1000"] = cr["completions"] / cr["population"] * 1000.0
                    cr = cr.sort_values("starts_per_1000", ascending=False, na_position="last")
                    out["census_rates"] = cr
                    out["census_rates_note"] = (
                        "Uses **Census 2021** population for **England and Wales** LAs only. "
                        "Scottish and Northern Irish LAs are excluded from the denominator."
                    )
                    bullets.append(
                        f"Among regions with Census-linked population, **{cr.iloc[0]['Region or Country Name']}** "
                        f"has the highest **starts per 1,000 residents** ({float(cr.iloc[0]['starts_per_1000']):.1f})."
                    )
            elif include_census_rates:
                out["census_rates_note"] = (
                    f"Missing `{pop_path.name}`. Run: `python ons_census2021_etl.py --dataset sex_ts008`."
                )

    # EE 1c
    if not path_ee.is_file():
        out["ee_missing"] = path_ee.name
    else:
        ee = load_processed_parquet(path_ee.relative_to(root))
        ee = ee[ee["measure_breakdown"].astype(str).str.strip() == "All"].copy()
        ee["value"] = pd.to_numeric(ee["value"], errors="coerce")
        periods = _ordered_rolling_periods(ee["rolling_period"])
        latest_rp = periods[-1] if periods else None
        out["latest_rp"] = latest_rp
        if latest_rp is not None and not ee.empty:
            last = ee[ee["rolling_period"].astype(str) == latest_rp].copy()
            last = last.dropna(subset=["value"])
            out["ee_last"] = last
            if not last.empty:
                top_e = last.sort_values("value", ascending=False)
                v1 = float(top_e.iloc[0]["value"])
                names = top_e[top_e["value"] == v1]["country_or_region_name"].astype(str).tolist()
                joint = "joint top: " if len(names) > 1 else ""
                bullets.append(
                    f"{joint}Highest **EPC C+** share ({latest_rp}): **{', '.join(names)}** ({v1:.1f}%)."
                )

            if include_ee_period_trend and latest_rp is not None and len(periods) >= 1:
                k = max(2, min(int(ee_trend_n_periods), len(periods)))
                use_rp = periods[-k:]
                ee_tr = ee[ee["rolling_period"].astype(str).isin(use_rp)].copy()
                ee_tr = ee_tr.dropna(subset=["value"])
                latest_vals = ee_tr[ee_tr["rolling_period"].astype(str) == str(latest_rp)].copy()
                top_names: list[str] = []
                if not latest_vals.empty:
                    n_top = min(14, len(latest_vals))
                    top_names = latest_vals.nlargest(n_top, "value")["country_or_region_name"].astype(str).tolist()
                if top_names:
                    ee_tr = ee_tr[ee_tr["country_or_region_name"].astype(str).isin(top_names)]
                    out["ee_trend_long"] = ee_tr.sort_values(["rolling_period", "country_or_region_name"])

    # EPC 1a band C
    if not path_epc.is_file():
        out["epc_missing"] = path_epc.name
    else:
        epc = load_processed_parquet(path_epc.relative_to(root))
        epc["percentage"] = pd.to_numeric(epc["percentage"], errors="coerce")
        key_bands = epc[epc["epc_band"].astype(str).str.upper().isin(["A", "B", "C"])].dropna(
            subset=["percentage"]
        )
        out["epc_key_bands"] = key_bands if not key_bands.empty else None
        band_c = epc[epc["epc_band"].astype(str).str.upper() == "C"].dropna(subset=["percentage"])
        band_c = band_c.sort_values("percentage", ascending=False)
        out["epc_band_c"] = band_c
        if not band_c.empty:
            v1 = float(band_c.iloc[0]["percentage"])
            names = band_c[band_c["percentage"] == v1]["country_or_region_name"].astype(str).tolist()
            bullets.append(
                f"Largest share of dwellings in **EPC band C**: **{', '.join(names)}** ({v1:.2f}%)."
            )

    if (
        include_epc_ee_scatter
        and path_ee.is_file()
        and path_epc.is_file()
        and out.get("latest_rp") is not None
    ):
        lr = out["latest_rp"]
        ee_s = load_processed_parquet(path_ee.relative_to(root))
        ee_s = ee_s[
            (ee_s["measure_breakdown"].astype(str).str.strip() == "All")
            & (ee_s["rolling_period"].astype(str) == str(lr))
        ].copy()
        ee_s["value"] = pd.to_numeric(ee_s["value"], errors="coerce")
        ee_s = ee_s.dropna(subset=["value"])
        ee_s = ee_s.drop_duplicates(subset=["country_or_region_code"], keep="first")
        epc_s = load_processed_parquet(path_epc.relative_to(root))
        epc_s = epc_s[epc_s["epc_band"].astype(str).str.upper() == "C"].copy()
        epc_s["percentage"] = pd.to_numeric(epc_s["percentage"], errors="coerce")
        epc_s = epc_s.dropna(subset=["percentage"])
        epc_s = epc_s.drop_duplicates(subset=["country_or_region_code"], keep="first")
        sc = ee_s.merge(
            epc_s[["country_or_region_code", "percentage"]],
            on="country_or_region_code",
            how="inner",
        )
        sc = sc.rename(
            columns={"value": "rolling_epc_c_plus_pct", "percentage": "snapshot_epc_band_c_pct"}
        )
        out["epc_ee_scatter"] = sc

    prpi_path = root / "ons_private_rental_index_v41_tidy.parquet"
    if prpi_path.is_file():
        prpi = load_processed_parquet(prpi_path.relative_to(root))
        psub = prpi[
            (prpi["variable"].astype(str) == "year-on-year-change")
            & (prpi["geography_name"].astype(str).isin(["United Kingdom", "Great Britain"]))
        ].copy()
        if not psub.empty:
            psub["period"] = pd.to_datetime(psub["month_label"].astype(str), format="%b-%y", errors="coerce")
            psub["value"] = pd.to_numeric(psub["value"], errors="coerce")
            psub = psub.dropna(subset=["period", "value"]).sort_values("period")
            if not psub.empty:
                r = psub.iloc[-1]
                bullets.append(f"Latest **PRPI YoY** ({r['month_label']}): **{float(r['value']):+.2f}%**.")

    hpi3_path = root / "ons_uk_hpi_monthly_march2026_3_tidy.parquet"
    if hpi3_path.is_file():
        hpi3 = load_processed_parquet(hpi3_path.relative_to(root))
        hsub = hpi3[hpi3["geography"].astype(str) == "United Kingdom"].copy()
        if hsub.empty:
            hsub = hpi3[hpi3["geography"].astype(str) == "Great Britain"].copy()
        if not hsub.empty:
            hsub["period"] = pd.to_datetime(hsub["time_period"].astype(str), format="%b %Y", errors="coerce")
            hsub["value"] = pd.to_numeric(hsub["value"], errors="coerce")
            hsub = hsub.dropna(subset=["period", "value"]).sort_values("period")
            if not hsub.empty:
                r = hsub.iloc[-1]
                bullets.append(f"Latest **HPI annual change** ({r['time_period']}): **{float(r['value']):+.2f}%**.")

    out["hpi_prpi_callout"] = buy_vs_rent_spread_caption(root)
    out["chart6_hpi_prpi"] = _build_hpi_prpi_overlap(root)

    joined_path = root / "joined_la_housing_market_snapshot.parquet"
    if joined_path.is_file():
        joined = load_processed_parquet(joined_path.relative_to(root)).copy()
        if "pe_affordability_ratio" in joined.columns:
            joined["pe_affordability_ratio"] = pd.to_numeric(joined["pe_affordability_ratio"], errors="coerce")
            out["chart2_affordability"] = joined.dropna(subset=["pe_affordability_ratio"])
        if "region_name" in joined.columns and "median_price_existing_gbp" in joined.columns:
            joined["median_price_existing_gbp"] = pd.to_numeric(joined["median_price_existing_gbp"], errors="coerce")
            reg_med = (
                joined.dropna(subset=["region_name", "median_price_existing_gbp"])
                .groupby("region_name", as_index=False)["median_price_existing_gbp"]
                .median()
                .rename(columns={"region_name": "region"})
            )
            if not reg_med.empty:
                out["chart3_regional_median"] = reg_med.sort_values("median_price_existing_gbp", ascending=False)

    brief_snap = _briefing_inputs_snapshot(root)
    brief_payload = _uk_summary_briefing_payload(str(root), brief_snap)
    entry_df = brief_payload.get("tables", {}).get("entry")
    if isinstance(entry_df, pd.DataFrame) and not entry_df.empty:
        out["chart4_entry_gap"] = entry_df.dropna(subset=["entry_gap"]).copy()
    epc_rank = brief_payload.get("tables", {}).get("energy")
    if isinstance(epc_rank, pd.DataFrame) and not epc_rank.empty:
        out["chart5_epc_spread"] = epc_rank.copy()

    manifest_path = root / "processed_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            proc = manifest.get("processed_parquet", [])
            preview = pd.DataFrame(proc)[["path", "num_rows", "size_bytes", "mtime_utc"]].head(20)
            out["manifest_preview"] = preview
        except Exception:
            out["manifest_preview"] = None

    if include_bundled:
        bundled_df = None
        if path_bundled_pq.is_file():
            bundled_df = load_processed_parquet(path_bundled_pq.relative_to(root))
        elif path_bundled_csv.is_file():
            bundled_df = pd.read_csv(path_bundled_csv)
        if bundled_df is None:
            out["bundled_missing"] = str(path_bundled_pq.name)
        else:
            b = bundled_df.copy()
            b["starts"] = pd.to_numeric(b["starts"], errors="coerce")
            b["financial_year"] = b["financial_year"].astype(str)
            years_b = _sorted_fy(b["financial_year"])
            if years_b:
                if la_mode == "Latest financial year":
                    use_b = [years_b[-1]]
                else:
                    use_b = years_b[-int(n_years) :] if len(years_b) >= int(n_years) else years_b
                b = b[b["financial_year"].isin(use_b)]
                by_reg = (
                    b.groupby("Region or Country Name", observed=True, dropna=False)["starts"]
                    .sum(min_count=1)
                    .reset_index()
                )
                if len(use_b) > 1:
                    by_reg["starts"] = by_reg["starts"] / len(use_b)
                by_reg = by_reg.sort_values("starts", ascending=False)
                out["bundled_reg"] = by_reg
                out["bundled_year_span"] = len(use_b)

    out["bullets"] = bullets
    return out


def _render_overview_tab(payload: dict[str, Any]) -> None:
    st.markdown(
        "This page is a Key Insights registry for UK housing pressures and market context. "
        "It highlights defensible descriptive findings tied to named datasets and period definitions. "
        "Use it to communicate evidence-led observations before moving into lane-specific tabs."
    )

    st.subheader("Key Insights")
    cards = payload.get("insight_cards") or []
    for i, card in enumerate(cards, start=1):
        with st.container(border=True):
            st.markdown(f"**Insight {i}**")
            st.markdown(f"**Headline**  \n{card['headline']}")
            st.markdown(f"**Evidence**  \n{card['evidence']}")
            st.markdown(f"**Caveat**  \n{card['caveat']}")

    st.subheader("Strong chart set for credibility")
    st.caption("Fixed mapping: Chart 1-6")

    st.markdown("**Chart 1: UK + England FY starts trend (country tidy)**")
    c1 = payload.get("country_ts")
    if c1 is None or c1.empty:
        st.info("Chart 1 unavailable: country financial-year trend data is missing.")
    else:
        c1 = c1[c1["measure"].astype(str).str.lower() == "started"].copy()
        if not c1.empty:
            c1 = c1[c1["country_name"].isin(["United Kingdom", "England"])]
            if c1.empty:
                st.info("Chart 1 unavailable: no UK/England starts rows in current edition.")
            else:
                order_p = preferred_period_order(c1["period"])
                ch1 = (
                    alt.Chart(c1)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period:N", sort=order_p, title="Financial year"),
                        y=alt.Y("dwellings:Q", title="Starts (dwellings)"),
                        color=alt.Color("country_name:N", title="Geography"),
                        tooltip=["country_name", "period", alt.Tooltip("dwellings", format=",.0f")],
                    )
                    .properties(height=300)
                )
                st.altair_chart(ch1, width=ST_WIDTH)

    st.markdown("**Chart 2: LA affordability ratio distribution (histogram + threshold count)**")
    c2 = payload.get("chart2_affordability")
    if c2 is None or c2.empty:
        st.info("Chart 2 unavailable: joined affordability snapshot data is missing.")
    else:
        c2 = c2.dropna(subset=["pe_affordability_ratio"]).copy()
        threshold_n = int((c2["pe_affordability_ratio"] > 10).sum())
        st.caption(f"LAs above 10x affordability ratio: **{threshold_n}**.")
        ch2 = (
            alt.Chart(c2)
            .mark_bar()
            .encode(
                x=alt.X("pe_affordability_ratio:Q", bin=alt.Bin(maxbins=30), title="Affordability ratio"),
                y=alt.Y("count():Q", title="Local authority count"),
                tooltip=[alt.Tooltip("count():Q", title="LAs")],
            )
            .properties(height=260)
        )
        st.altair_chart(ch2, width=ST_WIDTH)

    st.markdown("**Chart 3: Regional median price bar (sorted)**")
    c3 = payload.get("chart3_regional_median")
    if c3 is None or c3.empty:
        st.info("Chart 3 unavailable: regional median summary is missing.")
    else:
        ch3 = (
            alt.Chart(c3)
            .mark_bar(color="#4c78a8")
            .encode(
                x=alt.X("median_price_existing_gbp:Q", title="Median price (GBP)"),
                y=alt.Y("region:N", sort="-x", title=None),
                tooltip=["region", alt.Tooltip("median_price_existing_gbp", format=",.0f")],
            )
            .properties(height=min(420, 26 * max(6, len(c3))))
        )
        st.altair_chart(ch3, width=ST_WIDTH)

    st.markdown("**Chart 4: Entry-gap scatter (Δ6a - Δ5a) by LA**")
    c4 = payload.get("chart4_entry_gap")
    if c4 is None or c4.empty:
        st.info("Chart 4 unavailable: entry-gap table is missing.")
    else:
        ch4 = (
            alt.Chart(c4)
            .mark_circle(size=55, opacity=0.75)
            .encode(
                x=alt.X("delta_median_price:Q", title="Δ5a median price"),
                y=alt.Y("entry_gap:Q", title="Entry gap (Δ6a - Δ5a)"),
                color=alt.Color("region:N", title="Region"),
                tooltip=[
                    "la_name",
                    "region",
                    alt.Tooltip("delta_median_price", format=",.0f"),
                    alt.Tooltip("delta_lq_price", format=",.0f"),
                    alt.Tooltip("entry_gap", format=",.0f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(ch4, width=ST_WIDTH)

    st.markdown("**Chart 5: England rolling EPC C+ trend + latest regional spread**")
    c5_trend = payload.get("ee_trend_long")
    c5_spread = payload.get("chart5_epc_spread")
    cols5 = st.columns(2)
    with cols5[0]:
        if c5_trend is None or c5_trend.empty:
            st.info("Trend unavailable.")
        else:
            eng = c5_trend[c5_trend["country_or_region_name"].astype(str) == "England"].copy()
            if eng.empty:
                st.info("England rolling trend unavailable.")
            else:
                order_rp = sorted(eng["rolling_period"].astype(str).unique().tolist(), key=_rolling_period_sort_key)
                ch5a = (
                    alt.Chart(eng)
                    .mark_line(point=True, color="#54a24b")
                    .encode(
                        x=alt.X("rolling_period:N", sort=order_rp, title="Rolling period"),
                        y=alt.Y("value:Q", title="EPC C+ (%)"),
                        tooltip=["rolling_period", alt.Tooltip("value", format=".2f")],
                    )
                    .properties(height=280)
                )
                st.altair_chart(ch5a, width=ST_WIDTH)
    with cols5[1]:
        if c5_spread is None or c5_spread.empty:
            st.info("Regional spread unavailable.")
        else:
            ch5b = (
                alt.Chart(c5_spread)
                .mark_bar(color="#72b7b2")
                .encode(
                    x=alt.X("epc_c_plus_pct:Q", title="EPC A-C (%)"),
                    y=alt.Y("region:N", sort="-x", title=None),
                    tooltip=["region", alt.Tooltip("epc_c_plus_pct", format=".1f")],
                )
                .properties(height=280)
            )
            st.altair_chart(ch5b, width=ST_WIDTH)

    st.markdown("**Chart 6: HPI vs PRPI indexed overlap (Great Britain)**")
    c6 = payload.get("chart6_hpi_prpi")
    if c6 is None or c6.empty:
        st.info("Chart 6 unavailable: overlapping HPI/PRPI index series is missing.")
    else:
        c6m = c6.melt(
            id_vars=["period"],
            value_vars=["hpi_rebased", "prpi_rebased"],
            var_name="series",
            value_name="value",
        )
        c6m["series"] = c6m["series"].map({"hpi_rebased": "HPI rebased", "prpi_rebased": "PRPI rebased"})
        ch6 = (
            alt.Chart(c6m)
            .mark_line(point=False)
            .encode(
                x=alt.X("period:T", title="Month"),
                y=alt.Y("value:Q", title="Indexed (first overlap month = 100)"),
                color=alt.Color("series:N", title=None),
                tooltip=["series", alt.Tooltip("value", format=".2f")],
            )
            .properties(height=320)
        )
        st.altair_chart(ch6, width=ST_WIDTH)

    st.subheader("Interpretation rule")
    st.info(
        "Use: `is associated with`, `coincides with`, `is consistent with`, `in this snapshot`, "
        "`for this geography/period`.\n\n"
        "Avoid: `caused by`, `proves`, `driven primarily by` unless causal modeling is added."
    )

    st.subheader("How this fits the project")
    st.markdown(
        """
- **Inputs** — ONS Excel workbooks referenced from `*_config.py`, plus an optional bundled workbook for LA starts.
- **Cleaning** — ETL scripts align geography codes, parse financial years, and write tidy Parquet/CSV to `data/processed/`.
- **Provenance** — Raw downloads carry `*.meta.json` sidecars (source URL, hash, Open Government Licence).
- **Dashboard** — Other Streamlit pages under `pages/` cover prices, fuel, maps, and narratives; charts use Altair with `chart_theme.ST_WIDTH`.
- **ML / backtests** — Optional rolling HPI evaluations and exploratory forward index views live on **ML predictions & backtests** (`pages/17_ML_predictions.py`); outputs are generated offline under `data/processed/` (see project README).
- **Joins** — Optional merged tables live under `joins/` (see `joins/README.md`; e.g. `joins/build_la_housing_market_snapshot.py`).
- **API** — Optional REST layer: `run_api.py` with `housing_api/`.
- **Tests** — `tests/` exercise transforms; run the relevant ETL before relying on figures.
"""
    )
    st.subheader("Related pages (sidebar)")
    st.markdown(
        """
| Page | Focus |
|------|--------|
| **Housing starts** | Bundled LA starts by financial year |
| **House building — country / local authority** | Full ONS supply detail |
| **Map — local authority** | Folium map when boundary data is present |
| **Energy efficiency — EPC / five-year rolling** | Bands and rolling metrics |
| **Census 2021 vs house building** | Population vs supply rates |
| **Price / earnings ratio**, **median price**, **UK HPI** | Prices and affordability |
| **Housing market comparator** | Pre-joined Lane A / B snapshot |
| **LA clustering** | Exploratory multivariate grouping |
| **ML predictions & backtests** | Rolling HPI backtests, regional comparison, forward index change (exploratory), LA benchmark |
"""
    )
    hpi_prpi_callout = payload.get("hpi_prpi_callout")
    if hpi_prpi_callout:
        with st.expander("Buy vs rent (indexed — PRPI vs HPI)"):
            st.markdown(hpi_prpi_callout)
    st.subheader("Data freshness / build catalogue")
    manifest_preview = payload.get("manifest_preview")
    if manifest_preview is None or manifest_preview.empty:
        st.caption("No `processed_manifest.json` detected. Run `python scripts/build_processed_manifest.py`.")
    else:
        st.dataframe(
            manifest_preview,
            width=ST_WIDTH,
            height=min(520, 120 + 28 * min(len(manifest_preview), 15)),
        )

    ogl_attribution_expander()


def _render_country_tab(payload: dict[str, Any], hb_country_ed: str, country_trend_years: int) -> None:
    st.subheader("House building by UK country (financial year)")
    _lp = payload.get("latest_country_period")
    _period_note = f" · Latest FY period in this file: **{_lp}**" if _lp else ""
    st.caption(
        f"ONS country dataset — **annual financial year** tables · "
        f"[Dataset page]({HB_COUNTRY_DATASET_PAGE}) · Edition: **{HOUSEBUILDING_COUNTRY_EDITIONS[hb_country_ed].label}**"
        f"{_period_note}"
    )
    if payload["country_missing"]:
        st.warning(
            f"Missing `{payload['country_missing']}`. Run: `python ons_housebuilding_country_etl.py --edition {hb_country_ed}`"
        )
    elif payload["country_plot"] is None:
        st.info(payload.get("country_info") or "No annual financial year rows found.")
    else:
        plot_country = payload["country_plot"]
        ch_c = (
            alt.Chart(plot_country)
            .mark_bar()
            .encode(
                x=alt.X("dwellings:Q", title="Dwellings"),
                y=alt.Y("country_name:N", title=None, sort="-x"),
                row=alt.Row(
                    "measure_label:N",
                    title=None,
                    header=alt.Header(labelOrient="top", labelFontWeight="bold"),
                ),
                tooltip=[
                    "country_name",
                    "measure",
                    alt.Tooltip("period", title="Period"),
                    alt.Tooltip("dwellings", format=",.0f"),
                ],
            )
            .resolve_scale(x="shared")
            .properties(height=150)
        )
        st.altair_chart(ch_c, width=ST_WIDTH)

        ts = payload.get("country_ts")
        if ts is not None and not ts.empty:
            st.subheader("Country house building over time (financial year)")
            st.caption(
                "Same **country** dataset as above — **starts** and **completions** for each UK nation, "
                f"last **{country_trend_years}** FY periods in the file (see sidebar)."
            )
            order_p = preferred_period_order(ts["period"])
            ch_ts = (
                alt.Chart(ts)
                .mark_line(point=True)
                .encode(
                    x=alt.X("period:N", sort=order_p, title="Financial year"),
                    y=alt.Y("dwellings:Q", title="Dwellings"),
                    color=alt.Color("country_name:N", title="Nation"),
                    strokeDash=alt.StrokeDash("measure_label:N", title="Measure"),
                    tooltip=[
                        "country_name",
                        "measure_label",
                        alt.Tooltip("period", title="FY"),
                        alt.Tooltip("dwellings", format=",.0f"),
                    ],
                )
                .properties(height=400)
            )
            st.altair_chart(ch_ts, width=ST_WIDTH)


def _render_la_tab(
    payload: dict[str, Any],
    hb_la_ed: str,
    include_census_rates: bool,
) -> None:
    st.subheader("House building by region / nation (local authority dataset)")
    st.caption(
        f"Sums of LA-level ONS figures. **Do not** compare these regional totals to **England** on the UK country tab — "
        f"that tab is the official **England** national total; here, **England** is split into regions. "
        f"[Dataset page]({HB_LA_DATASET_PAGE}) · Edition: **{HOUSEBUILDING_LA_EDITIONS[hb_la_ed].label}**"
    )
    if payload["la_missing"]:
        st.warning(
            f"Missing `{payload['la_missing']}`. Run: `python ons_housebuilding_la_etl.py --edition {hb_la_ed}`"
        )
    elif payload.get("la_info"):
        st.info(payload["la_info"])
    else:
        wl = payload["la_window_label"]
        for block in payload["la_region_frames"]:
            mdf = block["df"]
            ch_r = (
                alt.Chart(mdf)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "dwellings:Q",
                        title="Dwellings" + (" (mean per year)" if block["use_years_n"] > 1 else ""),
                    ),
                    y=alt.Y("Region or Country Name:N", sort="-x", title=None),
                    tooltip=[
                        "Region or Country Name",
                        "measure",
                        alt.Tooltip("dwellings", format=",.1f"),
                    ],
                )
                .properties(height=min(420, 28 * max(6, mdf["Region or Country Name"].nunique())))
            )
            st.markdown(f"**{block['title']}** ({wl})")
            st.altair_chart(ch_r, width=ST_WIDTH)

        st.subheader("Top local authorities (starts)")
        if payload["la_top_la"] is None:
            st.info("No starts rows for the selected window.")
        else:
            by_la = payload["la_top_la"]
            ch_la = (
                alt.Chart(by_la)
                .mark_bar()
                .encode(
                    x=alt.X("dwellings:Q", title=payload["la_y_title"]),
                    y=alt.Y("Local Authority Name:N", sort="-x", title=None),
                    tooltip=["Local Authority Name", alt.Tooltip("dwellings", format=",.1f")],
                )
                .properties(height=min(520, 24 * len(by_la)))
            )
            st.altair_chart(ch_la, width=ST_WIDTH)

        rb = payload.get("region_balance")
        if rb is not None and not rb.empty:
            st.subheader("Completions vs starts (regional balance)")
            st.caption(
                f"Ratio **completions ÷ starts** for the same window as the charts above ({wl}). "
                "Values above **1** can reflect pipeline timing (units completing from earlier starts)."
            )
            ch_rb = (
                alt.Chart(rb)
                .mark_bar(color="#54a24b")
                .encode(
                    x=alt.X("completion_to_start_ratio:Q", title="Completions ÷ starts"),
                    y=alt.Y("Region or Country Name:N", sort="-x", title=None),
                    tooltip=[
                        "Region or Country Name",
                        alt.Tooltip("starts", format=",.1f"),
                        alt.Tooltip("completions", format=",.1f"),
                        alt.Tooltip("completion_to_start_ratio", format=".3f"),
                    ],
                )
                .properties(height=min(480, 28 * max(6, len(rb))))
            )
            st.altair_chart(ch_rb, width=ST_WIDTH)

        cr = payload.get("census_rates")
        cr_note = payload.get("census_rates_note")
        if cr is not None and not cr.empty:
            st.subheader("Census-weighted supply intensity (England & Wales)")
            st.caption(
                f"[Census 2021 bulletin]({CENSUS_BULLETIN_URL}) · `{POPULATION_DERIVED_STEM}.parquet` · "
                f"{cr_note or ''}"
            )
            ch_cr = (
                alt.Chart(cr)
                .mark_bar(color="#e45756")
                .encode(
                    x=alt.X("starts_per_1000:Q", title="Starts per 1,000 residents"),
                    y=alt.Y("Region or Country Name:N", sort="-x", title=None),
                    tooltip=[
                        "Region or Country Name",
                        alt.Tooltip("population", format=",.0f"),
                        alt.Tooltip("starts", format=",.1f"),
                        alt.Tooltip("starts_per_1000", format=".2f"),
                        alt.Tooltip("completions_per_1000", format=".2f"),
                    ],
                )
                .properties(height=min(480, 28 * max(6, len(cr))))
            )
            st.altair_chart(ch_cr, width=ST_WIDTH)
        elif include_census_rates and cr_note:
            st.subheader("Census-weighted supply intensity (England & Wales)")
            st.info(cr_note)


def _render_energy_epc_tab(
    payload: dict[str, Any],
    ee_ed: str,
    epc_ed: str,
    ee_trend_n_periods: int,
    include_ee_period_trend: bool,
    include_epc_ee_scatter: bool,
) -> None:
    st.subheader("Share of dwellings EPC band C or above (England & Wales, rolling)")
    _erp = payload.get("latest_rp")
    _ee_period = f" · Latest rolling period in this file: **{_erp}**" if _erp else ""
    st.caption(
        f"ONS table **1c** — **five-year rolling** windows · "
        f"[Dataset page]({EE_DATASET_PAGE}) · Edition: **{EE_FIVEYEAR_EDITIONS[ee_ed].label}**"
        f"{_ee_period}"
    )
    if payload["ee_missing"]:
        st.warning(f"Missing `{payload['ee_missing']}`. Run: `python ons_ee_fiveyear_etl.py --edition {ee_ed}`")
    elif payload["ee_last"] is None or payload["ee_last"].empty:
        st.info("No rolling period data.")
    else:
        last = payload["ee_last"]
        ch_ee = (
            alt.Chart(last)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title="% dwellings EPC C+"),
                y=alt.Y("country_or_region_name:N", sort="-x", title=None),
                tooltip=["country_or_region_name", "rolling_period", alt.Tooltip("value", format=".2f")],
            )
            .properties(height=min(480, 26 * max(6, last["country_or_region_name"].nunique())))
        )
        st.altair_chart(ch_ee, width=ST_WIDTH)

        etr = payload.get("ee_trend_long")
        if include_ee_period_trend and etr is not None and not etr.empty:
            st.subheader("Rolling EPC C+ across recent windows")
            st.caption(
                f"Top geographies by latest **C+** share, traced over the last **{ee_trend_n_periods}** "
                "rolling periods in this file (see sidebar). Compares the same metric across different windows, not a single harmonised time series."
            )
            order_rp = sorted(etr["rolling_period"].astype(str).unique().tolist(), key=_rolling_period_sort_key)
            ch_etr = (
                alt.Chart(etr)
                .mark_line(point=True)
                .encode(
                    x=alt.X("rolling_period:N", sort=order_rp, title="Rolling window"),
                    y=alt.Y("value:Q", title="% dwellings EPC C+"),
                    color=alt.Color("country_or_region_name:N", title="Area"),
                    tooltip=[
                        "country_or_region_name",
                        "rolling_period",
                        alt.Tooltip("value", format=".2f"),
                    ],
                )
                .properties(height=420)
            )
            st.altair_chart(ch_etr, width=ST_WIDTH)

    st.subheader("EPC band C (stock distribution by region, England & Wales)")
    st.caption(
        f"ONS table **1a** — snapshot shares by band · "
        f"[Dataset page]({EPC_DATASET_PAGE}) · Edition: **{EPC_EDITIONS[epc_ed].label}**"
    )
    if payload["epc_missing"]:
        st.warning(f"Missing `{payload['epc_missing']}`. Run: `python ons_epc_etl.py --edition {epc_ed}`")
    else:
        if payload["epc_band_c"] is None or payload["epc_band_c"].empty:
            st.info("No band C rows.")
        else:
            band_c = payload["epc_band_c"]
            ch_epc = (
                alt.Chart(band_c)
                .mark_bar(color="#4c78a8")
                .encode(
                    x=alt.X("percentage:Q", title="% of dwellings in band C"),
                    y=alt.Y("country_or_region_name:N", sort="-x", title=None),
                    tooltip=["country_or_region_name", "epc_band", alt.Tooltip("percentage", format=".2f")],
                )
                .properties(height=min(500, 24 * max(6, len(band_c))))
            )
            st.altair_chart(ch_epc, width=ST_WIDTH)

        kb = payload.get("epc_key_bands")
        if kb is not None and not kb.empty:
            st.subheader("EPC bands A–C (by area, snapshot)")
            st.caption(
                "Same table **1a** edition — shares for bands A–C (complement rolling **C+** above)."
            )
            cols = st.columns(3)
            for i, band in enumerate(["A", "B", "C"]):
                sub = kb[kb["epc_band"].astype(str).str.upper() == band].copy()
                with cols[i]:
                    st.caption(f"Band {band}")
                    if sub.empty:
                        st.caption("—")
                        continue
                    sub = sub.sort_values("percentage", ascending=False)
                    ch_kb = (
                        alt.Chart(sub)
                        .mark_bar(color="#72b7b2")
                        .encode(
                            x=alt.X("percentage:Q", title="% of dwellings"),
                            y=alt.Y("country_or_region_name:N", sort="-x", title=None),
                            tooltip=[
                                "country_or_region_name",
                                "epc_band",
                                alt.Tooltip("percentage", format=".2f"),
                            ],
                        )
                        .properties(height=min(300, 22 * max(5, len(sub))))
                    )
                    st.altair_chart(ch_kb, width=ST_WIDTH)

        sc = payload.get("epc_ee_scatter")
        if include_epc_ee_scatter and sc is not None and not sc.empty:
            st.subheader("Snapshot EPC band C vs rolling EPC C+ (linked by region code)")
            st.caption(
                "**X:** table **1a** share in **band C** (stock snapshot). **Y:** table **1c** **C+** share "
                f"(latest rolling window **{_erp}**). Different definitions and periods — use for **broad** consistency checks only."
            )
            ch_sc = (
                alt.Chart(sc)
                .mark_circle(size=70, opacity=0.85)
                .encode(
                    x=alt.X("snapshot_epc_band_c_pct:Q", title="Band C % (snapshot 1a)"),
                    y=alt.Y("rolling_epc_c_plus_pct:Q", title="EPC C+ % (rolling 1c)"),
                    tooltip=[
                        "country_or_region_name",
                        alt.Tooltip("snapshot_epc_band_c_pct", format=".2f"),
                        alt.Tooltip("rolling_epc_c_plus_pct", format=".2f"),
                    ],
                )
                .properties(height=420)
            )
            st.altair_chart(ch_sc, width=ST_WIDTH)


def _render_bundled_tab(payload: dict[str, Any]) -> None:
    st.subheader("Bundled workbook — housing starts (not ONS LA house building)")
    st.warning(
        "This series comes from the **bundled** `UK_local_authority_housing_data` pipeline. "
        "It is **not** the same as the ONS local authority house-building series on the other tabs."
    )
    if payload["bundled_missing"]:
        st.info(
            f"Missing `{payload['bundled_missing']}` or CSV. Run: `python uk_local_authority_housing_data.py`"
        )
    elif payload["bundled_reg"] is not None:
        by_reg = payload["bundled_reg"]
        span = int(payload.get("bundled_year_span") or 0)
        x_title = "Starts (mean per year)" if span > 1 else "Starts (dwellings)"
        ch_b = (
            alt.Chart(by_reg)
            .mark_bar(color="#f58518")
            .encode(
                x=alt.X("starts:Q", title=x_title),
                y=alt.Y("Region or Country Name:N", sort="-x", title=None),
                tooltip=["Region or Country Name", alt.Tooltip("starts", format=",.1f")],
            )
            .properties(height=min(400, 28 * max(5, len(by_reg))))
        )
        st.altair_chart(ch_b, width=ST_WIDTH)


def _render_insights_briefing_strip() -> None:
    """National England & Wales hero metrics (same defaults as Housing insights briefing)."""
    st.subheader("Briefing snapshot — England & Wales")
    st.caption(
        "Workplace-based price/earnings where used · tidy Parquet under `data/processed/` · "
        f"PE `{_BRIEF_PE_ED}` · HB LA `{_BRIEF_HB_LA_ED}` · HB country `{_BRIEF_HB_COUNTRY_ED}` · "
        f"HPI `{_BRIEF_HPI_ED}` · Median admin `{_BRIEF_MEDIAN_ED}` · EPC `{_BRIEF_EPC_ED}` · EE `{_BRIEF_EE_ED}` · "
        f"PE anchor **{DEFAULT_PE_ANCHOR_YEARS[0]}–{DEFAULT_PE_ANCHOR_YEARS[1]}** when present in data · "
        f"Supply comparison **{DEFAULT_SUPPLY_COMPARE_FY[0]}** → **{DEFAULT_SUPPLY_COMPARE_FY[1]}**."
    )
    snap_b = _briefing_inputs_snapshot(Path(PROCESSED_DIR))
    brief_payload = _uk_summary_briefing_payload(str(PROCESSED_DIR), snap_b)
    meta_b = brief_payload["meta"]
    hero_b = brief_payload["hero"]
    st.markdown(
        f"{meta_b.get('horizon_label', '')} Preset: **{meta_b.get('preset_label', '')}**."
    )
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        v_end = hero_b.get("ew_ratio_end")
        d_lbl = hero_b.get("ew_ratio_delta_str")
        st.metric(
            label="E&W median P/E (table 1c)",
            value=f"{v_end:.2f}" if v_end is not None else "—",
            delta=d_lbl if d_lbl else None,
        )
    with b2:
        n_ep = hero_b.get("entry_pressure_n")
        st.metric(
            label="LAs: Δ LQ price > Δ median",
            value=f"{int(n_ep)}" if n_ep is not None else "—",
        )
    with b3:
        sr, sd = hero_b.get("supply_region"), hero_b.get("supply_delta")
        sf0, sf1 = hero_b.get("supply_fy0"), hero_b.get("supply_fy1")
        if sr and sd is not None and sf0 and sf1:
            st.metric(
                label=f"Largest Δ regional starts ({sf0} → {sf1})",
                value=sr,
                delta=f"{sd:+.0f} vs {sf0}",
            )
        else:
            st.metric(label="Largest Δ regional starts", value="—")
    with b4:
        br, wr = hero_b.get("epc_best_region"), hero_b.get("epc_worst_region")
        bpct, wpct = hero_b.get("epc_best_pct"), hero_b.get("epc_worst_pct")
        if br and wr and bpct is not None and wpct is not None:
            st.metric(label="EPC A–C — best region", value=f"{br} ({bpct:.1f}%)")
            st.caption(f"Lowest A–C: **{wr}** ({wpct:.1f}%).")
        else:
            st.metric(label="EPC A–C — best region", value="—")
    try:
        st.page_link("pages/24_Housing_insights_briefing.py", label="Open Housing insights briefing")
    except Exception:
        st.markdown("Full one-page read: **`pages/24_Housing_insights_briefing.py`**")
    st.divider()


def main() -> None:
    st.set_page_config(page_title="UK housing summary", layout="wide")
    st.title("UK housing summary")
    st.caption(
        "Cross-dataset snapshot of UK house building (ONS country and LA), England and Wales EPC energy metrics, "
        "and optional bundled starts. Charts use Altair at full width (`chart_theme.ST_WIDTH`)."
    )
    _render_insights_briefing_strip()

    with st.sidebar.expander("Data editions", expanded=True):
        hb_country_ed = st.selectbox(
            "House building — country",
            list(HOUSEBUILDING_COUNTRY_EDITIONS.keys()),
            format_func=lambda k: HOUSEBUILDING_COUNTRY_EDITIONS[k].label,
        )
        hb_la_ed = st.selectbox(
            "House building — local authority",
            list(HOUSEBUILDING_LA_EDITIONS.keys()),
            format_func=lambda k: HOUSEBUILDING_LA_EDITIONS[k].label,
        )
        ee_ed = st.selectbox(
            "Energy efficiency (rolling)",
            list(EE_FIVEYEAR_EDITIONS.keys()),
            format_func=lambda k: EE_FIVEYEAR_EDITIONS[k].label,
        )
        epc_ed = st.selectbox(
            "EPC bands",
            list(EPC_EDITIONS.keys()),
            format_func=lambda k: EPC_EDITIONS[k].label,
        )

    with st.sidebar.expander("Local authority supply window", expanded=True):
        la_mode = st.radio(
            "Aggregate LAs by",
            ("Latest financial year", "Mean over last N financial years"),
            horizontal=False,
        )
        n_years = 5
        if la_mode == "Mean over last N financial years":
            n_years = st.number_input("N (financial years)", min_value=2, max_value=20, value=5, step=1)

        top_n_la = st.slider("Top local authorities (chart)", 5, 25, 15)
        include_bundled = st.checkbox(
            "Show **Bundled starts** tab (separate workbook)",
            value=False,
            help="Not the ONS LA house-building series; see Housing starts page.",
        )

    with st.sidebar.expander("Deeper summary analytics"):
        country_trend_years = st.slider("Country FY trend depth (years)", 3, 15, 10)
        include_census_rates = st.checkbox(
            "Census regional rates (starts per 1k pop)",
            value=True,
            help="Needs `census2021_la_population_2021.parquet` (England & Wales LAs).",
        )
        include_ee_period_trend = st.checkbox("Multi-period rolling EPC C+ lines", value=True)
        ee_trend_n_periods = 3
        if include_ee_period_trend:
            ee_trend_n_periods = st.number_input(
                "Rolling windows to compare", min_value=2, max_value=5, value=3, step=1
            )
        include_epc_ee_scatter = st.checkbox(
            "Scatter: EPC band C (snapshot) vs C+ (rolling)",
            value=True,
            help="Joins table 1a band C to table 1c C+ on region code — different periods by design.",
        )

    _inputs_snap = _summary_inputs_snapshot(PROCESSED_DIR, hb_country_ed, hb_la_ed, ee_ed, epc_ed)
    payload = _summary_payload(
        str(PROCESSED_DIR),
        hb_country_ed,
        hb_la_ed,
        ee_ed,
        epc_ed,
        la_mode,
        int(n_years),
        int(top_n_la),
        include_bundled,
        int(country_trend_years),
        include_census_rates,
        int(ee_trend_n_periods),
        include_ee_period_trend,
        include_epc_ee_scatter,
        inputs_snapshot=_inputs_snap,
    )
    tab_labels = ["Overview", "UK country supply", "Regions & local authorities", "Energy & EPC"]
    if include_bundled:
        tab_labels.append("Bundled starts")
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_overview_tab(payload)

    with tabs[1]:
        _render_country_tab(payload, hb_country_ed, int(country_trend_years))

    with tabs[2]:
        _render_la_tab(payload, hb_la_ed, include_census_rates)

    with tabs[3]:
        _render_energy_epc_tab(
            payload,
            ee_ed,
            epc_ed,
            int(ee_trend_n_periods),
            include_ee_period_trend,
            include_epc_ee_scatter,
        )

    if include_bundled:
        with tabs[4]:
            _render_bundled_tab(payload)

    st.caption(
        "Figures use the periods and editions shown on each tab. Do not treat them as one harmonised time series "
        "without explicit alignment."
    )


main()
