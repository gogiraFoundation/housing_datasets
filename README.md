# UK housing datasets

A small, reproducible toolkit for turning **Excel** workbooks into **clean wide tables**, then **tidy long-form** datasets written as **CSV** and **Parquet**, with a **Streamlit** dashboard (multipage app under `pages/`, **Altair** charts) for exploration.

**ONS statistics** are fetched with **pinned URLs** in Python config modules, **SHA-256** hashes recorded, and a **sidecar `*.meta.json`** next to each raw file for provenance and **Open Government Licence** attribution. **pytest** exercises the ETL logic so layout changes from ONS are caught early.

---

## What’s in the stack

| Stage | What happens |
|--------|----------------|
| **Input** | Bundled workbook (local-authority housing starts) and/or ONS `.xlsx` downloads |
| **Clean** | Headers aligned, suppressed cells (e.g. `[x]`) coerced to null, consistent ID columns (especially LA codes and financial years) |
| **Tidy** | One observation per row: measures, periods, geography — easy to join and plot |
| **Output** | `data/processed/*.csv` and `*.parquet` (raw workbooks under `data/raw/` are gitignored except metadata patterns you add) |
| **App** | `streamlit run app.py` — home in `app.py`; themed views in `pages/*.py` |

---

## Dashboard pages and graphics

Most views use **Altair** (`st.altair_chart`) and wide **data tables** (`st.dataframe`) with **`width="stretch"`**, centralised as **`ST_WIDTH`** in [`chart_theme.py`](chart_theme.py) so charts align with the wide layout. The **Map — local authority** page uses **Folium** + **streamlit-folium** for 2D choropleths (optional **Pydeck** extrusion for a 3D view). Metrics include house building, median price, affordability ratio, and **regional** EPC band C % mapped onto LA polygons (`use_container_width=True` on the map; tables use `ST_WIDTH`). **Open Government Licence** attribution appears on ONS-backed pages.

| Order | Page | Role |
|-------|------|------|
| 0 | [`pages/0_UK_housing_summary.py`](pages/0_UK_housing_summary.py) | Cross-dataset summary, Key findings, EPC A–C small multiples; links to comparator, price/earnings, **`joins/README.md`** |
| 1 | [`pages/1_Housing_starts.py`](pages/1_Housing_starts.py) | Bundled workbook LA starts |
| 2 | [`pages/2_Energy_efficiency_EPC.py`](pages/2_Energy_efficiency_EPC.py) | EPC bands 1a–1d |
| 3 | [`pages/3_Energy_efficiency_five_year_rolling.py`](pages/3_Energy_efficiency_five_year_rolling.py) | Five-year rolling energy tables |
| 4 | [`pages/4_House_building_local_authority.py`](pages/4_House_building_local_authority.py) | ONS LA starts / completions |
| 5 | [`pages/5_House_building_country.py`](pages/5_House_building_country.py) | ONS UK country house building |
| 6 | [`pages/6_Housing_energy_narrative.py`](pages/6_Housing_energy_narrative.py) | Supply + EPC + heating narrative |
| 7 | [`pages/7_Map_local_authority.py`](pages/7_Map_local_authority.py) | LA choropleth: house building, median price, affordability, regional EPC proxy; optional Pydeck 3D |
| 8 | [`pages/8_Census_2021_housing_compare.py`](pages/8_Census_2021_housing_compare.py) | Census population vs LA supply |
| 9 | [`pages/9_Main_fuel_heating.py`](pages/9_Main_fuel_heating.py) | Main fuel / central heating (tables 1a–3b) |
| 10 | [`pages/10_UK_HPI_monthly.py`](pages/10_UK_HPI_monthly.py) | UK HPI monthly price statistics (ONS workbook) |
| 11 | [`pages/11_House_price_m2_room.py`](pages/11_House_price_m2_room.py) | House price per m² and per room, England & Wales (2004–2016) |
| 12 | [`pages/12_Median_price_admin.py`](pages/12_Median_price_admin.py) | Median price paid — administrative geographies (existing or new build) |
| 13 | [`pages/13_House_price_explorer.py`](pages/13_House_price_explorer.py) | House Price Explorer (legacy 1995–2013 LA series) |
| 14 | [`pages/14_House_price_earnings_ratio.py`](pages/14_House_price_earnings_ratio.py) | House price to workplace-based earnings (median / LQ; region, county, LA) |
| 15 | [`pages/15_Housing_market_comparator.py`](pages/15_Housing_market_comparator.py) | LA vs region housing market comparator (supply, median price, fuel; region EPC) |
| 16 | [`pages/16_LA_clustering.py`](pages/16_LA_clustering.py) | K-means / hierarchical clusters on Lane A indicators (exploratory) |
| 17 | [`pages/17_ML_predictions.py`](pages/17_ML_predictions.py) | Rolling HPI backtests (`ts_backtest_*.json`), regional metrics, **Forward index change** (exploratory forecasts), LA cross-section benchmark |

