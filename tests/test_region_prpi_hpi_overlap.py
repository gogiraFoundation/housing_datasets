from __future__ import annotations

import pandas as pd

from joins.build_la_housing_market_snapshot import _region_hpi_prpi_growth


def test_region_hpi_prpi_growth_overlap(tmp_path):
    hpi = pd.DataFrame(
        {
            "time_period": ["Jan 2020", "Feb 2020", "Jan 2020", "Feb 2020"],
            "geography": ["England", "England", "East", "East"],
            "value": [100.0, 110.0, 200.0, 220.0],
        }
    )
    prpi = pd.DataFrame(
        {
            "month_label": ["Jan-20", "Feb-20", "Jan-20", "Feb-20"],
            "geography_name": ["England", "England", "East of England", "East of England"],
            "variable": ["index", "index", "index", "index"],
            "value": [100.0, 105.0, 100.0, 102.0],
        }
    )
    hpi.to_parquet(tmp_path / "ons_uk_hpi_monthly_march2026_1_tidy.parquet", index=False)
    prpi.to_parquet(tmp_path / "ons_private_rental_index_v41_tidy.parquet", index=False)

    out = _region_hpi_prpi_growth(tmp_path, hpi_edition="march2026", prpi_edition="v41")
    assert set(out["region_name"]) == {"England", "East of England"}

    eng = out[out["region_name"] == "England"].iloc[0]
    assert round(float(eng["hpi_growth_overlap_pct"]), 2) == 10.0
    assert round(float(eng["prpi_growth_overlap_pct"]), 2) == 5.0
    assert round(float(eng["hpi_minus_prpi_growth_pp"]), 2) == 5.0
