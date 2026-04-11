"""Load univariate series from UK HPI monthly or country house-building Parquet."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ons_housebuilding_country_periods import preferred_period_order


def parse_hpi_time_period(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%b %Y", errors="coerce")


def load_hpi_series(
    processed_dir: Path,
    *,
    edition: str,
    sheet: str = "1",
    geography: str = "United Kingdom",
) -> tuple[pd.Series, pd.DatetimeIndex, dict[str, str]]:
    """Load one geography column from a UK HPI time sheet (1,2,3,7)."""
    path = Path(processed_dir) / f"ons_uk_hpi_monthly_{edition}_{sheet}_tidy.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    sub = df[df["geography"].astype(str).str.strip() == geography.strip()].copy()
    if sub.empty:
        raise ValueError(f"No rows for geography {geography!r} in {path.name}.")
    sub["time"] = parse_hpi_time_period(sub["time_period"])
    sub = sub.dropna(subset=["time"]).sort_values("time")
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub = sub.dropna(subset=["value"])
    y = pd.Series(sub["value"].values, index=pd.DatetimeIndex(sub["time"]), name="value")
    meta = {"dataset": "uk_hpi_monthly", "edition": edition, "sheet": sheet, "geography": geography}
    return y, y.index, meta


def aggregate_hpi_monthly_to_annual(y: pd.Series, *, rule: str) -> pd.Series:
    """Calendar-year aggregation of a monthly HPI series.

    ``last`` — value at the last month in each calendar year (typically December).
    ``mean`` — mean of monthly values within each calendar year.
    """
    y = y.sort_index()
    if rule == "last":
        out = y.resample("YE").last()
    elif rule == "mean":
        agg = y.groupby(y.index.year).mean()
        out = pd.Series(
            agg.values,
            index=pd.DatetimeIndex([pd.Timestamp(year=int(yr), month=12, day=31) for yr in agg.index]),
            name=y.name,
        )
    else:
        raise ValueError("rule must be 'last' or 'mean'")
    out = out.dropna()
    out.name = y.name
    return out


def load_hpi_series_annual(
    processed_dir: Path,
    *,
    edition: str,
    sheet: str = "1",
    geography: str = "United Kingdom",
    annual_rule: str = "last",
) -> tuple[pd.Series, pd.DatetimeIndex, dict[str, str]]:
    """UK HPI monthly Parquet aggregated to one value per calendar year."""
    y_m, _idx, base = load_hpi_series(
        processed_dir,
        edition=edition,
        sheet=sheet,
        geography=geography,
    )
    y = aggregate_hpi_monthly_to_annual(y_m, rule=annual_rule)
    meta = {
        "dataset": "uk_hpi_annual",
        "edition": base["edition"],
        "sheet": base["sheet"],
        "geography": base["geography"],
        "annual_rule": annual_rule,
    }
    return y, y.index, meta


def load_housebuilding_country_series(
    processed_dir: Path,
    *,
    edition: str,
    table_id: str,
    measure: str,
    sector: str,
) -> tuple[pd.Series, pd.Index, dict[str, str]]:
    """One univariate series from `ons_housebuilding_country_{edition}_tidy.parquet`."""
    path = Path(processed_dir) / f"ons_housebuilding_country_{edition}_tidy.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    m = measure.strip().lower()
    sub = df[
        (df["table_id"].astype(str) == table_id)
        & (df["measure"].astype(str).str.lower() == m)
        & (df["sector"].astype(str).str.strip() == sector.strip())
    ].copy()
    if sub.empty:
        raise ValueError(f"No rows for table_id={table_id}, measure={measure}, sector={sector!r}.")
    order = preferred_period_order(sub["period"])
    sub["period"] = pd.Categorical(sub["period"].astype(str), categories=order, ordered=True)
    sub = sub.sort_values("period")
    sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
    sub = sub.dropna(subset=["dwellings"])
    idx = pd.Index(sub["period"].astype(str), name="period")
    y = pd.Series(sub["dwellings"].values, index=idx, name="dwellings")
    freq = str(sub["frequency"].iloc[0])
    meta = {
        "dataset": "housebuilding_country",
        "edition": edition,
        "table_id": table_id,
        "measure": measure,
        "sector": sector,
        "frequency": freq,
    }
    return y, y.index, meta


def infer_seasonal_period(meta: dict[str, str]) -> int:
    """Season length for naive / ETS (12 monthly, 4 quarterly)."""
    if meta.get("dataset") == "uk_hpi_annual":
        return 1
    if meta.get("dataset") == "uk_hpi_monthly":
        return 12
    freq = str(meta.get("frequency", "")).lower()
    if "quarter" in freq:
        return 4
    if "financial" in freq or "calendar" in freq:
        return 1
    return 4
