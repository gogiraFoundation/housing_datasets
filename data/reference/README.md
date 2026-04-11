# Reference tables (optional)

## LAD to region (England)

- **`lad_to_region_england.csv`** — One row per local authority district in England with parent region.  
  **Source:** derive from ONS main fuel table **2a** for a given edition (unique `(local_authority_district_code, region_code)`), or use an official [Open Geography Portal](https://geoportal.statistics.gov.uk/) lookup.  
  Expected columns: `lad_code`, `region_code`, `region_name`.

The aggregation script `joins/aggregate_la_supply_to_region.py` can build this file from `ons_mainfuel_{edition}_2a_tidy.parquet` if you pass `--write-lookup`.

## Population (optional, for per-capita rankings)

- **`population_la_midyear.csv`** — Mid-year estimates by LA.  
  Columns: `lad_code`, `year` (e.g. `2021`), `population` (numeric).  
  Obtain from [ONS population estimates](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates) (table structure varies by release; align `lad_code` to GSS codes used in house building).

If this file is absent, `joins/build_la_rankings.py` still writes rankings that do not require population (e.g. completions per start where both exist).
