#!/usr/bin/env bash
# Run all ETL pipelines (see README.md), then start the Streamlit dashboard.
# Usage:
#   ./start.sh
#   SKIP_ETL=1 ./start.sh              # app only (data already in data/processed/)
#   USE_RUN_DASHBOARD=1 ./start.sh     # use run_dashboard.py (health + optional restart)
#   ./start.sh --app-only              # same as SKIP_ETL=1
#   ./start.sh --monitor               # same as USE_RUN_DASHBOARD=1
#   SKIP_GEO=1 ./start.sh              # do not fetch LAD GeoJSON even if missing (air-gapped / custom file)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

skip_etl=0
use_run_dashboard=0
for arg in "$@"; do
  case "$arg" in
    --app-only) skip_etl=1 ;;
    --monitor) use_run_dashboard=1 ;;
  esac
done
if [[ "${SKIP_ETL:-0}" == "1" ]]; then
  skip_etl=1
fi
if [[ "${USE_RUN_DASHBOARD:-0}" == "1" ]]; then
  use_run_dashboard=1
fi

if [[ "$skip_etl" -eq 0 ]]; then
  echo "[start] running pipelines with: $PYTHON"
  "$PYTHON" uk_local_authority_housing_data.py
  "$PYTHON" ons_epc_etl.py --edition march2025
  "$PYTHON" ons_ee_fiveyear_etl.py --edition march2025
  "$PYTHON" ons_housebuilding_la_etl.py --edition fye_march2025
  "$PYTHON" ons_housebuilding_country_etl.py --edition current
  "$PYTHON" ons_mainfuel_etl.py --edition march2025
  "$PYTHON" ons_uk_hpi_monthly_etl.py --edition march2026
  "$PYTHON" ons_house_m2_room_etl.py --edition 2004to2016
  "$PYTHON" ons_median_price_admin_etl.py --dataset existing --edition yearendingseptember2025
  "$PYTHON" ons_median_price_admin_etl.py --dataset new --edition yearendingseptember2025
  "$PYTHON" ons_price_earnings_ratio_etl.py --edition current
  "$PYTHON" ons_house_price_explorer_etl.py --edition current
  echo "[start] ETL finished; starting dashboard"
else
  echo "[start] SKIP_ETL=1 / --app-only: skipping pipelines"
fi

GEO_FILE="$ROOT/data/geo/lad_uk_wgs84.geojson"
if [[ "${SKIP_GEO:-0}" == "1" ]]; then
  if [[ ! -f "$GEO_FILE" ]]; then
    echo "[start] SKIP_GEO=1: not downloading LAD GeoJSON; map page may use demo boundaries unless you add data/geo/lad_uk_wgs84.geojson (see data/geo/README.md)."
  fi
elif [[ ! -f "$GEO_FILE" ]]; then
  echo "[start] LAD GeoJSON missing; downloading boundaries (one-time unless file removed)..."
  "$PYTHON" scripts/download_lad_boundaries.py
fi

if [[ "$use_run_dashboard" -eq 1 ]]; then
  exec "$PYTHON" run_dashboard.py
else
  exec "$PYTHON" -m streamlit run app.py
fi
