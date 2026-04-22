# Joining housing supply and energy statistics

ONS products in this repo use **different geographies**. Join only on **matching definitions**; do not match LA-level stock tables to region-level EPC tables without an official lookup and aggregation.

## Joinability matrix

| Source | Tidy output (examples) | Geography | Primary join keys |
|--------|------------------------|-----------|-------------------|
| Bundled housing starts | `uk_housing_starts_tidy.parquet` | Local authority | `Local Authority Code`, `Local Authority Name` |
| ONS house building (LA) | `ons_housebuilding_la_*_tidy.parquet` | Local authority | Same four ID columns (`Local Authority Code`, …) |
| ONS main fuel tables **2a, 2b** | `ons_mainfuel_*_2a_tidy.parquet`, `…_2b_tidy.parquet` | Region + LAD | `local_authority_district_code`, `local_authority_district_name` |
| ONS main fuel **1a–1c** | `ons_mainfuel_*_1a_tidy.parquet`, … | Country / region | `country_or_region_code`, `country_or_region_name` |
| Individual EPC bands | `ons_epc_bands_*_*_tidy.parquet` | Country / region | `country_or_region_code`, `country_or_region_name` |
| Five-year rolling | `ons_ee_fiveyear_*_*_tidy.parquet` | Country / region | `country_or_region_code`, `country_or_region_name` |
| Median energy efficiency score | `ons_median_eescore_*_*_tidy.parquet` | Country / region (per sheet) | `country_or_region_code`, `country_or_region_name` |
| Census 2021 topic summaries (LTLA) | `ons_census2021_*_tidy.parquet`, `census2021_la_population_2021.parquet` | Lower-tier local authorities (England & Wales) | `lad_code` ↔ `Local Authority Code` (normalised) |
| House price / workplace earnings | `ons_price_earnings_ratio_*_{5a,5b,5c}_tidy.parquet` | Local authority (tables **5a–5c** only) | `local_authority_code` ↔ `lad_code` (normalised), same **calendar year** across 5a/5b/5c for a snapshot |

## Clean joins (recommended)

1. **LA supply × LA heating mix (cross-section)**  
   Join `ons_housebuilding_la_{edition}_tidy` to `ons_mainfuel_{edition}_2a` (and/or `_2b`) on **normalised** `Local Authority Code` ↔ `local_authority_district_code` (9-character GSS codes, strip whitespace).  
   House building is a **time series** (financial year); main fuel tables are a **snapshot** for the workbook’s reference period. Do not treat fuel percentages as time-aligned to every financial year without an explicit assumption documented in metadata.

2. **Region stock × region supply (after aggregation)**  
   Aggregate LA house building to **region** using a **verified** LAD→region lookup (see `data/reference/`). Then join to five-year rolling, EPC, or main fuel 1a–1c on **region code** (map ONS naming differences via codes, not labels).

## Joins to avoid without extra bridging data

- **EPC bands or five-year rolling → LA** directly: those tables are not published at LA in the workbooks automated here.
- **Financial year ↔ five-year rolling window** as the same time period: different definitions; compare only with clear labelling.

## Population vs EPC (same geography)

**Census population is at LA; EPC bands and five-year rolling energy tables in this repo are at country/region.** To compare “population vs EPC” in one table, use **region-level** rows: sum Census LA population to **`region_code`** using the same LAD→region mapping as main fuel 2a (as in **Lane B** below). Do not attribute regional EPC percentages to a single LA without a different data source.

## LA housing market snapshot (two lanes)

[`build_la_housing_market_snapshot.py`](build_la_housing_market_snapshot.py) builds two Parquet files after upstream ETLs have run:

- **Lane A (`joined_la_housing_market_snapshot.parquet`):** one row per `lad_code` — LAD→region (from `data/reference/lad_to_region_england.csv` or main fuel 2a), optional Census 2021 population, **latest** financial year starts/completions from ONS LA house building, **latest** median price from HPSSA **median existing admin table 2a** (all property types), optional **median new** admin 2a (defaults align with existing when Parquet is present), pivoted main fuel **2a/2b**, optional **UK HPI** sheet 8 (England LAs), optional **price/earnings** columns from `ons_price_earnings_ratio_{edition}_{5a,5b,5c}_tidy.parquet` (latest **calendar year** common to all three sheets: `pe_median_price_gbp`, `pe_workplace_earnings_gbp`, `pe_affordability_ratio`). Optional **vacant / second-home headline counts** per LAD from `ons_vacant_second_homes_{edition}_1a_tidy.parquet` (`--vacant-second-homes-edition ""` to skip). Skip the price/earnings join with `--skip-price-earnings` or `--price-earnings-edition ""`. Periods differ by design (see `*.meta.json` sidecar). The Streamlit **Map — local authority** page can show **Lane B** on a **region** boundary file (see `scripts/download_region_boundaries.py`, `data/geo/README.md`).
- **Lane B (`region_housing_market_snapshot.parquet`):** one row per `region_code` — **aggregated** LA supply for the latest financial year, **EPC 1a** band C and A–C sums, **five-year rolling** table **1c** `measure_breakdown == All` (EPC C+ %) for the latest rolling window, **`region_population_census2021`** (sum of Census 2021 LA populations mapped via main fuel 2a, plus `region_population_year` when present). Do not merge Lane B onto every LA row.

```bash
python joins/build_la_housing_market_snapshot.py
```

Use [`pages/15_Housing_market_comparator.py`](../pages/15_Housing_market_comparator.py) to explore the outputs.

## Scripts in this folder

| Script | Purpose |
|--------|---------|
| `build_joined_la_housebuilding_mainfuel.py` | LA house building + main fuel 2a/2b → `data/processed/joined_la_housebuilding_mainfuel_*.parquet` |
| `build_la_housing_market_snapshot.py` | Lane A + Lane B market snapshots → `joined_la_housing_market_snapshot.parquet`, `region_housing_market_snapshot.parquet` |
| `aggregate_la_supply_to_region.py` | Sum LA dwellings by region + financial year using LAD→region lookup |
| `build_la_rankings.py` | Optional per-capita metrics when `data/reference/population_la_midyear.csv` is present |
| `build_processed_manifest.py` | (in `../scripts/`) Catalogue of processed files + raw `*.meta.json` hashes |
