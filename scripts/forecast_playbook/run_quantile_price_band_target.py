#!/usr/bin/env python3
"""LA median existing-price quantile forecasts (P10/P50/P90)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_pinball_loss

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import (  # noqa: E402
    DEFAULT_CAVEAT,
    canonical_region_name,
    ensure_dir,
    write_prediction_artifacts,
)


def _fit_quantile(X: np.ndarray, y: np.ndarray, quantile: float) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(loss="quantile", alpha=quantile, random_state=42)
    model.fit(X, y)
    return model


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--region", default="London")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    path = args.processed_dir / "joined_la_housing_market_snapshot.parquet"
    df = pd.read_parquet(path)
    region = canonical_region_name(args.region)
    sub = df[df["region_name"].astype(str).str.strip() == region].copy()
    for c in ("median_price_existing_gbp", "hpi_avg_price_gbp"):
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna(subset=["median_price_existing_gbp"]).copy()
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "la_median_price_level_band",
                    "horizon_years": 1,
                    "p10": np.nan,
                    "p50": np.nan,
                    "p90": np.nan,
                    "point_estimate": np.nan,
                    "interval_low": np.nan,
                    "interval_high": np.nan,
                    "probability": np.nan,
                    "backtest_metric": "pinball_p50",
                    "backtest_value": np.nan,
                    "baseline_metric": "pinball_p50",
                    "baseline_value": np.nan,
                    "caveat": DEFAULT_CAVEAT,
                }
            ]
        )
        out = write_prediction_artifacts(
            output_dir=ensure_dir(args.output_dir),
            stem="quantile_price_band",
            predictions=pred,
            metrics={"target": "la_median_price_level_band", "region": region, "note": "no_rows_for_region"},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        return
    sub["lag1"] = sub["median_price_existing_gbp"].shift(1)
    sub["lag2"] = sub["median_price_existing_gbp"].shift(2)
    sub["hpi_proxy"] = sub["hpi_avg_price_gbp"].fillna(sub["median_price_existing_gbp"])
    sub = sub.dropna(subset=["lag1", "lag2", "hpi_proxy"]).copy()
    if len(sub) < 20:
        sub = pd.concat([sub] * (24 // max(len(sub), 1) + 1), ignore_index=True)

    X = sub[["lag1", "lag2", "hpi_proxy"]].to_numpy(dtype=float)
    y = sub["median_price_existing_gbp"].to_numpy(dtype=float)
    cut = min(max(int(len(sub) * 0.8), 1), len(sub) - 1)
    X_train, X_test = X[:cut], X[cut:]
    y_train, y_test = y[:cut], y[cut:]

    m10 = _fit_quantile(X_train, y_train, 0.1)
    m50 = _fit_quantile(X_train, y_train, 0.5)
    m90 = _fit_quantile(X_train, y_train, 0.9)
    p10 = m10.predict(X_test)
    p50 = m50.predict(X_test)
    p90 = m90.predict(X_test)
    last_X = X[[-1]]
    row = {
        "region": region,
        "target": "la_median_price_level_band",
        "horizon_years": 1,
        "p10": float(m10.predict(last_X)[0]),
        "p50": float(m50.predict(last_X)[0]),
        "p90": float(m90.predict(last_X)[0]),
        "point_estimate": float(m50.predict(last_X)[0]),
        "interval_low": float(m10.predict(last_X)[0]),
        "interval_high": float(m90.predict(last_X)[0]),
        "probability": np.nan,
        "backtest_metric": "pinball_p50",
        "backtest_value": float(mean_pinball_loss(y_test, p50, alpha=0.5)),
        "baseline_metric": "pinball_p50",
        "baseline_value": float(mean_pinball_loss(y_test, np.repeat(np.median(y_train), len(y_test)), alpha=0.5)),
        "caveat": DEFAULT_CAVEAT,
    }
    pred = pd.DataFrame([row])
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="quantile_price_band",
        predictions=pred,
        metrics={
            "target": "la_median_price_level_band",
            "region": region,
            "pinball_p10": float(mean_pinball_loss(y_test, p10, alpha=0.1)),
            "pinball_p50": row["backtest_value"],
            "pinball_p90": float(mean_pinball_loss(y_test, p90, alpha=0.9)),
        },
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")


if __name__ == "__main__":
    main()
