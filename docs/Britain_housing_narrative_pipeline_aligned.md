# Britain’s housing system: narrative aligned to this repository’s outputs

This document implements the alignment plan: a revised article grounded in **current** files under `data/processed/`, an annotation layer, gaps, and chart specifications. **Figures cited** below were produced with [`scripts/snapshot_narrative_stats.py`](../scripts/snapshot_narrative_stats.py) and ad hoc queries on the same Parquet (run the script after each ETL refresh).

**Pinned artefacts (this workspace, April 2026):**

| Role | Path |
| --- | --- |
| LA join metadata | [`data/processed/joined_la_housing_market_snapshot.meta.json`](../data/processed/joined_la_housing_market_snapshot.meta.json) |
| LA join table | [`data/processed/joined_la_housing_market_snapshot.parquet`](../data/processed/joined_la_housing_market_snapshot.parquet) |
| Region join metadata | [`data/processed/region_housing_market_snapshot.meta.json`](../data/processed/region_housing_market_snapshot.meta.json) |
| Region join table | [`data/processed/region_housing_market_snapshot.parquet`](../data/processed/region_housing_market_snapshot.parquet) |
| National supply (ONS country, tidy) | [`data/processed/ons_housebuilding_country_current_tidy.parquet`](../data/processed/ons_housebuilding_country_current_tidy.parquet) |
| Energy rolling (England & Wales) | [`data/processed/ons_ee_fiveyear_march2025_1c_tidy.parquet`](../data/processed/ons_ee_fiveyear_march2025_1c_tidy.parquet) |

---

## A. Revised report (aligned)

### Executive summary

Official UK housing statistics are easier to misread than to publish: different indicators use **different geographies** (United Kingdom vs England vs England and Wales), **different time bases** (financial year starts, year-ending-September median prices, calendar-year earnings), and **different levels** (local authority vs region). This project does not replace ONS methodology; it **tidies** published workbooks into long-form Parquet, then builds **two** market snapshots—one at **local authority** scale for supply, prices and workplace-based affordability, and one at **ONS region** scale where EPC band shares and five-year rolling energy metrics are defined.

The picture that emerges from the **processed outputs alone** is not a single “national” market but a **patchwork**: median prices and affordability ratios diverge sharply by region; England’s housing **starts** fell abruptly after the 2008 crisis and, on the United Kingdom financial-year series, spent much of the 2010s and early 2020s **below** the elevated levels seen before 2008; separately, ONS five-year rolling data for **England** show the share of dwellings rated EPC band C or above rising from about **40%** to about **59%** between the earliest and latest rolling windows in the March 2025 edition file. Indexed comparison of ONS UK HPI and private rental price index series for **Great Britain** (to January 2024 in the current processed monthly files) shows **cumulative outperformance of purchase prices relative to rents** by roughly **31 percentage points** over the overlapping window—an index spread, not a statement about cash rents versus mortgage payments.

### Supply: volatility and geography matter

Using `ons_housebuilding_country_current_tidy.parquet` with `frequency == annual_financial_year`, **England** dwelling **starts** fell from **340,880** in 2007–08 to **176,010** in 2008–09—a shock consistent with the post-financial-crisis narrative. The latest England financial year in the file, **2024–25**, records **225,770** starts.

For the **United Kingdom** on the same basis, the post-2011 period is especially weak relative to the mid-2000s peak: from **2011–12** through **2024–25**, only **three** of **fourteen** financial years recorded UK starts **above** 200,000 (`count_gt_200k` in the stats script). That supports a **carefully scoped** statement about **weak UK starts in the 2010s–early 2020s**, not the broader claim that starts “rarely exceed” 200,000 across the whole period since the late 1990s (the UK series spent much of **1997–98 to 2007–08** well above that threshold).

The LA snapshot [`joined_la_housing_market_snapshot.parquet`](../data/processed/joined_la_housing_market_snapshot.parquet) attaches **latest** financial-year **starts and completions** (`supply_starts`, `supply_completions`, `supply_financial_year` currently **2024–2025**) to each local authority row, together with Census **2021 population** where available. Any sentence linking population change to supply must name **both** reference periods: population is a **2021** stock; supply is a **financial year flow**.

