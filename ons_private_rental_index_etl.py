"""ONS: Index of Private Housing Rental Prices — download CSV and tidy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_private_rental_index_config import PRIVATE_RENTAL_INDEX_EDITIONS

_REPO_ROOT = Path(__file__).resolve().parent

# Expected ONS CSV columns (v4 time-series); first column is the observation value.
_COL_RENAME = {
    "v4_1": "value",
    "Data Marking": "data_marking",
    "mmm-yy": "month_label",
    "Time": "time_period",
    "administrative-geography": "geography_code",
    "Geography": "geography_name",
    "index-and-year-change": "variable",
    "IndexAndYearChange": "variable_label",
}


def _coerce_numeric(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        s = s.replace(r"\[x\]", pd.NA, regex=True)
    return pd.to_numeric(s, errors="coerce").astype(pd.Float64Dtype())


def _snake_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower().strip()).strip("_")


def transform_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Map ONS CSV columns to a single tidy table."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    unknown = [c for c in df.columns if c not in _COL_RENAME]
    if unknown:
        # First column is typically the observation dimension (v4_1 or similar).
        if len(df.columns) == len(_COL_RENAME) + 1 and unknown == [df.columns[0]]:
            df = df.rename(columns={df.columns[0]: "v4_1"})
            df.columns = [str(c).strip() for c in df.columns]
        else:
            raise ValueError(
                f"Unexpected CSV columns: {unknown!r}. Full columns: {list(df.columns)}"
            )
    missing = [k for k in _COL_RENAME if k not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns after normalisation: {missing}")
    out = df.rename(columns=_COL_RENAME)
    out["value"] = _coerce_numeric(out["value"])
    if "data_marking" in out.columns and out["data_marking"].dtype == object:
        out["data_marking"] = out["data_marking"].replace(r"^\s*$", pd.NA, regex=True)
    cols = [
        "geography_code",
        "geography_name",
        "variable",
        "variable_label",
        "time_period",
        "month_label",
        "value",
        "data_marking",
    ]
    return out[cols]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8", low_memory=False)


def transform_file(path: Path) -> pd.DataFrame:
    return transform_csv(read_csv(path))


def transform_and_write(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    write_parquet: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tidy = transform_file(path)
    stem = f"ons_private_rental_index_{edition_key}_tidy"
    csv_path = output_dir / f"{stem}.csv"
    tidy.to_csv(csv_path, index=False)
    pq_path = output_dir / f"{stem}.parquet"
    if write_parquet:
        write_parquet_atomic(tidy, pq_path, index=False)
    if verbose:
        print(f"Wrote {csv_path}")
        if write_parquet:
            print(f"Wrote {pq_path}")
    return tidy


def _edition_from_key(key: str) -> EpcEdition:
    if key not in PRIVATE_RENTAL_INDEX_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(PRIVATE_RENTAL_INDEX_EDITIONS))}."
        )
    return PRIVATE_RENTAL_INDEX_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS Index of Private Housing Rental Prices (experimental index and YoY %).",
    )
    p.add_argument(
        "--edition",
        default="v41",
        help="Edition key from ons_private_rental_index_config (default: v41).",
    )
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "raw",
        help="Directory for downloaded .csv and .meta.json.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "processed",
        help="Directory for tidy CSV/Parquet outputs.",
    )
    p.add_argument("-i", "--input", type=Path, default=None, help="Existing CSV (skip download).")
    p.add_argument("--extract-only", action="store_true", help="Only download and write metadata.")
    p.add_argument("--transform-only", action="store_true", help="Only transform; needs existing file.")
    p.add_argument("--force", action="store_true", help="Re-download even if hash matches.")
    p.add_argument("--skip-hash-check", action="store_true", help="Reuse raw file without SHA-256 check.")
    p.add_argument("--skip-download", action="store_true", help="Use file at --input or default raw path.")
    p.add_argument("--skip-parquet", action="store_true", help="CSV only.")
    p.add_argument("-q", "--quiet", action="store_true", help="Less logging.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    edition = _edition_from_key(args.edition)
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.output_dir)
    verbose = not args.quiet

    csv_path = Path(args.input) if args.input is not None else raw_dir / edition.suggested_filename

    if args.transform_only and args.extract_only:
        raise SystemExit("Choose at most one of --extract-only and --transform-only.")

    if args.transform_only:
        if not csv_path.is_file():
            raise SystemExit(f"--transform-only requires an existing CSV: {csv_path}")
    elif args.skip_download:
        if not csv_path.is_file():
            raise SystemExit(f"--skip-download requires an existing file: {csv_path}")
    else:
        dest, did = download_edition(
            edition,
            csv_path,
            force=args.force,
            skip_hash_check=args.skip_hash_check,
        )
        if verbose:
            print(f"{'Downloaded' if did else 'Using existing'} {dest}")

    if args.extract_only:
        return

    transform_and_write(
        csv_path,
        out_dir,
        edition.key,
        write_parquet=not args.skip_parquet,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()
