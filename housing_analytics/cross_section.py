"""Cross-section LA benchmarking: ElasticNet / LightGBM with region GroupKFold."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TargetName = Literal["median_price_existing_gbp", "pe_affordability_ratio"]

ID_COLUMNS = frozenset(
    {
        "lad_code",
        "la_name",
        "median_la_name",
        "region_name",
        "region_code",
    }
)

# Columns that must not be used as features when predicting a given target (leakage / definitional).
TARGET_BLOCKS: dict[str, frozenset[str]] = {
    "median_price_existing_gbp": frozenset(
        {
            "median_price_existing_gbp",
            "median_price_period_label",
            "median_price_admin_edition",
        }
    ),
    "pe_affordability_ratio": frozenset(
        {
            "pe_affordability_ratio",
            "pe_median_price_gbp",
            "pe_workplace_earnings_gbp",
            "pe_snapshot_year",
            "price_earnings_edition",
        }
    ),
}


def _numeric_feature_columns(df: pd.DataFrame, target: str) -> list[str]:
    block = TARGET_BLOCKS.get(target, frozenset())
    out: list[str] = []
    for c in df.columns:
        if c == target or c in ID_COLUMNS or c in block:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return sorted(out)


@dataclass
class BenchmarkResult:
    cv_scores: pd.DataFrame
    oof_predictions: pd.DataFrame
    feature_importance: pd.DataFrame | None
    model_name: str


def _elasticnet_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", ElasticNet(alpha=0.05, l1_ratio=0.5, random_state=0, max_iter=5000)),
        ]
    )


def _lgbm_regressor():
    """Import LightGBM lazily so importing this module works without OpenMP/libomp (e.g. some macOS setups)."""
    from lightgbm import LGBMRegressor

    return LGBMRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=0,
        verbose=-1,
    )


def run_group_kfold_benchmark(
    df: pd.DataFrame,
    *,
    target: TargetName,
    model: Literal["elastic_net", "lightgbm"],
    n_splits: int = 5,
    log_target: bool = False,
) -> BenchmarkResult:
    """Out-of-fold predictions by region_code; residuals = actual - predicted."""
    if target not in df.columns:
        raise KeyError(f"Missing target column {target!r}")
    feat_cols = _numeric_feature_columns(df, target)
    if not feat_cols:
        raise ValueError("No numeric feature columns after exclusions.")

    sub = df.dropna(subset=[target, "region_code"]).copy()
    sub[target] = pd.to_numeric(sub[target], errors="coerce")
    y_raw = sub[target].values.astype(float)
    if log_target:
        sub = sub[y_raw > 0].copy()
        y_raw = sub[target].values.astype(float)
        y = np.log(y_raw)
    else:
        y = y_raw
    X = sub[feat_cols].apply(pd.to_numeric, errors="coerce")
    groups = sub["region_code"].astype(str).values

    n_groups = int(sub["region_code"].nunique())
    if n_groups < 2:
        raise ValueError("Need at least two distinct region_code values for GroupKFold.")
    n_splits_eff = max(2, min(n_splits, n_groups))
    gkf = GroupKFold(n_splits=n_splits_eff)
    oof = np.full(len(sub), np.nan)
    rows: list[dict[str, Any]] = []

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        Xt, Xv = X.iloc[train_idx], X.iloc[test_idx]
        yt, yv = y[train_idx], y[test_idx]
        if model == "elastic_net":
            pipe = _elasticnet_pipeline()
            pipe.fit(Xt, yt)
            pred = pipe.predict(Xv)
        else:
            imputer = SimpleImputer(strategy="median")
            Xt_i = imputer.fit_transform(Xt)
            Xv_i = imputer.transform(Xv)
            reg = _lgbm_regressor()
            reg.fit(Xt_i, yt)
            pred = reg.predict(Xv_i)
        oof[test_idx] = pred
        rows.append(
            {
                "fold": fold,
                "r2": r2_score(yv, pred),
                "mae": mean_absolute_error(yv, pred),
                "rmse": float(np.sqrt(mean_squared_error(yv, pred))),
                "n_test": len(test_idx),
            }
        )

    cv_df = pd.DataFrame(rows)
    y_hat = np.exp(oof) if log_target else oof
    y_actual = y_raw
    resid = y_actual - y_hat
    la_nm = sub["la_name"].values if "la_name" in sub.columns else sub["lad_code"].values
    rn = sub["region_name"].values if "region_name" in sub.columns else np.array([""] * len(sub))
    out_df = pd.DataFrame(
        {
            "lad_code": sub["lad_code"].values,
            "la_name": la_nm,
            "region_name": rn,
            "region_code": sub["region_code"].values,
            "actual": y_actual,
            "predicted": y_hat,
            "residual": resid,
        }
    )
    out_df["residual_definition"] = "actual_minus_predicted"

    fi: pd.DataFrame | None = None
    if model == "lightgbm":
        imputer = SimpleImputer(strategy="median")
        Xi = imputer.fit_transform(X)
        reg = _lgbm_regressor()
        reg.fit(Xi, y)
        fi = pd.DataFrame({"feature": feat_cols, "importance": reg.feature_importances_}).sort_values(
            "importance", ascending=False
        )

    return BenchmarkResult(cv_scores=cv_df, oof_predictions=out_df, feature_importance=fi, model_name=model)


def load_lane_a_snapshot(processed_dir: Path, stem: str = "joined_la_housing_market_snapshot") -> pd.DataFrame:
    path = Path(processed_dir) / f"{stem}.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def export_residuals(path: Path, result: BenchmarkResult) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.oof_predictions.to_csv(path, index=False)