### Prices and affordability: evidence at local authority scale

Median prices in the snapshot come from ONS HPSSA **existing dwellings, administrative geographies, table 2a (all dwelling types)**—here edition `yearendingseptember2025`, latest period label **Year ending Sep 2025** per metadata. **Regional medians of LA medians** (all LAs with a value in the snapshot) range from about **£161,500** (North East) to **£540,000** (London)—a clear north–south and London premium **within this one indicator**.

Workplace-based **price-to-earnings** fields use the ONS affordability workbook tables **5a–5c**: the pipeline keeps the **latest calendar year common to all three** sheets (`pe_snapshot_year` **2025** in current metadata), with an explicit caveat that the **house price** period label is year-ending September while **earnings** are calendar-year ASHE gross. Among **315** local authorities with a non-missing `pe_affordability_ratio`, **83** exceed **10**; the maximum observed ratio is **25.22** (Kensington and Chelsea). That substantiates a precise claim about **double-digit ratios in a substantial minority of LAs** in this snapshot, replacing vague “several high-demand areas.”

Optional columns `hpi_avg_price_gbp` and `hpi_annual_pct_change` on the LA table come from **UK HPI monthly workbook sheet 8** (England local authorities only); they must not be described as “UK-wide LA coverage.”

### Energy: region-level bands, LA-level scores elsewhere

ONS **EPC band distributions** in this repository (`ons_epc_bands_*_1a_tidy.parquet`) are published at **country or region** granularity. The region snapshot therefore carries `epc_pct_band_c` and `epc_pct_bands_abc` alongside **five-year rolling** `ee_epc_c_plus_pct` for the window **Q2 2020 to Q1 2025** (edition March 2025). For **England**, table **1c** with `measure_breakdown == All` shows the **C+** share moving from **40.43%** (window **Q2 2008 to Q1 2013**) to **58.56%** (**Q2 2020 to Q1 2025**) in the processed file—evidence of **improvement over successive rolling windows**, not a single “decade” slice unless you define the decade as those endpoints.

Statements that **EPC progress “varies widely between local authorities”** are **not** supported by the **band share** columns in the LA snapshot (those are not joined at LA). They **can** be supported using the separate tidy files **`ons_median_eescore_march2025_*_tidy.parquet`**, which include local-authority-style geographies, or by mapping regional band metrics back to narrative without implying LA-level band tables.

### How the platform fits the story

Raw ONS releases are ingested by edition-specific ETL modules (`ons_*_etl.py`), written as **tidy Parquet** under `data/processed/`, and optionally merged by [`joins/build_la_housing_market_snapshot.py`](../joins/build_la_housing_market_snapshot.py). Sidecar `*.meta.json` files record **editions, periods, and caveats**. Streamlit pages under `pages/` and the FastAPI registry in [`housing_api/registry.py`](../housing_api/registry.py) expose the same artefacts for exploration and filtered reads. Reproducibility is **file-based**: refresh the Parquet, rebuild the join, re-run [`scripts/snapshot_narrative_stats.py`](../scripts/snapshot_narrative_stats.py).

### Closing

The housing debate gains clarity when claims are **scoped to a series, geography, and period**. This codebase makes that scoping operational: LA rows for **supply, HPSSA medians, and workplace affordability**; region rows for **aggregated supply, EPC bands, rolling energy, and population sums**; national country tables for **long-run starts**. It does not, by itself, prove causal statements about “primary determinants” of affordability or household formation dynamics—those require additional modelling or datasets.

---

## B. Annotation layer (draft claim → evidence)

