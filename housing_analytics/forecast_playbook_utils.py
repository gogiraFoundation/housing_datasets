"""Shared utilities for the 10-year regional forecast playbook."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CAVEAT = "Macro shocks and policy regime changes are not explicitly modeled in these forecasts."
DEFAULT_REGION = "London"
REGION_ALIASES = {
    "East": "East of England",
    "Northern Ireland [note 3]": "Northern Ireland",
}


@dataclass(frozen=True)
class HorizonMetric:
    """Container for horizon-specific backtest and baseline comparisons."""

    horizon: int
    metric: str
    model_value: float
    baseline_value: float

    @property
    def delta_vs_baseline(self) -> float:
        return float(self.model_value - self.baseline_value)

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "horizon": self.horizon,
            "metric": self.metric,
            "model_value": self.model_value,
            "baseline_value": self.baseline_value,
            "delta_vs_baseline": self.delta_vs_baseline,
        }


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_float(v: Any, default: float = float("nan")) -> float:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return default
    return out


def load_hpi_regions(processed_dir: Path, edition: str) -> list[str]:
    """Return sorted region geographies from UK HPI sheet 1."""
    path = Path(processed_dir) / f"ons_uk_hpi_monthly_{edition}_1_tidy.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path, columns=["geography"])
    regions = sorted({str(x).strip() for x in df["geography"].dropna().unique() if str(x).strip()})
    return regions


def canonical_region_name(region: str) -> str:
    s = str(region).strip()
    return REGION_ALIASES.get(s, s)


def baseline_drift(y_train: np.ndarray, horizon: int) -> np.ndarray:
    if len(y_train) < 2:
        return np.full(horizon, np.nan)
    slope = y_train[-1] - y_train[-2]
    steps = np.arange(1, horizon + 1, dtype=float)
    return y_train[-1] + slope * steps


def baseline_seasonal_naive(y_train: np.ndarray, horizon: int, seasonal_period: int = 12) -> np.ndarray:
    if len(y_train) < seasonal_period:
        return np.full(horizon, np.nan)
    out = np.empty(horizon, dtype=float)
    for i in range(horizon):
        idx = len(y_train) - seasonal_period + (i % seasonal_period)
        out[i] = y_train[idx] if idx < len(y_train) else y_train[-1]
    return out


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    m = np.isfinite(y_true) & np.isfinite(y_pred)
    if not m.any():
        return float("nan")
    return float(np.mean(np.abs(y_true[m] - y_pred[m])))


def quantile_interval(values: pd.Series, q_low: float = 0.1, q_high: float = 0.9) -> tuple[float, float]:
    s = pd.to_numeric(values, errors="coerce").dropna()
    if s.empty:
        return float("nan"), float("nan")
    return float(s.quantile(q_low)), float(s.quantile(q_high))


def write_prediction_artifacts(
    *,
    output_dir: Path,
    stem: str,
    predictions: pd.DataFrame,
    metrics: dict[str, Any],
    calibration: dict[str, Any] | None = None,
) -> dict[str, Path]:
    ensure_dir(output_dir)
    pred_path = output_dir / f"{stem}_predictions.csv"
    metrics_path = output_dir / f"{stem}_metrics.json"
    predictions.to_csv(pred_path, index=False)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    out = {"predictions": pred_path, "metrics": metrics_path}
    if calibration is not None:
        calibration_path = output_dir / f"{stem}_calibration.json"
        calibration_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
        out["calibration"] = calibration_path
    return out


def scoreboard_row(
    *,
    region: str,
    target: str,
    horizon: int,
    point_estimate: float,
    interval_low: float | None,
    interval_high: float | None,
    probability: float | None,
    backtest_metric: str,
    backtest_value: float,
    baseline_value: float,
    caveat: str = DEFAULT_CAVEAT,
) -> dict[str, Any]:
    return {
        "region": region,
        "target": target,
        "horizon": horizon,
        "point_estimate": point_estimate,
        "interval_low": interval_low,
        "interval_high": interval_high,
        "probability": probability,
        "backtest_metric": backtest_metric,
        "backtest_value": backtest_value,
        "baseline_value": baseline_value,
        "delta_vs_baseline": backtest_value - baseline_value,
        "caveat": caveat,
    }
