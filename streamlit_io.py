"""Shared Streamlit data loading: single ``data/processed`` root and cached Parquet reads."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

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


def _is_deployment_env() -> bool:
    return any(
        bool(os.environ.get(name))
        for name in ("DEPLOYMENT", "RENDER", "RAILWAY_ENVIRONMENT", "STREAMLIT_SHARING_MODE")
    )


def _count_processed_data_files(processed_dir: Path) -> int:
    if not processed_dir.is_dir():
        return 0
    parquet = list(processed_dir.glob("*.parquet"))
    csv = list(processed_dir.glob("*.csv"))
    return len(parquet) + len(csv)


def _run_command(cmd: list[str]) -> tuple[bool, str | None]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    return False, stderr or stdout or f"exit code {proc.returncode}"


def _deploy_bootstrap_processed_data(processed_dir: Path) -> None:
    """Best-effort deployment bootstrap for empty processed data directories."""
    if not _is_deployment_env():
        return
    if _count_processed_data_files(processed_dir) > 0:
        return
    if os.environ.get("HOUSING_SKIP_DEPLOY_BOOTSTRAP", "0") == "1":
        return

    py = sys.executable or "python3"
    run_suite = REPO_ROOT / "scripts" / "run_etl_suite.py"
    la_starts = REPO_ROOT / "uk_local_authority_housing_data.py"

    if run_suite.is_file():
        ok, detail = _run_command([py, str(run_suite), "--profile", os.environ.get("ETL_PROFILE", "standard")])
        if ok and _count_processed_data_files(processed_dir) > 0:
            return
        if detail:
            print(f"[streamlit_io] deploy bootstrap: run_etl_suite failed: {detail}")

    if la_starts.is_file():
        ok, detail = _run_command([py, str(la_starts)])
        if ok and _count_processed_data_files(processed_dir) > 0:
            return
        if detail:
            print(f"[streamlit_io] deploy bootstrap: la_starts pipeline failed: {detail}")


PROCESSED_DIR = processed_data_directory()
_deploy_bootstrap_processed_data(PROCESSED_DIR)


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