| Draft theme | Status | Data backing | Derived from |
| --- | --- | --- | --- |
| “Build more homes” / long-run supply | **Supported (scoped)** | UK and England FY starts from country tidy; GFC dip; weak 2010s UK counts vs pre-crisis | `ons_housebuilding_country_current_tidy.parquet` (`country_name`, `measure`, `frequency`, `dwellings`, `period`) |
| “Rarely exceeding 200,000” (England / late 1990s onward) | **Unsupported as written** | England FY starts exceeded 200k in most years 1997–98 to 2024–25 in this file | Same Parquet; **reword** to UK post-2011 pattern or drop |
| Regional imbalance in **prices** | **Supported** | Regional median of LA medians £161.5k–£540k | `joined_la_housing_market_snapshot.parquet` |
| P/E > 10× in “several” areas | **Under-specified → strengthened** | 83 / 315 LAs > 10; max 25.22 | `pe_affordability_ratio`; join metadata for year/period caveat |
| “Affordability divergence / falling ratios despite modest price growth” | **Not in snapshot** | Snapshot is **latest common year** only | [`housing_data/price_earnings_snapshot.py`](../housing_data/price_earnings_snapshot.py); needs multi-year tidy analysis |
| “Local incomes primary determinant” | **Overstated / causal** | Joint workplace earnings and ratio in ONS framework | Soften to **association**; cite 5a–5c methodology text |
| “Household formation vs supply” | **Unsupported in join** | Population stock 2021 on LA table; optional Census households tidy exists but is **not** in the snapshot | `census2021_la_population_2021.parquet`; `ons_census2021_households_ts041_tidy.parquet` (separate) |
| EPC C+ “past decade” | **Supported if defined** | England All-dwellings C+ 40.43% → 58.56% first vs last rolling window in file | `ons_ee_fiveyear_march2025_1c_tidy.parquet` |
| EPC “varies by LA” | **Misaligned if meaning band shares** | Band table 1a is region/country | `ons_epc_bands_*_1a_tidy.parquet`; use **median EPC score** tables for LA dispersion |
| “Linking starts, affordability, EPC in one view” | **Partially supported** | **Lane A** links starts, medians, affordability; **Lane B** links regional supply + EPC + EE; not one LA row with LA EPC bands | [`joins/README.md`](../joins/README.md), [`build_la_housing_market_snapshot.py`](../joins/build_la_housing_market_snapshot.py) |
| Buy vs rent dynamics | **Supported (indexed)** | Great Britain HPI minus PRPI spread ≈ +31.2 pp to Jan 2024 | [`housing_analytics/hpi_prpi_callout.py`](../housing_analytics/hpi_prpi_callout.py), `ons_uk_hpi_monthly_march2026_1_tidy.parquet`, `ons_private_rental_index_v41_tidy.parquet` |
| 250k–300k “benchmark” | **External** | Not computed in repo | Attribute to external source or omit |
| Figure “1997–2025” | **Check axis** | Country file spans FY **1969–70** to **2024–25**; calendar years to **2024** for some frequencies | Same country Parquet |

---

## C. Gaps and improvements

1. **Temporal affordability**: add a small analysis (or Streamlit view) that aggregates `ons_price_earnings_ratio_{edition}_5a/5c_tidy.parquet` across years to support “ratios falling while prices rise” with **numbers**.
2. **LA-level energy in Lane A**: optional merge of `ons_median_eescore_*` at LA into `joined_la_housing_market_snapshot` if you need one-row “supply–price–efficiency score” stories (bands would stay region-level).
3. **HPI–PRPI on region snapshot**: current `region_housing_market_snapshot.parquet` in this workspace **omits** `hpi_minus_prpi_growth_pp` (overlap merge can be empty when geography/time alignment fails); **regenerate** the join when both series align, or compute spread directly in reporting code (already in `build_la_housing_market_snapshot.py`).
4. **Households**: `ons_census2021_households_ts041_tidy.parquet` offers a path to **household** counts; not yet wired into the LA snapshot—use with explicit methodology if cited.
5. **Vacant / second homes**: tidy `ons_vacant_second_homes_*` is registered in [`housing_api/registry.py`](../housing_api/registry.py) but absent from the core join—rich material for “structural” narrative if added to a future join.

---

## D. High-impact visualisations (data-backed)

### Fixed mapping: Chart 1-6

- **Chart 1:** UK + England FY starts trend (country tidy)  
  **Chart 1 unavailable:** country financial-year trend data is missing.

- **Chart 2:** LA affordability ratio distribution (histogram + threshold count)  
  **Chart 2 unavailable:** joined affordability snapshot data is missing.

- **Chart 3:** Regional median price bar (sorted)  
  **Chart 3 unavailable:** regional median summary is missing.

