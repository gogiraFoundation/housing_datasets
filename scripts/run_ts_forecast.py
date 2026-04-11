#!/usr/bin/env python3
"""Rolling-origin backtest for UK HPI monthly or country house-building series."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.paths import PROCESSED_DIR
from housing_analytics.ts_backtest import rolling_origin_backtest, write_backtest_report
from housing_analytics.ts_load import (
    infer_seasonal_period,
    load_hpi_series,
    load_hpi_series_annual,
    load_housebuilding_country_series,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset",
        choices=("hpi", "housebuilding"),
        default="hpi",
        help="Data source (default: hpi).",
    )
    p.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    p.add_argument("--edition", default="march2026", help="Workbook edition key.")
    p.add_argument("--sheet", default="1", help="UK HPI sheet id (1,2,3,7) when dataset=hpi.")
    p.add_argument(
        "--frequency",
        choices=("monthly", "annual"),
        default="monthly",
        help="HPI only: monthly series (default) or calendar-year aggregation from the same Parquet.",
    )
    p.add_argument(
        "--annual-rule",
        choices=("last", "mean"),
        default="last",
        help="HPI only: last month per calendar year vs mean of months (with --frequency annual).",
    )
    p.add_argument("--geography", default="United Kingdom", help="HPI geography column value.")
    p.add_argument("--table-id", default="1a", help="House-building table id when dataset=housebuilding.")
    p.add_argument("--measure", default="started", help="started|completed")
    p.add_argument(
        "--sector",
        default="All Dwellings",
        help="Sector label from ONS (e.g. All Dwellings, Private Enterprise, …).",
    )
    p.add_argument(
        "--min-train",
        type=int,
        default=None,
        help="Minimum training length before first test origin (default: 36 monthly, 15 annual).",
    )
    p.add_argument("--horizon", type=int, default=3, help="Forecast horizon per window.")
    p.add_argument(
        "--models",
        default="seasonal_naive,ets,sarimax,lagged_hgbr",
        help="Comma-separated model names.",
    )
    p.add_argument("-o", "--output", type=Path, default=None, help="JSON report path (default: stdout dir).")
    args = p.parse_args()

    if args.dataset != "hpi" and args.frequency != "monthly":
        raise SystemExit("--frequency annual applies only with --dataset hpi")

    processed_dir = Path(args.processed_dir)
    if args.dataset == "hpi":
        if args.frequency == "annual":
            y, _idx, meta = load_hpi_series_annual(
                processed_dir,
                edition=args.edition,
                sheet=args.sheet,
                geography=args.geography,
                annual_rule=args.annual_rule,
            )
        else:
            y, _idx, meta = load_hpi_series(
                processed_dir,
                edition=args.edition,
                sheet=args.sheet,
                geography=args.geography,
            )
    else:
        y, _idx, meta = load_housebuilding_country_series(
            processed_dir,
            edition=args.edition,
            table_id=args.table_id,
            measure=args.measure,
            sector=args.sector,
        )

    min_train = args.min_train
    if min_train is None:
        if args.dataset == "hpi" and args.frequency == "annual":
            n = len(y)
            cap = n - args.horizon
            if cap < 1:
                min_train = 1
            elif cap >= 5:
                min_train = min(15, max(5, cap))
            else:
                min_train = cap
        else:
            min_train = 36

    sp = infer_seasonal_period(meta)
    models = tuple(m.strip() for m in args.models.split(",") if m.strip())
    windows_df, bundle = rolling_origin_backtest(
        y,
        seasonal_period=sp,
        min_train=min_train,
        horizon=args.horizon,
        models=models,
    )
    out_path = args.output
    if out_path is None:
        stem = f"ts_backtest_{meta['dataset']}_{args.edition}".replace(" ", "_")
        if args.dataset == "hpi" and args.frequency == "annual":
            stem = f"{stem}_{args.annual_rule}"
        out_path = processed_dir / f"{stem}.json"

    report_meta = {**meta, "min_train": min_train, "horizon": args.horizon, "seasonal_period": sp}
    write_backtest_report(
        out_path,
        meta=report_meta,
        windows_df=windows_df,
        summary={"summary_by_model": bundle.get("summary_by_model", [])},
    )
    print(f"Wrote {out_path}")
    if windows_df.empty:
        print("No completed windows (increase series length or adjust min_train / models).")


if __name__ == "__main__":
    main()
