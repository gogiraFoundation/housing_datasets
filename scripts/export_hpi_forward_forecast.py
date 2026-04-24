#!/usr/bin/env python3
"""Export forward HPI forecasts (full-history fit) to JSON for reproducibility."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from housing_analytics.forward_hpi import SHEET1_GEOGRAPHIES, forward_forecast_hpi_levels
from housing_analytics.paths import PROCESSED_DIR
from housing_analytics.scenario_forecast import scenario_forecast_growth


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    p.add_argument("--edition", default="march2026")
    p.add_argument("--sheet", default="1")
    p.add_argument("--frequency", choices=("monthly", "annual"), default="monthly")
    p.add_argument("--annual-rule", default="last")
    p.add_argument("--horizon", type=int, default=12)
    p.add_argument(
        "--models",
        default="ets,sarimax,autoarima_ets_ensemble",
        help="Comma-separated model names (seasonal_naive,ets,sarimax,lagged_hgbr,autoarima_ets_ensemble).",
    )
    p.add_argument(
        "--geographies",
        default="",
        help="Comma-separated areas; default: all sheet-1 geographies from forward_hpi.SHEET1_GEOGRAPHIES.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="JSON path (default: data/processed/hpi_forward_forecast_<edition>_h<horizon>.json).",
    )
    p.add_argument(
        "--scenario-level",
        choices=("none", "region", "la"),
        default="region",
        help="Append driver-based baseline/low/high scenario output.",
    )
    args = p.parse_args()

    models = tuple(m.strip() for m in args.models.split(",") if m.strip())
    if not models:
        raise SystemExit("Provide at least one model in --models")

    geos = (
        tuple(g.strip() for g in args.geographies.split(",") if g.strip())
        if args.geographies.strip()
        else SHEET1_GEOGRAPHIES
    )

    processed = Path(args.processed_dir)
    rows: list[dict] = []
    for g in geos:
        for m in models:
            r = forward_forecast_hpi_levels(
                processed,
                edition=args.edition,
                sheet=args.sheet,
                geography=g,
                frequency=args.frequency,
                annual_rule=args.annual_rule,
                model_name=m,
                horizon=args.horizon,
            )
            row = dict(r)
            row["model_run"] = m
            rows.append(row)

    out_path = args.output
    if out_path is None:
        out_path = processed / f"hpi_forward_forecast_{args.edition}_h{args.horizon}.json"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "options": {
            "processed_dir": str(processed.resolve()),
            "edition": args.edition,
            "sheet": args.sheet,
            "frequency": args.frequency,
            "annual_rule": args.annual_rule,
            "horizon": args.horizon,
            "models": list(models),
            "geographies": list(geos),
        },
        "rows": rows,
    }
    if args.scenario_level != "none":
        scen, scen_meta = scenario_forecast_growth(processed, level=args.scenario_level)
        payload["scenarios"] = {
            "level": args.scenario_level,
            "metadata": scen_meta,
            "rows": scen.to_dict(orient="records"),
        }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
