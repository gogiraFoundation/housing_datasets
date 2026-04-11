"""Rolling-origin backtesting for univariate series."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from housing_analytics.ts_forecast import (
    forecast_model,
    metrics,
    mase,
    rolling_seasonal_naive_predict,
)


def rolling_origin_backtest(
    y: pd.Series,
    *,
    seasonal_period: int,
    min_train: int,
    horizon: int,
    models: tuple[str, ...] = ("seasonal_naive", "ets", "sarimax", "lagged_hgbr"),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Walk forward: train on y[:t], predict next `horizon` steps, record metrics."""
    vals = pd.to_numeric(y, errors="coerce").astype(float).values
    n = len(vals)
    rows: list[dict[str, Any]] = []
    for t in range(min_train, n - horizon + 1):
        y_train = vals[:t]
        y_true = vals[t : t + horizon]
        naive = rolling_seasonal_naive_predict(y_train, seasonal_period=seasonal_period, horizon=horizon)
        for model_name in models:
            pred = forecast_model(
                y_train,
                model_name,
                seasonal_period=seasonal_period,
                horizon=horizon,
            )
            if pred is None or np.any(~np.isfinite(pred)):
                continue
            met = metrics(y_true, pred)
            met["model"] = model_name
            met["origin"] = t
            met["horizon"] = horizon
            met["mase_vs_naive"] = mase(y_true, pred, naive)
            rows.append(met)

    df = pd.DataFrame(rows)
    summary_by_model: list[dict[str, Any]] = []
    if not df.empty:
        summary_by_model = (
            df.groupby("model", as_index=False)[["mae", "rmse", "mape", "mase_vs_naive"]]
            .mean()
            .to_dict(orient="records")
        )
    return df, {"per_window": df, "summary_by_model": summary_by_model}


def write_backtest_report(
    report_path: Path,
    *,
    meta: dict[str, Any],
    windows_df: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows = summary.get("summary_by_model", [])
    best_mae: str | None = None
    if rows:
        sdf = pd.DataFrame(rows)
        if "mae" in sdf.columns and "model" in sdf.columns and sdf["mae"].notna().any():
            best_mae = str(sdf.loc[sdf["mae"].idxmin(), "model"])
    summary_out = {**summary, "best_model_mae": best_mae}
    out = {
        "meta": meta,
        "summary": summary_out,
        "n_windows": int(len(windows_df)),
    }
    report_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    csv_path = report_path.with_suffix(".windows.csv")
    windows_df.to_csv(csv_path, index=False)
