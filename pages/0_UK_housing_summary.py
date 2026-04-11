"""Streamlit: UK housing summary — country, region, LA supply plus EPC/Energy snapshots (explicit periods)."""

from __future__ import annotations

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
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_PERIOD_START_YEAR = re.compile(r"^Q2 (\d{4})")

FOUR_NATIONS = {"England", "Wales", "Scotland", "Northern Ireland"}


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
    bullets: list[str] = []

    path_country = root / f"ons_housebuilding_country_{hb_country_ed}_tidy.parquet"
    path_la = root / f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet"
    path_ee = root / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet"
    path_epc = root / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet"
    path_bundled_pq = root / "uk_housing_starts_tidy.parquet"
    path_bundled_csv = root / "uk_housing_starts_tidy.csv"

    out: dict[str, Any] = {
        "bullets": bullets,
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
    }

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


def _render_overview_tab(bullets: list[str]) -> None:
    st.markdown(
        "This page summarises **several ONS publications** and optional bundled inputs. Each tab uses the "
        "periods and editions selected in the sidebar. The views are **not** a single harmonised time series; "
        "read tab captions before comparing numbers."
    )
    st.markdown(
        "**Coverage.** House-building statistics are **UK-wide** (country and local authority). "
        "EPC bands and five-year rolling energy metrics are **England and Wales only**. "
        "ONS **country** tables give the official **England** national total; the **local authority** dataset "
        "splits England into **regions** (e.g. London, North West) and is not comparable to that national total."
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
    st.subheader("Key findings")
    if bullets:
        for b in bullets:
            st.markdown(f"- {b}")
    else:
        st.info("Run ETL scripts so `data/processed/` contains the Parquet files used on the other tabs.")

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


def main() -> None:
    st.set_page_config(page_title="UK housing summary", layout="wide")
    st.title("UK housing summary")
    st.caption(
        "Cross-dataset snapshot of UK house building (ONS country and LA), England and Wales EPC energy metrics, "
        "and optional bundled starts. Charts use Altair at full width (`chart_theme.ST_WIDTH`)."
    )
    st.divider()

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
    bullets: list[str] = payload["bullets"]

    tab_labels = ["Overview", "UK country supply", "Regions & local authorities", "Energy & EPC"]
    if include_bundled:
        tab_labels.append("Bundled starts")
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_overview_tab(bullets)

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
