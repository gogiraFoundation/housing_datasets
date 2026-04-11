"""Forward one-shot HPI forecasts from full history (index or price series)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from housing_analytics.ts_forecast import forecast_model
from housing_analytics.ts_load import infer_seasonal_period, load_hpi_series, load_hpi_series_annual

# Labels must match `ons_uk_hpi_monthly_*_1_tidy.parquet` geography column (sheet 1).
SHEET1_GEOGRAPHIES: tuple[str, ...] = (
    "United Kingdom",
    "Great Britain",
    "England",
    "Wales",
    "Scotland",
    "Northern Ireland [note 3]",
    "East",
    "East Midlands",
    "London",
    "North East",
    "North West",
    "South East",
    "South West",
    "West Midlands",
    "Yorkshire and The Humber",
)

MODEL_NAMES: frozenset[str] = frozenset({"seasonal_naive", "ets", "sarimax", "lagged_hgbr"})


def best_models_from_ts_backtest_json(
    processed_dir: Path,
    *,
    edition: str,
    sheet: str,
    frequency: Literal["monthly", "annual"],
    annual_rule: str,
    horizon: int,
    geographies: list[str],
) -> list[str]:
    """Collect ``best_model_mae`` from ``ts_backtest_*.json`` reports that match scope.

    Returns a sorted list of distinct model names (one entry if every geography agrees).
    Returns ``[]`` if no matching file or no ``best_model_mae`` for any selected geography.
    """
    processed_dir = Path(processed_dir)
    expected_ds = "uk_hpi_monthly" if frequency == "monthly" else "uk_hpi_annual"
    want = {str(g).strip() for g in geographies}
    by_geo: dict[str, str] = {}

    for path in sorted(processed_dir.glob("ts_backtest_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        meta = doc.get("meta") or {}
        if meta.get("dataset") != expected_ds:
            continue
        if str(meta.get("edition", "")).strip() != str(edition).strip():
            continue
        meta_sheet = str(meta.get("sheet", "1")).strip()
        if meta_sheet != str(sheet).strip():
            continue
        geo = str(meta.get("geography", "")).strip()
        if geo not in want:
            continue
        h_meta = meta.get("horizon")
        if h_meta is None:
            continue
        try:
            if float(h_meta) != float(horizon):
                continue
        except (TypeError, ValueError):
            continue
        if frequency == "annual":
            if str(meta.get("annual_rule", "last")).strip() != str(annual_rule).strip():
                continue
        summ = doc.get("summary") or {}
        best = summ.get("best_model_mae")
        if not best or str(best) not in MODEL_NAMES:
            continue
        by_geo[geo] = str(best)

    if not by_geo:
        return []
    models = [by_geo[g] for g in geographies if g in by_geo]
    if not models:
        return []
    return sorted(set(models))


def end_horizon_pct_change(
    y: np.ndarray,
    *,
    model_name: str,
    seasonal_period: int,
    horizon: int,
) -> dict[str, Any]:
    """Train on full ``y``; return last level, forecast at end of horizon, and % change vs last."""
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return {"last_level": None, "forecast_end": None, "pct_change": None, "error": "empty_series"}
    last = float(y[-1])
    if not np.isfinite(last) or abs(last) < 1e-12:
        return {"last_level": last, "forecast_end": None, "pct_change": None, "error": "invalid_last_level"}
    pred = forecast_model(y, model_name, seasonal_period=seasonal_period, horizon=horizon)
    if pred is None or len(pred) < horizon:
        return {"last_level": last, "forecast_end": None, "pct_change": None, "error": "forecast_failed"}
    fe = float(pred[horizon - 1])
    if not np.isfinite(fe):
        return {"last_level": last, "forecast_end": None, "pct_change": None, "error": "forecast_failed"}
    pct = (fe / last - 1.0) * 100.0
    return {"last_level": last, "forecast_end": fe, "pct_change": float(pct), "error": None}


def forward_forecast_hpi_levels(
    processed_dir: Path,
    *,
    edition: str,
    sheet: str,
    geography: str,
    frequency: Literal["monthly", "annual"] = "monthly",
    annual_rule: str = "last",
    model_name: str,
    horizon: int,
) -> dict[str, Any]:
    """Load one HPI series, fit on full history, forecast ``horizon`` steps, return levels and % change."""
    processed_dir = Path(processed_dir)
    if frequency == "annual":
        y, _idx, meta = load_hpi_series_annual(
            processed_dir,
            edition=edition,
            sheet=sheet,
            geography=geography,
            annual_rule=annual_rule,
        )
    else:
        y, _idx, meta = load_hpi_series(
            processed_dir,
            edition=edition,
            sheet=sheet,
            geography=geography,
        )
    vals = pd.to_numeric(y, errors="coerce").astype(float).values
    sp = infer_seasonal_period(meta)
    out = end_horizon_pct_change(
        vals,
        model_name=model_name,
        seasonal_period=sp,
        horizon=horizon,
    )
    row = {**meta, **out, "n_obs": int(len(vals))}
    return row
