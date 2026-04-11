"""Tests for LA clustering."""

from __future__ import annotations

import pandas as pd

from housing_analytics.clustering import cluster_local_authorities


def test_kmeans_cluster_smoke():
    df = pd.DataFrame(
        {
            "lad_code": ["E01", "E02", "E03", "E04", "E05"],
            "la_name": list("abcde"),
            "region_code": ["R1", "R1", "R2", "R2", "R2"],
            "x1": [1.0, 2.0, 50.0, 51.0, 52.0],
            "x2": [1.0, 1.5, 50.0, 49.0, 51.0],
        }
    )
    res = cluster_local_authorities(df, n_clusters=2, method="kmeans", random_state=0)
    assert len(res.labels) == 5
    assert res.frame["cluster_id"].nunique() == 2
