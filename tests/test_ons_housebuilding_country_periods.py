"""Tests for ONS country period ordering (chart axis)."""

from __future__ import annotations

import pandas as pd

from ons_housebuilding_country_periods import preferred_period_order


def test_quarterly_periods_chronological_not_lexical():
    s = pd.Series(
        [
            "Apr - Jun 1978",
            "Jan - Mar 1978",
            "Oct - Dec 1978",
            "Jul - Sep 1978",
        ]
    )
    assert preferred_period_order(s) == [
        "Jan - Mar 1978",
        "Apr - Jun 1978",
        "Jul - Sep 1978",
        "Oct - Dec 1978",
    ]


def test_quarters_order_across_years():
    s = pd.Series(["Jan - Mar 1979", "Jan - Mar 1978"])
    assert preferred_period_order(s) == ["Jan - Mar 1978", "Jan - Mar 1979"]
