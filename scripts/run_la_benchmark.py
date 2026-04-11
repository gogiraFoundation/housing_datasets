#!/usr/bin/env python3
"""Cross-section benchmark: ElasticNet or LightGBM on Lane A snapshot with region GroupKFold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.cross_section import export_residuals, load_lane_a_snapshot, run_group_kfold_benchmark
from housing_analytics.paths import PROCESSED_DIR


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    p.add_argument("--snapshot-stem", default="joined_la_housing_market_snapshot")
    p.add_argument(
        "--target",
        choices=("median_price_existing_gbp", "pe_affordability_ratio"),
        default="median_price_existing_gbp",
    )
    p.add_argument("--model", choices=("elastic_net", "lightgbm"), default="elastic_net")
    p.add_argument("--n-splits", type=int, default=5)
    p.add_argument("--log-target", action="store_true", help="Model log1p(target) for skewed targets.")
    p.add_argument("-o", "--output", type=Path, default=None, help="CSV path for residuals.")
    args = p.parse_args()

    df = load_lane_a_snapshot(args.processed_dir, stem=args.snapshot_stem)
    result = run_group_kfold_benchmark(
        df,
        target=args.target,
        model=args.model,
        n_splits=args.n_splits,
        log_target=args.log_target,
    )
    out = args.output
    if out is None:
        out = args.processed_dir / f"la_benchmark_{args.target}_{args.model}_residuals.csv"
    export_residuals(out, result)
    cv_path = Path(out).parent / f"la_benchmark_{args.target}_{args.model}_cv.json"
    cv_payload = {
        "target": args.target,
        "model": args.model,
        "n_splits": args.n_splits,
        "log_target": args.log_target,
        "cv_scores": result.cv_scores.to_dict(orient="records"),
    }
    cv_path.write_text(json.dumps(cv_payload, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Wrote {cv_path}")
    print(result.cv_scores)


if __name__ == "__main__":
    main()
