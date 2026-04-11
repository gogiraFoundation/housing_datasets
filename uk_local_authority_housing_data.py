"""Load and clean UK local authority housing starts from Excel; export wide and tidy tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from housing_data.wide_la import LA_ID_COLUMNS, clean_wide_la_housing

DEFAULT_WORKBOOK = Path(__file__).resolve().parent / "UK_local_authority_housing_data.xlsx"
DEFAULT_SHEET = "UK_Starts"
DEFAULT_SKIPROWS = 5

ID_COL_NAMES = LA_ID_COLUMNS


def load_raw(
    path: str | Path,
    *,
    sheet_name: str = DEFAULT_SHEET,
    skiprows: int = DEFAULT_SKIPROWS,
) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Workbook not found: {path}")
    return pd.read_excel(path, sheet_name=sheet_name, skiprows=skiprows, engine="openpyxl")


def clean_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty rows/columns; standardise four ID columns; validate year column names."""
    return clean_wide_la_housing(df)


def melt_to_tidy(df_wide: pd.DataFrame) -> pd.DataFrame:
    value_vars = [c for c in df_wide.columns if c not in ID_COL_NAMES]
    if not value_vars:
        raise ValueError("No year/value columns to melt.")
    tidy = df_wide.melt(
        id_vars=ID_COL_NAMES,
        value_vars=value_vars,
        var_name="financial_year",
        value_name="starts",
    )
    tidy = tidy.assign(
        starts=pd.to_numeric(tidy["starts"], errors="coerce").astype(pd.Int64Dtype()),
    )
    return tidy


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    *,
    sheet_name: str = DEFAULT_SHEET,
    skiprows: int = DEFAULT_SKIPROWS,
    write_parquet: bool = True,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = load_raw(input_path, sheet_name=sheet_name, skiprows=skiprows)
    wide = clean_wide(raw)
    tidy = melt_to_tidy(wide)

    wide_csv = output_dir / "uk_housing_starts_wide.csv"
    tidy_csv = output_dir / "uk_housing_starts_tidy.csv"
    wide.to_csv(wide_csv, index=False)
    tidy.to_csv(tidy_csv, index=False)

    if write_parquet:
        tidy_parquet = output_dir / "uk_housing_starts_tidy.parquet"
        tidy.to_parquet(tidy_parquet, index=False)

    if verbose:
        print(f"Wrote {wide_csv}")
        print(f"Wrote {tidy_csv}")
        if write_parquet:
            print(f"Wrote {output_dir / 'uk_housing_starts_tidy.parquet'}")

    return wide, tidy


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UK local authority housing starts: Excel to CSV/Parquet.")
    p.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_WORKBOOK,
        help=f"Path to .xlsx workbook (default: {DEFAULT_WORKBOOK.name} next to this script).",
    )
    p.add_argument("--sheet", default=DEFAULT_SHEET, help="Worksheet name.")
    p.add_argument("--skiprows", type=int, default=DEFAULT_SKIPROWS, help="Rows to skip before the table header.")
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "processed",
        help="Directory for uk_housing_starts_*.csv (and .parquet).",
    )
    p.add_argument("--skip-parquet", action="store_true", help="Do not write Parquet.")
    p.add_argument("-q", "--quiet", action="store_true", help="Less console output.")
    return p


def main() -> None:
    args = _build_arg_parser().parse_args()
    run_pipeline(
        args.input,
        args.output_dir,
        sheet_name=args.sheet,
        skiprows=args.skiprows,
        write_parquet=not args.skip_parquet,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
