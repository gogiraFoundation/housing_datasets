"""Tests for ONS EPC Bands ETL (transform and metadata helpers)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from ons_epc_config import EPC_EDITIONS
from ons_epc_etl import (
    meta_path_for_xlsx,
    read_epc_sheet,
    sha256_file,
    transform_sheet_1a,
    transform_sheet_1b,
    transform_workbook,
    write_meta,
)


def _write_workbook_like_ons(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """Four preamble rows (like ONS tables), then header + data."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, df in sheets.items():
        ws = wb.create_sheet(title)
        for _ in range(4):
            ws.append([None])
        ws.append(list(df.columns))
        for _, row in df.iterrows():
            ws.append(row.tolist())
    wb.save(path)


def _minimal_1a_block() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["E92000001", "England", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
        ],
        columns=[
            "Country or region code",
            "Country or region name",
            "Band A",
            "Band B",
            "Band C",
            "Band D",
            "Band E",
            "Band F",
            "Band G",
        ],
    )


def test_transform_sheet_1a_columns_and_types():
    raw = _minimal_1a_block()
    tidy = transform_sheet_1a(raw)
    assert list(tidy.columns) == [
        "table_id",
        "country_or_region_code",
        "country_or_region_name",
        "epc_band",
        "percentage",
    ]
    assert tidy["table_id"].eq("1a").all()
    assert set(tidy["epc_band"]) == set("ABCDEFG")
    assert tidy["percentage"].dtype == pd.Float64Dtype()
    assert tidy["percentage"].iloc[0] == 1.0


def test_transform_sheet_1a_bad_band_raises():
    bad = _minimal_1a_block()
    bad = bad.rename(columns={"Band G": "Band Z"})
    with pytest.raises(ValueError, match="unexpected column"):
        transform_sheet_1a(bad)


def test_transform_sheet_1b_melt():
    cols = [
        "Country or region code",
        "Country or region name",
        "Detached - Band A",
        "Detached - Band B",
        "Flats and maisonettes - Band A",
    ]
    raw = pd.DataFrame(
        [["E1", "England", 0.1, 0.2, 0.3]],
        columns=cols,
    )
    tidy = transform_sheet_1b(raw)
    assert len(tidy) == 3
    assert set(tidy["property_type"]) == {"Detached", "Flats and maisonettes"}
    assert tidy["percentage"].dtype == pd.Float64Dtype()


def test_read_epc_sheet_skips_header_rows(tmp_path: Path):
    """Simulate ONS layout: four preamble rows then header."""
    path = tmp_path / "mini.xlsx"
    _write_workbook_like_ons(path, {"1a": _minimal_1a_block()})
    loaded = read_epc_sheet(path, "1a")
    tidy = transform_sheet_1a(loaded)
    assert len(tidy) == 7


def test_transform_workbook_writes_outputs(tmp_path: Path):
    path = tmp_path / "wb.xlsx"
    sheets = {
        "1a": _minimal_1a_block(),
        "1b": pd.DataFrame(
            [["E1", "E", 1.0, 2.0]],
            columns=[
                "Country or region code",
                "Country or region name",
                "Detached - Band A",
                "Detached - Band B",
            ],
        ),
        "1c": pd.DataFrame(
            [["E1", "E", 1.0, 2.0]],
            columns=[
                "Country or region code",
                "Country or region name",
                "Pre 1930 - Band A",
                "Pre 1930 - Band B",
            ],
        ),
        "1d": pd.DataFrame(
            [["E1", "E", 1.0, 2.0]],
            columns=[
                "Country or region code",
                "Country or region name",
                "Existing dwellings - Band A",
                "New dwellings - Band A",
            ],
        ),
    }
    _write_workbook_like_ons(path, sheets)
    out = tmp_path / "out"
    transform_workbook(path, out, edition_key="test", write_parquet=True, verbose=False)
    assert (out / "ons_epc_bands_test_1a_tidy.csv").is_file()
    assert (out / "ons_epc_bands_test_1a_tidy.parquet").is_file()


def test_meta_roundtrip(tmp_path: Path):
    x = tmp_path / "f.xlsx"
    x.write_bytes(b"x")
    ed = EPC_EDITIONS["march2025"]
    hx = sha256_file(x)
    mp = write_meta(x, edition=ed, sha256_hex=hx, downloaded_at="2026-01-01T00:00:00Z")
    assert mp == meta_path_for_xlsx(x)
    assert mp.is_file()


def test_download_skipped_when_hash_matches(monkeypatch, tmp_path: Path):
    from ons_epc_etl import download_edition

    dest = tmp_path / "ons_epc_bands_march2025.xlsx"
    dest.write_bytes(b"abc")
    ed = EPC_EDITIONS["march2025"]
    write_meta(dest, edition=ed, sha256_hex=sha256_file(dest), downloaded_at="2026-01-01T00:00:00Z")

    called: list[str] = []

    def fake_get(*_a, **_k):
        called.append("get")
        raise AssertionError("should not download when hash matches")

    monkeypatch.setattr("ons_epc_etl._session", lambda: type("S", (), {"get": fake_get})())
    path, did = download_edition(ed, dest, force=False, skip_hash_check=False)
    assert path == dest
    assert did is False
    assert called == []
