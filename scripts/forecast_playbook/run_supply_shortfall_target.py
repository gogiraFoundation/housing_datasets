#!/usr/bin/env python3
"""Predict probability that demand pressure exceeds supply completions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

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
    df = pd.read_parquet(path)
    region = canonical_region_name(args.region)
    sub = df[df["region_name"].astype(str).str.strip() == region].copy()
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "supply_shortfall_likelihood",
                    "horizon_years": 1,
                    "point_estimate": np.nan,
                    "interval_low": np.nan,
                    "interval_high": np.nan,
                    "probability": np.nan,
                    "backtest_metric": "brier",
                    "backtest_value": np.nan,
                    "baseline_metric": "brier",
                    "baseline_value": np.nan,
                    "auc": np.nan,
                    "caveat": DEFAULT_CAVEAT,
                }
            ]
        )
        out = write_prediction_artifacts(
            output_dir=ensure_dir(args.output_dir),
            stem="supply_shortfall",
            predictions=pred,
            metrics={"target": "supply_shortfall_likelihood", "region": region, "note": "no_rows_for_region"},
            calibration={"calibration_method": "sigmoid_cv3", "brier_score": np.nan},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        print(f"Wrote {out['calibration']}")
        return
    feats = ["pe_affordability_ratio", "hpi_annual_pct_change", "supply_completions", "second_home_dwellings_count"]
    for c in feats:
        sub[c] = pd.to_numeric(sub.get(c), errors="coerce")
    sub = sub.dropna(subset=["pe_affordability_ratio", "supply_completions"]).copy()
    if len(sub) < 40:
        sub = pd.concat([sub] * (45 // max(len(sub), 1) + 1), ignore_index=True)
    demand_proxy = sub["pe_affordability_ratio"].fillna(sub["pe_affordability_ratio"].median()) + (
        sub["hpi_annual_pct_change"].fillna(0.0) / 10.0
    )
    sub["target_shortfall"] = (demand_proxy > sub["supply_completions"].fillna(sub["supply_completions"].median())).astype(int)
    X_df = sub[feats].copy()
    med = X_df.median(numeric_only=True).fillna(0.0)
    X = X_df.fillna(med).fillna(0.0).to_numpy(dtype=float)
    y = sub["target_shortfall"].to_numpy(dtype=int)
    cut = int(len(sub) * 0.8)
    X_tr, X_te = X[:cut], X[cut:]
    y_tr, y_te = y[:cut], y[cut:]
    if len(np.unique(y_tr)) > 1:
        base = LogisticRegression(max_iter=500)
        clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)
        clf.fit(X_tr, y_tr)
        p_te = clf.predict_proba(X_te)[:, 1]
        p_last = float(clf.predict_proba(X[[-1]])[0, 1])
        brier = float(brier_score_loss(y_te, p_te)) if len(y_te) else float("nan")
        auc = float(roc_auc_score(y_te, p_te)) if len(np.unique(y_te)) > 1 else float("nan")
    else:
        p_last = float(y_tr[0]) if len(y_tr) else 0.5
        p_te = np.repeat(p_last, len(y_te))
        brier = float(brier_score_loss(y_te, p_te)) if len(y_te) else float("nan")
        auc = float("nan")
    pred = pd.DataFrame(
        [
            {
                "region": region,
                "target": "supply_shortfall_likelihood",
                "horizon_years": 1,
                "point_estimate": p_last,
                "interval_low": max(0.0, p_last - 0.15),
                "interval_high": min(1.0, p_last + 0.15),
                "probability": p_last,
                "backtest_metric": "brier",
                "backtest_value": brier,
                "baseline_metric": "brier",
                "baseline_value": float(brier_score_loss(y_te, np.repeat(y_tr.mean(), len(y_te)))) if len(y_te) else float("nan"),
                "auc": auc,
                "caveat": DEFAULT_CAVEAT,
            }
        ]
    )
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="supply_shortfall",
        predictions=pred,
        metrics={"target": "supply_shortfall_likelihood", "region": region, "auc": auc, "brier": brier},
        calibration={"calibration_method": "sigmoid_cv3", "brier_score": brier},
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")
    print(f"Wrote {out['calibration']}")


if __name__ == "__main__":
    main()
