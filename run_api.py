#!/usr/bin/env python3
"""Run the FastAPI housing datasets API (uvicorn).

Serves ``housing_api.app``: ``GET /health``; optional ``GET /metrics`` when
``HOUSING_API_ENABLE_METRICS=1``; authenticated dataset routes under ``/api/v1/datasets`` (list,
rows with optional filters, ``/export``, ``/chart-spec`` for LA house-building). OpenAPI UI at
``/api/v1/docs`` unless ``HOUSING_API_DOCS=0``. Prefix is ``housing_api.constants.API_PREFIX``.

Environment (production):

- ``HOUSING_API_KEYS`` — comma-separated API keys; required for dataset routes (503 if unset).
  Prefer ``HOUSING_API_KEYS_FILE`` (mounted secret file: one key per line or comma-separated single
  line) or ``HOUSING_API_KEYS_SECRET_ID`` (AWS Secrets Manager; install ``boto3``) when ``HOUSING_API_KEYS``
  is unset. Rotate keys via your secret store; restart workers after rotation.
- ``HOUSING_REPO_ROOT`` — repo root containing ``data/processed/`` (optional; defaults next to package).
- ``HOUSING_API_ENV`` — set ``production`` to disable OpenAPI UIs by default (override with ``HOUSING_API_DOCS=1``).
- ``HOUSING_API_DOCS`` — ``0`` / ``1`` explicitly disables or enables OpenAPI/Swagger UIs.
- ``HOUSING_API_DEFAULT_LIMIT`` / ``HOUSING_API_MAX_ROWS`` — page size defaults and ceiling for ``GET .../datasets/{id}``.
- ``HOUSING_API_MAX_EXPORT_ROWS`` / ``HOUSING_API_MAX_EXPORT_JSON_ROWS`` — export row caps (JSON is stricter than CSV).
- ``HOUSING_API_MAX_ROWS_WITHOUT_FILTERS`` — for ``generic`` datasets, refuse full-table reads above this row count
  unless ``columns=`` is passed, ``HOUSING_API_ALLOW_LARGE_GENERIC=1``, or the threshold is raised (see README).
- ``HOUSING_API_USE_DUCKDB`` — ``1`` to read ``generic`` pages via DuckDB (LIMIT/OFFSET) instead of loading the full
  DataFrame when possible.
- ``HOUSING_API_ENABLE_METRICS`` — ``1`` to expose ``GET /metrics`` (Prometheus-style text).
- ``HOUSING_API_METRICS_REQUIRE_KEY`` — ``1`` to require the same Bearer / ``X-API-Key`` auth as
  datasets for ``/metrics`` (for scrapes behind a shared listener without network ACLs only).
  When metrics are enabled and this is unset, restrict ``/metrics`` with firewall or reverse proxy.
- ``HOUSING_API_HOST`` / ``HOUSING_API_PORT`` — bind address (default ``127.0.0.1:8000``).

Application logs (JSON) include ``path``, ``method``, ``latency_ms``, and ``client`` (``key_1`` style);
they do **not** log ``Authorization`` or ``X-API-Key``. Configure Uvicorn/proxy access logs so sensitive
headers are not written in production.

The Streamlit dashboard (``streamlit run app.py``) has no application-level auth; use a private
network, reverse-proxy auth, or a host that enforces access (e.g. Streamlit Cloud).
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import uvicorn
    except ImportError:
        print("error: uvicorn is required. pip install uvicorn[standard]", file=sys.stderr)
        return 1

    host = os.environ.get("HOUSING_API_HOST", "127.0.0.1")
    port = int(os.environ.get("HOUSING_API_PORT", "8000"))
    uvicorn.run("housing_api.app:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
