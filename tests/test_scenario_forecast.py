from __future__ import annotations

from pathlib import Path

import pandas as pd

from housing_analytics.scenario_forecast import scenario_forecast_growth


def test_scenario_forecast_region_smoke(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "region_code": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"],
            "region_name": [f"Region {i}" for i in range(10)],
            "region_supply_completed": [100 + i for i in range(10)],
            "region_supply_started": [90 + i for i in range(10)],
            "epc_pct_bands_abc": [60 + i for i in range(10)],
            "ee_epc_c_plus_pct": [70 + i for i in range(10)],
            "hpi_minus_prpi_growth_pp": [1 + i * 0.1 for i in range(10)],
            "region_population_census2021": [1_000_000 + i * 1000 for i in range(10)],
            "hpi_growth_overlap_pct": [2 + i * 0.2 for i in range(10)],
        }
    )
    p = tmp_path / "region_housing_market_snapshot.parquet"
    df.to_parquet(p, index=False)
    out, meta = scenario_forecast_growth(tmp_path, level="region")
    assert not out.empty
    assert {"scenario_baseline_growth", "scenario_low_growth", "scenario_high_growth"}.issubset(out.columns)
    assert "target_is_proxy" in meta
    assert "target_metric" in meta


def test_scenario_forecast_region_alias_and_proxy_score_columns(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "region_code": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"],
            "region_name": [f"Region {i}" for i in range(10)],
            "region_supply_completions": [100 + i for i in range(10)],
            "region_supply_starts": [90 + i for i in range(10)],
            "epc_pct_bands_abc": [60 + i for i in range(10)],
            "ee_epc_c_plus_pct": [70 + i for i in range(10)],
            "region_population_census2021": [1_000_000 + i * 1000 for i in range(10)],
        }
    )
    p = tmp_path / "region_housing_market_snapshot.parquet"
    df.to_parquet(p, index=False)
    out, meta = scenario_forecast_growth(tmp_path, level="region")
    assert not out.empty
    assert bool(meta.get("target_is_proxy")) is True
    assert str(meta.get("target_metric", "")).startswith("proxy_")
    assert {"scenario_baseline_growth", "scenario_low_growth", "scenario_high_growth"}.issubset(out.columns)
    assert {"scenario_baseline_score", "scenario_low_score", "scenario_high_score"}.issubset(out.columns)
