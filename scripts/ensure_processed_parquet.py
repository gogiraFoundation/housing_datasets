#!/usr/bin/env python3
"""Fail fast when processed parquet files are missing."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def resolved_processed_dir(repo_root: Path) -> Path:
    raw = os.environ.get("HOUSING_PROCESSED_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (repo_root / "data" / "processed").resolve()


def main() -> int:
    p = argparse.ArgumentParser(description="Ensure processed parquet files exist before app boot.")
    p.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum number of *.parquet files required (default: 1).",
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    processed = resolved_processed_dir(repo_root)

    if args.min_count < 0:
        print("[ensure] --min-count must be >= 0")
        return 2
    if not processed.is_dir():
        print(f"[ensure] Missing processed directory: {processed}")
        return 1

    files = sorted(processed.glob("*.parquet"))
    count = len(files)
    if count < args.min_count:
        print(
            f"[ensure] Expected at least {args.min_count} parquet file(s) in {processed}, found {count}. "
            "Run ETL first (for example: scripts/build_deploy_parquet.sh) or set HOUSING_PROCESSED_DIR "
            "to the directory that contains built parquet artefacts."
        )
        return 1

    print(f"[ensure] OK: found {count} parquet file(s) in {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
