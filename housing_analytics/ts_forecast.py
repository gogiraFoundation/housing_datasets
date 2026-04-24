"""Time-series models with point and probabilistic forecast helpers."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

_CORE_MODEL_NAMES: frozenset[str] = frozenset(
    {"seasonal_naive", "ets", "sarimax", "lagged_hgbr", "autoarima_ets_ensemble"}
)


@contextmanager
def _suppress_statsmodels_fit_warnings() -> Iterator[None]:
    """Rolling backtests hit many short windows; statsmodels is noisy by default."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels.tsa.statespace.sarimax")
        warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels.tsa.holtwinters")
        warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels.base.model")
        yield


def seasonal_naive_forecast(
    y: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray:
    """One-step or multi-step using seasonal lag (same season last year / last quarter)."""
    if seasonal_period < 1:
        return np.full(horizon, np.nan)
    # Non-seasonal baseline: repeat last in-sample value (flat forecast for all horizons).
    if seasonal_period == 1:
        if len(y) < 1:
            return np.full(horizon, np.nan)
        return np.full(horizon, float(y[-1]))
    if len(y) < seasonal_period + horizon:
        return np.full(horizon, np.nan)
    out = np.empty(horizon)
    for h in range(horizon):
        idx = len(y) - seasonal_period + h
        if 0 <= idx < len(y):
            out[h] = y[idx]
        else:
            out[h] = np.nan
    return out


def rolling_seasonal_naive_predict(
    y_train: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray:
    """Predict y[t:t+horizon] using values at t-seasonal_period+h (in-sample style for backtest)."""
    return seasonal_naive_forecast(y_train, seasonal_period=seasonal_period, horizon=horizon)


def fit_predict_ets(
    y_train: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray | None:
    if len(y_train) < 8:
        return None
    try:
        with _suppress_statsmodels_fit_warnings():
            if seasonal_period <= 1:
                model = ExponentialSmoothing(
                    y_train,
                    trend="add",
                    seasonal=None,
                    initialization_method="estimated",
                ).fit(optimized=True)
            elif len(y_train) < seasonal_period * 2 + 2:
                return None
            else:
                model = ExponentialSmoothing(
                    y_train,
                    seasonal_periods=seasonal_period,
                    trend="add",
                    seasonal="add",
                    initialization_method="estimated",
                ).fit(optimized=True)
            fc = model.forecast(horizon)
        return np.asarray(fc, dtype=float)
    except Exception:
        return None


def fit_predict_sarimax(
    y_train: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray | None:
    try:
        with _suppress_statsmodels_fit_warnings():
            if seasonal_period <= 1:
                if len(y_train) < 10:
                    return None
                model = SARIMAX(
                    y_train,
                    order=(1, 1, 1),
                    seasonal_order=(0, 0, 0, 0),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
            else:
                if len(y_train) < seasonal_period * 2 + 5:
                    return None
                model = SARIMAX(
                    y_train,
                    order=(1, 1, 1),
                    seasonal_order=(1, 1, 1, seasonal_period),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
            res = model.fit(disp=False)
            fc = res.get_forecast(steps=horizon)
            return np.asarray(fc.predicted_mean, dtype=float)
    except Exception:
        return None


def fit_predict_autoarima_proxy(
    y_train: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray | None:
    """Small SARIMAX grid search by AIC (AutoARIMA-like fallback-free proxy)."""
    if len(y_train) < 20:
        return None
    if seasonal_period <= 1:
        seasonal_orders = [(0, 0, 0, 0)]
    else:
        seasonal_orders = [(0, 1, 1, seasonal_period), (1, 1, 0, seasonal_period), (1, 1, 1, seasonal_period)]
    orders = [(1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 1)]
    best_aic = float("inf")
    best_res = None
    with _suppress_statsmodels_fit_warnings():
        for order in orders:
            for s_order in seasonal_orders:
                try:
                    model = SARIMAX(
                        y_train,
                        order=order,
                        seasonal_order=s_order,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    res = model.fit(disp=False)
                except Exception:
                    continue
                aic = float(getattr(res, "aic", np.inf))
                if np.isfinite(aic) and aic < best_aic:
                    best_aic = aic
                    best_res = res
    if best_res is None:
        return None
    try:
        fc = best_res.get_forecast(steps=horizon)
        return np.asarray(fc.predicted_mean, dtype=float)
    except Exception:
        return None


def fit_predict_autoarima_ets_ensemble(
    y_train: np.ndarray,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray | None:
    """Blend ETS with an AutoARIMA-like SARIMAX search."""
    p_auto = fit_predict_autoarima_proxy(y_train, seasonal_period=seasonal_period, horizon=horizon)
    p_ets = fit_predict_ets(y_train, seasonal_period=seasonal_period, horizon=horizon)
    good = [p for p in (p_auto, p_ets) if p is not None and len(p) >= horizon and np.all(np.isfinite(p))]
    if not good:
        return None
    if len(good) == 1:
        return good[0]
    return np.mean(np.vstack(good), axis=0)


def _lag_matrix(y: np.ndarray, lags: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Rows are time indices where all lags exist; target is y[t]."""
    max_lag = max(lags)
    rows: list[np.ndarray] = []
    targets: list[float] = []
    for t in range(max_lag, len(y)):
        row = [y[t - lag] for lag in lags]
        rows.append(np.array(row, dtype=float))
        targets.append(float(y[t]))
    if not rows:
        return np.empty((0, len(lags))), np.empty(0)
    return np.stack(rows, axis=0), np.array(targets, dtype=float)


def fit_predict_lagged_hgbr(
    y_train: np.ndarray,
    *,
    horizon: int,
    lags: list[int] | None = None,
) -> np.ndarray | None:
    """Direct multi-step: train on lags, recursive forecast for h steps."""
    if lags is None:
        lags = [1, 2, 3, 12] if len(y_train) > 14 else [1, 2, 3]
    max_lag = max(lags)
    if len(y_train) <= max_lag + 5:
        return None
    X, y_t = _lag_matrix(y_train, lags)
    if len(y_t) < 10:
        return None
    imputer = SimpleImputer(strategy="median")
    X_i = imputer.fit_transform(X)
    reg = HistGradientBoostingRegressor(max_depth=5, random_state=0)
    reg.fit(X_i, y_t)

    out = np.empty(horizon)
    buf = list(y_train.tolist())
    for h in range(horizon):
        x_row = np.array([[buf[-lag] for lag in lags]], dtype=float)
        x_row = imputer.transform(x_row)
        pred = float(reg.predict(x_row)[0])
        out[h] = pred
        buf.append(pred)
    return out


def forecast_model(
    y_train: np.ndarray,
    model_name: str,
    *,
    seasonal_period: int,
    horizon: int,
) -> np.ndarray | None:
    """Dispatch to supported point forecasters (same as rolling backtests)."""
    if model_name == "seasonal_naive":
        return rolling_seasonal_naive_predict(y_train, seasonal_period=seasonal_period, horizon=horizon)
    if model_name == "ets":
        return fit_predict_ets(y_train, seasonal_period=seasonal_period, horizon=horizon)
    if model_name == "sarimax":
        return fit_predict_sarimax(y_train, seasonal_period=seasonal_period, horizon=horizon)
    if model_name == "lagged_hgbr":
        return fit_predict_lagged_hgbr(y_train, horizon=horizon)
    if model_name == "autoarima_ets_ensemble":
        return fit_predict_autoarima_ets_ensemble(y_train, seasonal_period=seasonal_period, horizon=horizon)
    raise ValueError(f"Unknown model {model_name!r}")


def _residual_scale(y_train: np.ndarray, *, seasonal_period: int) -> float | None:
    """Simple residual scale proxy from seasonal differences."""
    y_train = np.asarray(y_train, dtype=float)
    y_train = y_train[np.isfinite(y_train)]
    if len(y_train) < 6:
        return None
    if seasonal_period > 1 and len(y_train) > seasonal_period:
        d = y_train[seasonal_period:] - y_train[:-seasonal_period]
    else:
        d = np.diff(y_train)
    d = d[np.isfinite(d)]
    if len(d) < 3:
        return None
    s = float(np.nanstd(d))
    if not np.isfinite(s) or s <= 1e-12:
        return None
    return s


def probabilistic_forecast_model(
    y_train: np.ndarray,
    model_name: str,
    *,
    seasonal_period: int,
    horizon: int,
) -> dict[str, np.ndarray] | None:
    """Return point and quantile trajectories (P10/P50/P90 + 95% interval)."""
    point = forecast_model(y_train, model_name, seasonal_period=seasonal_period, horizon=horizon)
    if point is None or len(point) < horizon:
        return None
    point = np.asarray(point, dtype=float)
    if not np.all(np.isfinite(point)):
        return None
    scale = _residual_scale(np.asarray(y_train, dtype=float), seasonal_period=seasonal_period)
    if scale is None:
        scale = max(float(np.nanstd(np.asarray(y_train, dtype=float))), 1e-6)
    steps = np.arange(1, horizon + 1, dtype=float)
    sigma_h = scale * np.sqrt(steps)
    z10 = 1.2815515655446004
    z95 = 1.959963984540054
    p50 = point
    p10 = p50 - z10 * sigma_h
    p90 = p50 + z10 * sigma_h
    lower = p50 - z95 * sigma_h
    upper = p50 + z95 * sigma_h
    return {"point": point, "p10": p10, "p50": p50, "p90": p90, "lower": lower, "upper": upper}


def pinball_loss(y_true: np.ndarray, y_q: np.ndarray, q: float) -> float:
    m = np.isfinite(y_true) & np.isfinite(y_q)
    if not m.any():
        return float("nan")
    yt = y_true[m]
    yhat = y_q[m]
    diff = yt - yhat
    return float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """MAE, RMSE, MAPE (ignore pairs with nan)."""
    m = np.isfinite(y_true) & np.isfinite(y_pred)
    if not m.any():
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan")}
    yt = y_true[m]
    yp = y_pred[m]
    err = yp - yt
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    denom = np.where(np.abs(yt) < 1e-9, np.nan, yt)
    mape = float(np.nanmean(np.abs((yp - yt) / denom)) * 100.0)
    return {"mae": mae, "rmse": rmse, "mape": mape}


def mase(y_true: np.ndarray, y_pred: np.ndarray, y_naive: np.ndarray) -> float:
    """Mean absolute scaled error vs naive benchmark."""
    m = np.isfinite(y_true) & np.isfinite(y_pred) & np.isfinite(y_naive)
    if not m.any():
        return float("nan")
    return float(np.mean(np.abs(y_true[m] - y_pred[m])) / max(np.mean(np.abs(y_true[m] - y_naive[m])), 1e-12))