- **Chart 4:** Entry-gap scatter (delta 6a - delta 5a) by LA  
  **Chart 4 unavailable:** entry-gap table is missing.

- **Chart 5:** England rolling EPC C+ trend + latest regional spread  
  **Trend unavailable.**  
  **Regional spread unavailable.**

- **Chart 6:** HPI vs PRPI indexed overlap (Great Britain)  
  **Chart 6 unavailable:** overlapping HPI/PRPI index series is missing.

### Interpretation rule

Use: **is associated with**, **coincides with**, **is consistent with**, **in this snapshot**, **for this geography/period**.

Avoid: **caused by**, **proves**, **driven primarily by** unless causal modeling is added.

### How this fits the project

This fixed mapping provides a stable chart contract for reporting: each chart slot is tied to a defined dataset dependency, and when that dependency is absent the narrative degrades gracefully to explicit "unavailable" messages instead of over-claiming. It keeps interpretation aligned to descriptive evidence in the current processed snapshot and preserves auditability across geographies and time definitions.

1. **United Kingdom and England housing starts, annual financial year**  
   - **Data:** `ons_housebuilding_country_current_tidy.parquet`  
   - **Filter:** `measure == "started"`, `frequency == "annual_financial_year"`, `country_name` in `{"United Kingdom","England"}`  
   - **Chart:** dual line, x = `period`, y = `dwellings`  
   - **Caption:** note financial year labels (e.g. `2024-25`).

2. **Local authority choropleth or ranked bars — workplace affordability**  
   - **Data:** `joined_la_housing_market_snapshot.parquet`  
   - **Field:** `pe_affordability_ratio` (colour or bar length); subtitle `pe_snapshot_year` + period labels from metadata.

3. **Scatter — supply intensity vs affordability**  
   - **Data:** same LA snapshot  
   - **x:** `supply_starts / population * 1000` (handle missing `population`)  
   - **y:** `pe_affordability_ratio`  
   - **colour:** `region_name` (consistent palette: `REGION_COLOR_DOMAIN` in [`housing_analytics/insights_briefing.py`](../housing_analytics/insights_briefing.py)).

4. **England — EPC C+ share across rolling windows**  
   - **Data:** `ons_ee_fiveyear_march2025_1c_tidy.parquet`  
   - **Filter:** `measure_breakdown == "All"`, `country_or_region_name == "England"`  
   - **Chart:** line, x = `rolling_period`, y = `value`  
   - **Caption:** five-year rolling windows overlap; read as ONS headline metric, not annual flow.

5. **Region snapshot panel — supply vs EPC bands**  
   - **Data:** `region_housing_market_snapshot.parquet`  
   - **Bars or dot plot:** `region_supply_starts` vs `epc_pct_bands_abc` or `ee_epc_c_plus_pct`  
   - **Footnote:** EPC/EE are England and Wales geographies; Scotland/NI rows may have nulls (see `region_housing_market_snapshot.meta.json`).

6. **Optional — buy vs rent (indexed)**  
   - **Logic:** [`buy_vs_rent_spread_caption`](../housing_analytics/hpi_prpi_callout.py) or dual indexed lines on overlapping months for `geography_name == "Great Britain"`.  
   - **Caption:** explicitly “rebased indices; not sterling levels.”

---

## E. Claim audit checklist (original draft sections)

| Original section / claim | Tag |
| --- | --- |
| Key findings — “rarely exceeding 200,000” (England, late 1990s onward) | **Unsupported** — replace with UK post-2011 facts or England-specific counts |
| Key findings — uneven supply growth | **Supported** — LA `supply_*` + country FY series |
| Key findings — London/south vs north medians | **Supported** — HPSSA medians by region (above) |
| Key findings — P/E > 10× | **Supported** — 83 LAs; define universe (315 with ratio) |
| Key findings — “affordability divergence widening” without numbers | **Weak** — needs time series |
| Key findings — energy C+ rise | **Supported** — rolling-window England 1c |
| Key findings — LA variation in EPC | **Misaligned** for band shares — use median score or rephrase to **region** |
| Key findings — integrated starts/affordability/EPC | **Overstated** — clarify Lane A vs Lane B |
| Long arc / Figure 1997–2025 | **Adjust axis** to actual `period` range in file |
| 250–300k benchmark | **External** |
| Household formation | **Unsupported** in join (optional Census households file) |
| “Primary determinant” incomes | **Overstated** — correlation / ONS joint publication only |

