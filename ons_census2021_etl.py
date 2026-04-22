"""Census 2021 topic summaries: ONS CMD API metadata, download xlsx+csv, tidy Parquet/CSV."""

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

from housing_data.atomic_io import write_parquet_atomic
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ons_census2021_config import (
    API_BASE,
    CENSUS_DATASETS,
    POPULATION_DERIVED_STEM,
    CensusTopicSummary,
    human_dataset_page,
)
from ons_epc_config import OGL_ATTRIBUTION, USER_AGENT

_REPO_ROOT = Path(__file__).resolve().parent

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


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


def raw_xlsx_path(raw_dir: Path, c: CensusTopicSummary) -> Path:
    return raw_dir / f"ons_census2021_{c.dataset_id}_ed{c.edition}_v{c.pinned_version}.xlsx"


def raw_csv_path(raw_dir: Path, c: CensusTopicSummary) -> Path:
    return raw_dir / f"ons_census2021_{c.dataset_id}_ed{c.edition}_v{c.pinned_version}.csv"


def fetch_version_metadata(c: CensusTopicSummary, *, timeout: tuple[float, float] = (30.0, 120.0)) -> dict[str, Any]:
    url = f"{API_BASE}/datasets/{c.dataset_id}/editions/{c.edition}/versions/{c.pinned_version}"
    r = _session().get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def write_meta_xlsx(
    xlsx_path: Path,
    *,
    c: CensusTopicSummary,
    sha256_hex: str,
    downloaded_at: str,
    api_json: dict[str, Any],
    csv_href: str,
    xls_href: str,
) -> Path:
    payload = {
        "source_url": xls_href,
        "csv_url": csv_href,
        "dataset_page_url": human_dataset_page(c.dataset_id, c.edition, c.pinned_version),
        "bulletin_url": c.bulletin_url,
        "dataset_id": c.dataset_id,
        "edition": c.edition,
        "version": c.pinned_version,
        "api_self_url": api_json.get("links", {}).get("self", {}).get("href", ""),
        "edition_key": c.key,
        "edition_label": c.label,
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


def download_url_to_file(url: str, dest: Path, *, timeout: tuple[float, float] = (30.0, 300.0)) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    sess = _session()
    r = sess.get(url, stream=True, timeout=timeout)
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


def _slug_dim(name: str, used: set[str]) -> str:
    base = _SLUG_SAFE.sub("_", str(name).strip().lower()).strip("_")
    if not base:
        base = "dim"
    out = base[:72]
    n = 0
    cand = out
    while cand in used:
        n += 1
        cand = f"{out}_{n}"
    used.add(cand)
    return cand


def normalize_census_csv(df: pd.DataFrame) -> pd.DataFrame:
    """ONS CMD CSV: LA code, LA name, …dimensions…, Observation."""
    if df.empty:
        raise ValueError("Empty CSV.")
    cols = [str(c).strip() for c in df.columns]
    if len(cols) < 3:
        raise ValueError(f"Expected at least 3 columns; got {cols!r}.")
    last = cols[-1]
    if str(last).strip().lower() != "observation":
        raise ValueError(f"Expected last column 'Observation'; got {last!r}.")
    used: set[str] = set()
    rename: dict[str, str] = {cols[0]: "lad_code", cols[1]: "lad_name", last: "observation"}
    used.update({"lad_code", "lad_name", "observation"})
    for c in cols[2:-1]:
        rename[c] = _slug_dim(c, used)
    out = df.rename(columns=rename).copy()
    out["lad_code"] = out["lad_code"].astype(str).str.strip()
    out["lad_name"] = out["lad_name"].astype(str).str.strip()
    out["observation"] = pd.to_numeric(out["observation"], errors="coerce")
    return out


def tidy_stem(c: CensusTopicSummary) -> str:
    return f"ons_census2021_{c.key}_tidy"


def transform_csv_to_tidy(
    csv_path: Path,
    c: CensusTopicSummary,
    *,
    write_parquet: bool = True,
    output_dir: Path | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    output_dir = Path(output_dir or _REPO_ROOT / "data" / "processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    tidy = normalize_census_csv(df)
    tidy["dataset_id"] = c.dataset_id
    tidy["census_year"] = 2021
    stem = tidy_stem(c)
    csv_out = output_dir / f"{stem}.csv"
    tidy.to_csv(csv_out, index=False)
    if write_parquet:
        write_parquet_atomic(tidy, output_dir / f"{stem}.parquet", index=False)
    if verbose:
        print(f"Wrote {csv_out}")
        if write_parquet:
            print(f"Wrote {output_dir / f'{stem}.parquet'}")
    return tidy


def write_la_population_2021(
    sex_tidy: pd.DataFrame,
    output_dir: Path,
    *,
    write_parquet: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Sum Female + Male per LA from TS008 sex table (usual residents)."""
    pop = (
        sex_tidy.groupby(["lad_code", "lad_name"], as_index=False)["observation"]
        .sum()
        .rename(columns={"observation": "population"})
    )
    pop["year"] = 2021
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = POPULATION_DERIVED_STEM
    pop.to_csv(output_dir / f"{stem}.csv", index=False)
    if write_parquet:
        write_parquet_atomic(pop, output_dir / f"{stem}.parquet", index=False)
    if verbose:
        print(f"Wrote {output_dir / f'{stem}.csv'}")
        if write_parquet:
            print(f"Wrote {output_dir / f'{stem}.parquet'}")
    return pop


def download_and_transform_one(
    c: CensusTopicSummary,
    raw_dir: Path,
    output_dir: Path,
    *,
    force: bool = False,
    skip_hash_check: bool = False,
    write_parquet: bool = True,
    verbose: bool = True,
    extract_only: bool = False,
) -> tuple[Path, pd.DataFrame | None]:
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    api_json = fetch_version_metadata(c)
    dls = api_json.get("downloads") or {}
    xls = dls.get("xls") or {}
    csv = dls.get("csv") or {}
    xls_href = xls.get("href")
    csv_href = csv.get("href")
    if not xls_href or not csv_href:
        raise RuntimeError(f"No xls/csv href in API response for {c.dataset_id}.")

    xlsx_path = raw_xlsx_path(raw_dir, c)
    csv_path = raw_csv_path(raw_dir, c)

    need_download = force or not xlsx_path.is_file() or not csv_path.is_file()
    if not need_download and not skip_hash_check:
        meta = load_meta(xlsx_path)
        current = sha256_file(xlsx_path)
        if meta and meta.get("sha256") == current:
            need_download = False
        else:
            need_download = True

    if need_download:
        if verbose:
            print(f"Downloading {c.dataset_id} v{c.pinned_version} …")
        download_url_to_file(xls_href, xlsx_path)
        download_url_to_file(csv_href, csv_path)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        hx = sha256_file(xlsx_path)
        write_meta_xlsx(
            xlsx_path,
            c=c,
            sha256_hex=hx,
            downloaded_at=now,
            api_json=api_json,
            csv_href=csv_href,
            xls_href=xls_href,
        )
        if verbose:
            print(f"Wrote {xlsx_path} + metadata")
    elif verbose:
        print(f"Using existing {xlsx_path.name}")

    if extract_only:
        return xlsx_path, None

    tidy = transform_csv_to_tidy(csv_path, c, write_parquet=write_parquet, output_dir=output_dir, verbose=verbose)
    if c.key == "sex_ts008":
        write_la_population_2021(tidy, output_dir, write_parquet=write_parquet, verbose=verbose)
    return xlsx_path, tidy


def transform_only(
    c: CensusTopicSummary,
    raw_dir: Path,
    output_dir: Path,
    *,
    write_parquet: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    csv_path = raw_csv_path(raw_dir, c)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing raw CSV: {csv_path}")
    tidy = transform_csv_to_tidy(csv_path, c, write_parquet=write_parquet, output_dir=output_dir, verbose=verbose)
    if c.key == "sex_ts008":
        write_la_population_2021(tidy, output_dir, write_parquet=write_parquet, verbose=verbose)
    return tidy


def _parse_dataset_arg(arg: str) -> list[CensusTopicSummary]:
    if arg == "all":
        return list(CENSUS_DATASETS.values())
    if arg not in CENSUS_DATASETS:
        raise SystemExit(f"Unknown --dataset {arg!r}. Use: all, {', '.join(sorted(CENSUS_DATASETS))}.")
    return [CENSUS_DATASETS[arg]]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset",
        default="all",
        help=f"Dataset key or 'all' (default: all). Keys: {', '.join(sorted(CENSUS_DATASETS))}.",
    )
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "raw",
        help="Directory for downloaded .xlsx, .csv, and .meta.json.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "processed",
        help="Directory for tidy CSV/Parquet outputs.",
    )
    p.add_argument("--extract-only", action="store_true", help="Only download raw files and metadata.")
    p.add_argument("--transform-only", action="store_true", help="Transform existing raw CSV only (no HTTP).")
    p.add_argument("--force", action="store_true", help="Re-download even if hash matches.")
    p.add_argument("--skip-hash-check", action="store_true", help="Reuse raw files without SHA-256 check.")
    p.add_argument("--skip-parquet", action="store_true", help="CSV only.")
    p.add_argument("-q", "--quiet", action="store_true", help="Less logging.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.extract_only and args.transform_only:
        raise SystemExit("Choose at most one of --extract-only and --transform-only.")
    verbose = not args.quiet
    items = _parse_dataset_arg(args.dataset)
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.output_dir)

    for c in items:
        if args.transform_only:
            transform_only(
                c,
                raw_dir,
                out_dir,
                write_parquet=not args.skip_parquet,
                verbose=verbose,
            )
        else:
            download_and_transform_one(
                c,
                raw_dir,
                out_dir,
                force=args.force,
                skip_hash_check=args.skip_hash_check,
                write_parquet=not args.skip_parquet,
                verbose=verbose,
                extract_only=args.extract_only,
            )


if __name__ == "__main__":
    main()
