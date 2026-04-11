"""ONS House Price Explorer — download and tidy (legacy LA tool workbook)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_house_price_explorer_config import (
    HOUSE_PRICE_EXPLORER_DATA_SHEETS,
    HOUSE_PRICE_EXPLORER_EDITIONS,
    sheet_slug,
)

_REPO_ROOT = Path(__file__).resolve().parent


def _read_xls(path: Path, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, engine="xlrd")


def transform_price_or_count_totals(df: pd.DataFrame, sheet: str, *, table_kind: str) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "LA Name" not in df.columns or "LA Code" not in df.columns:
        raise ValueError(f"Sheet {sheet}: expected LA Name and LA Code.")
    id_vars = ["LA Name", "LA Code"]
    tidy = df.melt(id_vars=id_vars, var_name="year", value_name="value")
    tidy = tidy.rename(columns={"LA Name": "la_name", "LA Code": "la_code"})
    tidy["year"] = pd.to_numeric(tidy["year"], errors="coerce").astype("Int64")
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce").astype(pd.Float64Dtype())
    tidy["table_id"] = sheet
    tidy["table_kind"] = table_kind
    return tidy[["table_id", "table_kind", "la_code", "la_name", "year", "value"]]


def transform_count_by_type(path: Path, sheet: str) -> pd.DataFrame:
    df2 = pd.read_excel(path, sheet_name=sheet, header=[0, 1], engine="xlrd")
    id_df = df2.iloc[:, :2].copy()
    id_df.columns = ["la_name", "la_code"]
    rest2 = df2.iloc[:, 2:].copy()
    if rest2.shape[1] == 0:
        raise ValueError(f"Sheet {sheet}: no data columns.")
    rest2.columns = [f"{int(float(a))}_{b}" for a, b in rest2.columns]
    tidy = pd.concat([id_df, rest2], axis=1)
    tidy = tidy.melt(id_vars=["la_name", "la_code"], var_name="year_property", value_name="value")
    split = tidy["year_property"].str.split("_", n=1, expand=True)
    tidy["year"] = pd.to_numeric(split[0], errors="coerce").astype("Int64")
    tidy["property_type"] = split[1]
    tidy = tidy.drop(columns=["year_property"])
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce").astype(pd.Float64Dtype())
    tidy["table_id"] = sheet
    tidy["table_kind"] = "count_by_type"
    return tidy[["table_id", "table_kind", "la_code", "la_name", "year", "property_type", "value"]]


def transform_type_price_snapshot(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "LA Code" not in df.columns or "LA Name" not in df.columns:
        raise ValueError(f"Sheet {sheet}: expected LA Code and LA Name.")
    id_vars = ["LA Code", "LA Name"]
    tidy = df.melt(id_vars=id_vars, var_name="property_type", value_name="median_price_gbp")
    tidy = tidy.rename(columns={"LA Code": "la_code", "LA Name": "la_name"})
    tidy["median_price_gbp"] = pd.to_numeric(tidy["median_price_gbp"], errors="coerce").astype(pd.Float64Dtype())
    tidy["table_id"] = sheet
    tidy["table_kind"] = "median_by_type_snapshot"
    return tidy[["table_id", "table_kind", "la_code", "la_name", "property_type", "median_price_gbp"]]


def transform_sheet(path: Path, sheet: str) -> pd.DataFrame:
    if sheet in ("1. Price Data", "2. Count Data Totals"):
        df = _read_xls(path, sheet)
        kind = "median_price" if sheet.startswith("1") else "sale_count_total"
        return transform_price_or_count_totals(df, sheet, table_kind=kind)
    if sheet == "3. Count Data":
        return transform_count_by_type(path, sheet)
    if sheet == "4.Type Price Data":
        df = _read_xls(path, sheet)
        return transform_type_price_snapshot(df, sheet)
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
    for sheet in HOUSE_PRICE_EXPLORER_DATA_SHEETS:
        tidy = transform_sheet(path, sheet)
        stem = f"ons_house_price_explorer_{edition_key}_{sheet_slug(sheet)}_tidy"
        csv_path = output_dir / f"{stem}.csv"
        tidy.to_csv(csv_path, index=False)
        pq_path = output_dir / f"{stem}.parquet"
        if write_parquet:
            tidy.to_parquet(pq_path, index=False)
        results[sheet] = tidy
        if verbose:
            print(f"Wrote {csv_path}")
            if write_parquet:
                print(f"Wrote {pq_path}")
    return results


def _edition_from_key(key: str) -> EpcEdition:
    if key not in HOUSE_PRICE_EXPLORER_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(HOUSE_PRICE_EXPLORER_EDITIONS))}."
        )
    return HOUSE_PRICE_EXPLORER_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ONS House Price Explorer (legacy .xls): download and tidy.")
    p.add_argument("--edition", default="current", help="Edition key (default: current).")
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "raw",
        help="Directory for downloaded .xls and .meta.json.",
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