---

## F. 10-year regional forecast playbook (concrete implementation)

This section adds a reproducible playbook for seven forecast targets, with one fully worked regional example and a mirrored all-regions command.

### F1. Input refresh and lane snapshots

Run this first to ensure Lane A and Lane B snapshots are current:

```bash
python scripts/build_processed_manifest.py
python joins/build_la_housing_market_snapshot.py --output-dir data/processed
```

Expected output:
- `data/processed/joined_la_housing_market_snapshot.parquet`
- `data/processed/region_housing_market_snapshot.parquet`

### F2. Worked example: London

Run all seven targets for London:

```bash
python scripts/forecast_playbook/run_forecast_playbook.py \
  --edition march2026 \
  --region "London"
```

Outputs (under `data/processed/forecasts/march2026/london/`):
- `hpi_growth_predictions.csv` and `hpi_growth_metrics.json`
- `affordability_pressure_predictions.csv` and `affordability_pressure_metrics.json`
- `quantile_price_band_predictions.csv` and `quantile_price_band_metrics.json`
- `divergence_risk_predictions.csv`, `divergence_risk_metrics.json`, `divergence_risk_calibration.json`
- `supply_shortfall_predictions.csv`, `supply_shortfall_metrics.json`, `supply_shortfall_calibration.json`
- `epc_adoption_predictions.csv` and `epc_adoption_metrics.json`
- `vacancy_pressure_predictions.csv`, `vacancy_pressure_metrics.json`, `vacancy_pressure_calibration.json`

Each prediction file publishes:
- `point_estimate` plus `interval_low`/`interval_high` or `probability`
- horizon-specific backtest score (`backtest_metric`, `backtest_value`)
- baseline comparison (`baseline_metric`, `baseline_value`)
- one-line caveat (`caveat`)

### F3. Mirror template for all regions

```bash
python scripts/forecast_playbook/run_forecast_playbook.py \
  --edition march2026 \
  --all-regions
```

Consolidated scoreboard:
- `data/processed/forecasts/march2026/forecast_playbook_scoreboard.parquet`

### F4. Per-target command templates (single region)

Use `--region "London"` for worked example; replace with any region string from `ons_uk_hpi_monthly_march2026_1_tidy.parquet`.

```bash
python scripts/forecast_playbook/run_hpi_growth_target.py --edition march2026 --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_affordability_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_quantile_price_band_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_divergence_risk_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_supply_shortfall_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_epc_adoption_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
python scripts/forecast_playbook/run_vacancy_pressure_target.py --region "London" --output-dir data/processed/forecasts/march2026/london
```

### F5. Output interpretation rubric

- **Regional HPI growth (12m/24m):** positive point estimate means projected index growth (`hpi_index_t+h / hpi_index_t - 1`); use MAE vs seasonal-naive MAE to judge value add.
- **Affordability pressure change (1-3y):** positive delta implies worsening affordability pressure; if interval spans zero, direction confidence is low.
- **LA median price quantile band:** `P10/P50/P90` provide downside/base/upside levels; narrow bands indicate lower cross-LA uncertainty.
- **Rent-vs-price divergence risk:** `probability` reflects chance that HPI outpaces PRPI; spread estimate gives expected `hpi_minus_prpi_growth_pp` size.
- **Supply shortfall likelihood:** calibrated probability near 1.0 indicates high risk of demand proxy outgrowing completions; compare Brier score to baseline.
- **EPC adoption trajectory:** point estimate is expected annual change in `% EPC C+`; positive values indicate faster energy-efficiency adoption.
- **Vacancy/second-home pressure class:** class probabilities (`rising/stable/falling`) are model output; threshold logic is documented in output rows for explainability.

### F6. Standard caveat

All forecast outputs include:
- `Macro shocks and policy regime changes are not explicitly modeled in these forecasts.`

---

*End of aligned narrative package.*
