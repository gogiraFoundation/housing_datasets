"""ONS UK house building by country (starts/completions) edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "ukhousebuildingpermanentdwellingsstartedandcompleted"
)

HOUSEBUILDING_COUNTRY_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current edition",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "ukhousebuildingpermanentdwellingsstartedandcompleted/current/indicatorsofukhousebuilding.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_housebuilding_country_current.xlsx",
    ),
}

HOUSEBUILDING_COUNTRY_TABLES = (
    "1a",
    "1b",
    "1c",
    "1d",
    "1e",
    "1f",
    "2a",
    "2b",
    "2c",
    "2d",
    "2e",
    "3a",
    "3b",
    "3c",
    "3d",
    "3e",
)

HOUSEBUILDING_COUNTRY_SKIPROWS = 5
