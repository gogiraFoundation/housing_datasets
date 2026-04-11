from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from housing_api.constants import API_PREFIX
from housing_api.settings import enable_metrics


def normalize_path_for_metrics(path: str) -> str:
    """Collapse dataset id segments so Prometheus labels stay low-cardinality."""
    list_path = f"{API_PREFIX}/datasets"
    base = f"{API_PREFIX}/datasets/"
    if path == list_path:
        return path
    if not path.startswith(base):
        return path
    rest = path[len(base) :]
    if "/" not in rest:
        return f"{API_PREFIX}/datasets/{{id}}"
    _dataset_id, sub = rest.split("/", 1)
    if sub == "export":
        return f"{API_PREFIX}/datasets/{{id}}/export"
    if sub == "chart-spec":
        return f"{API_PREFIX}/datasets/{{id}}/chart-spec"
    return f"{API_PREFIX}/datasets/{{id}}"

_requests_total: dict[tuple[str, str], int] = {}
_latency_sum_ms: dict[tuple[str, str], float] = {}
_latency_count: dict[tuple[str, str], int] = {}


def _bump(method: str, path: str, latency_ms: float) -> None:
    key = (method, path)
    _requests_total[key] = _requests_total.get(key, 0) + 1
    _latency_sum_ms[key] = _latency_sum_ms.get(key, 0.0) + latency_ms
    _latency_count[key] = _latency_count.get(key, 0) + 1


class PrometheusSimpleMiddleware(BaseHTTPMiddleware):
    """In-memory counters + latency; GET /metrics when HOUSING_API_ENABLE_METRICS is set."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not enable_metrics():
            return await call_next(request)
        if request.url.path == "/metrics":
            return await call_next(request)
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000.0
        path = request.scope.get("path", "") or ""
        norm = normalize_path_for_metrics(path)
        _bump(request.method, norm, ms)
        return response


def metrics_response() -> PlainTextResponse:
    lines: list[str] = []
    for (method, path), n in sorted(_requests_total.items()):
        safe = path.replace('"', '\\"')
        lines.append(f'http_requests_total{{method="{method}",path="{safe}"}} {n}')
    for (method, path), s in sorted(_latency_sum_ms.items()):
        c = _latency_count.get((method, path), 1)
        avg = s / c
        safe = path.replace('"', '\\"')
        lines.append(f'http_request_latency_ms_avg{{method="{method}",path="{safe}"}} {avg:.4f}')
    body = "\n".join(lines) + ("\n" if lines else "")
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")
