"""Tests for ONS main fuel / central heating ETL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from ons_mainfuel_config import MAINFUEL_DATA_SHEETS
from ons_mainfuel_etl import transform_sheet


def test_1a_melt():
    df = pd.DataFrame(
        [
            ["E1", "England", 5.0, 10.0],
        ],
        columns=[
            "Country or region code",
            "Country or region name",
            "Mains gas",
            "Electricity",
        ],
    )
    tidy = transform_sheet(df, "1a")
    assert len(tidy) == 2
    assert set(tidy["fuel_or_method"]) == {"Mains gas", "Electricity"}


def test_1b_existing_new():
    df = pd.DataFrame(
        [
            ["E1", "England", 1.0, 2.0],
        ],
        columns=[
            "Country or region code",
            "Country or region name",
            "Existing Mains gas",
            "New Electricity",
        ],
    )
    tidy = transform_sheet(df, "1b")
    assert len(tidy) == 2
    assert set(zip(tidy["dwelling_class"], tidy["fuel_or_method"])) == {
        ("Existing", "Mains gas"),
        ("New", "Electricity"),
    }


def test_1c_property_fuel():
    df = pd.DataFrame(
        [
            ["E1", "England", 3.0, 4.0],
        ],
        columns=[
            "Country or region code",
            "Country or region name",
            "Detached Mains gas",
            "Flats and maisonettes Electricity",
        ],
    )
    tidy = transform_sheet(df, "1c")
    assert len(tidy) == 2
    assert set(zip(tidy["property_type"], tidy["fuel_or_method"])) == {
        ("Detached", "Mains gas"),
        ("Flats and maisonettes", "Electricity"),
    }


def test_transform_all_sheets_minimal_workbook(tmp_path: Path):
    from ons_mainfuel_etl import read_sheet, transform_workbook

    path = tmp_path / "m.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    # Minimal columns that satisfy each sheet's header contract
    for sn in MAINFUEL_DATA_SHEETS:
        ws = wb.create_sheet(sn)
        for _ in range(4):
            ws.append([None])
        if sn == "1a":
            ws.append(
                [
                    "Country or region code",
                    "Country or region name",
                    "Mains gas",
                ]
            )
            ws.append(["E1", "England", 50.0])
        elif sn == "1b":
            ws.append(
                [
                    "Country or region code",
                    "Country or region name",
                    "Existing Mains gas",
                ]
            )
            ws.append(["E1", "England", 50.0])
        elif sn == "1c":
            ws.append(
                [
                    "Country or region code",
                    "Country or region name",
                    "Detached Mains gas",
                ]
            )
            ws.append(["E1", "England", 50.0])
        elif sn == "2a":
            ws.append(
                [
                    "Region code",
                    "Region name",
                    "Local authority district code",
                    "Local authority district name",
                    "Mains gas",
                ]
            )
            ws.append(["R1", "Region", "L1", "LA", 40.0])
        elif sn == "2b":
            ws.append(
                [
                    "Region code",
                    "Region name",
                    "Local authority district code",
                    "Local authority district name",
                    "Existing Mains gas",
                ]
            )
            ws.append(["R1", "Region", "L1", "LA", 40.0])
        elif sn == "3a":
            ws.append(
                [
                    "Local authority district code",
                    "Local authority district name",
                    "Middle super output layer (MSOA) code",
                    "Middle super output layer (MSOA) name",
                    "Mains gas",
                ]
            )
            ws.append(["L1", "LA", "M1", "MSOA", 30.0])
        else:  # 3b
            ws.append(
                [
                    "Local authority district code",
                    "Local authority district name",
                    "Middle super output layer (MSOA) code",
                    "Middle super output layer (MSOA) name",
                    "New Mains gas",
                ]
            )
            ws.append(["L1", "LA", "M1", "MSOA", 30.0])
    wb.save(path)

    out = tmp_path / "out"
    transform_workbook(path, out, edition_key="test", write_parquet=True, verbose=False)
    assert (out / "ons_mainfuel_test_1a_tidy.parquet").is_file()

    raw1a = read_sheet(path, "1a")
    assert len(transform_sheet(raw1a, "1a")) == 1
