"""ONS: Main fuel type or method of heating (central heating), England and Wales — download and tidy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_mainfuel_config import (
    MAINFUEL_DATA_SHEETS,
    MAINFUEL_EDITIONS,
    MAINFUEL_PROPERTY_TYPES_ORDER,
    MAINFUEL_TABLE_SKIPROWS,
)

_REPO_ROOT = Path(__file__).resolve().parent

_HEADERS_COUNTRY = ("Country or region code", "Country or region name")
_HEADERS_REGION_LA = (
    "Region code",
    "Region name",
    "Local authority district code",
    "Local authority district name",
)
_HEADERS_LA_MSOA = (
    "Local authority district code",
    "Local authority district name",
    "Middle super output layer (MSOA) code",
    "Middle super output layer (MSOA) name",
)

_RENAME_COUNTRY = {
    _HEADERS_COUNTRY[0]: "country_or_region_code",
    _HEADERS_COUNTRY[1]: "country_or_region_name",
}
_RENAME_REGION_LA = {
    _HEADERS_REGION_LA[0]: "region_code",
    _HEADERS_REGION_LA[1]: "region_name",
    _HEADERS_REGION_LA[2]: "local_authority_district_code",
    _HEADERS_REGION_LA[3]: "local_authority_district_name",
}
_RENAME_LA_MSOA = {
    _HEADERS_LA_MSOA[0]: "local_authority_district_code",
    _HEADERS_LA_MSOA[1]: "local_authority_district_name",
    _HEADERS_LA_MSOA[2]: "msoa_code",
    _HEADERS_LA_MSOA[3]: "msoa_name",
}

_EXISTING_NEW = re.compile(r"^(Existing|New)\s+(.+)$")


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=MAINFUEL_TABLE_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _assert_headers(df: pd.DataFrame, expected: tuple[str, ...], sheet: str) -> None:
    exp = list(expected)
    got = list(df.columns[: len(exp)])
    if got != exp:
        raise ValueError(f"Sheet {sheet}: expected columns {exp!r}, got {got!r}.")


def _coerce_value(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(pd.Float64Dtype())


def melt_fuel_only(df: pd.DataFrame, sheet: str, excel_headers: tuple[str, ...], rename: dict[str, str]) -> pd.DataFrame:
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    _assert_headers(out, excel_headers, sheet)
    out = out.rename(columns=rename)
    id_vars = list(rename.values())
    value_cols = [c for c in out.columns if c not in id_vars]
    if not value_cols:
        raise ValueError(f"Sheet {sheet}: no value columns.")
    tidy = out.melt(id_vars=id_vars, var_name="fuel_or_method", value_name="value")
    tidy["value"] = _coerce_value(tidy["value"])
    tidy["table_id"] = sheet
    return tidy


def melt_existing_new_fuel(
    df: pd.DataFrame,
    sheet: str,
    excel_headers: tuple[str, ...],
    rename: dict[str, str],
) -> pd.DataFrame:
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    _assert_headers(out, excel_headers, sheet)
    out = out.rename(columns=rename)
    id_vars = list(rename.values())
    tidy = out.melt(id_vars=id_vars, var_name="_col", value_name="value")
    en: list[tuple[str, str]] = []
    for raw in tidy["_col"]:
        m = _EXISTING_NEW.match(str(raw).strip())
        if not m:
            raise ValueError(f"Sheet {sheet}: column {raw!r} does not match Existing/New + fuel.")
        en.append((m.group(1), m.group(2).strip()))
    tidy["dwelling_class"] = [a for a, _ in en]
    tidy["fuel_or_method"] = [b for _, b in en]
    tidy = tidy.drop(columns=["_col"])
    tidy["value"] = _coerce_value(tidy["value"])
    tidy["table_id"] = sheet
    return tidy


def _split_property_fuel(column_name: str) -> tuple[str, str]:
    s = str(column_name).strip()
    for prop in sorted(MAINFUEL_PROPERTY_TYPES_ORDER, key=len, reverse=True):
        prefix = prop + " "
        if s.startswith(prefix):
            return prop, s[len(prefix) :].strip()
    raise ValueError(f"Cannot parse property type + fuel from column {column_name!r}.")


def melt_property_fuel_1c(df: pd.DataFrame) -> pd.DataFrame:
    sheet = "1c"
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    _assert_headers(out, _HEADERS_COUNTRY, sheet)
    out = out.rename(columns=_RENAME_COUNTRY)
    id_vars = list(_RENAME_COUNTRY.values())
    value_cols = [c for c in out.columns if c not in id_vars]
    for c in value_cols:
        _split_property_fuel(c)
    tidy = out.melt(id_vars=id_vars, var_name="_col", value_name="value")
    pf = tidy["_col"].map(_split_property_fuel)
    tidy["property_type"] = pf.map(lambda x: x[0])
    tidy["fuel_or_method"] = pf.map(lambda x: x[1])
    tidy = tidy.drop(columns=["_col"])
    tidy["value"] = _coerce_value(tidy["value"])
    tidy["table_id"] = sheet
    return tidy


def transform_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if sheet == "1a":
        t = melt_fuel_only(df, sheet, _HEADERS_COUNTRY, _RENAME_COUNTRY)
        return t[
            ["table_id", "country_or_region_code", "country_or_region_name", "fuel_or_method", "value"]
        ]
    if sheet == "1b":
        t = melt_existing_new_fuel(df, sheet, _HEADERS_COUNTRY, _RENAME_COUNTRY)
        return t[
            [
                "table_id",
                "country_or_region_code",
                "country_or_region_name",
                "dwelling_class",
                "fuel_or_method",
                "value",
            ]
        ]
    if sheet == "1c":
        t = melt_property_fuel_1c(df)
        return t[
            [
                "table_id",
                "country_or_region_code",
                "country_or_region_name",
                "property_type",
                "fuel_or_method",
                "value",
            ]
        ]
    if sheet == "2a":
        t = melt_fuel_only(df, sheet, _HEADERS_REGION_LA, _RENAME_REGION_LA)
        return t[
            [
                "table_id",
                "region_code",
                "region_name",
                "local_authority_district_code",
                "local_authority_district_name",
                "fuel_or_method",
                "value",
            ]
        ]
    if sheet == "2b":
        t = melt_existing_new_fuel(df, sheet, _HEADERS_REGION_LA, _RENAME_REGION_LA)
        return t[
            [
                "table_id",
                "region_code",
                "region_name",
                "local_authority_district_code",
                "local_authority_district_name",
                "dwelling_class",
                "fuel_or_method",
                "value",
            ]
        ]
    if sheet == "3a":
        t = melt_fuel_only(df, sheet, _HEADERS_LA_MSOA, _RENAME_LA_MSOA)
        return t[
            [
                "table_id",
                "local_authority_district_code",
                "local_authority_district_name",
                "msoa_code",
                "msoa_name",
                "fuel_or_method",
                "value",
            ]
        ]
    if sheet == "3b":
        t = melt_existing_new_fuel(df, sheet, _HEADERS_LA_MSOA, _RENAME_LA_MSOA)
        return t[
            [
                "table_id",
                "local_authority_district_code",
                "local_authority_district_name",
                "msoa_code",
                "msoa_name",
                "dwelling_class",
                "fuel_or_method",
                "value",
            ]
        ]
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
    for sheet in MAINFUEL_DATA_SHEETS:
        raw = read_sheet(path, sheet)
        tidy = transform_sheet(raw, sheet)
        stem = f"ons_mainfuel_{edition_key}_{sheet}_tidy"
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
    if key not in MAINFUEL_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(MAINFUEL_EDITIONS))}."
        )
    return MAINFUEL_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS main fuel type / central heating: download and tidy tables 1a–3b.",
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
