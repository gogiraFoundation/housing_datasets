"""Driver-based scenario forecasts for LA/region growth targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer


def _safe_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        else:
            out[c] = np.nan
    return out


def _build_feature_table(base: pd.DataFrame) -> tuple[pd.DataFrame, list[str], str]:
    # Schema aliases to tolerate existing snapshot naming.
    aliases = {
        "region_supply_completions": "region_supply_completed",
        "region_supply_starts": "region_supply_started",
    }
    for src, dst in aliases.items():
        if src in base.columns and dst not in base.columns:
            base[dst] = base[src]
    if "lad_code" in base.columns:
        geo_col = "lad_code"
        target = "hpi_annual_pct_change" if "hpi_annual_pct_change" in base.columns else "hpi_minus_prpi_growth_pp"
        feature_cols = [
            "supply_completions",
            "supply_starts",
            "vacant_dwellings_count",
            "second_home_dwellings_count",
            "pe_affordability_ratio",
            "hpi_avg_price_gbp",
            "median_price_existing_gbp",
        ]
    else:
        geo_col = "region_code"
        target = "hpi_growth_overlap_pct"
        feature_cols = [
            "region_supply_completed",
            "region_supply_started",
            "epc_pct_bands_abc",
            "ee_epc_c_plus_pct",
            "hpi_minus_prpi_growth_pp",
            "region_population_census2021",
        ]
    base = _safe_num(base, feature_cols + [target])
    # Lagged growth proxy in snapshot data.
    base["lagged_growth"] = base[target]
    feature_cols = feature_cols + ["lagged_growth"]
    return base, feature_cols, geo_col


def _pick_target_with_fallback(train: pd.DataFrame) -> tuple[pd.Series, str, bool]:
    """Return y, target metric name, and whether it is a proxy score."""
    for cand in ("hpi_growth_overlap_pct", "hpi_annual_pct_change", "hpi_minus_prpi_growth_pp", "lagged_growth"):
        if cand in train.columns:
            y = pd.to_numeric(train[cand], errors="coerce")
            if y.notna().sum() >= 3:
                return y, cand, False
    # Proxy fallback: blend normalized drivers when growth targets are unavailable.
    proxy_cols = [
        c
        for c in (
            "region_supply_completed",
            "region_supply_started",
            "epc_pct_bands_abc",
            "ee_epc_c_plus_pct",
            "region_population_census2021",
            "supply_completions",
            "supply_starts",
            "vacant_dwellings_count",
            "second_home_dwellings_count",
            "pe_affordability_ratio",
        )
        if c in train.columns
    ]
    parts: list[pd.Series] = []
    for c in proxy_cols:
        s = pd.to_numeric(train[c], errors="coerce")
        if s.notna().sum() < 3:
            continue
        mu = float(s.mean())
        sd = float(s.std(ddof=0))
        if not np.isfinite(sd) or sd <= 1e-12:
            continue
        z = (s - mu) / sd
        if c in {"vacant_dwellings_count", "second_home_dwellings_count", "pe_affordability_ratio"}:
            z = -z
        parts.append(z)
    if not parts:
        return pd.Series(np.nan, index=train.index, dtype=float), "proxy_score_unavailable", True
    y_proxy = pd.concat(parts, axis=1).mean(axis=1)
    return y_proxy, "proxy_driver_score", True


def scenario_forecast_growth(
    processed_dir: Path,
    *,
    level: Literal["la", "region"] = "region",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return baseline/low/high growth scenarios from driver-sensitive model."""
    processed_dir = Path(processed_dir)
    path = (
        processed_dir / "joined_la_housing_market_snapshot.parquet"
        if level == "la"
        else processed_dir / "region_housing_market_snapshot.parquet"
    )
    if not path.is_file():
        return pd.DataFrame(), {"target_metric": None, "target_is_proxy": None, "reason": "missing_snapshot"}
    base = pd.read_parquet(path)
    if base.empty:
        return pd.DataFrame(), {"target_metric": None, "target_is_proxy": None, "reason": "empty_snapshot"}
    base, feature_cols, geo_col = _build_feature_table(base)
    train = base.dropna(subset=[geo_col]).copy()
    if train.empty:
        return pd.DataFrame(), {"target_metric": None, "target_is_proxy": None, "reason": "no_geo_rows"}
    y, target_metric, target_is_proxy = _pick_target_with_fallback(train)
    X = train[feature_cols].copy()
    keep_cols = [c for c in X.columns if X[c].notna().any()]
    if not keep_cols:
        return pd.DataFrame(), {
            "target_metric": target_metric,
            "target_is_proxy": target_is_proxy,
            "reason": "no_driver_columns",
        }
    X = X[keep_cols]
    low = X.copy()
    high = X.copy()
    y_med = float(np.nanmedian(y)) if y.notna().any() else float("nan")
    if not np.isfinite(y_med):
        return pd.DataFrame(), {
            "target_metric": target_metric,
            "target_is_proxy": target_is_proxy,
            "reason": "target_all_nan",
        }
    y_fit = y.fillna(y_med)
    imp = SimpleImputer(strategy="median")
    X_i = imp.fit_transform(X)
    model = HistGradientBoostingRegressor(max_depth=4, random_state=0)
    model.fit(X_i, y_fit)
    x_base = imp.transform(X)
    pred_base = model.predict(x_base)
    # Low/high scenarios perturb supply and affordability-sensitive features.
    for c in low.columns:
        lc = c.lower()
        if "supply" in lc or "ee_" in lc or "epc_" in lc:
            low[c] = low[c] * 0.90
            high[c] = high[c] * 1.10
        if "affordability" in lc or "vacant" in lc or "second_home" in lc:
            low[c] = low[c] * 1.10
            high[c] = high[c] * 0.90
    pred_low = model.predict(imp.transform(low))
    pred_high = model.predict(imp.transform(high))
    out = pd.DataFrame(
        {
            "geography": train[geo_col].astype(str),
            "scenario_baseline_growth": pred_base.astype(float),
            "scenario_low_growth": pred_low.astype(float),
            "scenario_high_growth": pred_high.astype(float),
            "scenario_target_metric": target_metric,
            "scenario_target_is_proxy": bool(target_is_proxy),
        }
    )
    if target_is_proxy:
        out["scenario_baseline_score"] = out["scenario_baseline_growth"]
        out["scenario_low_score"] = out["scenario_low_growth"]
        out["scenario_high_score"] = out["scenario_high_growth"]
    if "region_name" in train.columns:
        out["name"] = train["region_name"].astype(str).values
    elif "la_name" in train.columns:
        out["name"] = train["la_name"].astype(str).values
    out = out.sort_values("geography").reset_index(drop=True)
    meta = {
        "target_metric": target_metric,
        "target_is_proxy": bool(target_is_proxy),
        "n_rows": int(len(out)),
        "n_features_used": int(len(keep_cols)),
        "features_used": keep_cols,
        "reason": None,
    }
    return out, meta
