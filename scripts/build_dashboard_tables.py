"""Emit pre-aggregated dashboard Parquet views (e.g. latest financial-year country snapshot)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ons_housebuilding_country_periods import preferred_period_order

_REPO = Path(__file__).resolve().parents[1]


def latest_country_annual_fy(processed: Path, edition: str) -> pd.DataFrame | None:
    path = processed / f"ons_housebuilding_country_{edition}_tidy.parquet"
    if not path.is_file():
        return None
    df = pd.read_parquet(path)
    sub = df[
        (df["frequency"].astype(str) == "annual_financial_year")
        & (df["sector"].astype(str).str.strip() == "All Dwellings")
    ].copy()
    if sub.empty:
        return None
    order = preferred_period_order(sub["period"])
    latest = order[-1] if order else None
    if latest is None:
        return None
    return sub[sub["period"].astype(str) == latest].copy()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--edition",
        default="current",
        help="House-building country edition key (default: current).",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_REPO / "data" / "processed",
        help="Directory for dashboard_*.parquet outputs.",
    )
    args = p.parse_args()
    processed = Path(args.output_dir)
    processed.mkdir(parents=True, exist_ok=True)
    snap = latest_country_annual_fy(processed, args.edition)
    if snap is None:
        print("No country snapshot produced (missing Parquet or no annual FY rows).")
        return
    out = processed / f"dashboard_country_latest_fy_{args.edition}.parquet"
    snap.to_parquet(out, index=False)
    print(f"Wrote {out} ({len(snap)} rows)")


if __name__ == "__main__":
    main()
