"""Cluster local authorities on scaled numeric indicators (Lane A snapshot)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from housing_analytics.cross_section import ID_COLUMNS


def _clustering_feature_columns(df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for c in df.columns:
        if c in ID_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return sorted(out)


@dataclass
class ClusterResult:
    labels: np.ndarray
    lad_codes: np.ndarray
    feature_columns: list[str]
    X_scaled: np.ndarray
    pca_2d: np.ndarray | None
    silhouette: float | None
    method: str
    frame: pd.DataFrame


def cluster_local_authorities(
    df: pd.DataFrame,
    *,
    n_clusters: int = 5,
    method: Literal["kmeans", "agglomerative"] = "kmeans",
    random_state: int = 0,
    pca_components: int | None = 2,
) -> ClusterResult:
    """K-means or Ward hierarchical clustering on imputed median + standardised features."""
    feat = _clustering_feature_columns(df)
    if len(feat) < 2:
        raise ValueError("Need at least two numeric feature columns.")
    sub = df.dropna(subset=["lad_code"]).copy().reset_index(drop=True)
    lad_codes = sub["lad_code"].astype(str).values
    X = sub[feat].apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median")
    Xi = imputer.fit_transform(X)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xi)

    if method == "kmeans":
        km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        labels = km.fit_predict(Xs)
    else:
        agg = AgglomerativeClustering(n_clusters=n_clusters, linkage="ward")
        labels = agg.fit_predict(Xs)

    sil: float | None = None
    if 1 < n_clusters < len(labels):
        try:
            sil = float(silhouette_score(Xs, labels))
        except Exception:
            sil = None

    pca2: np.ndarray | None = None
    if pca_components and pca_components >= 2 and Xs.shape[1] >= 2:
        k = min(pca_components, Xs.shape[1], Xs.shape[0])
        pca = PCA(n_components=k, random_state=random_state)
        pca2 = pca.fit_transform(Xs)[:, :2]

    frame = sub.copy()
    frame["cluster_id"] = labels

    return ClusterResult(
        labels=labels,
        lad_codes=lad_codes,
        feature_columns=feat,
        X_scaled=Xs,
        pca_2d=pca2,
        silhouette=sil,
        method=method,
        frame=frame,
    )


def attach_cluster_labels(df: pd.DataFrame, result: ClusterResult) -> pd.DataFrame:
    """Merge cluster_id onto rows by lad_code (first match if duplicates)."""
    key = df["lad_code"].astype(str).str.strip()
    out = df[key.isin(set(result.lad_codes))].copy()
    lab_map = {str(a): int(b) for a, b in zip(result.lad_codes, result.labels, strict=True)}
    out["cluster_id"] = out["lad_code"].astype(str).str.strip().map(lab_map)
    return out