---

## Data themes in this repo

| Theme | Role in the codebase |
|--------|----------------------|
| **UK housing summary** | [`pages/0_UK_housing_summary.py`](pages/0_UK_housing_summary.py) — cross-dataset **country**, **region/LA** supply, **rolling EPC C+**, **EPC 1a** (band C and A–C), auto **Key findings** bullets; optional bundled starts; on-page pointers to **price/earnings**, **housing market comparator**, Census compare, and [`joins/README.md`](joins/README.md). |
| **LA housing starts** | [`uk_local_authority_housing_data.py`](uk_local_authority_housing_data.py) + [`pages/1_Housing_starts.py`](pages/1_Housing_starts.py) — bundled workbook; same identifier columns as ONS LA house-building tables. |
| **ONS house building (LA)** | [`ons_housebuilding_la_etl.py`](ons_housebuilding_la_etl.py) → [`pages/4_House_building_local_authority.py`](pages/4_House_building_local_authority.py) — starts and completions by financial year. |
| **ONS house building (country)** | [`ons_housebuilding_country_etl.py`](ons_housebuilding_country_etl.py) → [`pages/5_House_building_country.py`](pages/5_House_building_country.py) — country/sector, multiple frequencies. |
| **EPC bands (England & Wales)** | Tables 1a–1d — [`ons_epc_etl.py`](ons_epc_etl.py) → [`pages/2_Energy_efficiency_EPC.py`](pages/2_Energy_efficiency_EPC.py). |
| **Energy efficiency (5-year rolling)** | Median scores, EPC C+, CO₂, main fuel over windows — [`ons_ee_fiveyear_etl.py`](ons_ee_fiveyear_etl.py) → [`pages/3_Energy_efficiency_five_year_rolling.py`](pages/3_Energy_efficiency_five_year_rolling.py). |
| **Main fuel / central heating (E&W)** | Country/region/LA/MSOA — [`ons_mainfuel_etl.py`](ons_mainfuel_etl.py) → [`pages/9_Main_fuel_heating.py`](pages/9_Main_fuel_heating.py). Related fuel splits also appear in the **five-year rolling** tables (page 3). |
| **UK HPI (monthly)** | [`ons_uk_hpi_monthly_etl.py`](ons_uk_hpi_monthly_etl.py) → [`pages/10_UK_HPI_monthly.py`](pages/10_UK_HPI_monthly.py) — indices, average prices, buyer and tenure splits, LA snapshots. |
| **House price per m² / per room (E&W)** | [`ons_house_m2_room_etl.py`](ons_house_m2_room_etl.py) → [`pages/11_House_price_m2_room.py`](pages/11_House_price_m2_room.py) — annual **2004–2016** tables (legacy `.xls`). |
| **Median price — admin geographies** | [`ons_median_price_admin_etl.py`](ons_median_price_admin_etl.py) → [`pages/12_Median_price_admin.py`](pages/12_Median_price_admin.py) — existing vs new build, tables **1a–4e** (HPSSA-style **xlsx**). |
| **Price / earnings ratio (E&W)** | [`ons_price_earnings_ratio_etl.py`](ons_price_earnings_ratio_etl.py) → [`pages/14_House_price_earnings_ratio.py`](pages/14_House_price_earnings_ratio.py) — affordability (median and lower quartile), tables **1a–6c** (`xlsx`). |
| **Housing market comparator (two lanes)** | [`joins/build_la_housing_market_snapshot.py`](joins/build_la_housing_market_snapshot.py) → [`pages/15_Housing_market_comparator.py`](pages/15_Housing_market_comparator.py) — **Lane A:** LA snapshot (supply, population, median price, optional price/earnings 5a–5c, fuel, optional HPI). **Lane B:** region snapshot (aggregated supply, EPC 1a, five-year rolling, Census population summed to region). |
| **ML / backtests & forward views** | [`housing_analytics/`](housing_analytics/) — rolling-origin metrics ([`scripts/run_ts_forecast.py`](scripts/run_ts_forecast.py)), optional sweeps ([`scripts/sweep_hpi_short_horizons.py`](scripts/sweep_hpi_short_horizons.py), [`scripts/sweep_hpi_geographies.py`](scripts/sweep_hpi_geographies.py)), LA benchmark ([`scripts/run_la_benchmark.py`](scripts/run_la_benchmark.py)), JSON export ([`scripts/export_hpi_forward_forecast.py`](scripts/export_hpi_forward_forecast.py)). Dashboard: [`pages/17_ML_predictions.py`](pages/17_ML_predictions.py). Outputs under `data/processed/` (`ts_backtest_*.json`, benchmark CSVs). Forward charts are **illustrative** (not macro scenarios); validate on short horizons first. |
| **House Price Explorer (legacy)** | [`ons_house_price_explorer_etl.py`](ons_house_price_explorer_etl.py) → [`pages/13_House_price_explorer.py`](pages/13_House_price_explorer.py) — **1995–2013** LA prices and counts (`.xls`). |
| **Census 2021 (demography, LTLA)** | Topic summaries TS007–TS009, TS006, TS041 via **ONS CMD API** — [`ons_census2021_etl.py`](ons_census2021_etl.py) → [`pages/8_Census_2021_housing_compare.py`](pages/8_Census_2021_housing_compare.py) (population vs LA house-building). |

