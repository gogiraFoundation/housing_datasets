from __future__ import annotations

import os


def api_keys() -> list[str]:
    raw = os.environ.get("HOUSING_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def enable_metrics() -> bool:
    return os.environ.get("HOUSING_API_ENABLE_METRICS", "").lower() in ("1", "true", "yes")


def metrics_require_key() -> bool:
    return os.environ.get("HOUSING_API_METRICS_REQUIRE_KEY", "").lower() in ("1", "true", "yes")


def enable_docs() -> bool:
    return os.environ.get("HOUSING_API_DOCS", "1").lower() not in ("0", "false", "no")


def repo_root() -> str:
    return os.environ.get("HOUSING_REPO_ROOT", "")
