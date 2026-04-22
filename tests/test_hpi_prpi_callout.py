from __future__ import annotations

import pandas as pd

from housing_analytics.hpi_prpi_callout import buy_vs_rent_spread_caption


def test_buy_vs_rent_spread_caption(tmp_path):
    prpi = pd.DataFrame(
        {
            "month_label": ["Jan-20", "Feb-20"],
            "geography_name": ["England", "England"],
            "variable": ["index", "index"],
            "value": [100.0, 102.0],
        }
    )
    hpi = pd.DataFrame(
        {
            "time_period": ["Jan 2020", "Feb 2020"],
            "geography": ["England", "England"],
            "value": [100.0, 105.0],
        }
    )
    prpi.to_parquet(tmp_path / "ons_private_rental_index_v41_tidy.parquet", index=False)
    hpi.to_parquet(tmp_path / "ons_uk_hpi_monthly_march2026_1_tidy.parquet", index=False)
    cap = buy_vs_rent_spread_caption(tmp_path, geography_name="England")
    assert cap is not None
    assert "percentage points" in cap
    assert "England" in cap
