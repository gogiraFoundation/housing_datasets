#!/usr/bin/env python3
"""Run rolling backtests for UK HPI at several short horizons; print best model by MAE."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--edition", default="march2026")
    p.add_argument("--geography", default="United Kingdom")
    p.add_argument(
        "--horizons",
        default="3,6,12",
        help="Comma-separated horizons (months for monthly HPI).",
    )
    p.add_argument(
        "--models",
        default="seasonal_naive,ets,sarimax,lagged_hgbr",
        help="Same as run_ts_forecast.py --models.",
    )
    p.add_argument(
        "--frequency",
        choices=("monthly", "annual"),
        default="monthly",
        help="Pass through to run_ts_forecast.py.",
    )
    args = p.parse_args()

    horizons = [int(x.strip()) for x in args.horizons.split(",") if x.strip()]
    script = _REPO / "scripts" / "run_ts_forecast.py"
    rows: list[dict[str, str | int | float | None]] = []

    freq_tag = "monthly" if args.frequency == "monthly" else "annual"
    for h in horizons:
        out = args.processed_dir / f"ts_backtest_uk_hpi_{freq_tag}_{args.edition}_horizon_{h}.json"
        cmd = [
            sys.executable,
            str(script),
            "--dataset",
            "hpi",
            "--edition",
            args.edition,
            "--geography",
            args.geography,
            "--frequency",
            args.frequency,
            "--horizon",
            str(h),
            "--models",
            args.models,
            "-o",
            str(out),
        ]
        subprocess.run(cmd, check=True, cwd=str(_REPO))
        doc = json.loads(out.read_text(encoding="utf-8"))
        best = (doc.get("summary") or {}).get("best_model_mae")
        summ = (doc.get("summary") or {}).get("summary_by_model", [])
        mae_by = {r["model"]: r["mae"] for r in summ if "model" in r and "mae" in r}
        rows.append({"horizon": h, "best_model_mae": best, **{f"mae_{k}": v for k, v in mae_by.items()}})

    print("horizon", "best_model_mae", sep="\t")
    for r in rows:
        print(r["horizon"], r.get("best_model_mae"), sep="\t")
    print("\nReports written under", args.processed_dir, f"({freq_tag}, horizon_* in filename).")


if __name__ == "__main__":
    main()
