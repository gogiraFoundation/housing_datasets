#!/usr/bin/env bash
# Run all ETL pipelines (see README.md), then start the Streamlit dashboard.
# Usage:
#   ./start.sh
#   SKIP_ETL=1 ./start.sh              # app only (data already in data/processed/)
#   USE_RUN_DASHBOARD=1 ./start.sh     # use run_dashboard.py (health + optional restart)
#   ./start.sh --app-only              # same as SKIP_ETL=1
#   ./start.sh --monitor               # same as USE_RUN_DASHBOARD=1
#   SKIP_GEO=1 ./start.sh              # do not fetch LAD GeoJSON even if missing (air-gapped / custom file)
#   ETL_PROFILE=full ./start.sh        # standard ETL + Census TS008 + processed_manifest (see scripts/run_etl_suite.py)
#   ETL_WITH_JOINS=1 ./start.sh        # append join builders after the suite (needs prior outputs)
#   ETL_CONTINUE_ON_ERROR=1 ./start.sh # run all suite steps even if one fails

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
  echo "[start] running pipelines with: $PYTHON (see scripts/run_etl_suite.py)"
  ETL_ARGS=(--profile "${ETL_PROFILE:-standard}")
  if [[ "${ETL_WITH_JOINS:-0}" == "1" ]]; then
    ETL_ARGS+=(--with-joins)
  fi
  if [[ "${ETL_CONTINUE_ON_ERROR:-0}" == "1" ]]; then
    ETL_ARGS+=(--continue-on-error)
  fi
  "$PYTHON" scripts/run_etl_suite.py "${ETL_ARGS[@]}"
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
