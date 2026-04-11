"""Sort keys for ONS country house-building period labels (chart axis order)."""

from __future__ import annotations

import re

import pandas as pd

# ONS quarterly labels use the quarter start month (Jan / Apr / Jul / Oct).
_QUARTER_RE = re.compile(
    r"^(Jan|Apr|Jul|Oct)\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$"
)
_FY_RE = re.compile(r"^(\d{4})-(\d{2})$")
_CY_RE = re.compile(r"^(\d{4})$")
_QUARTER_INDEX = {"Jan": 0, "Apr": 1, "Jul": 2, "Oct": 3}


def period_sort_key(period: str) -> tuple:
    """Sort key: quarterly by calendar time; FY / CY next; everything else last."""
    s = str(period).strip()
    m = _QUARTER_RE.match(s)
    if m:
        q = _QUARTER_INDEX[m.group(1)]
        return (0, int(m.group(2)), q)
    m = _FY_RE.match(s)
    if m:
        return (1, int(m.group(1)), int(m.group(2)))
    m = _CY_RE.match(s)
    if m:
        return (2, int(m.group(1)), 0)
    return (3, s, "")


def preferred_period_order(periods: pd.Series) -> list[str]:
    """Unique period strings in chart-friendly order (quarters chronological, not lexical)."""
    uniq = periods.dropna().astype(str).unique().tolist()
    return sorted(uniq, key=period_sort_key)