---

## Why this shape

- **Reproducible ONS flow:** download → hash → transform → processed outputs; attribution is echoed in README and stored beside raw files.
- **Consistent tidy outputs:** stable column names for joins (LA identifiers, financial year on house-building series).
- **Tests with ETL:** `tests/` reduce silent breakage when ONS alters sheet layout.

---

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Dashboard

```bash
streamlit run app.py
```

To refresh **all** pipelines (same commands as under [Running pipelines](#running-pipelines)) then open the app: `./start.sh` from the repo root (requires network for ONS downloads). If `data/geo/lad_uk_wgs84.geojson` is missing, `start.sh` runs [`scripts/download_lad_boundaries.py`](scripts/download_lad_boundaries.py) once so the **Map — local authority** page has UK boundaries; set `SKIP_GEO=1` to skip that fetch.

Use the sidebar to open each theme. Processed Parquet/CSV files must exist under `data/processed/` for the ONS-backed pages (run the matching ETL first).

Optional wrapper with health checks and restart: [`run_dashboard.py`](run_dashboard.py).

### Tests

From the repository root:

```bash
python3 -m pytest -q
```

(`pytest` also works when the working directory is the repo root and imports resolve.)

### API (FastAPI)

After building ``data/processed/`` outputs, you can serve them read-only via the API:

```bash
python run_api.py
```

Defaults to ``127.0.0.1:8000``. Set ``HOUSING_API_KEYS`` to a comma-separated list of keys; clients send ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``. Set ``HOUSING_REPO_ROOT`` if the process cwd is not the repository root. For production, set ``HOUSING_API_DOCS=0`` to disable OpenAPI UIs under ``/api/v1/docs``.

Optional Prometheus-style metrics: ``HOUSING_API_ENABLE_METRICS=1`` exposes ``GET /metrics`` without an API key by default—do not put that listener on the public internet unless you restrict the route (firewall, reverse proxy) or set ``HOUSING_API_METRICS_REQUIRE_KEY=1`` and configure your scraper with the same key as the API.

The **Streamlit** app has no built-in login; treat it like any internal tool (VPN, authenticated proxy, or a managed host with access control).

---

## Project layout (high level)

| Path | Purpose |
|------|---------|
| `app.py` | Streamlit **home** page (thin entry). |
| `chart_theme.py` | Shared **`ST_WIDTH`** for Altair charts and wide dataframes. |
| `pages/` | Multipage app: one file per dashboard theme. |
| `joins/` | Join scripts and [`joins/README.md`](joins/README.md) (keys, caveats); e.g. [`build_la_housing_market_snapshot.py`](joins/build_la_housing_market_snapshot.py). |
| `*_config.py` | Pinned URLs, edition keys, filenames. |
| `*_etl.py` | Download, metadata sidecars, transforms. |
| `data/raw/` | Downloaded `.xlsx` (ignored by git) + `*.meta.json` sidecars. |
| `data/processed/` | Tidy CSV and Parquet outputs (ignored by git; `.gitkeep` retained). |
| `tests/` | pytest coverage for pipelines. |
| `housing_analytics/` | Optional forecasting helpers (`ts_forecast`, `ts_backtest`, `forward_hpi`) used by scripts and page 17. |
| `scripts/` | Dashboard helpers (`build_*`, `download_lad_boundaries.py`), **HPI backtests** (`run_ts_forecast.py`, `sweep_hpi_*.py`), **`export_hpi_forward_forecast.py`**, **`run_la_benchmark.py`**. |
| `run_api.py` | Optional **FastAPI** server for processed datasets (see **API (FastAPI)** above). |

---

## Running pipelines

**Bundled LA starts** — [`uk_local_authority_housing_data.py`](uk_local_authority_housing_data.py): reads `UK_local_authority_housing_data.xlsx` (sheet `UK_Starts` by default), writes wide/tidy CSV and Parquet under `data/processed/`. Run `python uk_local_authority_housing_data.py --help` for paths and flags. The checked-in workbook is a **development snapshot**; replace from the official source for publication-grade work.

**ONS downloads** — Each `ons_*_config.py` pins **dataset pages**, **file URLs**, and **edition keys**. Each `ons_*_etl.py` downloads (when needed), writes `*.meta.json`, and emits tidy files under `data/processed/`. Typical pattern: `python ons_<name>_etl.py --edition <key>` where `<key>` is defined in the paired config. Use `python ons_<name>_etl.py --help` for extract-only, transform-only, hash, and output options. New ONS editions: add a key in the relevant config.

**House prices (ONS)** — **UK HPI monthly** (`xlsx`): `python ons_uk_hpi_monthly_etl.py --edition march2026` → `data/processed/ons_uk_hpi_monthly_<edition>_<sheet>_tidy.parquet` for worksheets `1`–`11`. **Price per m² / per room** (`xls`, 2004–2016): `python ons_house_m2_room_etl.py --edition 2004to2016` → `data/processed/ons_house_m2_room_2004to2016_Table<N>_tidy.parquet`. **Median price by admin geography** (existing or new build, `xlsx`): `python ons_median_price_admin_etl.py --dataset existing --edition yearendingseptember2025` (and `--dataset new` for new builds) → `ons_median_price_{existing|new}_admin_<edition>_<sheet>_tidy.parquet` for sheets `1a`–`4e`. **House price to workplace-based earnings ratio** (`xlsx`): `python ons_price_earnings_ratio_etl.py --edition current` → `ons_price_earnings_ratio_<edition>_<sheet>_tidy.parquet` for sheets `1a`–`6c`. **House Price Explorer** (legacy `xls`): `python ons_house_price_explorer_etl.py --edition current`. Requires **`xlrd`** for `.xls` (see `requirements.txt`).

**Map boundaries (UK LAD, WGS84)** — For the **Map — local authority** page, run [`scripts/download_lad_boundaries.py`](scripts/download_lad_boundaries.py) once to create `data/geo/lad_uk_wgs84.geojson` (see [`data/geo/README.md`](data/geo/README.md)). The demo GeoJSON only includes two districts.

**Census 2021 topic summaries** — Use [`ons_census2021_etl.py`](ons_census2021_etl.py): metadata and download URLs come from **`GET https://api.beta.ons.gov.uk/v1/datasets/{TS}/editions/2021/versions/{v}`** (pinned `v` per table in [`ons_census2021_config.py`](ons_census2021_config.py)). Raw `.xlsx` and `.csv` land in `data/raw/`; tidy outputs and `census2021_la_population_2021.*` (from TS008) go to `data/processed/`. Example: `python ons_census2021_etl.py --dataset all` (large downloads including TS009).

**Licensing:** Crown / public sector information is licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Attribute ONS material when you publish or redistribute outputs. Downloads use a descriptive `User-Agent`, timeouts, and limited retries.

| ONS dataset (link) | Config | ETL |
|--------------------|--------|-----|
| [Individual EPC Bands, England and Wales](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/individualenergyperformancecertificateepcbandsenglandandwales) | [`ons_epc_config.py`](ons_epc_config.py) | [`ons_epc_etl.py`](ons_epc_etl.py) |
| [Energy efficiency — five years rolling](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/energyefficiencyofhousingenglandandwalesfiveyearsrolling) | [`ons_ee_fiveyear_config.py`](ons_ee_fiveyear_config.py) | [`ons_ee_fiveyear_etl.py`](ons_ee_fiveyear_etl.py) |
| [House building by local authority](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority) | [`ons_housebuilding_la_config.py`](ons_housebuilding_la_config.py) | [`ons_housebuilding_la_etl.py`](ons_housebuilding_la_etl.py) |
| [House building by country](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/ukhousebuildingpermanentdwellingsstartedandcompleted) | [`ons_housebuilding_country_config.py`](ons_housebuilding_country_config.py) | [`ons_housebuilding_country_etl.py`](ons_housebuilding_country_etl.py) |
| [Main fuel / central heating, England and Wales](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/mainfueltypeormethodofheatingusedincentralheatingenglandandwales) | [`ons_mainfuel_config.py`](ons_mainfuel_config.py) | [`ons_mainfuel_etl.py`](ons_mainfuel_etl.py) |
| [Median energy efficiency score, England and Wales](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/medianenergyefficiencyscoreenglandandwales) | [`ons_median_eescore_config.py`](ons_median_eescore_config.py) | [`ons_median_eescore_etl.py`](ons_median_eescore_etl.py) |
| [Median house prices — existing dwellings, admin geographies](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/medianhousepricesforadministrativegeographiesexistingdwellings) | [`ons_median_price_admin_config.py`](ons_median_price_admin_config.py) | [`ons_median_price_admin_etl.py`](ons_median_price_admin_etl.py) (`--dataset existing`) |
| [Median house prices — newly built dwellings, admin geographies](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/medianhousepricesforadministrativegeographiesnewlybuiltdwellings) | [`ons_median_price_admin_config.py`](ons_median_price_admin_config.py) | [`ons_median_price_admin_etl.py`](ons_median_price_admin_etl.py) (`--dataset new`) |
| [House price to workplace-based earnings ratio](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/ratioofhousepricetoworkplacebasedearningslowerquartileandmedian) | [`ons_price_earnings_ratio_config.py`](ons_price_earnings_ratio_config.py) | [`ons_price_earnings_ratio_etl.py`](ons_price_earnings_ratio_etl.py) |
| [House Price Explorer](https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/housepriceexplorer) | [`ons_house_price_explorer_config.py`](ons_house_price_explorer_config.py) | [`ons_house_price_explorer_etl.py`](ons_house_price_explorer_etl.py) |
| [Census 2021 — population & households (unrounded bulletin)](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/bulletins/populationandhouseholdestimatesenglandandwales/census2021unroundeddata) | [`ons_census2021_config.py`](ons_census2021_config.py) | [`ons_census2021_etl.py`](ons_census2021_etl.py) |

**Joins (LA supply × heating mix)** — See [`joins/README.md`](joins/README.md). Build derived Parquet with `python joins/build_joined_la_housebuilding_mainfuel.py` (after running the house-building LA and main-fuel ETLs). Aggregate LA supply to region with `python joins/aggregate_la_supply_to_region.py`. **Two-lane LA + region market snapshots** (for [`pages/15_Housing_market_comparator.py`](pages/15_Housing_market_comparator.py)): `python joins/build_la_housing_market_snapshot.py` after the relevant ETLs (include `ons_price_earnings_ratio_etl.py` for Lane A price/earnings columns; Census population for Lane B region totals). Optional LA rankings: `python joins/build_la_rankings.py` — use `data/reference/population_la_midyear.csv` **or** `data/processed/census2021_la_population_2021.csv` (from `ons_census2021_etl.py --dataset sex_ts008`) for per-capita columns.

**ML / HPI backtests (optional)** — After UK HPI tidy Parquet exists: `python scripts/run_ts_forecast.py --dataset hpi --edition march2026 --geography "United Kingdom"` writes `ts_backtest_*.json` (+ `.windows.csv`). Sweep horizons with `scripts/sweep_hpi_short_horizons.py`; sweep all sheet-1 geographies with `scripts/sweep_hpi_geographies.py`. LA feature benchmark: `python scripts/run_la_benchmark.py` (needs `joined_la_housing_market_snapshot.parquet`). Reproducible forward index export: `python scripts/export_hpi_forward_forecast.py`. The **ML predictions & backtests** page ([`pages/17_ML_predictions.py`](pages/17_ML_predictions.py)) visualises backtests and exploratory forward % change; read disclaimers on that page.

**Processed catalogue** — `python scripts/build_processed_manifest.py` writes `data/processed/processed_manifest.json` (lists Parquet outputs and raw `*.meta.json` references).

**CI** — [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `pytest` on push and weekly.

---

## Requirements

Python 3 with dependencies listed in [`requirements.txt`](requirements.txt) (`pandas`, `openpyxl`, `pyarrow`, `requests`, `streamlit`, `altair`, `folium`, `streamlit-folium`, `pytest`).
