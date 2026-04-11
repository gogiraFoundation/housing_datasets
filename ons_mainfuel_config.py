"""ONS: Main fuel type or method of heating (central heating), England and Wales — edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "mainfueltypeormethodofheatingusedincentralheatingenglandandwales"
)

MAINFUEL_EDITIONS: dict[str, EpcEdition] = {
    "march2025": EpcEdition(
        key="march2025",
        label="March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "mainfueltypeormethodofheatingusedincentralheatingenglandandwales/march2025/"
            "mainfueltypeenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_mainfuel_march2025.xlsx",
    ),
    "march2024": EpcEdition(
        key="march2024",
        label="March 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "mainfueltypeormethodofheatingusedincentralheatingenglandandwales/march2024/"
            "mainfueltypeenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_mainfuel_march2024.xlsx",
    ),
    "march2023": EpcEdition(
        key="march2023",
        label="March 2023",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "mainfueltypeormethodofheatingusedincentralheatingenglandandwales/march2023/"
            "mainfueltypeormethodusedincentralheatingenglandandwalesuptomarch2023.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_mainfuel_march2023.xlsx",
    ),
}

MAINFUEL_TABLE_SKIPROWS = 4

MAINFUEL_DATA_SHEETS = ("1a", "1b", "1c", "2a", "2b", "3a", "3b")

# Property type prefixes in table 1c (longest first for matching).
MAINFUEL_PROPERTY_TYPES_ORDER = (
    "Flats and maisonettes",
    "Semi-detached",
    "Terraced",
    "Detached",
)
