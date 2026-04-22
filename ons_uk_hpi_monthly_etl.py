"""ONS: UK House Price Index monthly price statistics — download and tidy."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_uk_hpi_monthly_config import (
    UK_HPI_DATA_SHEETS,
    UK_HPI_LA_HEADER_ROW,
    UK_HPI_MONTHLY_EDITIONS,
    UK_HPI_SPLIT_HEADER_ROW,
    UK_HPI_TIME_HEADER_ROW,
)

_REPO_ROOT = Path(__file__).resolve().parent

_TIME_SHEETS = frozenset({"1", "2", "3", "7"})
_SPLIT_SHEETS = frozenset({"4", "5", "6"})
_LA_SHEETS = frozenset({"8", "9", "10", "11"})

_LA_COUNTRY: dict[str, str] = {
    "8": "England",
    "9": "Wales",
    "10": "Scotland",
    "11": "Northern Ireland",
}


def _strip_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def _coerce_numeric(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        s = s.replace(r"\[x\]", pd.NA, regex=True)
    return pd.to_numeric(s, errors="coerce").astype(pd.Float64Dtype())


def transform_time_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if "Time period" not in df.columns:
        raise ValueError(f"Sheet {sheet}: expected 'Time period' column.")
    id_vars = ["Time period"]
    value_cols = [c for c in df.columns if c not in id_vars]
    if not value_cols:
        raise ValueError(f"Sheet {sheet}: no value columns.")
    tidy = df.melt(id_vars=id_vars, var_name="geography", value_name="value")
    tidy["value"] = _coerce_numeric(tidy["value"])
    tidy["table_id"] = sheet
    return tidy.rename(columns={"Time period": "time_period"})[
        ["table_id", "time_period", "geography", "value"]
    ]


def transform_split_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    c = list(df.columns)
    if len(c) < 7:
        raise ValueError(f"Sheet {sheet}: expected at least 7 columns for split layout.")
    left = df[[c[0], c[1], c[2]]].copy()
    left.columns = ["time_period", c[1], c[2]]
    t1 = left.melt(id_vars=["time_period"], var_name="series", value_name="value")
    t1["table_block"] = "level_gbp"
    t1["value"] = _coerce_numeric(t1["value"])

    right = df[[c[4], c[5], c[6]]].copy()
    right.columns = ["time_period", c[5], c[6]]
    t2 = right.melt(id_vars=["time_period"], var_name="series", value_name="value")
    t2["table_block"] = "annual_pct_change"
    t2["value"] = _coerce_numeric(t2["value"])

    tidy = pd.concat([t1, t2], ignore_index=True)
    tidy["table_id"] = sheet
    return tidy[["table_id", "table_block", "time_period", "series", "value"]]


def transform_la_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if "AreaCode" not in df.columns or "RegionName" not in df.columns:
        raise ValueError(f"Sheet {sheet}: expected AreaCode and RegionName.")
    value_cols = [c for c in df.columns if c not in ("AreaCode", "RegionName")]
    if not value_cols:
        raise ValueError(f"Sheet {sheet}: no metric columns.")
    sub = df[["AreaCode", "RegionName", *value_cols]].copy()
    sub = sub.rename(columns={"AreaCode": "area_code", "RegionName": "area_name"})
    tidy = sub.melt(id_vars=["area_code", "area_name"], var_name="metric", value_name="value")
    tidy["value"] = _coerce_numeric(tidy["value"])
    tidy["table_id"] = sheet
    tidy["country_group"] = _LA_COUNTRY[sheet]
    return tidy[["table_id", "country_group", "area_code", "area_name", "metric", "value"]]


def read_sheet(path: Path, sheet: str) -> pd.DataFrame:
    if sheet in _TIME_SHEETS:
        df = pd.read_excel(
            path,
            sheet_name=sheet,
            header=UK_HPI_TIME_HEADER_ROW,
            engine="openpyxl",
        )
        return _strip_columns(df)
    if sheet in _SPLIT_SHEETS:
        df = pd.read_excel(
            path,
            sheet_name=sheet,
            header=UK_HPI_SPLIT_HEADER_ROW,
            engine="openpyxl",
        )
        return _strip_columns(df)
    if sheet in _LA_SHEETS:
        df = pd.read_excel(
            path,
            sheet_name=sheet,
            header=UK_HPI_LA_HEADER_ROW,
            engine="openpyxl",
        )
        return _strip_columns(df)
    raise ValueError(f"Unknown sheet {sheet!r}")


def transform_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if sheet in _TIME_SHEETS:
        return transform_time_sheet(df, sheet)
    if sheet in _SPLIT_SHEETS:
        return transform_split_sheet(df, sheet)
    if sheet in _LA_SHEETS:
        return transform_la_sheet(df, sheet)
    raise ValueError(f"Unknown sheet {sheet!r}")


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
    for sheet in UK_HPI_DATA_SHEETS:
        raw = read_sheet(path, sheet)
        tidy = transform_sheet(raw, sheet)
        stem = f"ons_uk_hpi_monthly_{edition_key}_{sheet}_tidy"
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
    if key not in UK_HPI_MONTHLY_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(UK_HPI_MONTHLY_EDITIONS))}."
        )
    return UK_HPI_MONTHLY_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS UK HPI monthly price statistics: download and tidy.",
    )
    p.add_argument("--edition", default="march2026", help="Edition key (default: march2026).")
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
