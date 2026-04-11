"""ONS: House Price Explorer (median prices and sale counts by LA, 1995–2013)."""

from __future__ import annotations

import re

from ons_epc_config import EpcEdition


def sheet_slug(sheet_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", sheet_name.lower().strip()).strip("_")

DATASET_PAGE = "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/housepriceexplorer"

HOUSE_PRICE_EXPLORER_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "housepriceexplorer/current/housepriceexplorer_tcm77-395364.xls"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_house_price_explorer_current.xls",
    ),
}

# Data sheets (exclude intro/tool/metadata).
HOUSE_PRICE_EXPLORER_DATA_SHEETS = (
    "1. Price Data",
    "2. Count Data Totals",
    "3. Count Data",
    "4.Type Price Data",
)

HOUSE_PRICE_EXPLORER_SHEET_SLUGS: dict[str, str] = {s: sheet_slug(s) for s in HOUSE_PRICE_EXPLORER_DATA_SHEETS}
