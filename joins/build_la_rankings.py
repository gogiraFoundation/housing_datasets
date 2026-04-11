"""Rank local authorities on house-building metrics; optional per-capita when population CSV exists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_PROCESSED = _REPO / "data" / "processed"
_DEFAULT_REF = _REPO / "data" / "reference"


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def load_population(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.is_file():
        return None
    pop = pd.read_csv(path)
    pop["lad_code"] = pop["lad_code"].map(_norm_lad)
    return pop


def rankings_from_housebuilding(
    hb: pd.DataFrame,
    *,
    financial_year: str,
    pop: pd.DataFrame | None,
) -> pd.DataFrame:
    sub = hb[hb["financial_year"].astype(str) == financial_year].copy()
    sub["lad_code"] = sub["Local Authority Code"].map(_norm_lad)

    starts = sub[sub["measure"].str.lower() == "starts"].set_index("lad_code")["dwellings"]
    comp = sub[sub["measure"].str.lower() == "completions"].set_index("lad_code")["dwellings"]
    la = pd.DataFrame({"starts": starts, "completions": comp}).reset_index()
    la["completions_per_start"] = la["completions"] / la["starts"].replace(0, pd.NA)

    if pop is not None:
        py = pop.sort_values("year").groupby("lad_code").last().reset_index()
        la = la.merge(py[["lad_code", "population"]], on="lad_code", how="left")
        la["starts_per_capita"] = la["starts"] / la["population"].replace(0, pd.NA)
    else:
        la["population"] = pd.NA
        la["starts_per_capita"] = pd.NA

    la["financial_year"] = financial_year
    la["rank_starts"] = la["starts"].rank(ascending=False, method="min")
    if pop is not None:
        la["rank_starts_per_capita"] = la["starts_per_capita"].rank(ascending=False, method="min")
    return la.sort_values("starts", ascending=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--housebuilding-edition", default="fye_march2025")
    p.add_argument("--financial-year", default="2023-2024", help="Financial year label as in tidy data.")
    p.add_argument("-o", "--output-dir", type=Path, default=_DEFAULT_PROCESSED)
    p.add_argument(
        "--population",
        type=Path,
        default=_DEFAULT_REF / "population_la_midyear.csv",
        help=(
            "Optional CSV with lad_code, year, population. "
            "After `python ons_census2021_etl.py --dataset sex_ts008`, you can pass "
            "`data/processed/census2021_la_population_2021.csv` for Census 2021 LA totals."
        ),
    )
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    hb_path = out_dir / f"ons_housebuilding_la_{args.housebuilding_edition}_tidy.parquet"
    if not hb_path.is_file():
        raise FileNotFoundError(hb_path)

    hb = pd.read_parquet(hb_path)
    pop = load_population(args.population)

    ranked = rankings_from_housebuilding(hb, financial_year=args.financial_year, pop=pop)
    tag = f"{args.housebuilding_edition}_{args.financial_year.replace('-', '_')}"
    stem = f"ranked_la_housebuilding_{tag}"
    pq = out_dir / f"{stem}.parquet"
    meta_path = out_dir / f"{stem}.meta.json"

    ranked.to_parquet(pq, index=False)
    meta = {
        "source": str(hb_path),
        "population_used": str(args.population) if pop is not None else None,
        "financial_year": args.financial_year,
        "suppression_note": "Nulls from source [x] suppression reduce comparability for some LAs.",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote {pq}")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
