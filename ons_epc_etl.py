"""Extract (ONS download), transform (sheets 1a–1d), and load (CSV/Parquet + JSON metadata)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ons_epc_config import (
    EPC_DATA_SHEETS,
    EPC_TABLE_SKIPROWS,
    EpcEdition,
    EPC_EDITIONS,
    ID_HEADERS,
    OGL_ATTRIBUTION,
    USER_AGENT,
)

_REPO_ROOT = Path(__file__).resolve().parent

_ID_RENAME = {
    ID_HEADERS[0]: "country_or_region_code",
    ID_HEADERS[1]: "country_or_region_name",
}

_BAND_A_RE = re.compile(r"^Band\s+([A-G])$")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.5,
        status_forcelist=(502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def meta_path_for_xlsx(xlsx_path: Path) -> Path:
    return xlsx_path.with_name(xlsx_path.stem + ".meta.json")


def load_meta(path: Path) -> dict[str, Any] | None:
    mp = meta_path_for_xlsx(path)
    if not mp.is_file():
        return None
    with mp.open(encoding="utf-8") as f:
        return json.load(f)


def write_meta(
    xlsx_path: Path,
    *,
    edition: EpcEdition,
    sha256_hex: str,
    downloaded_at: str,
) -> Path:
    payload = {
        "source_url": edition.source_url,
        "dataset_page_url": edition.dataset_page_url,
        "edition_key": edition.key,
        "edition_label": edition.label,
        "downloaded_at": downloaded_at,
        "sha256": sha256_hex,
        "bytes": xlsx_path.stat().st_size,
        "file_name": xlsx_path.name,
        "attribution": OGL_ATTRIBUTION,
    }
    out = meta_path_for_xlsx(xlsx_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return out


def download_edition(
    edition: EpcEdition,
    dest: Path,
    *,
    force: bool = False,
    skip_hash_check: bool = False,
    timeout: tuple[float, float] = (30.0, 120.0),
) -> tuple[Path, bool]:
    """Download workbook to dest. Returns (path, did_download)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.is_file() and not force:
        if skip_hash_check:
            return dest, False
        existing_meta = load_meta(dest)
        current_hash = sha256_file(dest)
        if existing_meta and existing_meta.get("sha256") == current_hash:
            return dest, False

    sess = _session()
    r = sess.get(edition.source_url, stream=True, timeout=timeout)
    r.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
        tmp.replace(dest)
    except Exception:
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        raise

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    hx = sha256_file(dest)
    write_meta(dest, edition=edition, sha256_hex=hx, downloaded_at=now)
    return dest, True


def read_epc_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        skiprows=EPC_TABLE_SKIPROWS,
        header=0,
        engine="openpyxl",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _assert_id_headers(df: pd.DataFrame, sheet_name: str) -> None:
    if len(df.columns) < 2:
        raise ValueError(f"Sheet {sheet_name}: expected at least 2 columns, got {len(df.columns)}.")
    if df.columns[0] != ID_HEADERS[0] or df.columns[1] != ID_HEADERS[1]:
        raise ValueError(
            f"Sheet {sheet_name}: expected first columns {ID_HEADERS!r}, got {(df.columns[0], df.columns[1])!r}."
        )


def _coerce_percentage(s: pd.Series) -> pd.Series:
    out = pd.to_numeric(s, errors="coerce")
    return out.astype(pd.Float64Dtype())


def transform_sheet_1a(df: pd.DataFrame) -> pd.DataFrame:
    _assert_id_headers(df, "1a")
    out = df.rename(columns=_ID_RENAME)
    id_vars = list(_ID_RENAME.values())
    value_cols = [c for c in out.columns if c not in id_vars]
    for c in value_cols:
        if not _BAND_A_RE.match(str(c).strip()):
            raise ValueError(f"Sheet 1a: unexpected column {c!r}; expected 'Band A' … 'Band G'.")
    tidy = out.melt(id_vars=id_vars, var_name="_band_col", value_name="percentage")
    tidy["epc_band"] = tidy["_band_col"].str.replace(r"^Band\s+", "", regex=True)
    tidy = tidy.drop(columns=["_band_col"])
    tidy["table_id"] = "1a"
    tidy["percentage"] = _coerce_percentage(tidy["percentage"])
    return tidy[
        ["table_id", "country_or_region_code", "country_or_region_name", "epc_band", "percentage"]
    ]


def _split_dimension_band(column_name: str) -> tuple[str, str]:
    s = str(column_name).strip()
    if " - Band " not in s:
        raise ValueError(f"Cannot parse dimension/band from column {column_name!r}.")
    left, band = s.rsplit(" - Band ", 1)
    band = band.strip()
    if len(band) != 1 or band not in "ABCDEFG":
        raise ValueError(f"Invalid EPC band in column {column_name!r}.")
    return left.strip(), band


