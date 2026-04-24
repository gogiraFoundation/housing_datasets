#!/usr/bin/env python3
"""Orchestrate the full 10-year regional forecast playbook."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forecast_playbook_utils import ensure_dir, load_hpi_regions  # noqa: E402


TARGET_SCRIPTS = (
    "run_hpi_growth_target.py",
    "run_affordability_target.py",
    "run_quantile_price_band_target.py",
    "run_divergence_risk_target.py",
    "run_supply_shortfall_target.py",
    "run_epc_adoption_target.py",
    "run_vacancy_pressure_target.py",
)


def _run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _collect_scoreboard_rows(region_output: Path) -> list[pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    for pred_file in sorted(region_output.glob("*_predictions.csv")):
        try:
            df = pd.read_csv(pred_file)
        except Exception:
            continue
        if not df.empty:
            rows.append(df)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=_REPO / "data" / "processed")
    p.add_argument("--edition", default="march2026")
    p.add_argument("--region", default="London", help="Single-region run target (ignored with --all-regions).")
    p.add_argument("--all-regions", action="store_true")
    p.add_argument("--base-output-dir", type=Path, default=_REPO / "data" / "processed" / "forecasts")
    args = p.parse_args()

    base_out = ensure_dir(args.base_output_dir / args.edition)
    regions = load_hpi_regions(args.processed_dir, args.edition) if args.all_regions else [args.region]
    all_rows: list[pd.DataFrame] = []

    for region in regions:
        region_slug = region.lower().replace(" ", "_")
        out_dir = ensure_dir(base_out / region_slug)
        print(f"Running playbook for region={region}")
        for script in TARGET_SCRIPTS:
            cmd = [
                sys.executable,
                str(Path(__file__).resolve().parent / script),
                "--processed-dir",
                str(args.processed_dir),
                "--region",
                region,
                "--output-dir",
                str(out_dir),
            ]
            _run(cmd)
        all_rows.extend(_collect_scoreboard_rows(out_dir))

    if all_rows:
        scoreboard = pd.concat(all_rows, ignore_index=True, sort=False)
        score_path = base_out / "forecast_playbook_scoreboard.parquet"
        scoreboard.to_parquet(score_path, index=False)
        print(f"Wrote {score_path}")
    else:
        print("No prediction rows were produced.")


if __name__ == "__main__":
    main()
