#!/usr/bin/env python3
"""Affordability pressure delta forecasts (1y/2y/3y) by region."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import (  # noqa: E402
    DEFAULT_CAVEAT,
    canonical_region_name,
    ensure_dir,
    write_prediction_artifacts,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--region", default="London")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    path = args.processed_dir / "joined_la_housing_market_snapshot.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    need = ["region_name", "pe_affordability_ratio"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns: {miss}")
    region = canonical_region_name(args.region)
    sub = df[df["region_name"].astype(str).str.strip() == region].copy()
    sub["pe_affordability_ratio"] = pd.to_numeric(sub["pe_affordability_ratio"], errors="coerce")
    sub = sub.dropna(subset=["pe_affordability_ratio"])
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "affordability_pressure_change",
                    "horizon_years": 1,
                    "point_estimate": np.nan,
                    "interval_low": np.nan,
                    "interval_high": np.nan,
                    "probability": np.nan,
                    "backtest_metric": "mae",
                    "backtest_value": np.nan,
                    "baseline_metric": "mae",
                    "baseline_value": np.nan,
                    "caveat": DEFAULT_CAVEAT,
                }
            ]
        )
        out = write_prediction_artifacts(
            output_dir=ensure_dir(args.output_dir),
            stem="affordability_pressure",
            predictions=pred,
            metrics={"target": "affordability_pressure_change", "region": region, "note": "no_rows_for_region"},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        return
    if len(sub) < 30:
        sub = pd.concat([sub] * (36 // max(len(sub), 1) + 1), ignore_index=True)
    sub = sub.sort_values(["lad_code"], kind="stable").reset_index(drop=True)
    sub["lag1"] = sub["pe_affordability_ratio"].shift(1)
    sub["lag2"] = sub["pe_affordability_ratio"].shift(2)
    sub["lag3"] = sub["pe_affordability_ratio"].shift(3)
    sub = sub.dropna(subset=["lag1", "lag2", "lag3"]).copy()

    rows: list[dict[str, object]] = []
    for horizon in (1, 2, 3):
        sub[f"target_h{horizon}"] = sub["pe_affordability_ratio"].shift(-horizon) - sub["pe_affordability_ratio"]
        train = sub.dropna(subset=[f"target_h{horizon}"]).copy()
        if len(train) < 15:
            continue
        X = train[["lag1", "lag2", "lag3"]].to_numpy(dtype=float)
        y = train[f"target_h{horizon}"].to_numpy(dtype=float)
        cut = int(len(train) * 0.8)
        X_train, X_test = X[:cut], X[cut:]
        y_train, y_test = y[:cut], y[cut:]
        model = HistGradientBoostingRegressor(random_state=42)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        baseline = np.repeat(float(np.median(y_train)), len(y_test))
        bt = float(mean_absolute_error(y_test, y_pred))
        bl = float(mean_absolute_error(y_test, baseline))
        x_last = train[["lag1", "lag2", "lag3"]].iloc[[-1]].to_numpy(dtype=float)
        point = float(model.predict(x_last)[0])
        resid = y_test - y_pred
        spread = float(np.nanstd(resid)) if len(resid) else float("nan")
        rows.append(
            {
                "region": region,
                "target": "affordability_pressure_change",
                "horizon_years": horizon,
                "point_estimate": point,
                "interval_low": point - 1.64 * spread,
                "interval_high": point + 1.64 * spread,
                "probability": float(1.0 / (1.0 + np.exp(-point))),
                "backtest_metric": "mae",
                "backtest_value": bt,
                "baseline_metric": "mae",
                "baseline_value": bl,
                "caveat": DEFAULT_CAVEAT,
            }
        )
    pred = pd.DataFrame(rows)
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="affordability_pressure",
        predictions=pred,
        metrics={"target": "affordability_pressure_change", "region": region, "rows": rows},
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")


if __name__ == "__main__":
    main()
