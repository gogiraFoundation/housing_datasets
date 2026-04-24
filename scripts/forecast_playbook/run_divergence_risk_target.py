#!/usr/bin/env python3
"""Predict rent-vs-price divergence sign and spread magnitude."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.ensemble import HistGradientBoostingRegressor

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import (  # noqa: E402
    DEFAULT_CAVEAT,
    canonical_region_name,
    ensure_dir,
    write_prediction_artifacts,
)


def _build_spread_series(processed_dir: Path, region: str) -> pd.DataFrame:
    hpi_path = processed_dir / "ons_uk_hpi_monthly_march2026_1_tidy.parquet"
    prpi_path = processed_dir / "ons_private_rental_index_v41_tidy.parquet"
    if not hpi_path.is_file() or not prpi_path.is_file():
        return pd.DataFrame(columns=["period", "spread"])
    hpi = pd.read_parquet(hpi_path)
    hpi["period"] = pd.to_datetime(hpi["time_period"].astype(str), format="%b %Y", errors="coerce")
    hpi["value"] = pd.to_numeric(hpi["value"], errors="coerce")
    hpi["region_name"] = hpi["geography"].map(canonical_region_name)
    hpi = hpi[hpi["region_name"] == region][["period", "value"]].dropna().rename(columns={"value": "hpi_idx"})
    prpi = pd.read_parquet(prpi_path)
    prpi = prpi[prpi["variable"].astype(str) == "index"].copy()
    prpi["period"] = pd.to_datetime(prpi["month_label"].astype(str), format="%b-%y", errors="coerce")
    prpi["value"] = pd.to_numeric(prpi["value"], errors="coerce")
    prpi["region_name"] = prpi["geography_name"].map(canonical_region_name)
    prpi = prpi[prpi["region_name"] == region][["period", "value"]].dropna().rename(columns={"value": "prpi_idx"})
    joined = hpi.merge(prpi, on="period", how="inner").sort_values("period")
    if joined.empty:
        return pd.DataFrame(columns=["period", "spread"])
    joined["hpi_growth"] = joined["hpi_idx"].pct_change(12) * 100.0
    joined["prpi_growth"] = joined["prpi_idx"].pct_change(12) * 100.0
    joined["spread"] = joined["hpi_growth"] - joined["prpi_growth"]
    return joined[["period", "spread"]].dropna()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--region", default="London")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    region = canonical_region_name(args.region.strip())
    sub = _build_spread_series(args.processed_dir, region)
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "rent_vs_price_divergence_risk",
                    "horizon_months": 12,
                    "point_estimate": np.nan,
                    "interval_low": np.nan,
                    "interval_high": np.nan,
                    "probability": np.nan,
                    "backtest_metric": "mae",
                    "backtest_value": np.nan,
                    "baseline_metric": "mae",
                    "baseline_value": np.nan,
                    "classification_metric": "brier",
                    "classification_value": np.nan,
                    "caveat": DEFAULT_CAVEAT,
                }
            ]
        )
        out = write_prediction_artifacts(
            output_dir=ensure_dir(args.output_dir),
            stem="divergence_risk",
            predictions=pred,
            metrics={"target": "rent_vs_price_divergence_risk", "region": region, "note": "no_spread_history"},
            calibration={"brier_score": np.nan},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        print(f"Wrote {out['calibration']}")
        return
    if len(sub) < 24:
        raise SystemExit("Need at least 24 monthly spread rows for divergence target.")
    sub["lag1"] = sub["spread"].shift(1)
    sub["lag2"] = sub["spread"].shift(2)
    sub = sub.dropna(subset=["lag1", "lag2"]).copy()
    sub["target_sign"] = (sub["spread"] > 0).astype(int)
    X = sub[["lag1", "lag2"]].to_numpy(dtype=float)
    y_cls = sub["target_sign"].to_numpy(dtype=int)
    y_reg = sub["spread"].to_numpy(dtype=float)
    cut = max(int(len(sub) * 0.7), 3)
    X_tr, X_te = X[:cut], X[cut:]
    y_cls_tr, y_cls_te = y_cls[:cut], y_cls[cut:]
    y_reg_tr, y_reg_te = y_reg[:cut], y_reg[cut:]

    cls = LogisticRegression(max_iter=400)
    cls.fit(X_tr, y_cls_tr)
    cls_p = cls.predict_proba(X_te)[:, 1]
    reg = HistGradientBoostingRegressor(random_state=42)
    reg.fit(X_tr, y_reg_tr)
    reg_pred = reg.predict(X_te)
    last_x = X[[-1]]
    p_div = float(cls.predict_proba(last_x)[0, 1])
    point = float(reg.predict(last_x)[0])
    spread = float(np.nanstd(y_reg_te - reg_pred)) if len(reg_pred) else float("nan")

    pred = pd.DataFrame(
        [
            {
                "region": region,
                "target": "rent_vs_price_divergence_risk",
                "horizon_months": 12,
                "point_estimate": point,
                "interval_low": point - 1.64 * spread,
                "interval_high": point + 1.64 * spread,
                "probability": p_div,
                "backtest_metric": "mae",
                "backtest_value": float(mean_absolute_error(y_reg_te, reg_pred)) if len(reg_pred) else float("nan"),
                "baseline_metric": "mae",
                "baseline_value": float(mean_absolute_error(y_reg_te, np.repeat(np.mean(y_reg_tr), len(y_reg_te))))
                if len(y_reg_te)
                else float("nan"),
                "classification_metric": "brier",
                "classification_value": float(brier_score_loss(y_cls_te, cls_p)) if len(y_cls_te) else float("nan"),
                "caveat": DEFAULT_CAVEAT,
            }
        ]
    )
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="divergence_risk",
        predictions=pred,
        metrics={"target": "rent_vs_price_divergence_risk", "region": region},
        calibration={"brier_score": float(brier_score_loss(y_cls_te, cls_p)) if len(y_cls_te) else float("nan")},
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")
    print(f"Wrote {out['calibration']}")


if __name__ == "__main__":
    main()
