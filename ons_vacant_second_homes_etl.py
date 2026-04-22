"""ONS: Vacant dwellings and second homes (no usual residents), Census 2021 — download and tidy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_vacant_second_homes_config import (
    VACANT_SECOND_HOMES_DATA_SHEETS,
    VACANT_SECOND_HOMES_EDITIONS,
    VACANT_SECOND_HOMES_HEADER_ROW,
)

_REPO_ROOT = Path(__file__).resolve().parent

_HEADLINE_VACANT = "Vacant dwellings"
_HEADLINE_SECOND = "Second homes (with no usual residents)"


def _snake_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower().strip()).strip("_")


def infer_geography_level(code: str) -> str:
    c = str(code).strip().upper()
    if len(c) < 3:
        return "unknown"
    if c.startswith("K04"):
        return "england_and_wales"
    if c.startswith("E92") or c.startswith("W92"):
        return "country"
    if c.startswith("E12"):
        return "region"
    if c.startswith("E06") or c.startswith("W06"):
        return "local_authority_district"
    if c.startswith("E07") or c.startswith("E08") or c.startswith("E09"):
        return "local_authority_district"
    if c.startswith("E02") or c.startswith("W02"):
        return "msoa"
    if c.startswith("E01") or c.startswith("W01"):
        return "lsoa"
    return "other"


def _coerce_count(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        s = s.replace(r"^\s*$", pd.NA, regex=True)
        s = s.replace("c", pd.NA, regex=False)
    return pd.to_numeric(s, errors="coerce").astype(pd.Int64Dtype())


def read_data_sheet(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=VACANT_SECOND_HOMES_HEADER_ROW,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    if len(df.columns) < 2:
        raise ValueError(f"Sheet {sheet}: expected at least 2 columns.")
    df = df.rename(columns={df.columns[0]: "area_code", df.columns[1]: "area_name"})
    return df


def transform_sheet_1abc(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    for col in (_HEADLINE_VACANT, _HEADLINE_SECOND):
        if col not in df.columns:
            raise ValueError(f"Sheet {sheet}: missing column {col!r}. Got: {list(df.columns)}")
    id_vars = ["area_code", "area_name"]
    mapping = {_HEADLINE_VACANT: "vacant", _HEADLINE_SECOND: "second_home"}
    parts: list[pd.DataFrame] = []
    for col, group in mapping.items():
        sub = df[id_vars + [col]].rename(columns={col: "value"})
        sub["dwelling_group"] = group
        sub["breakdown_type"] = pd.NA
        sub["breakdown_label"] = pd.NA
        parts.append(sub)
    out = pd.concat(parts, ignore_index=True)
    out["table_id"] = sheet
    out["geography_level"] = out["area_code"].map(infer_geography_level)
    out["value"] = _coerce_count(out["value"])
    return out[
        ["table_id", "geography_level", "area_code", "area_name", "dwelling_group", "breakdown_type", "breakdown_label", "value"]
    ]


def transform_sheet_accommodation(df: pd.DataFrame, sheet: str, *, dwelling_group: str) -> pd.DataFrame:
    id_vars = ["area_code", "area_name"]
    value_cols = [c for c in df.columns if c not in id_vars]
    if not value_cols:
        raise ValueError(f"Sheet {sheet}: no value columns.")
    tidy = df.melt(id_vars=id_vars, var_name="_raw_dim", value_name="value")
    tidy["breakdown_type"] = "accommodation_type"
    tidy["breakdown_label"] = tidy["_raw_dim"].map(_snake_header)
    tidy = tidy.drop(columns=["_raw_dim"])
    tidy["table_id"] = sheet
    tidy["dwelling_group"] = dwelling_group
    tidy["geography_level"] = tidy["area_code"].map(infer_geography_level)
    tidy["value"] = _coerce_count(tidy["value"])
    return tidy[
        ["table_id", "geography_level", "area_code", "area_name", "dwelling_group", "breakdown_type", "breakdown_label", "value"]
    ]


def transform_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if sheet in ("1a", "1b", "1c"):
        return transform_sheet_1abc(df, sheet)
    if sheet == "2":
        return transform_sheet_accommodation(df, sheet, dwelling_group="vacant")
    if sheet == "3":
        t = transform_sheet_accommodation(df, sheet, dwelling_group="vacant")
        t["breakdown_type"] = "bedrooms"
        return t
    if sheet == "4":
        return transform_sheet_accommodation(df, sheet, dwelling_group="second_home")
    if sheet == "5":
        t = transform_sheet_accommodation(df, sheet, dwelling_group="second_home")
        t["breakdown_type"] = "bedrooms"
        return t
    raise ValueError(f"Unknown sheet {sheet!r}")


def transform_workbook(
    path: Path,
    output_dir: Path,
    edition_key: str,
    *,
    file_prefix: str = "ons_vacant_second_homes",
    write_parquet: bool = True,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    for sheet in VACANT_SECOND_HOMES_DATA_SHEETS:
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
    if key not in VACANT_SECOND_HOMES_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(VACANT_SECOND_HOMES_EDITIONS))}."
        )
    return VACANT_SECOND_HOMES_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "ONS Census 2021: vacant dwellings and second homes (no usual residents) "
            "(tables 1a–1c, 2–5)."
        ),
    )
    p.add_argument(
        "--edition",
        default="current",
        help="Edition key from ons_vacant_second_homes_config (default: current).",
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
