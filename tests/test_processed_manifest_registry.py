"""Contract: when ``processed_manifest.json`` exists, every on-disk registry Parquet is listed."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from housing_api.data_access import load_manifest
from housing_api.registry import REGISTRY, safe_processed_path


def test_manifest_lists_registry_parquet_when_present(tmp_path: Path) -> None:
    proc = tmp_path / "data" / "processed"
    proc.mkdir(parents=True)
    meta = REGISTRY["uk_housing_starts"]
    p = safe_processed_path(tmp_path, meta)
    assert p is not None
    pd.DataFrame({"financial_year": ["2010-2011"], "dwellings": [1.0]}).to_parquet(p, index=False)
    rel = str(p.relative_to(tmp_path))
    (proc / "processed_manifest.json").write_text(
        json.dumps({"processed_parquet": [{"path": rel, "num_rows": 1}]}),
        encoding="utf-8",
    )
    man = load_manifest(tmp_path)
    assert man is not None
    paths = {row["path"] for row in man.get("processed_parquet", [])}
    assert rel in paths


def test_load_manifest_respects_housing_processed_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ext = tmp_path / "external_processed"
    ext.mkdir()
    payload = {"processed_parquet": []}
    (ext / "processed_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("HOUSING_PROCESSED_DIR", str(ext))
    try:
        repo = tmp_path / "fake_repo"
        assert load_manifest(repo) == payload
    finally:
        monkeypatch.delenv("HOUSING_PROCESSED_DIR", raising=False)


def test_safe_processed_path_respects_housing_processed_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ext = tmp_path / "external_processed"
    ext.mkdir()
    meta = REGISTRY["uk_housing_starts"]
    target = ext / meta.filename
    target.write_bytes(b"x")
    monkeypatch.setenv("HOUSING_PROCESSED_DIR", str(ext))
    try:
        repo = tmp_path / "fake_repo"
        assert safe_processed_path(repo, meta) == target.resolve()
    finally:
        monkeypatch.delenv("HOUSING_PROCESSED_DIR", raising=False)
