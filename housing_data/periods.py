"""Shared period-label parsing for ONS housing time series."""

from __future__ import annotations

import re


def pe_year_from_period(label: object) -> int | None:
    """Align ONS price/earnings tables: 5a uses 'Year ending Sep YYYY'; 5b/5c use 'YYYY'."""
    s = str(label).strip()
    if s == "5-Year Average":
        return None
    m = re.match(r"Year ending Sep (\d{4})", s)
    if m:
        return int(m.group(1))
    if re.match(r"^\d{4}$", s):
        return int(s)
    return None
