from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from housing_api.registry import DatasetMeta, safe_processed_path


def load_manifest(repo_root: Path) -> dict[str, Any] | None:
    p = repo_root / "data" / "processed" / "processed_manifest.json"
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
    rel = str(path.relative_to(repo_root))
    man = load_manifest(repo_root)
    mrow = manifest_row_for_file(man, rel)
    columns = None
    if mrow and isinstance(mrow.get("columns"), list):
        columns = [str(c) for c in mrow["columns"]]
    return True, st.st_size, mtime_iso, columns


def read_parquet_all(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def dataframe_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Serialize rows for JSON responses (ISO datetimes; NaN as null).

    Uses ``DataFrame.to_json`` for consistent typing; for very large exports prefer CSV streaming.
    """
    return json.loads(df.to_json(orient="records", date_format="iso"))


def compute_etag(components: list[str]) -> str:
    h = hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()[:32]
    return f'"{h}"'
