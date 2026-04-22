# Boundary data for maps

The Streamlit **Map — housing** page expects **GeoJSON** in **WGS84** (EPSG:4326): LAD polygons use a **9-character GSS** `lad_code` matching `Local Authority Code` in ONS house-building outputs; **region** mode uses `regions_uk_wgs84.geojson` (see below).

## Canonical file (recommended)

`data/geo/lad_uk_wgs84.geojson` — full **United Kingdom** Local Authority Districts (**December 2022 UK BUC**, ultra-generalised). Properties include:

- **`LAD22CD`** — ONS district code (same scheme as `Local Authority Code` in the tidy Parquet).
- **`lad_code`** — duplicate of `LAD22CD` in uppercase (for joins and tooltips).
- **`LAD22NM`** — district name.

Generate or refresh from ONS ArcGIS:

```bash
python scripts/download_lad_boundaries.py
```

## Region boundaries (Lane B choropleth)

`data/geo/regions_uk_wgs84.geojson` — merged **England Government Office Regions** (December 2022 EN BUC) plus **Wales, Scotland, and Northern Ireland** country polygons (December 2022 UK BUC). Each feature includes:

- **`region_code`** — GSS code (`RGN22CD` for English regions, `CTRY22CD` for the three countries).
- **`region_name`** — `RGN22NM` or `CTRY22NM`.
- **`lad_code`** — duplicate of `region_code` so the map layer can reuse the same join key field name as LAD GeoJSON.

Generate or refresh:

```bash
python scripts/download_region_boundaries.py
```

## Legacy filenames

The map page also accepts (in order of preference):

1. `lad_uk_wgs84.geojson` — full UK (see above).
2. `lad_england.geojson` — older docs referred to this name; same property rules (`LAD21CD` / `LAD22CD` / `lad_code`).
3. `minimal_lad_demo.geojson` — two placeholder polygons for testing only.

## Option A — Demo file

`minimal_lad_demo.geojson` contains two placeholder polygons for pipeline testing only (most of the map will be empty).

## Coordinate reference

Web maps require **WGS84** (longitude/latitude). The download script requests `outSR=4326` from the ONS service.

## Metrics on the map page

- **House building, median price (existing / new), affordability, Lane A snapshot tooltips, and house building × main fuel** use **local authority** rows joined by `lad_code`.
- **Regions (Lane B snapshot)** colours **region polygons** using `region_housing_market_snapshot.parquet` (supply, EPC, five-year rolling, etc.) — not an LA choropleth.
- **EPC band C %** on the LA map uses ONS table 1a at **country/region** only; each **LA** polygon is coloured with its **region’s** band C share. See the warning on the page; this is **not** an LA stock estimate.

## Attribution

Boundary products contain **Ordnance Survey** and **ONS** intellectual property; use in line with [ONS Open Geography](https://geoportal.statistics.gov.uk/) and [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) terms.
