"""ONS: House Price Statistics for Small Areas by national park — download and tidy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_national_park_hpssa_config import (
    NATIONAL_PARK_HPSSA_DATA_SHEETS,
    NATIONAL_PARK_HPSSA_EDITIONS,
    NATIONAL_PARK_HPSSA_HEADER_ROW,
)

_REPO_ROOT = Path(__file__).resolve().parent

_PROPERTY_BAND = {"a": "all", "b": "detached", "c": "semi_detached", "d": "terraced", "e": "flats_maisonettes"}
_MEASURE = {"1": "sales_count", "2": "median_price_gbp", "3": "lower_quartile_price_gbp"}


def _meta_for_sheet(sheet: str) -> tuple[str, str]:
    if len(sheet) != 2:
        raise ValueError(f"Unexpected sheet name {sheet!r}")
    row, col = sheet[0], sheet[1]
    return _MEASURE[row], _PROPERTY_BAND[col]


def read_data_sheet(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=NATIONAL_PARK_HPSSA_HEADER_ROW,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _period_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if str(c).strip().startswith("Year ending")]


def _snake_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower().strip()).strip("_")


def transform_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    measure, property_band = _meta_for_sheet(sheet)
    periods = _period_columns(df)
    if not periods:
        raise ValueError(f"Sheet {sheet}: no 'Year ending …' columns.")
    id_vars = [c for c in df.columns if c not in periods]
    if not id_vars:
        raise ValueError(f"Sheet {sheet}: no geography identifier columns.")
    tidy = df.melt(id_vars=id_vars, var_name="period_label", value_name="value")
    ren = {c: _snake_header(c) for c in id_vars}
    tidy = tidy.rename(columns=ren)
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce").astype(pd.Float64Dtype())
    tidy["table_id"] = sheet
    tidy["measure"] = measure
    tidy["geography_level"] = "national_park"
    tidy["property_band"] = property_band
    geo_cols = [ren[c] for c in id_vars]
    return tidy[
        ["table_id", "measure", "geography_level", "property_band", *geo_cols, "period_label", "value"]
    ]


def transform_workbook(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    file_prefix: str = "ons_national_park_hpssa",
    write_parquet: bool = True,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    for sheet in NATIONAL_PARK_HPSSA_DATA_SHEETS:
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
    if key not in NATIONAL_PARK_HPSSA_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(NATIONAL_PARK_HPSSA_EDITIONS))}."
        )
    return NATIONAL_PARK_HPSSA_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "ONS House Price Statistics for Small Areas by national park: "
            "sales counts (1a–1e), median price (2a–2e), lower quartile price (3a–3e)."
        ),
    )
    p.add_argument(
        "--edition",
        default="yearendingseptember2025",
        help="Edition key from ons_national_park_hpssa_config (default: yearendingseptember2025).",
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
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.output_dir)
    verbose = not args.quiet

    xlsx_path = Path(args.input) if args.input is not None else raw_dir / edition.suggested_filename

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
