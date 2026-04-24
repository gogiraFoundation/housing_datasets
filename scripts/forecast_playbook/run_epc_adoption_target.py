#!/usr/bin/env python3
"""Forecast expected annual change in EPC C+ share."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
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

    path = args.processed_dir / "region_housing_market_snapshot.parquet"
    df = pd.read_parquet(path)
    region = canonical_region_name(args.region)
    sub = df[df["region_name"].astype(str).str.strip() == region].copy()
    if "region_supply_completions" in sub.columns and "region_supply_completed" not in sub.columns:
        sub["region_supply_completed"] = sub["region_supply_completions"]
    for c in ("ee_epc_c_plus_pct", "epc_pct_bands_abc", "region_supply_completed"):
        sub[c] = pd.to_numeric(sub.get(c), errors="coerce")
    sub = sub.dropna(subset=["ee_epc_c_plus_pct"]).copy()
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "epc_adoption_trajectory",
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
            stem="epc_adoption",
            predictions=pred,
            metrics={"target": "epc_adoption_trajectory", "region": region, "note": "no_rows_for_region"},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        return
    if len(sub) < 6:
        sub = pd.concat([sub] * (10 // max(len(sub), 1) + 1), ignore_index=True)
    sub["t"] = np.arange(len(sub), dtype=float)
    sub["target_delta"] = sub["ee_epc_c_plus_pct"].diff().fillna(0.0)
    feats = ["t", "epc_pct_bands_abc", "region_supply_completed"]
    X = sub[feats].fillna(sub[feats].median()).to_numpy(dtype=float)
    y = sub["target_delta"].to_numpy(dtype=float)
    cut = min(max(int(len(sub) * 0.8), 1), len(sub) - 1)
    X_tr, X_te = X[:cut], X[cut:]
    y_tr, y_te = y[:cut], y[cut:]
    model = LinearRegression()
    model.fit(X_tr, y_tr)
    pred_te = model.predict(X_te)
    base_te = np.repeat(np.mean(y_tr), len(y_te))
    bt = float(mean_absolute_error(y_te, pred_te)) if len(y_te) else float("nan")
    bl = float(mean_absolute_error(y_te, base_te)) if len(y_te) else float("nan")
    x_last = X[[-1]].copy()
    x_last[0, 0] += 1.0
    point = float(model.predict(x_last)[0])
    spread = float(np.nanstd(y_te - pred_te)) if len(y_te) else float("nan")
    pred = pd.DataFrame(
        [
            {
                "region": region,
                "target": "epc_adoption_trajectory",
                "horizon_years": 1,
                "point_estimate": point,
                "interval_low": point - 1.64 * spread,
                "interval_high": point + 1.64 * spread,
                "probability": np.nan,
                "backtest_metric": "mae",
                "backtest_value": bt,
                "baseline_metric": "mae",
                "baseline_value": bl,
                "caveat": DEFAULT_CAVEAT,
            }
        ]
    )
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="epc_adoption",
        predictions=pred,
        metrics={"target": "epc_adoption_trajectory", "region": region, "mae": bt, "baseline_mae": bl},
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")


if __name__ == "__main__":
    main()
