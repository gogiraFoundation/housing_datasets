#!/usr/bin/env bash
# Build tidy Parquet artefacts during image/workspace build.
#
# Usage:
#   ./scripts/build_deploy_parquet.sh
#   ETL_PROFILE=full ETL_WITH_JOINS=1 ./scripts/build_deploy_parquet.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

ETL_PROFILE="${ETL_PROFILE:-standard}"
ETL_WITH_JOINS="${ETL_WITH_JOINS:-1}"
ETL_CONTINUE_ON_ERROR="${ETL_CONTINUE_ON_ERROR:-0}"

echo "[build] generating processed parquet with ${PYTHON}"
ETL_ARGS=(--profile "${ETL_PROFILE}")
if [[ "${ETL_WITH_JOINS}" == "1" ]]; then
  ETL_ARGS+=(--with-joins)
fi
if [[ "${ETL_CONTINUE_ON_ERROR}" == "1" ]]; then
  ETL_ARGS+=(--continue-on-error)
fi

"${PYTHON}" scripts/run_etl_suite.py "${ETL_ARGS[@]}"
"${PYTHON}" scripts/download_lad_boundaries.py
"${PYTHON}" scripts/download_region_boundaries.py
"${PYTHON}" scripts/build_processed_manifest.py

echo "[build] done: data/processed is populated"
