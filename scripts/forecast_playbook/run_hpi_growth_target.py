#!/usr/bin/env python3
"""Regional HPI growth forecasts (12m/24m) with backtest comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import (  # noqa: E402
    DEFAULT_CAVEAT,
    baseline_seasonal_naive,
    ensure_dir,
    load_hpi_regions,
    mae,
    quantile_interval,
    scoreboard_row,
    write_prediction_artifacts,
)
from housing_analytics.ts_forecast import forecast_model  # noqa: E402
from housing_analytics.ts_load import load_hpi_series  # noqa: E402


def _pick_model(y_train: np.ndarray, horizon: int, seasonal_period: int) -> tuple[str, float, float]:
    y_eval = y_train[-(horizon + 12) :]
    y_fit = y_train[: -(horizon)] if len(y_train) > horizon else y_train
    if len(y_fit) < 24:
        return "seasonal_naive", float("nan"), float("nan")
    candidates = ("ets", "sarimax", "lagged_hgbr", "autoarima_ets_ensemble")
    best_model = "seasonal_naive"
    best_mae = float("inf")
    baseline = baseline_seasonal_naive(y_fit, horizon=horizon, seasonal_period=seasonal_period)
    baseline_mae = mae(y_eval[-horizon:], baseline)
    for model in candidates:
        pred = forecast_model(y_fit, model, seasonal_period=seasonal_period, horizon=horizon)
        if pred is None:
            continue
        model_mae = mae(y_eval[-horizon:], pred)
        if np.isfinite(model_mae) and model_mae < best_mae:
            best_mae = model_mae
            best_model = model
    return best_model, best_mae, baseline_mae


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--edition", default="march2026")
    p.add_argument("--region", default="London")
    p.add_argument("--horizons", default="12,24")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    regions = load_hpi_regions(args.processed_dir, args.edition)
    region = args.region.strip()
    if region not in regions:
        raise SystemExit(f"Region {region!r} not in HPI file. Known regions: {', '.join(regions)}")

    y, _idx, _meta = load_hpi_series(args.processed_dir, edition=args.edition, geography=region, sheet="1")
    y_arr = y.to_numpy(dtype=float)
    seasonal_period = 12
    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    rows: list[dict[str, object]] = []
    score_rows: list[dict[str, object]] = []
    for h in horizons:
        model, model_mae, baseline_mae = _pick_model(y_arr, h, seasonal_period)
        pred_idx = forecast_model(y_arr, model, seasonal_period=seasonal_period, horizon=h)
        if pred_idx is None:
            continue
        point_growth = float(pred_idx[-1] / y_arr[-1] - 1.0)
        interval_low, interval_high = quantile_interval(pd.Series(pred_idx / y_arr[-1] - 1.0))
        rows.append(
            {
                "region": region,
                "target": "regional_hpi_growth",
                "horizon_months": h,
                "model": model,
                "point_estimate": point_growth,
                "interval_low": interval_low,
                "interval_high": interval_high,
                "probability": np.nan,
                "backtest_metric": "mae",
                "backtest_value": model_mae,
                "baseline_metric": "mae",
                "baseline_value": baseline_mae,
                "caveat": DEFAULT_CAVEAT,
            }
        )
        score_rows.append(
            scoreboard_row(
                region=region,
                target="regional_hpi_growth",
                horizon=h,
                point_estimate=point_growth,
                interval_low=interval_low,
                interval_high=interval_high,
                probability=None,
                backtest_metric="mae",
                backtest_value=model_mae,
                baseline_value=baseline_mae,
            )
        )
    pred_df = pd.DataFrame(rows)
    metrics = {"region": region, "target": "regional_hpi_growth", "rows": rows}
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="hpi_growth",
        predictions=pred_df,
        metrics=metrics,
    )
    scoreboard_path = args.output_dir / "hpi_growth_scoreboard_rows.json"
    scoreboard_path.write_text(json.dumps(score_rows, indent=2), encoding="utf-8")
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")
    print(f"Wrote {scoreboard_path}")


if __name__ == "__main__":
    main()