def transform_sheet_1b(df: pd.DataFrame) -> pd.DataFrame:
    _assert_id_headers(df, "1b")
    out = df.rename(columns=_ID_RENAME)
    id_vars = list(_ID_RENAME.values())
    tidy = out.melt(id_vars=id_vars, var_name="_metric", value_name="percentage")
    for c in tidy["_metric"].unique():
        _split_dimension_band(str(c))
    splits = tidy["_metric"].map(_split_dimension_band)
    tidy["property_type"] = splits.map(lambda t: t[0])
    tidy["epc_band"] = splits.map(lambda t: t[1])
    tidy = tidy.drop(columns=["_metric"])
    tidy["table_id"] = "1b"
    tidy["percentage"] = _coerce_percentage(tidy["percentage"])
    return tidy[
        ["table_id", "country_or_region_code", "country_or_region_name", "property_type", "epc_band", "percentage"]
    ]


def transform_sheet_1c(df: pd.DataFrame) -> pd.DataFrame:
    _assert_id_headers(df, "1c")
    out = df.rename(columns=_ID_RENAME)
    id_vars = list(_ID_RENAME.values())
    tidy = out.melt(id_vars=id_vars, var_name="_metric", value_name="percentage")
    splits = tidy["_metric"].map(_split_dimension_band)
    tidy["property_age_band"] = splits.map(lambda t: t[0])
    tidy["epc_band"] = splits.map(lambda t: t[1])
    tidy = tidy.drop(columns=["_metric"])
    tidy["table_id"] = "1c"
    tidy["percentage"] = _coerce_percentage(tidy["percentage"])
    return tidy[
        [
            "table_id",
            "country_or_region_code",
            "country_or_region_name",
            "property_age_band",
            "epc_band",
            "percentage",
        ]
    ]


def transform_sheet_1d(df: pd.DataFrame) -> pd.DataFrame:
    _assert_id_headers(df, "1d")
    out = df.rename(columns=_ID_RENAME)
    id_vars = list(_ID_RENAME.values())
    tidy = out.melt(id_vars=id_vars, var_name="_metric", value_name="percentage")
    splits = tidy["_metric"].map(_split_dimension_band)
    tidy["dwelling_age_class"] = splits.map(lambda t: t[0])
    tidy["epc_band"] = splits.map(lambda t: t[1])
    tidy = tidy.drop(columns=["_metric"])
    tidy["table_id"] = "1d"
    tidy["percentage"] = _coerce_percentage(tidy["percentage"])
    return tidy[
        [
            "table_id",
            "country_or_region_code",
            "country_or_region_name",
            "dwelling_age_class",
            "epc_band",
            "percentage",
        ]
    ]


_TRANSFORMERS = {
    "1a": transform_sheet_1a,
    "1b": transform_sheet_1b,
    "1c": transform_sheet_1c,
    "1d": transform_sheet_1d,
}


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
    for sheet in EPC_DATA_SHEETS:
        raw = read_epc_sheet(path, sheet)
        tidy = _TRANSFORMERS[sheet](raw)
        stem = f"ons_epc_bands_{edition_key}_{sheet}_tidy"
        csv_path = output_dir / f"{stem}.csv"
        tidy.to_csv(csv_path, index=False)
        if write_parquet:
            pq_path = output_dir / f"{stem}.parquet"
            tidy.to_parquet(pq_path, index=False)
        results[sheet] = tidy
        if verbose:
            print(f"Wrote {csv_path}")
            if write_parquet:
                print(f"Wrote {output_dir / f'{stem}.parquet'}")
    return results


def _edition_from_key(key: str) -> EpcEdition:
    if key not in EPC_EDITIONS:
        raise SystemExit(f"Unknown edition {key!r}. Choose one of: {', '.join(sorted(EPC_EDITIONS))}.")
    return EPC_EDITIONS[key]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ONS Individual EPC Bands: download and tidy tables 1a–1d.")
    p.add_argument(
        "--edition",
        default="march2025",
        help="Edition key from ons_epc_config.EPC_EDITIONS (default: march2025).",
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
    p.add_argument("-i", "--input", type=Path, default=None, help="Existing workbook (skips download if set).")
    p.add_argument("--extract-only", action="store_true", help="Only download and write metadata.")
    p.add_argument("--transform-only", action="store_true", help="Only transform; requires --input.")
    p.add_argument("--force", action="store_true", help="Re-download even if hash matches sidecar.")
    p.add_argument(
        "--skip-hash-check",
        action="store_true",
        help="If raw file exists, skip re-download without verifying SHA-256 against sidecar.",
    )
    p.add_argument("--skip-download", action="store_true", help="Use file from --input or default raw path; no HTTP.")
    p.add_argument("--skip-parquet", action="store_true", help="Write CSV only.")
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
