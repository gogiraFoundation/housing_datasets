"""ONS: House price per m² and per room (England and Wales) — download and tidy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from housing_data.atomic_io import write_parquet_atomic
from ons_epc_config import EpcEdition
from ons_epc_etl import download_edition
from ons_house_m2_room_config import HOUSE_M2_DATA_SHEETS, HOUSE_M2_HEADER_ROW, HOUSE_M2_ROOM_EDITIONS

_REPO_ROOT = Path(__file__).resolve().parent

# (metric, dwelling_segment, geography_level)
HOUSE_M2_TABLE_META: dict[str, tuple[str, str, str]] = {
    "Table1": ("price_per_sqm", "house_and_flat", "region"),
    "Table2": ("price_per_sqm", "flats_only", "region"),
    "Table3": ("price_per_sqm", "excluding_flats", "region"),
    "Table4": ("price_per_room", "house_and_flat", "region"),
    "Table5": ("price_per_room", "flats_only", "region"),
    "Table6": ("price_per_room", "excluding_flats", "region"),
    "Table7": ("price_per_room", "house_and_flat", "local_authority"),
    "Table8": ("price_per_room", "flats_only", "local_authority"),
    "Table9": ("price_per_room", "excluding_flats", "local_authority"),
    "Table10": ("price_per_sqm", "house_and_flat", "local_authority"),
    "Table11": ("price_per_sqm", "flats_only", "local_authority"),
    "Table12": ("price_per_sqm", "excluding_flats", "local_authority"),
}

_YEAR_RE = re.compile(r"^20\d{2}$")


def _engine_for_path(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".xls":
        return "xlrd"
    if suf in (".xlsx", ".xlsm"):
        return "openpyxl"
    raise ValueError(f"Unsupported workbook format: {path.suffix}")


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=HOUSE_M2_HEADER_ROW,
        engine=_engine_for_path(path),
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _rename_geo_columns(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    out = df.dropna(axis=1, how="all").copy()
    cols = list(out.columns)
    if not cols:
        raise ValueError(f"Sheet {sheet}: empty columns.")
    c0 = cols[0].strip()
    if c0 in ("Area code", "Region code"):
        out = out.rename(columns={cols[0]: "region_code"})
    else:
        raise ValueError(f"Sheet {sheet}: unexpected first column {c0!r}.")
    c1 = cols[1].strip()
    if "region" in c1.lower() and "name" in c1.lower():
        out = out.rename(columns={cols[1]: "region_name"})
    else:
        raise ValueError(f"Sheet {sheet}: unexpected second column {c1!r}.")

    meta = HOUSE_M2_TABLE_META.get(sheet)
    if meta and meta[2] == "local_authority":
        if len(cols) < 4:
            raise ValueError(f"Sheet {sheet}: expected LA columns.")
        out = out.rename(columns={cols[2]: "la_code", cols[3]: "la_name"})
    return out


def _year_columns(df: pd.DataFrame, sheet: str) -> list[str]:
    years: list[str] = []
    for c in df.columns:
        s = str(c).strip()
        if _YEAR_RE.match(s):
            years.append(c)
        elif isinstance(c, (int, float)) and not pd.isna(c) and 2000 <= int(float(c)) <= 2100:
            years.append(c)
    if not years:
        raise ValueError(f"Sheet {sheet}: no year columns found.")
    return years


def transform_sheet(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    if sheet not in HOUSE_M2_TABLE_META:
        raise ValueError(f"Unknown sheet {sheet!r}")
    metric, segment, geo_level = HOUSE_M2_TABLE_META[sheet]
    work = _rename_geo_columns(df, sheet)
    id_cols = ["region_code", "region_name"]
    if geo_level == "local_authority":
        id_cols = ["region_code", "region_name", "la_code", "la_name"]
    ycols = _year_columns(work, sheet)
    for c in id_cols:
        if c not in work.columns:
            raise ValueError(f"Sheet {sheet}: missing {c}.")
    sub = work[id_cols + ycols].copy()
    tidy = sub.melt(id_vars=id_cols, var_name="year", value_name="value")
    tidy["year"] = pd.to_numeric(tidy["year"], errors="coerce").astype("Int64")
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce").astype(pd.Float64Dtype())
    tidy["metric"] = metric
    tidy["dwelling_segment"] = segment
    tidy["geography_level"] = geo_level
    tidy["table_id"] = sheet
    tidy = tidy.dropna(subset=["region_code"], how="any")
    return tidy[
        [
            "table_id",
            "metric",
            "dwelling_segment",
            "geography_level",
            *id_cols,
            "year",
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
    for sheet in HOUSE_M2_DATA_SHEETS:
        raw = read_sheet(path, sheet)
        tidy = transform_sheet(raw, sheet)
        stem = f"ons_house_m2_room_{edition_key}_{sheet}_tidy"
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
    if key not in HOUSE_M2_ROOM_EDITIONS:
        raise SystemExit(
            f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(HOUSE_M2_ROOM_EDITIONS))}."
        )
    return HOUSE_M2_ROOM_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ONS house price per m² / per room (England and Wales): download and tidy.",
    )
    p.add_argument("--edition", default="2004to2016", help="Edition key (default: 2004to2016).")
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
