"""ONS: Median energy efficiency score, England and Wales — download and tidy all data sheets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_median_eescore_config import (
    MEDIAN_EESCORE_DATA_SHEETS,
    MEDIAN_EESCORE_EDITIONS,
    MEDIAN_TABLE_SKIPROWS,
    SHEET_ID_LAYOUT,
)

_REPO_ROOT = Path(__file__).resolve().parent

_COUNTRY = ("Country or region code", "Country or region name")
_REGION_LA = (
    "Region code",
    "Region name",
    "Local authority district code",
    "Local authority district name",
)
_LA_MSOA = (
    "Local authority district code",
    "Local authority district name",
    "Middle super output layer (MSOA) code",
    "Middle super output layer (MSOA) name",
)
_PC = ("Parliamentary constituency code", "Parliamentary constituency name")

_RENAME_COUNTRY = {
    _COUNTRY[0]: "country_or_region_code",
    _COUNTRY[1]: "country_or_region_name",
}
_RENAME_REGION_LA = {
    _REGION_LA[0]: "region_code",
    _REGION_LA[1]: "region_name",
    _REGION_LA[2]: "local_authority_district_code",
    _REGION_LA[3]: "local_authority_district_name",
}
_RENAME_LA_MSOA = {
    _LA_MSOA[0]: "local_authority_district_code",
    _LA_MSOA[1]: "local_authority_district_name",
    _LA_MSOA[2]: "msoa_code",
    _LA_MSOA[3]: "msoa_name",
}
_RENAME_PC = {_PC[0]: "parliamentary_constituency_code", _PC[1]: "parliamentary_constituency_name"}


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=MEDIAN_TABLE_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _assert_id_headers(got: list[str], expected: tuple[str, ...], sheet: str) -> None:
    exp = list(expected)
    if got[: len(exp)] != exp:
        raise ValueError(f"Sheet {sheet}: expected columns to start with {exp!r}, got {got[: len(exp)]!r}.")


def _coerce_value(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(pd.Float64Dtype())


def melt_median_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    layout = SHEET_ID_LAYOUT[sheet]
    out = df.dropna(axis=1, how="all").dropna(how="all").copy()
    cols = list(out.columns)

    if layout == "country":
        _assert_id_headers(cols, _COUNTRY, sheet)
        out = out.rename(columns=_RENAME_COUNTRY)
        id_vars = list(_RENAME_COUNTRY.values())
    elif layout == "region_la":
        _assert_id_headers(cols, _REGION_LA, sheet)
        out = out.rename(columns=_RENAME_REGION_LA)
        id_vars = list(_RENAME_REGION_LA.values())
    elif layout == "la_msoa":
        _assert_id_headers(cols, _LA_MSOA, sheet)
        out = out.rename(columns=_RENAME_LA_MSOA)
        id_vars = list(_RENAME_LA_MSOA.values())
    elif layout == "pc":
        _assert_id_headers(cols, _PC, sheet)
        out = out.rename(columns=_RENAME_PC)
        id_vars = list(_RENAME_PC.values())
    else:
        raise ValueError(f"Unknown layout {layout!r} for sheet {sheet}.")

    value_cols = [c for c in out.columns if c not in id_vars]
    if not value_cols:
        raise ValueError(f"Sheet {sheet}: no measure columns.")
    tidy = out.melt(id_vars=id_vars, var_name="measure_label", value_name="median_score")
    tidy["median_score"] = _coerce_value(tidy["median_score"])
    tidy["table_id"] = sheet
    base_cols = ["table_id"] + id_vars + ["measure_label", "median_score"]
    return tidy[base_cols]


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
    for sheet in MEDIAN_EESCORE_DATA_SHEETS:
        raw = read_sheet(path, sheet)
        tidy = melt_median_sheet(raw, sheet)
        stem = f"ons_median_eescore_{edition_key}_{sheet}_tidy"
        csv_path = output_dir / f"{stem}.csv"
        tidy.to_csv(csv_path, index=False)
        if write_parquet:
            pq_path = output_dir / f"{stem}.parquet"
            tidy.to_parquet(pq_path, index=False)
        results[sheet] = tidy
        if verbose:
            print(f"Wrote {csv_path}")
            if write_parquet:
                print(f"Wrote {pq_path}")
    return results


def _edition_from_key(key: str) -> EpcEdition:
    if key not in MEDIAN_EESCORE_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(MEDIAN_EESCORE_EDITIONS))}."
        )
    return MEDIAN_EESCORE_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS median energy efficiency score: download and tidy all data sheets.",
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
    p.add_argument("--transform-only", action="store_true", help="Only transform; needs workbook on disk.")
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
