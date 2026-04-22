"""Contract: when ``processed_manifest.json`` exists, every on-disk registry Parquet is listed."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

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
