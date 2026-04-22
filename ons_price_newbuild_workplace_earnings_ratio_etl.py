"""ONS: House price (newly built dwellings) to workplace-based earnings ratio — download and tidy."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_price_earnings_ratio_config import PRICE_EARNINGS_RATIO_DATA_SHEETS, PRICE_EARNINGS_RATIO_HEADER_ROW
from ons_price_earnings_ratio_etl import transform_sheet
from ons_price_newbuild_workplace_earnings_ratio_config import NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS

_REPO_ROOT = Path(__file__).resolve().parent


def read_data_sheet(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=PRICE_EARNINGS_RATIO_HEADER_ROW,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def transform_workbook(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    file_prefix: str = "ons_price_newbuild_workplace_earnings_ratio",
    write_parquet: bool = True,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    for sheet in PRICE_EARNINGS_RATIO_DATA_SHEETS:
        raw = read_data_sheet(path, sheet)
        tidy = transform_sheet(raw, sheet)
        stem = f"{file_prefix}_{edition_key}_{sheet}_tidy"
        csv_path = output_dir / f"{stem}.csv"
        tidy.to_csv(csv_path, index=False)
        pq_path = output_dir / f"{stem}.parquet"
        if write_parquet:
            write_parquet_atomic(tidy, pq_path, index=False)
        results[sheet] = tidy
        if verbose:
            print(f"Wrote {csv_path}")
            if write_parquet:
                print(f"Wrote {pq_path}")
    return results


def _edition_from_key(key: str) -> EpcEdition:
    if key not in NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS))}."
        )
    return NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "ONS house price (newly built dwellings) to workplace-based earnings ratio (England and Wales)."
        ),
    )
    p.add_argument(
        "--edition",
        default="current",
        help="Edition key from ons_price_newbuild_workplace_earnings_ratio_config (default: current).",
    )
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "raw",
        help="Directory for downloaded .xlsx and .meta.json.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "processed",
        help="Directory for tidy CSV/Parquet outputs.",
    )
    p.add_argument("-i", "--input", type=Path, default=None, help="Existing workbook (skip download).")
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
    out_dir = Path(args.output_dir)
    verbose = not args.quiet

    xlsx_path = Path(args.input) if args.input is not None else Path(args.raw_dir) / edition.suggested_filename

    if args.transform_only and args.extract_only:
        raise SystemExit("Choose at most one of --extract-only and --transform-only.")

    if args.transform_only:
        if not xlsx_path.is_file():
            raise SystemExit(f"--transform-only requires an existing workbook: {xlsx_path}")
    elif args.skip_download:
        if not xlsx_path.is_file():
            raise SystemExit(f"--skip-download requires an existing file: {xlsx_path}")
    else:
        dest, did = download_edition(
            edition,
            xlsx_path,
            force=args.force,
            skip_hash_check=args.skip_hash_check,
        )
        if verbose:
            print(f"{'Downloaded' if did else 'Using existing'} {dest}")

    if args.extract_only:
        return

    transform_workbook(
        xlsx_path,
        out_dir,
        edition.key,
        write_parquet=not args.skip_parquet,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()
