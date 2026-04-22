from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from housing_data.atomic_io import write_parquet_atomic


def test_write_parquet_atomic_replace(tmp_path: Path) -> None:
    dest = tmp_path / "out.parquet"
    write_parquet_atomic(pd.DataFrame({"x": [1]}), dest, index=False)
    assert dest.is_file()
    assert not (tmp_path / "out.parquet.tmp").exists()
    write_parquet_atomic(pd.DataFrame({"x": [2, 3]}), dest, index=False)
    r = pd.read_parquet(dest)
    assert list(r["x"]) == [2, 3]


def test_write_parquet_atomic_cleanup_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "out.parquet"

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", boom)
    with pytest.raises(OSError):
        write_parquet_atomic(pd.DataFrame({"x": [1]}), dest, index=False)
    assert not dest.is_file()
    assert not (tmp_path / "out.parquet.tmp").is_file()
