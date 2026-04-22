from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_parquet_atomic(df: pd.DataFrame, path: Path | str, **to_parquet_kw: Any) -> None:
    """Write Parquet to ``*.tmp`` then replace into ``path`` so readers never see a half file."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        df.to_parquet(tmp, **to_parquet_kw)
        tmp.replace(dest)
    except Exception:
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        raise
