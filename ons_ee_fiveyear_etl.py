"""ONS: Energy efficiency of housing, England and Wales, five years rolling — download and tidy tables."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_ee_fiveyear_config import (
    EE_DATA_SHEETS,
    EE_FIVEYEAR_EDITIONS,
    EE_ID_HEADERS,
    EE_TABLE_SKIPROWS,
)

_REPO_ROOT = Path(__file__).resolve().parent

_ID_RENAME = {
    EE_ID_HEADERS[0]: "country_or_region_name",
    EE_ID_HEADERS[1]: "country_or_region_code",
}

_PERIOD_TAIL = re.compile(r"^Q2 \d{4} to Q1 \d{4}$")


def _split_metric_period(column_name: str) -> tuple[str, str]:
    """Split 'All Q2 2008 to Q1 2013' or 'Detached Q2 2008…' into breakdown label and period."""
    s = str(column_name).strip()
    idx = s.rfind(" Q2 ")
    if idx == -1:
        raise ValueError(f"Cannot parse rolling period from column {column_name!r}.")
    prefix = s[:idx].strip()
    period = s[idx + 1 :].strip()
    if not _PERIOD_TAIL.match(period):
        raise ValueError(f"Unexpected period part in column {column_name!r}: {period!r}.")
    return prefix, period


def read_ee_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=EE_TABLE_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _assert_id_headers(df: pd.DataFrame, sheet_name: str) -> None:
    if len(df.columns) < 2:
        raise ValueError(f"Sheet {sheet_name}: expected at least 2 columns, got {len(df.columns)}.")
    if df.columns[0] != EE_ID_HEADERS[0] or df.columns[1] != EE_ID_HEADERS[1]:
        raise ValueError(
            f"Sheet {sheet_name}: expected first columns {EE_ID_HEADERS!r}, "
            f"got {(df.columns[0], df.columns[1])!r}."
        )


def melt_rolling_sheet(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    _assert_id_headers(out, sheet_name)
    out = out.rename(columns=_ID_RENAME)
    id_vars = list(_ID_RENAME.values())
    value_cols = [c for c in out.columns if c not in id_vars]
    for c in value_cols:
        _split_metric_period(c)
    tidy = out.melt(id_vars=id_vars, var_name="_col", value_name="value")
    parts = tidy["_col"].map(_split_metric_period)
    tidy["measure_breakdown"] = parts.map(lambda t: t[0])
    tidy["rolling_period"] = parts.map(lambda t: t[1])
    tidy = tidy.drop(columns=["_col"])
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce").astype(pd.Float64Dtype())
    tidy["table_id"] = sheet_name
    return tidy[
        [
            "table_id",
            "country_or_region_name",
            "country_or_region_code",
            "measure_breakdown",
            "rolling_period",
            "value",
        ]
    ]


def transform_workbook(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    write_parquet: bool = True,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    for sheet in EE_DATA_SHEETS:
        raw = read_ee_sheet(path, sheet)
        tidy = melt_rolling_sheet(raw, sheet)
        stem = f"ons_ee_fiveyear_{edition_key}_{sheet}_tidy"
        csv_path = output_dir / f"{stem}.csv"
        tidy.to_csv(csv_path, index=False)
        if write_parquet:
            pq_path = output_dir / f"{stem}.parquet"
            write_parquet_atomic(tidy, pq_path, index=False)
        results[sheet] = tidy
        if verbose:
            print(f"Wrote {csv_path}")
            if write_parquet:
                print(f"Wrote {pq_path}")
    return results


def _edition_from_key(key: str) -> EpcEdition:
    if key not in EE_FIVEYEAR_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(EE_FIVEYEAR_EDITIONS))}."
        )
    return EE_FIVEYEAR_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS Energy efficiency of housing, five years rolling: download and tidy all data sheets.",
    )
    p.add_argument("--edition", default="march2025", help="Edition key (default: march2025).")
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
    p.add_argument("--transform-only", action="store_true", help="Only transform; requires --input or raw file.")
    p.add_argument("--force", action="store_true", help="Re-download even if hash matches sidecar.")
    p.add_argument("--skip-hash-check", action="store_true", help="Reuse raw file without verifying SHA-256.")
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
