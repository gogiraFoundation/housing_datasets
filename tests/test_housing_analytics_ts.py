"""Tests for time-series backtesting (synthetic series)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from housing_analytics.ts_backtest import rolling_origin_backtest, write_backtest_report
from housing_analytics.forward_hpi import end_horizon_pct_change
from housing_analytics.ts_forecast import (
    fit_predict_autoarima_ets_ensemble,
    fit_predict_ets,
    fit_predict_sarimax,
    forecast_model,
    metrics,
    probabilistic_forecast_model,
    rolling_seasonal_naive_predict,
)
from housing_analytics.ts_load import aggregate_hpi_monthly_to_annual


def test_seasonal_naive_and_metrics():
    y = np.arange(48, dtype=float) + np.sin(np.linspace(0, 4 * np.pi, 48)) * 2
    pred = rolling_seasonal_naive_predict(y, seasonal_period=12, horizon=3)
    assert pred.shape == (3,)
    m = metrics(np.array([1.0, 2.0]), np.array([1.5, 2.5]))
    assert m["mae"] == 0.5


def test_seasonal_naive_period_1_is_flat_last_value():
    y = np.arange(10, dtype=float)
    pred = rolling_seasonal_naive_predict(y, seasonal_period=1, horizon=4)
    assert pred.shape == (4,)
    assert np.allclose(pred, float(y[-1]))


def test_aggregate_hpi_monthly_to_annual():
    idx = pd.date_range("2020-01", "2022-12", freq="MS")
    y = pd.Series(np.arange(len(idx), dtype=float), index=idx, name="value")
    last = aggregate_hpi_monthly_to_annual(y, rule="last")
    mean = aggregate_hpi_monthly_to_annual(y, rule="mean")
    assert len(last) == 3
    assert len(mean) == 3
    assert last.iloc[-1] == y.loc["2022-12-01"]
    assert mean.iloc[0] == float(y.loc["2020"].mean())


def test_rolling_backtest_smoke():
    rng = np.random.default_rng(0)
    t = np.arange(60)
    yvals = 100 + 0.5 * t + 10 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 2, size=60)
    s = pd.Series(yvals)
    df, bundle = rolling_origin_backtest(
        s,
        seasonal_period=12,
        min_train=36,
        horizon=2,
        models=("seasonal_naive", "ets", "sarimax", "lagged_hgbr"),
    )
    assert not df.empty
    assert "summary_by_model" in bundle
    assert bundle["summary_by_model"]


def test_ets_sarimax_short_series():
    y = np.linspace(10, 20, 40)
    assert fit_predict_ets(y, seasonal_period=12, horizon=2) is not None
    assert fit_predict_sarimax(y, seasonal_period=12, horizon=2) is not None
    assert fit_predict_autoarima_ets_ensemble(y, seasonal_period=12, horizon=2) is not None


def test_rolling_backtest_annual_frequency_smoke():
    rng = np.random.default_rng(1)
    years = np.arange(40)
    yvals = 100 + 2.0 * years + rng.normal(0, 3, size=40)
    idx = pd.DatetimeIndex([pd.Timestamp(year=1985 + i, month=12, day=31) for i in range(40)])
    s = pd.Series(yvals, index=idx)
    df, bundle = rolling_origin_backtest(
        s,
        seasonal_period=1,
        min_train=15,
        horizon=3,
        models=("seasonal_naive", "ets", "sarimax"),
    )
    assert not df.empty
    assert bundle["summary_by_model"]


def test_forecast_model_dispatch_matches_seasonal_naive():
    y = np.arange(24, dtype=float)
    p = forecast_model(y, "seasonal_naive", seasonal_period=12, horizon=3)
    assert p is not None
    q = rolling_seasonal_naive_predict(y, seasonal_period=12, horizon=3)
    assert np.allclose(p, q)


def test_end_horizon_pct_change_naive():
    # Need len(y) >= seasonal_period + horizon for seasonal naive multi-step.
    y = np.linspace(100.0, 120.0, 20)
    out = end_horizon_pct_change(y, model_name="seasonal_naive", seasonal_period=12, horizon=2)
    assert out["error"] is None
    assert out["last_level"] == float(y[-1])
    assert out["forecast_end"] is not None
    assert out["pct_change"] is not None


def test_write_backtest_report_best_model_mae(tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    win = pd.DataFrame([{"model": "x", "mae": 1.0}])
    summary = {
        "summary_by_model": [
            {"model": "a", "mae": 2.0, "rmse": 3.0, "mape": 1.0, "mase_vs_naive": 0.9},
            {"model": "b", "mae": 1.0, "rmse": 2.0, "mape": 0.5, "mase_vs_naive": 0.8},
        ]
    }
    write_backtest_report(p, meta={"dataset": "test"}, windows_df=win, summary=summary)
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["summary"]["best_model_mae"] == "b"


def test_probabilistic_forecast_has_quantiles():
    y = np.linspace(100.0, 150.0, 48)
    out = probabilistic_forecast_model(y, "ets", seasonal_period=12, horizon=3)
    assert out is not None
    assert out["p10"].shape == (3,)
    assert out["p50"].shape == (3,)
    assert out["p90"].shape == (3,)
    assert np.all(out["p10"] <= out["p50"])
    assert np.all(out["p50"] <= out["p90"])
