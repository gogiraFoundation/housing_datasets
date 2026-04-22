from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.lower() in ("1", "true", "yes")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def api_env() -> str:
    """e.g. ``development`` | ``production`` — affects OpenAPI defaults."""
    return os.environ.get("HOUSING_API_ENV", "development").strip().lower()


def is_production_env() -> bool:
    return api_env() in ("production", "prod")


def _parse_key_lines(text: str) -> list[str]:
    keys: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        keys.append(s)
    return keys


def _load_keys_from_aws_secret(secret_id: str) -> list[str]:
    try:
        import boto3  # type: ignore[import-untyped]
    except ImportError as e:  # pragma: no cover - exercised when optional dep missing
        raise RuntimeError(
            "HOUSING_API_KEYS_SECRET_ID is set but boto3 is not installed. "
            "Install boto3 or use HOUSING_API_KEYS / HOUSING_API_KEYS_FILE."
        ) from e
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_id)
    payload = resp.get("SecretString") or ""
    payload = payload.strip()
    if not payload:
        return []
    try:
        obj: Any = json.loads(payload)
    except json.JSONDecodeError:
        return [k.strip() for k in payload.split(",") if k.strip()]
    if isinstance(obj, list):
        return [str(x).strip() for x in obj if str(x).strip()]
    if isinstance(obj, dict) and "keys" in obj:
        raw = obj["keys"]
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, str):
            return [k.strip() for k in raw.split(",") if k.strip()]
    if isinstance(obj, dict) and "HOUSING_API_KEYS" in obj:
        raw = obj["HOUSING_API_KEYS"]
        if isinstance(raw, str):
            return [k.strip() for k in raw.split(",") if k.strip()]
    return [k.strip() for k in payload.split(",") if k.strip()]


def api_keys() -> list[str]:
    """API keys: non-empty ``HOUSING_API_KEYS`` env wins; else file; else AWS secret id."""
    raw = os.environ.get("HOUSING_API_KEYS", "")
    env_keys = [k.strip() for k in raw.split(",") if k.strip()]
    if env_keys:
        return env_keys
    key_file = os.environ.get("HOUSING_API_KEYS_FILE", "").strip()
    if key_file:
        p = Path(key_file)
        if p.is_file():
            raw_file = p.read_text(encoding="utf-8").strip()
            if "\n" in raw_file:
                return _parse_key_lines(raw_file)
            return [k.strip() for k in raw_file.split(",") if k.strip()]
        return []
    secret_id = os.environ.get("HOUSING_API_KEYS_SECRET_ID", "").strip()
    if secret_id:
        return _load_keys_from_aws_secret(secret_id)
    return []


def enable_metrics() -> bool:
    return _truthy(os.environ.get("HOUSING_API_ENABLE_METRICS"))


def metrics_require_key() -> bool:
    return _truthy(os.environ.get("HOUSING_API_METRICS_REQUIRE_KEY"))


def enable_docs() -> bool:
    """OpenAPI/Swagger UIs. Production defaults off unless ``HOUSING_API_DOCS=1``."""
    docs_override = os.environ.get("HOUSING_API_DOCS", "").strip()
    if docs_override:
        return docs_override.lower() not in ("0", "false", "no")
    if is_production_env():
        return False
    return True


def repo_root() -> str:
    return os.environ.get("HOUSING_REPO_ROOT", "")


def resolved_processed_dir(repo_root: Path) -> Path:
    """Tidy outputs directory: ``HOUSING_PROCESSED_DIR`` or ``<repo_root>/data/processed``."""
    raw = os.environ.get("HOUSING_PROCESSED_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (repo_root / "data" / "processed").resolve()


def default_page_limit() -> int:
    return max(1, _int_env("HOUSING_API_DEFAULT_LIMIT", 500))


def max_page_limit() -> int:
    return max(1, _int_env("HOUSING_API_MAX_ROWS", 10_000))


def max_export_rows() -> int:
    return max(1, _int_env("HOUSING_API_MAX_EXPORT_ROWS", 250_000))


def max_export_json_rows() -> int:
    return max(1, _int_env("HOUSING_API_MAX_EXPORT_JSON_ROWS", 5000))


def generic_large_row_threshold() -> int:
    """Row counts above this trigger the generic full-scan guard (0 disables)."""
    return max(0, _int_env("HOUSING_API_MAX_ROWS_WITHOUT_FILTERS", 50_000))


def allow_large_generic_reads() -> bool:
    return _truthy(os.environ.get("HOUSING_API_ALLOW_LARGE_GENERIC"))


def use_duckdb_generic_pages() -> bool:
    """Use DuckDB for generic dataset row reads (LIMIT/OFFSET) to avoid full pandas load."""
    return _truthy(os.environ.get("HOUSING_API_USE_DUCKDB"))
