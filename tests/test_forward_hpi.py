"""Tests for forward HPI helpers and backtest JSON matching."""

from __future__ import annotations

import json
from pathlib import Path

from housing_analytics.forward_hpi import best_models_from_ts_backtest_json


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
