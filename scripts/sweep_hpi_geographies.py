#!/usr/bin/env python3
"""Run rolling UK HPI backtests for each geography on sheet 1 (countries, GB/UK, English regions)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Must match labels in `ons_uk_hpi_monthly_*_1_tidy.parquet` geography column.
SHEET1_GEOGRAPHIES: tuple[str, ...] = (
    "United Kingdom",
    "Great Britain",
    "England",
    "Wales",
    "Scotland",
    "Northern Ireland [note 3]",
    "East",
    "East Midlands",
    "London",
    "North East",
    "North West",
    "South East",
    "South West",
    "West Midlands",
    "Yorkshire and The Humber",
)


def _slug(geo: str) -> str:
    s = re.sub(r"[^\w\s-]", "", geo.strip())
    return re.sub(r"\s+", "_", s)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--edition", default="march2026")
    p.add_argument("--horizon", type=int, default=3)
    p.add_argument(
        "--models",
        default="seasonal_naive,ets,sarimax,lagged_hgbr",
        help="Same as run_ts_forecast.py --models.",
    )
    p.add_argument(
        "--frequency",
        choices=("monthly", "annual"),
        default="monthly",
    )
    p.add_argument(
        "--geographies",
        default="",
        help="Comma-separated list (default: built-in sheet-1 list).",
    )
    args = p.parse_args()

    geos = (
        tuple(g.strip() for g in args.geographies.split(",") if g.strip())
        if args.geographies.strip()
        else SHEET1_GEOGRAPHIES
    )
    script = _REPO / "scripts" / "run_ts_forecast.py"
    freq_tag = "monthly" if args.frequency == "monthly" else "annual"

    for geo in geos:
        slug = _slug(geo)
        out = args.processed_dir / f"ts_backtest_uk_hpi_{freq_tag}_{args.edition}_h{args.horizon}_{slug}.json"
        cmd = [
            sys.executable,
            str(script),
            "--dataset",
            "hpi",
            "--edition",
            args.edition,
            "--geography",
            geo,
            "--frequency",
            args.frequency,
            "--horizon",
            str(args.horizon),
            "--models",
            args.models,
            "-o",
            str(out),
        ]
        print("Running:", geo, "->", out.name, flush=True)
        subprocess.run(cmd, check=True, cwd=str(_REPO))

    print("Done.", len(geos), "reports under", args.processed_dir)


if __name__ == "__main__":
    main()
