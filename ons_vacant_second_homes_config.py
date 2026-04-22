"""ONS: Number of vacant dwellings and second homes (no usual residents), Census 2021 — workbook URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "numberofvacantdwellingsandsecondhomeswithnousualresidents"
)

_BASE = "/peoplepopulationandcommunity/housing/datasets/numberofvacantdwellingsandsecondhomeswithnousualresidents"

# Data tables only (exclude Cover_sheet, Table_of_contents, Notes).
VACANT_SECOND_HOMES_DATA_SHEETS: tuple[str, ...] = ("1a", "1b", "1c", "2", "3", "4", "5")

# Third row (0-based index 2) is the column header row on all data sheets.
VACANT_SECOND_HOMES_HEADER_ROW = 2

VACANT_SECOND_HOMES_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current edition (released 27 October 2023)",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE}/current/numberofvacantdwellingsandsecondhomes.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_vacant_second_homes_current.xlsx",
    ),
}
