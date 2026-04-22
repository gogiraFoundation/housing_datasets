from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from housing_api.registry import DatasetMeta, safe_processed_path
from housing_api.settings import resolved_processed_dir


def load_manifest(repo_root: Path) -> dict[str, Any] | None:
    p = resolved_processed_dir(repo_root) / "processed_manifest.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def manifest_row_for_file(manifest: dict[str, Any] | None, rel_path: str) -> dict[str, Any] | None:
    if not manifest:
        return None
    for row in manifest.get("processed_parquet", []):
        if row.get("path") == rel_path:
            return row
    return None


def dataset_disk_meta(repo_root: Path, meta: DatasetMeta) -> tuple[bool, int | None, str | None, list[str] | None]:
    """available, size_bytes, mtime_iso, columns from manifest or None."""
    path = safe_processed_path(repo_root, meta)
    if path is None or not path.is_file():
        return False, None, None, None
    st = path.stat()
    mtime_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    rel = f"data/processed/{meta.filename}"
    man = load_manifest(repo_root)
    mrow = manifest_row_for_file(man, rel)
    columns = None
    if mrow and isinstance(mrow.get("columns"), list):
        columns = [str(c) for c in mrow["columns"]]
    return True, st.st_size, mtime_iso, columns


def parquet_num_rows(path: Path) -> int | None:
    try:
        md = pq.ParquetFile(path).metadata
        if md is None:
            return None
        return md.num_rows
    except OSError:
        return None


def parquet_schema_column_names(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def validate_columns_subset(path: Path, columns: list[str] | None) -> list[str] | None:
    if not columns:
        return None
    names = parquet_schema_column_names(path)
    unknown = [c for c in columns if c not in names]
    if unknown:
        raise ValueError(f"Unknown column(s): {unknown!r}; valid names include {sorted(names)[:20]}…")
    return columns


def read_parquet_all(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if columns:
        return pd.read_parquet(path, columns=columns)
    return pd.read_parquet(path)


def _json_cell(v: Any) -> Any:
    if v is None:
        return None
    if v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        if isinstance(v, pd.Timestamp) and pd.isna(v):
            return None
        ts = pd.Timestamp(v) if not isinstance(v, pd.Timestamp) else v
        if pd.isna(ts):
            return None
        return ts.isoformat()
    if isinstance(v, date) and not isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", errors="replace")
    try:
        if hasattr(v, "item") and callable(v.item):
            out = v.item()
            if isinstance(out, float) and (math.isnan(out) or math.isinf(out)):
                return None
            if out is None:
                return None
            if isinstance(out, (pd.Timestamp, datetime, date)):
                return _json_cell(out)
            if isinstance(out, (int, float, str, bool)):
                return out
    except (ValueError, AttributeError):
        pass
    if isinstance(v, (int, float, str, bool)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    return str(v)


def dataframe_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Serialize rows for JSON responses (ISO datetimes; NaN/NA as null).

    Avoids ``to_json`` + ``json.loads`` round-trip.
    """
    records = df.to_dict(orient="records")
    out: list[dict[str, Any]] = []
    for row in records:
        out.append({k: _json_cell(v) for k, v in row.items()})
    return out


def compute_etag(components: list[str]) -> str:
    h = hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()[:32]
    return f'"{h}"'
