"""Tests for the FastAPI housing datasets API."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from housing_api.constants import API_PREFIX
from housing_api.metrics import normalize_path_for_metrics


@pytest.fixture
def api_key() -> str:
    return "pytest-api-key-rotated"


@pytest.fixture
def tmp_repo(tmp_path: Path, api_key: str) -> Path:
    """Minimal repo layout with one house-building LA parquet."""
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "financial_year": ["2009-2010", "2009-2010", "2010-2011"],
            "measure": ["starts", "completions", "starts"],
            "Region or Country Name": ["North East", "North East", "North East"],
            "Local Authority Name": ["Hartlepool", "Hartlepool", "Hartlepool"],
            "dwellings": [10.0, 5.0, 12.0],
        }
    )
    df.to_parquet(proc / "ons_housebuilding_la_fye_march2025_tidy.parquet", index=False)
    return tmp_path


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_repo: Path, api_key: str) -> TestClient:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "0")
    from housing_api.app import create_app

    return TestClient(create_app())


def test_normalize_path_for_metrics_matches_routes() -> None:
    p = API_PREFIX
    assert normalize_path_for_metrics(f"{p}/datasets") == f"{p}/datasets"
    assert normalize_path_for_metrics(f"{p}/datasets/ons_housebuilding_la_fye_march2025") == f"{p}/datasets/{{id}}"
    assert normalize_path_for_metrics(f"{p}/datasets/foo/export") == f"{p}/datasets/{{id}}/export"
    assert normalize_path_for_metrics(f"{p}/datasets/foo/chart-spec") == f"{p}/datasets/{{id}}/chart-spec"
    assert normalize_path_for_metrics("/health") == "/health"


def test_health_unauthenticated(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_datasets_requires_auth(client: TestClient) -> None:
    r = client.get(f"{API_PREFIX}/datasets")
    assert r.status_code == 401


def test_invalid_key_wrong_length_returns_401_not_500(client: TestClient) -> None:
    """hmac.compare_digest raises on length mismatch; auth must still return 401."""
    r = client.get(
        f"{API_PREFIX}/datasets",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 401


def test_no_api_keys_configured_503(monkeypatch: pytest.MonkeyPatch, tmp_repo: Path) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", "")
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    from housing_api.app import create_app

    c = TestClient(create_app())
    r = c.get(f"{API_PREFIX}/datasets")
    assert r.status_code == 503


def test_datasets_with_bearer(client: TestClient) -> None:
    r = client.get(f"{API_PREFIX}/datasets", headers={"Authorization": "Bearer pytest-api-key-rotated"})
    assert r.status_code == 200
    body = r.json()
    assert "datasets" in body
    ids = {d["id"] for d in body["datasets"]}
    assert "ons_housebuilding_la_fye_march2025" in ids


def test_datasets_x_api_key(client: TestClient) -> None:
    r = client.get(f"{API_PREFIX}/datasets", headers={"X-API-Key": "pytest-api-key-rotated"})
    assert r.status_code == 200


def test_unknown_dataset_404(client: TestClient) -> None:
    r = client.get(
        f"{API_PREFIX}/datasets/does-not-exist",
        headers={"Authorization": "Bearer pytest-api-key-rotated"},
    )
    assert r.status_code == 404


def test_rows_and_etag(client: TestClient) -> None:
    h = {"Authorization": "Bearer pytest-api-key-rotated"}
    r = client.get(f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025", headers=h)
    assert r.status_code == 200
    assert r.json()["total_rows"] == 3
    assert len(r.json()["rows"]) == 3
    etag = r.headers.get("ETag")
    assert etag
    r2 = client.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025",
        headers={**h, "If-None-Match": etag},
    )
    assert r2.status_code == 304


def test_export_csv(client: TestClient) -> None:
    r = client.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025/export?format=csv",
        headers={"Authorization": "Bearer pytest-api-key-rotated"},
    )
    assert r.status_code == 200
    assert "financial_year" in r.text


def test_chart_spec_vega(client: TestClient) -> None:
    r = client.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025/chart-spec?chart=line_by_year",
        headers={"Authorization": "Bearer pytest-api-key-rotated"},
    )
    assert r.status_code == 200
    spec = r.json()
    assert "encoding" in spec or "layer" in spec or "mark" in spec


def test_chart_spec_wrong_family_404(client: TestClient) -> None:
    # Registry has uk_housing_starts but file missing -> still chart 404 for generic
    r = client.get(
        f"{API_PREFIX}/datasets/uk_housing_starts/chart-spec",
        headers={"Authorization": "Bearer pytest-api-key-rotated"},
    )
    assert r.status_code == 404


def test_country_dataset_rows_filtered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, api_key: str) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "table_id": ["1"] * 4,
            "country_name": ["England", "England", "Wales", "Wales"],
            "frequency": ["annual_financial_year"] * 4,
            "period": ["2009-2010", "2010-2011", "2009-2010", "2010-2011"],
            "measure": ["starts", "starts", "starts", "starts"],
            "sector": ["All Dwellings"] * 4,
            "dwellings": [10, 20, 5, 8],
        }
    )
    df.to_parquet(proc / "ons_housebuilding_country_current_tidy.parquet", index=False)
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "0")
    from housing_api.app import create_app

    c = TestClient(create_app())
    r = c.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_country_current?country_name=England&period_min=2009-2010&period_max=2009-2010",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert r.status_code == 200
    assert r.json()["total_rows"] == 1
    assert r.json()["rows"][0]["country_name"] == "England"


def test_safe_processed_path_rejects_traversal(tmp_path: Path) -> None:
    from housing_api.registry import DatasetMeta, safe_processed_path

    (tmp_path / "data" / "processed").mkdir(parents=True)
    meta = DatasetMeta(
        id="evil",
        title="evil",
        family="generic",
        filename="../../outside.parquet",
    )
    assert safe_processed_path(tmp_path, meta) is None


def test_metrics_disabled_404(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_when_enabled(monkeypatch: pytest.MonkeyPatch, tmp_repo: Path, api_key: str) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "1")
    monkeypatch.setenv("HOUSING_API_METRICS_REQUIRE_KEY", "0")
    from housing_api.app import create_app

    c = TestClient(create_app())
    c.get("/health")
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


def test_metrics_require_key_401_without_credentials(monkeypatch: pytest.MonkeyPatch, tmp_repo: Path, api_key: str) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "1")
    monkeypatch.setenv("HOUSING_API_METRICS_REQUIRE_KEY", "1")
    from housing_api.app import create_app

    c = TestClient(create_app())
    r = c.get("/metrics")
    assert r.status_code == 401


def test_metrics_require_key_ok_with_bearer(
    monkeypatch: pytest.MonkeyPatch, tmp_repo: Path, api_key: str
) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "1")
    monkeypatch.setenv("HOUSING_API_METRICS_REQUIRE_KEY", "1")
    from housing_api.app import create_app

    c = TestClient(create_app())
    c.get("/health", headers={"Authorization": f"Bearer {api_key}"})
    r = c.get("/metrics", headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 200
    assert "http_requests_total" in r.text


def test_api_keys_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_path = tmp_path / "keys.txt"
    key_path.write_text("file-based-secret-key\n", encoding="utf-8")
    monkeypatch.delenv("HOUSING_API_KEYS", raising=False)
    monkeypatch.setenv("HOUSING_API_KEYS_FILE", str(key_path))
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "0")
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    pd.DataFrame({"a": [1]}).to_parquet(proc / "ons_housebuilding_la_fye_march2025_tidy.parquet", index=False)
    from housing_api.app import create_app

    c = TestClient(create_app())
    r = c.get(f"{API_PREFIX}/datasets", headers={"Authorization": "Bearer file-based-secret-key"})
    assert r.status_code == 200


def test_production_env_disables_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOUSING_API_ENV", "production")
    monkeypatch.delenv("HOUSING_API_DOCS", raising=False)
    from housing_api import settings

    assert settings.enable_docs() is False
    monkeypatch.setenv("HOUSING_API_DOCS", "1")
    assert settings.enable_docs() is True


def test_generic_large_table_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, api_key: str) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "0")
    monkeypatch.setenv("HOUSING_API_MAX_ROWS_WITHOUT_FILTERS", "2")
    monkeypatch.setenv("HOUSING_API_USE_DUCKDB", "0")
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    pd.DataFrame({"x": range(5)}).to_parquet(proc / "uk_housing_starts_tidy.parquet", index=False)
    from housing_api.app import create_app

    c = TestClient(create_app())
    h = {"Authorization": f"Bearer {api_key}"}
    r = c.get(f"{API_PREFIX}/datasets/uk_housing_starts", headers=h)
    assert r.status_code == 400
    r2 = c.get(f"{API_PREFIX}/datasets/uk_housing_starts?columns=x", headers=h)
    assert r2.status_code == 200
    assert r2.json()["total_rows"] == 5


def test_columns_not_allowed_for_housebuilding_la(client: TestClient) -> None:
    r = client.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025?columns=financial_year",
        headers={"Authorization": "Bearer pytest-api-key-rotated"},
    )
    assert r.status_code == 400


def test_api_keys_secret_id_uses_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    import housing_api.settings as api_settings

    monkeypatch.delenv("HOUSING_API_KEYS", raising=False)
    monkeypatch.delenv("HOUSING_API_KEYS_FILE", raising=False)
    monkeypatch.setenv("HOUSING_API_KEYS_SECRET_ID", "dummy-arn")

    def _fake(sid: str) -> list[str]:
        assert sid == "dummy-arn"
        return ["from-secret"]

    monkeypatch.setattr(api_settings, "_load_keys_from_aws_secret", _fake)
    assert api_settings.api_keys() == ["from-secret"]


def test_export_json_default_limit_respects_cap(monkeypatch: pytest.MonkeyPatch, tmp_repo: Path, api_key: str) -> None:
    monkeypatch.setenv("HOUSING_API_KEYS", api_key)
    monkeypatch.setenv("HOUSING_REPO_ROOT", str(tmp_repo))
    monkeypatch.setenv("HOUSING_API_DOCS", "0")
    monkeypatch.setenv("HOUSING_API_ENABLE_METRICS", "0")
    monkeypatch.setenv("HOUSING_API_MAX_EXPORT_JSON_ROWS", "2")
    from housing_api.app import create_app

    c = TestClient(create_app())
    r = c.get(
        f"{API_PREFIX}/datasets/ons_housebuilding_la_fye_march2025/export?format=json&limit=10",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert r.status_code == 422
