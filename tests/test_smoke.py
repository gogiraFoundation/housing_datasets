"""Lightweight import smoke tests (no Streamlit page execution)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from housing_api.app import create_app
from housing_api.constants import API_PREFIX
from streamlit_io import PROCESSED_DIR, REPO_ROOT, processed_data_directory


def test_streamlit_io_paths() -> None:
    assert processed_data_directory() == (REPO_ROOT / "data" / "processed").resolve()
    assert PROCESSED_DIR == processed_data_directory()


def test_streamlit_io_housing_processed_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    alt = tmp_path / "alt_processed"
    alt.mkdir()
    (alt / "dummy_tidy.parquet").write_bytes(b"not real parquet")
    monkeypatch.setenv("HOUSING_PROCESSED_DIR", str(alt))
    import streamlit_io as sio

    importlib.reload(sio)
    try:
        assert sio.PROCESSED_DIR.resolve() == alt.resolve()
        assert sio.processed_data_directory() == alt.resolve()
    finally:
        monkeypatch.delenv("HOUSING_PROCESSED_DIR", raising=False)
        importlib.reload(sio)


def test_fastapi_app_factory() -> None:
    app = create_app()
    assert app.title == "Housing datasets API"
    paths = {getattr(r, "path", None) for r in app.routes if getattr(r, "path", None)}
    p = API_PREFIX
    assert f"{p}/datasets" in paths
    assert f"{p}/datasets/{{dataset_id}}" in paths
    assert f"{p}/datasets/{{dataset_id}}/export" in paths
    assert f"{p}/datasets/{{dataset_id}}/chart-spec" in paths
