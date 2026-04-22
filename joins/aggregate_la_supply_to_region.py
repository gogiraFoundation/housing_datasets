"""Aggregate ONS LA house-building starts/completions to region using LAD→region from main fuel 2a."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_PROCESSED = _REPO / "data" / "processed"
_DEFAULT_REF = _REPO / "data" / "reference"


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def lookup_from_mainfuel_2a(mf2a: pd.DataFrame) -> pd.DataFrame:
    u = mf2a[["local_authority_district_code", "local_authority_district_name", "region_code", "region_name"]].copy()
    u["lad_code"] = u["local_authority_district_code"].map(_norm_lad)
    u = u.drop_duplicates(subset=["lad_code"], keep="first")
    return u[
        ["lad_code", "local_authority_district_code", "local_authority_district_name", "region_code", "region_name"]
    ]


def aggregate(
    processed_dir: Path,
    housebuilding_edition: str,
    mainfuel_edition: str,
) -> pd.DataFrame:
    processed_dir = Path(processed_dir)
    hb_path = processed_dir / f"ons_housebuilding_la_{housebuilding_edition}_tidy.parquet"
    mf2a_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2a_tidy.parquet"
    if not hb_path.is_file():
        raise FileNotFoundError(hb_path)
    if not mf2a_path.is_file():
        raise FileNotFoundError(mf2a_path)

    hb = pd.read_parquet(hb_path)
    mf2a = pd.read_parquet(mf2a_path)
    lookup = lookup_from_mainfuel_2a(mf2a)
    hb = hb.copy()
    hb["lad_code"] = hb["Local Authority Code"].map(_norm_lad)

    merged = hb.merge(lookup, on="lad_code", how="left")
    agg = (
        merged.groupby(
            ["region_code", "region_name", "financial_year", "measure"],
            dropna=False,
            observed=True,
        )["dwellings"]
        .sum(min_count=1)
        .reset_index()
    )
    agg["housebuilding_edition"] = housebuilding_edition
    agg["lookup_mainfuel_edition"] = mainfuel_edition
    return agg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--housebuilding-edition", default="fye_march2025")
    p.add_argument("--mainfuel-edition", default="march2025")
    p.add_argument("-o", "--output-dir", type=Path, default=_DEFAULT_PROCESSED)
    p.add_argument(
        "--write-lookup",
        type=Path,
        default=None,
        help="If set, write LAD→region CSV to this path (default: data/reference/lad_to_region_england.csv).",
    )
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    mf2a = pd.read_parquet(out_dir / f"ons_mainfuel_{args.mainfuel_edition}_2a_tidy.parquet")
    lookup = lookup_from_mainfuel_2a(mf2a)

    wl = args.write_lookup
    if wl is None:
        wl = _DEFAULT_REF / "lad_to_region_england.csv"
    Path(wl).parent.mkdir(parents=True, exist_ok=True)
    lookup.to_csv(wl, index=False)
    print(f"Wrote {wl}")

    agg = aggregate(out_dir, args.housebuilding_edition, args.mainfuel_edition)
    stem = f"region_supply_from_la_{args.housebuilding_edition}_via_mf_{args.mainfuel_edition}"
    pq = out_dir / f"{stem}.parquet"
    write_parquet_atomic(agg, pq, index=False)
    print(f"Wrote {pq}")


if __name__ == "__main__":
    main()
