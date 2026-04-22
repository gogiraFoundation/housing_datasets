from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_parquet_page_duckdb(
    path: Path,
    *,
    columns: list[str] | None,
    limit: int,
    offset: int,
) -> pd.DataFrame:
    """Read a single page from a Parquet file using DuckDB (LIMIT/OFFSET).

    Column names must already be validated against the file schema.
    """
    import duckdb

    cols_sql = "*" if not columns else ", ".join(_sql_ident(c) for c in columns)
    q = f"SELECT {cols_sql} FROM read_parquet(?) LIMIT ? OFFSET ?"
    con = duckdb.connect(database=":memory:")
    try:
        return con.execute(q, [str(path), limit, offset]).df()
    finally:
        con.close()


def _sql_ident(name: str) -> str:
    if not name or any(ch in name for ch in ('"', "\x00", "\n", "\r")):
        raise ValueError(f"Invalid column name: {name!r}")
    escaped = name.replace('"', '""')
    return f'"{escaped}"'
