"""Join ONS house building (LA) with main fuel tables 2a and 2b on local authority district code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_PROCESSED = _REPO / "data" / "processed"


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def build_joined(
    processed_dir: Path,
    housebuilding_edition: str,
    mainfuel_edition: str,
    *,
    how: str = "left",
) -> tuple[pd.DataFrame, dict]:
    processed_dir = Path(processed_dir)
    hb_path = processed_dir / f"ons_housebuilding_la_{housebuilding_edition}_tidy.parquet"
    mf2a_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2a_tidy.parquet"
    mf2b_path = processed_dir / f"ons_mainfuel_{mainfuel_edition}_2b_tidy.parquet"

    for p, label in (
        (hb_path, "house building LA"),
        (mf2a_path, "main fuel 2a"),
        (mf2b_path, "main fuel 2b"),
    ):
        if not p.is_file():
            raise FileNotFoundError(f"Missing {label} tidy file: {p}")

    hb = pd.read_parquet(hb_path)
    hb = hb.copy()
    hb["lad_code"] = hb["Local Authority Code"].map(_norm_lad)

    mf2a = pd.read_parquet(mf2a_path)
    mf2a = mf2a.copy()
    mf2a["lad_code"] = mf2a["local_authority_district_code"].map(_norm_lad)
    mf2a["mainfuel_pct"] = mf2a["value"]
    mf2a = mf2a.drop(columns=["value"])
    mf2a["mainfuel_sheet"] = "2a"
    mf2a["dwelling_class"] = pd.NA

    mf2b = pd.read_parquet(mf2b_path)
    mf2b = mf2b.copy()
    mf2b["lad_code"] = mf2b["local_authority_district_code"].map(_norm_lad)
    mf2b["mainfuel_pct"] = mf2b["value"]
    mf2b = mf2b.drop(columns=["value"])
    mf2b["mainfuel_sheet"] = "2b"

    mf = pd.concat([mf2a, mf2b], ignore_index=True)

    merged = hb.merge(
        mf,
        on="lad_code",
        how=how,
        suffixes=("", "_mf"),
    )

    meta = {
        "housebuilding_edition": housebuilding_edition,
        "mainfuel_edition": mainfuel_edition,
        "join_how": how,
        "join_key": "lad_code (normalised Local Authority Code == local_authority_district_code)",
        "housebuilding_rows": len(hb),
        "mainfuel_rows": len(mf),
        "merged_rows": len(merged),
        "lad_in_hb_not_in_mf": int(
            hb.loc[~hb["lad_code"].isin(mf["lad_code"].unique()), "lad_code"].nunique()
        ),
        "caveat": (
            "Main fuel is a snapshot for the workbook period; house building is by financial year. "
            "Fuel columns are repeated across years for each LA."
        ),
    }
    return merged, meta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--housebuilding-edition",
        default="fye_march2025",
        help="Edition key for ons_housebuilding_la_{edition}_tidy.parquet",
    )
    p.add_argument(
        "--mainfuel-edition",
        default="march2025",
        help="Edition key for ons_mainfuel_{edition}_*_tidy.parquet",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_DEFAULT_PROCESSED,
        help="Directory for joined Parquet (default: data/processed).",
    )
    p.add_argument(
        "--tag",
        default=None,
        help="Output stem tag (default: {hb}_{mf}).",
    )
    p.add_argument(
        "--inner",
        action="store_true",
        help="Inner join instead of left (keep only LAs present in both).",
    )
    args = p.parse_args()

    tag = args.tag or f"{args.housebuilding_edition}_{args.mainfuel_edition}"
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    merged, meta = build_joined(
        out_dir,
        args.housebuilding_edition,
        args.mainfuel_edition,
        how="inner" if args.inner else "left",
    )

    stem = f"joined_la_housebuilding_mainfuel_{tag}"
    pq = out_dir / f"{stem}.parquet"
    meta_path = out_dir / f"{stem}.meta.json"

    merged.to_parquet(pq, index=False)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote {pq}")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
