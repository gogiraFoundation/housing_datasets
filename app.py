"""Streamlit entry point: home page; themed views live under `pages/`."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="UK housing datasets",
    layout="wide",
)

st.title("UK housing datasets")
st.caption("Tidy housing statistics from Excel workbooks — pick a page in the sidebar.")
st.markdown(
    "Welcome. This project turns **housing statistics published in Excel** into **clean tables** "
    "and then **tidy long-form files** (CSV and Parquet) that are easy to chart, join, and reuse. "
    "The **sidebar** lists every interactive view."
)
st.divider()

st.subheader("How the codebase fits together")
st.markdown(
    """
1. **Inputs** — A bundled workbook for local-authority housing starts, plus **Office for National Statistics (ONS)** workbooks fetched using **URLs pinned in Python config files** (`*_config.py`).
2. **Cleaning** — Scripts skip header rows where needed, align **local authority codes and names**, parse **financial years**, and turn symbols such as `[x]` into empty values so numbers stay consistent.
3. **Tidy outputs** — Each pipeline reshapes wide sheets into **one row per observation** (measure, time period, geography, value) and writes to `data/processed/`.
4. **Provenance** — ONS downloads get a **SHA-256 hash** and a small **`*.meta.json` sidecar** next to the raw file (source URL, download time, **Open Government Licence** attribution).
5. **Joins (optional)** — Scripts under **`joins/`** merge tidy outputs on shared keys (e.g. LA codes) into snapshot Parquet files; see **`joins/README.md`** and **`joins/build_la_housing_market_snapshot.py`** (two-lane market tables).
6. **Dashboard** — This file is a **thin home page**; each topic has its own module under **`pages/`** with **Streamlit**, **Altair** charts ([`chart_theme.py`](chart_theme.py)), and a **Folium** map on the local-authority page.

**Tests** in `tests/` run the same transformation logic so breaks from sheet layout changes show up in CI or before you rely on the numbers.
"""
)

st.subheader("What you can explore")
st.markdown(
    """
| Page (sidebar) | What it shows |
|----------------|----------------|
| **UK housing summary** | **Country, region, and LA** supply (ONS), **rolling EPC C+**, **EPC 1a** (band C plus **A–C** small multiples), **Key findings** bullets; optional bundled starts; pointers to price/earnings, housing market comparator, and **`joins/README.md`**. |
| **Housing starts** | Local-authority starts by financial year from the bundled workbook. |
| **Energy efficiency — EPC** | ONS **EPC bands (A–G)** for England and Wales (tables 1a–1d). |
| **Energy efficiency — five-year rolling** | Rolling five-year windows: medians, EPC C+, CO₂, main fuel. |
| **House building — local authority** | ONS **starts and completions** by LA and financial year. |
| **House building — country** | ONS **starts and completions** by country, sector, and frequency (e.g. quarterly vs financial year). |
| **Housing + energy narrative** | Side-by-side **supply**, **EPC C+ (rolling)**, and **heating snapshot** with explicit period labels (not a single harmonised series). |
| **Map — local authority** | **Folium** map (quantile fill, hover tooltips, KPIs, top/bottom table) when `data/geo/lad_uk_wgs84.geojson` or other boundaries are present (`scripts/download_lad_boundaries.py`). |
| **Census 2021 vs house building** | **Census 2021 LA population** (TS008) vs **ONS LA starts/completions** — indicative rates per 1,000 residents (read methodology on the page). |
| **Main fuel / central heating** | ONS **main fuel** tables (1a–3b) for England and Wales. |
| **UK HPI — monthly** | ONS **UK House Price Index** monthly workbook (indices, prices, LA snapshots). |
| **House price per m² / room** | ONS **England and Wales** price per square metre and per room (**2004–2016** annual series). |
| **Median price — admin geographies** | ONS **median price paid** (**all**, existing, or **new build**) by region, LA, county, or combined authority — rolling annual quarters. |
| **House Price Explorer** | Legacy ONS workbook (**1995–2013**) — LA median prices and sale counts. |
| **Price / earnings ratio** | ONS **house price to workplace-based earnings** (median and lower quartile; country, county, LA). |
| **Price / residence earnings** | ONS **house price to residence-based earnings** (median and lower quartile; same tables as workplace series). |
| **New build / workplace earnings** | ONS **newly built dwelling** prices vs **workplace-based** earnings (median / LQ; tables **1a–6c**). |
| **National parks — sales & prices** | ONS **HPSSA by national park**: sales volumes, **median** and **lower quartile** price paid by property type (rolling quarters). |
| **Housing market comparator** | **Lane A** (LA): supply, Census population, median price, optional **price/earnings 5a–5c**, fuel, optional HPI · **Lane B** (region): aggregated supply, EPC, rolling EPC C+, **Census population by region** (`joins/build_la_housing_market_snapshot.py`). |
| **LA clustering** | **K-means** or **hierarchical** clusters on scaled Lane A indicators (PCA scatter); exploratory grouping, not a forecast. |
| **ML predictions & backtests** | **`run_ts_forecast.py`** (monthly or annual UK HPI), **`sweep_hpi_short_horizons.py`**, **`sweep_hpi_geographies.py`** (all sheet-1 areas), **Forward index change** tab (defaults models from `ts_backtest` JSON when matched), **`export_hpi_forward_forecast.py`** (JSON export), and **`run_la_benchmark.py`** residuals + CV table (`data/processed/`). |

The ONS **main fuel / central heating** workbook is transformed by `ons_mainfuel_etl.py` (see **Main fuel** page) and can be **joined** to LA house building (`joins/build_joined_la_housebuilding_mainfuel.py`). **Fuel mix** also appears under **Energy efficiency — five-year rolling** (tables 3a–3h).

**House prices:** `ons_uk_hpi_monthly_etl.py`, `ons_house_m2_room_etl.py`, `ons_median_price_admin_etl.py` (all/existing/new dwellings), `ons_national_park_hpssa_etl.py` (national park sales and prices), `ons_price_earnings_ratio_etl.py`, `ons_price_newbuild_workplace_earnings_ratio_etl.py` (new build vs workplace earnings), and `ons_price_residence_earnings_ratio_etl.py` (residence-based affordability), `ons_house_price_explorer_etl.py`, and `ons_private_rental_index_etl.py` (experimental private **rental price index** and YoY % from CSV) write tidy Parquet under `data/processed/` (see **README.md**).

**Reference:** `joins/README.md` (clean join rules; `joins/build_la_housing_market_snapshot.py` for two-lane snapshots), `scripts/build_processed_manifest.py` (catalogue of processed files), `ons_median_eescore_etl.py` (median EPC score workbook).
"""
)

st.subheader("Before you open a topic")
st.info(
    "Run the matching ETL script (or the bundled `uk_local_authority_housing_data.py` for housing starts) "
    "so `data/processed/` contains the CSV or Parquet files the pages expect. "
    "Commands and file names are documented in **README.md**."
)

st.caption(
    "Contains public sector information licensed under the Open Government Licence v3.0 where ONS data is used."
)
