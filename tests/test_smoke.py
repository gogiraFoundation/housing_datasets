"""Lightweight import smoke tests (no Streamlit page execution)."""

from __future__ import annotations

from housing_api.app import create_app
from housing_api.constants import API_PREFIX
from streamlit_io import PROCESSED_DIR, REPO_ROOT


def test_streamlit_io_paths() -> None:
    assert PROCESSED_DIR == REPO_ROOT / "data" / "processed"


def test_fastapi_app_factory() -> None:
    app = create_app()
    assert app.title == "Housing datasets API"
    paths = {getattr(r, "path", None) for r in app.routes if getattr(r, "path", None)}
    p = API_PREFIX
    assert f"{p}/datasets" in paths
    assert f"{p}/datasets/{{dataset_id}}" in paths
    assert f"{p}/datasets/{{dataset_id}}/export" in paths
    assert f"{p}/datasets/{{dataset_id}}/chart-spec" in paths
