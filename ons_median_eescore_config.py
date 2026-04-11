"""ONS: Median energy efficiency score, England and Wales — edition URLs and sheet layout keys."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "medianenergyefficiencyscoreenglandandwales"
)

MEDIAN_EESCORE_EDITIONS: dict[str, EpcEdition] = {
    "march2025": EpcEdition(
        key="march2025",
        label="March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "medianenergyefficiencyscoreenglandandwales/march2025/"
            "medianenergyefficiencyscoreenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_median_eescore_march2025.xlsx",
    ),
    "march2024": EpcEdition(
        key="march2024",
        label="March 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "medianenergyefficiencyscoreenglandandwales/march2024/"
            "medianenergyefficiencyscoreenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_median_eescore_march2024.xlsx",
    ),
    "march2023": EpcEdition(
        key="march2023",
        label="March 2023",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "medianenergyefficiencyscoreenglandandwales/march2023/"
            "medianenergyefficiencyscoreenglandandwalesuptomarch2023.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_median_eescore_march2023.xlsx",
    ),
}

# Skip Cover, Contents, Notes — all other named sheets are data tables.
MEDIAN_EESCORE_DATA_SHEETS = (
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
    "4a",
    "4b",
    "4c",
    "4d",
    "5a",
    "5b",
    "5c",
    "5d",
)

MEDIAN_TABLE_SKIPROWS = 4

# How to interpret leading identifier columns before measure columns (see joins/README.md).
SHEET_ID_LAYOUT: dict[str, str] = {
    "1a": "country",
    "1b": "country",
    "1c": "country",
    "1d": "country",
    "1e": "country",
    "1f": "country",
    "2a": "region_la",
    "2b": "region_la",
    "2c": "region_la",
    "2d": "region_la",
    "2e": "region_la",
    "3a": "la_msoa",
    "3b": "la_msoa",
    "3c": "la_msoa",
    "4a": "pc",
    "4b": "pc",
    "4c": "pc",
    "4d": "pc",
    "5a": "country",
    "5b": "country",
    "5c": "region_la",
    "5d": "region_la",
}
