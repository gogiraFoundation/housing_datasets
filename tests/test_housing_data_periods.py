"""Tests for housing_data.periods."""

from __future__ import annotations

from housing_data.periods import pe_year_from_period


def test_pe_year_from_period() -> None:
    assert pe_year_from_period("Year ending Sep 2025") == 2025
    assert pe_year_from_period("2024") == 2024
    assert pe_year_from_period("5-Year Average") is None
