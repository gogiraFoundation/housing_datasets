"""Tests for cross-section LA benchmarking."""

from __future__ import annotations

import pandas as pd

from housing_analytics.cross_section import run_group_kfold_benchmark


def test_group_kfold_benchmark_smoke():
    # Enough rows / region groups so GroupKFold train folds are non-degenerate for ElasticNet.
    df = pd.DataFrame(
        {
            "lad_code": ["E01", "E02", "E03", "E04", "E05", "E06"],
            "la_name": ["a", "b", "c", "d", "e", "f"],
            "region_name": ["R1", "R1", "R1", "R2", "R2", "R2"],
            "region_code": ["E100", "E100", "E100", "E200", "E200", "E200"],
            "supply_starts": [10.0, 20.0, 12.0, 15.0, 25.0, 18.0],
            "population": [1000.0, 2000.0, 1500.0, 3000.0, 4000.0, 3500.0],
            "median_price_existing_gbp": [200000.0, 250000.0, 210000.0, 180000.0, 220000.0, 190000.0],
        }
    )
    r = run_group_kfold_benchmark(df, target="median_price_existing_gbp", model="elastic_net", n_splits=2)
    assert len(r.oof_predictions) == 6
    assert "residual" in r.oof_predictions.columns
    assert r.cv_scores["fold"].nunique() >= 1
