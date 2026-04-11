# Boundary data for maps

The Streamlit **Map — local authority** page expects a **GeoJSON** in **WGS84** (EPSG:4326) with a **9-character GSS code** on each feature, matching `Local Authority Code` in ONS house-building outputs.

## Canonical file (recommended)

`data/geo/lad_uk_wgs84.geojson` — full **United Kingdom** Local Authority Districts (**December 2022 UK BUC**, ultra-generalised). Properties include:

- **`LAD22CD`** — ONS district code (same scheme as `Local Authority Code` in the tidy Parquet).
- **`lad_code`** — duplicate of `LAD22CD` in uppercase (for joins and tooltips).
- **`LAD22NM`** — district name.

Generate or refresh from ONS ArcGIS:

```bash
python scripts/download_lad_boundaries.py
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

- **House building, median price (existing), and affordability** are **local-authority** values joined by `LAD22CD` / `lad_code`.
- **EPC band C %** in ONS table 1a is published at **country/region** only. The map colours **each LA polygon** using its **region’s** band C share (constant within the region). See the warning on the page; this is **not** an LA stock estimate.

## Attribution

Boundary products contain **Ordnance Survey** and **ONS** intellectual property; use in line with [ONS Open Geography](https://geoportal.statistics.gov.uk/) and [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) terms.
