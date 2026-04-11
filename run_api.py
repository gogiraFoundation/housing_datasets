#!/usr/bin/env python3
"""Run the FastAPI housing datasets API (uvicorn).

Serves ``housing_api.app``: ``GET /health``; optional ``GET /metrics`` when
``HOUSING_API_ENABLE_METRICS=1``; authenticated dataset routes under ``/api/v1/datasets`` (list,
rows with optional filters, ``/export``, ``/chart-spec`` for LA house-building). OpenAPI UI at
``/api/v1/docs`` unless ``HOUSING_API_DOCS=0``. Prefix is ``housing_api.constants.API_PREFIX``.

Environment (production):

- ``HOUSING_API_KEYS`` — comma-separated API keys; required for dataset routes (503 if unset).
- ``HOUSING_REPO_ROOT`` — repo root containing ``data/processed/`` (optional; defaults next to package).
- ``HOUSING_API_DOCS`` — set ``0`` to disable OpenAPI/Swagger UIs.
- ``HOUSING_API_ENABLE_METRICS`` — ``1`` to expose ``GET /metrics`` (Prometheus-style text).
- ``HOUSING_API_METRICS_REQUIRE_KEY`` — ``1`` to require the same Bearer / ``X-API-Key`` auth as
  datasets for ``/metrics`` (for scrapes behind a shared listener without network ACLs only).
  When metrics are enabled and this is unset, restrict ``/metrics`` with firewall or reverse proxy.
- ``HOUSING_API_HOST`` / ``HOUSING_API_PORT`` — bind address (default ``127.0.0.1:8000``).

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
