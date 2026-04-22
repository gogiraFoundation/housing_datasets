"""Shared Streamlit data loading: single ``data/processed`` root and cached Parquet reads."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent


def processed_data_directory() -> Path:
    """Directory for tidy Parquet/CSV (default: ``<repo>/data/processed``).

    Set environment variable ``HOUSING_PROCESSED_DIR`` to an absolute path in deployments
    where ``data/processed`` is not in the image (it is gitignored) but artefacts are
    mounted or copied elsewhere.
    """
    raw = os.environ.get("HOUSING_PROCESSED_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (REPO_ROOT / "data" / "processed").resolve()


PROCESSED_DIR = processed_data_directory()


def resolve_processed_data_path(path: str | Path) -> Path:
    """Resolve *path* to a real path strictly under ``data/processed`` (after resolving)."""
    base = PROCESSED_DIR.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = (PROCESSED_DIR / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(base)
    except ValueError as e:
        raise ValueError(f"Refusing to load data outside data/processed: {path!r}") from e
    return p


@st.cache_data
def load_processed_parquet(path: str | Path, *, inputs_snapshot: str | None = None) -> pd.DataFrame:
    """Load a Parquet file under ``data/processed`` (relative or absolute path within that tree).

    ``inputs_snapshot`` is optional metadata included in the cache key so callers can
    invalidate when upstream ETL outputs change (e.g. mtime/size tuples as a string).
    """
    p = resolve_processed_data_path(path)
    _ = inputs_snapshot
    return pd.read_parquet(p)


@st.cache_data
def load_processed_csv(path: str | Path, *, inputs_snapshot: str | None = None) -> pd.DataFrame:
    """Load a CSV under ``data/processed`` (relative or absolute path within that tree)."""
    p = resolve_processed_data_path(path)
    _ = inputs_snapshot
    return pd.read_csv(p)
