"""Tests for ``streamlit_io.resolve_processed_data_path`` (sandbox to ``data/processed``)."""

from __future__ import annotations

from pathlib import Path

import pytest

import streamlit_io as sio


def test_resolve_relative_filename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    monkeypatch.setattr(sio, "PROCESSED_DIR", proc)
    out = sio.resolve_processed_data_path("test.parquet")
    assert out == (proc / "test.parquet").resolve()


def test_resolve_absolute_inside_processed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    target = proc / "a.parquet"
    target.write_bytes(b"")
    monkeypatch.setattr(sio, "PROCESSED_DIR", proc)
    out = sio.resolve_processed_data_path(target)
    assert out == target.resolve()


def test_resolve_rejects_absolute_outside_processed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    secret = tmp_path / "secret.csv"
    secret.write_text("x")
    monkeypatch.setattr(sio, "PROCESSED_DIR", proc)
    with pytest.raises(ValueError, match="outside data/processed"):
        sio.resolve_processed_data_path(secret)


def test_resolve_rejects_parent_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    monkeypatch.setattr(sio, "PROCESSED_DIR", proc)
    with pytest.raises(ValueError, match="outside data/processed"):
        sio.resolve_processed_data_path("../outside.parquet")
