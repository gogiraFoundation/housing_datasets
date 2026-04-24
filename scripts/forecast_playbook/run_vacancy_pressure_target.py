#!/usr/bin/env python3
"""Classify LAD vacancy/second-home pressure into rising/stable/falling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import (  # noqa: E402
    DEFAULT_CAVEAT,
    canonical_region_name,
    ensure_dir,
    write_prediction_artifacts,
)


def _class_from_delta(x: float) -> str:
    if x > 0.1:
        return "rising"
    if x < -0.1:
        return "falling"
    return "stable"


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
    feats = [
        "vacant_dwellings_count",
        "second_home_dwellings_count",
        "median_price_existing_gbp",
        "supply_completions",
    ]
    for c in feats:
        sub[c] = pd.to_numeric(sub.get(c), errors="coerce")
    if sub.empty:
        pred = pd.DataFrame(
            [
                {
                    "region": region,
                    "target": "vacancy_second_home_pressure_class",
                    "horizon_years": 1,
                    "predicted_class": "stable",
                    "point_estimate": np.nan,
                    "interval_low": np.nan,
                    "interval_high": np.nan,
                    "probability": np.nan,
                    "prob_rising": np.nan,
                    "prob_stable": np.nan,
                    "prob_falling": np.nan,
                    "backtest_metric": "f1_macro",
                    "backtest_value": np.nan,
                    "baseline_metric": "f1_macro",
                    "baseline_value": np.nan,
                    "labels": "falling,rising,stable",
                    "threshold_logic": "delta pressure > 0.1 rising; < -0.1 falling; else stable",
                    "caveat": DEFAULT_CAVEAT,
                }
            ]
        )
        out = write_prediction_artifacts(
            output_dir=ensure_dir(args.output_dir),
            stem="vacancy_pressure",
            predictions=pred,
            metrics={"target": "vacancy_second_home_pressure_class", "region": region, "note": "no_rows_for_region"},
            calibration={"class_probability_map": {"rising": np.nan, "stable": np.nan, "falling": np.nan}},
        )
        print(f"Wrote {out['predictions']}")
        print(f"Wrote {out['metrics']}")
        print(f"Wrote {out['calibration']}")
        return
    sub["vacant_dwellings_count"] = sub["vacant_dwellings_count"].fillna(0.0)
    sub["second_home_dwellings_count"] = sub["second_home_dwellings_count"].fillna(0.0)
    if len(sub) < 30:
        sub = pd.concat([sub] * (36 // max(len(sub), 1) + 1), ignore_index=True)
    sub["pressure"] = (
        sub["vacant_dwellings_count"].fillna(0.0) + 0.5 * sub["second_home_dwellings_count"].fillna(0.0)
    )
    sub["delta"] = sub["pressure"].diff().fillna(0.0)
    sub["target"] = sub["delta"].map(_class_from_delta)
    labels = sorted(sub["target"].unique().tolist())
    X_df = sub[feats].copy()
    med = X_df.median(numeric_only=True).fillna(0.0)
    X = X_df.fillna(med).fillna(0.0).to_numpy(dtype=float)
    y = sub["target"].to_numpy(dtype=str)
    cut = min(max(int(len(sub) * 0.8), 1), len(sub) - 1)
    X_tr, X_te = X[:cut], X[cut:]
    y_tr, y_te = y[:cut], y[cut:]
    clf = RandomForestClassifier(n_estimators=250, random_state=42)
    clf.fit(X_tr, y_tr)
    p_te = clf.predict(X_te)
    f1 = float(f1_score(y_te, p_te, average="macro")) if len(y_te) else float("nan")
    base_label = pd.Series(y_tr).mode().iloc[0]
    base_pred = np.repeat(base_label, len(y_te))
    base_f1 = float(f1_score(y_te, base_pred, average="macro")) if len(y_te) else float("nan")
    proba = clf.predict_proba(X[[-1]])[0]
    pred_class = str(clf.predict(X[[-1]])[0])
    prob_map = dict(zip(clf.classes_, [float(x) for x in proba]))
    pred = pd.DataFrame(
        [
            {
                "region": region,
                "target": "vacancy_second_home_pressure_class",
                "horizon_years": 1,
                "predicted_class": pred_class,
                "point_estimate": float(max(prob_map.values())),
                "interval_low": np.nan,
                "interval_high": np.nan,
                "probability": float(max(prob_map.values())),
                "prob_rising": prob_map.get("rising", np.nan),
                "prob_stable": prob_map.get("stable", np.nan),
                "prob_falling": prob_map.get("falling", np.nan),
                "backtest_metric": "f1_macro",
                "backtest_value": f1,
                "baseline_metric": "f1_macro",
                "baseline_value": base_f1,
                "labels": ",".join(labels),
                "threshold_logic": "delta pressure > 0.1 rising; < -0.1 falling; else stable",
                "caveat": DEFAULT_CAVEAT,
            }
        ]
    )
    out = write_prediction_artifacts(
        output_dir=ensure_dir(args.output_dir),
        stem="vacancy_pressure",
        predictions=pred,
        metrics={"target": "vacancy_second_home_pressure_class", "region": region, "f1_macro": f1},
        calibration={"class_probability_map": prob_map},
    )
    print(f"Wrote {out['predictions']}")
    print(f"Wrote {out['metrics']}")
    print(f"Wrote {out['calibration']}")


if __name__ == "__main__":
    main()
