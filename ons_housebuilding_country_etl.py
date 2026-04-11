"""ONS UK house building by country: download and tidy starts/completions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_housebuilding_country_config import (
    HOUSEBUILDING_COUNTRY_EDITIONS,
    HOUSEBUILDING_COUNTRY_SKIPROWS,
    HOUSEBUILDING_COUNTRY_TABLES,
)

_REPO_ROOT = Path(__file__).resolve().parent

_TABLE_META: dict[str, tuple[str, str]] = {
    "1a": ("United Kingdom", "quarterly"),
    "1b": ("England", "quarterly"),
    "1c": ("Wales", "quarterly"),
    "1d": ("Scotland", "quarterly"),
    "1e": ("Northern Ireland", "quarterly"),
    "1f": ("Great Britain", "quarterly"),
    "2a": ("United Kingdom", "annual_financial_year"),
    "2b": ("England", "annual_financial_year"),
    "2c": ("Wales", "annual_financial_year"),
    "2d": ("Scotland", "annual_financial_year"),
    "2e": ("Northern Ireland", "annual_financial_year"),
    "3a": ("United Kingdom", "annual_calendar_year"),
    "3b": ("England", "annual_calendar_year"),
    "3c": ("Wales", "annual_calendar_year"),
    "3d": ("Scotland", "annual_calendar_year"),
    "3e": ("Northern Ireland", "annual_calendar_year"),
}

_MEASURE_SECTOR = re.compile(r"^(Started|Completed)\s*-\s*(.+)$", re.I)


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=HOUSEBUILDING_COUNTRY_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _clean_sheet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    if "Period" not in out.columns:
        raise ValueError("Expected 'Period' column in source sheet.")
    out["Period"] = out["Period"].astype(str).str.strip()
    return out


def _melt_table(df: pd.DataFrame, table_id: str) -> pd.DataFrame:
    country_name, frequency = _TABLE_META[table_id]
    out = _clean_sheet(df)
    id_vars = [c for c in ["Period"] if c in out.columns]
    value_cols = [c for c in out.columns if c not in ("Revised", *id_vars)]
    if not value_cols:
        raise ValueError(f"Table {table_id}: no value columns to melt.")
    tidy = out.melt(id_vars=id_vars, value_vars=value_cols, var_name="_metric", value_name="dwellings")
    parts = tidy["_metric"].map(lambda s: _MEASURE_SECTOR.match(str(s).strip()))
    if parts.isna().any():
        bad = tidy.loc[parts.isna(), "_metric"].astype(str).iloc[0]
        raise ValueError(f"Table {table_id}: cannot parse measure/sector from column {bad!r}.")
    tidy["measure"] = parts.map(lambda m: m.group(1).lower())
    tidy["sector"] = parts.map(lambda m: m.group(2).strip())
    tidy["dwellings"] = pd.to_numeric(tidy["dwellings"], errors="coerce").astype(pd.Int64Dtype())
    tidy["table_id"] = table_id
    tidy["country_name"] = country_name
    tidy["frequency"] = frequency
    tidy = tidy.rename(columns={"Period": "period"})
    return tidy[
        [
            "table_id",
            "country_name",
            "frequency",
            "period",
            "measure",
            "sector",
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

    all_frames: list[pd.DataFrame] = []
    for table_id in HOUSEBUILDING_COUNTRY_TABLES:
        raw = read_sheet(path, table_id)
        tidy = _melt_table(raw, table_id)
        all_frames.append(tidy)
    full = pd.concat(all_frames, ignore_index=True)

    stem = f"ons_housebuilding_country_{edition_key}_tidy"
    csv_path = output_dir / f"{stem}.csv"
    full.to_csv(csv_path, index=False)
    if write_parquet:
        pq_path = output_dir / f"{stem}.parquet"
        full.to_parquet(pq_path, index=False)
    if verbose:
        print(f"Wrote {csv_path}")
        if write_parquet:
            print(f"Wrote {output_dir / f'{stem}.parquet'}")
    return full


def _edition_from_key(key: str) -> EpcEdition:
    if key not in HOUSEBUILDING_COUNTRY_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(HOUSEBUILDING_COUNTRY_EDITIONS))}."
        )
    return HOUSEBUILDING_COUNTRY_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS UK house building by country: download and tidy starts/completions.",
    )
    p.add_argument("--edition", default="current", help="Edition key (default: current).")
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
