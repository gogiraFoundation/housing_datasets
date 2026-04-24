"""Tests for forward HPI helpers and backtest JSON matching."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from housing_analytics.forward_hpi import best_models_from_ts_backtest_json, end_horizon_pct_change
from housing_analytics.scenario_forecast import scenario_forecast_growth


def test_best_models_from_ts_backtest_json_single_agreement(tmp_path: Path) -> None:
    doc = {
        "meta": {
            "dataset": "uk_hpi_monthly",
            "edition": "march2026",
            "sheet": "1",
            "geography": "England",
            "horizon": 12,
        },
        "summary": {"best_model_mae": "ets"},
    }
    (tmp_path / "ts_backtest_uk_hpi_monthly_march2026_h12_England.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    out = best_models_from_ts_backtest_json(
        tmp_path,
        edition="march2026",
        sheet="1",
        frequency="monthly",
        annual_rule="last",
        horizon=12,
        geographies=["England"],
    )
    assert out == ["ets"]


def test_best_models_from_ts_backtest_json_two_geographies_same_model(tmp_path: Path) -> None:
    for geo, name in [("England", "ts_backtest_a.json"), ("Wales", "ts_backtest_b.json")]:
        doc = {
            "meta": {
                "dataset": "uk_hpi_monthly",
                "edition": "march2026",
                "sheet": "1",
                "geography": geo,
                "horizon": 3,
            },
            "summary": {"best_model_mae": "sarimax"},
        }
        (tmp_path / name).write_text(json.dumps(doc), encoding="utf-8")
    out = best_models_from_ts_backtest_json(
        tmp_path,
        edition="march2026",
        sheet="1",
        frequency="monthly",
        annual_rule="last",
        horizon=3,
        geographies=["England", "Wales"],
    )
    assert out == ["sarimax"]


def test_best_models_from_ts_backtest_json_annual_rule(tmp_path: Path) -> None:
    doc = {
        "meta": {
            "dataset": "uk_hpi_annual",
            "edition": "march2026",
            "sheet": "1",
            "geography": "United Kingdom",
            "horizon": 10,
            "annual_rule": "mean",
        },
        "summary": {"best_model_mae": "seasonal_naive"},
    }
    (tmp_path / "ts_backtest_annual.json").write_text(json.dumps(doc), encoding="utf-8")
    out = best_models_from_ts_backtest_json(
        tmp_path,
        edition="march2026",
        sheet="1",
        frequency="annual",
        annual_rule="mean",
        horizon=10,
        geographies=["United Kingdom"],
    )
    assert out == ["seasonal_naive"]


def test_end_horizon_pct_change_has_probabilistic_fields() -> None:
    y = np.linspace(100.0, 140.0, 48)
    out = end_horizon_pct_change(y, model_name="ets", seasonal_period=12, horizon=3)
    assert out["error"] is None
    assert out["forecast_end_p10"] is not None
    assert out["forecast_end_p50"] is not None
    assert out["forecast_end_p90"] is not None
    assert float(out["forecast_end_p10"]) <= float(out["forecast_end_p50"]) <= float(out["forecast_end_p90"])


def test_scenario_rows_keep_score_columns_when_serialized(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "region_code": ["R1", "R2", "R3", "R4", "R5"],
            "region_name": [f"Region {i}" for i in range(5)],
            "region_supply_completions": [100 + i for i in range(5)],
            "region_supply_starts": [90 + i for i in range(5)],
            "epc_pct_bands_abc": [60 + i for i in range(5)],
            "ee_epc_c_plus_pct": [70 + i for i in range(5)],
            "region_population_census2021": [1_000_000 + i * 1000 for i in range(5)],
        }
    )
    p = tmp_path / "region_housing_market_snapshot.parquet"
    df.to_parquet(p, index=False)
    scen, meta = scenario_forecast_growth(tmp_path, level="region")
    assert bool(meta.get("target_is_proxy")) is True
    rows = scen.to_dict(orient="records")
    assert rows
    assert "scenario_baseline_score" in rows[0]
    assert "scenario_low_score" in rows[0]
    assert "scenario_high_score" in rows[0]
