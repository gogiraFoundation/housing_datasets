"""ONS UK house building by local authority: download and tidy starts/completions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from housing_data.wide_la import LA_ID_COLUMNS, clean_wide_la_housing
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_housebuilding_la_config import (
    HOUSEBUILDING_LA_EDITIONS,
    HOUSEBUILDING_LA_SHEETS,
    HOUSEBUILDING_LA_SKIPROWS,
)

_REPO_ROOT = Path(__file__).resolve().parent

ID_COL_NAMES = LA_ID_COLUMNS


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=HOUSEBUILDING_LA_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def clean_wide(df: pd.DataFrame) -> pd.DataFrame:
    return clean_wide_la_housing(df)


def melt_with_measure(df_wide: pd.DataFrame, *, measure: str) -> pd.DataFrame:
    value_vars = [c for c in df_wide.columns if c not in ID_COL_NAMES]
    if not value_vars:
        raise ValueError("No year/value columns to melt.")
    tidy = df_wide.melt(
        id_vars=ID_COL_NAMES,
        value_vars=value_vars,
        var_name="financial_year",
        value_name="dwellings",
    )
    tidy["dwellings"] = pd.to_numeric(tidy["dwellings"], errors="coerce").astype(pd.Int64Dtype())
    tidy["measure"] = measure
    return tidy[
        [
            "measure",
            "financial_year",
            "Region Type",
            "Region or Country Name",
            "Local Authority Code",
            "Local Authority Name",
            "dwellings",
        ]
    ]


def transform_workbook(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    write_parquet: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[pd.DataFrame] = []
    for measure, sheet_name in HOUSEBUILDING_LA_SHEETS.items():
        raw = read_sheet(path, sheet_name)
        wide = clean_wide(raw)
        tidy = melt_with_measure(wide, measure=measure)
        chunks.append(tidy)

    all_tidy = pd.concat(chunks, ignore_index=True)
    all_tidy["measure"] = pd.Categorical(all_tidy["measure"], categories=["starts", "completions"], ordered=True)

    stem = f"ons_housebuilding_la_{edition_key}_tidy"
    csv_path = output_dir / f"{stem}.csv"
    all_tidy.to_csv(csv_path, index=False)
    if write_parquet:
        pq_path = output_dir / f"{stem}.parquet"
        all_tidy.to_parquet(pq_path, index=False)
    if verbose:
        print(f"Wrote {csv_path}")
        if write_parquet:
            print(f"Wrote {output_dir / f'{stem}.parquet'}")
    return all_tidy


def _edition_from_key(key: str) -> EpcEdition:
    if key not in HOUSEBUILDING_LA_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(HOUSEBUILDING_LA_EDITIONS))}."
        )
    return HOUSEBUILDING_LA_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS UK house building by local authority: download and tidy starts/completions.",
    )
    p.add_argument("--edition", default="fye_march2025", help="Edition key (default: fye_march2025).")
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
    p.add_argument("--transform-only", action="store_true", help="Only transform; needs existing workbook.")
    p.add_argument("--force", action="store_true", help="Re-download even if hash matches.")
    p.add_argument("--skip-hash-check", action="store_true", help="Reuse raw file without SHA-256 check.")
    p.add_argument("--skip-download", action="store_true", help="Use file from --input or default raw path.")
    p.add_argument("--skip-parquet", action="store_true", help="CSV only.")
    p.add_argument("-q", "--quiet", action="store_true", help="Less logging.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    edition = _edition_from_key(args.edition)
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.output_dir)
    verbose = not args.quiet

    if args.transform_only and args.extract_only:
        raise SystemExit("Choose at most one of --extract-only and --transform-only.")

    xlsx_path = Path(args.input) if args.input is not None else raw_dir / edition.suggested_filename

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
