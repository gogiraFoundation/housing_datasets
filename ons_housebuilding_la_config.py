"""ONS UK house building by local authority (starts/completions) edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority"
)

HOUSEBUILDING_LA_EDITIONS: dict[str, EpcEdition] = {
    "fye_march2025": EpcEdition(
        key="fye_march2025",
        label="Financial year ending March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority/"
            "financialyearendingmarch2025/uklocalauthorityhousebuilding.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_housebuilding_la_fye_march2025.xlsx",
    ),
    "fye_march2024": EpcEdition(
        key="fye_march2024",
        label="Financial year ending March 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority/"
            "financialyearendingmarch2024/uklocalauthorityhousebuilding.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_housebuilding_la_fye_march2024.xlsx",
    ),
    "fye_march2023": EpcEdition(
        key="fye_march2023",
        label="Financial year ending March 2023",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority/"
            "financialyearendingmarch2023/uklocalauthorityhousebuilding.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_housebuilding_la_fye_march2023.xlsx",
    ),
    "fye_march2022": EpcEdition(
        key="fye_march2022",
        label="Financial year ending March 2022",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "housebuildingukpermanentdwellingsstartedandcompletedbylocalauthority/"
            "financialyearendingmarch2022/uklocalauthorityhousebuilding.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_housebuilding_la_fye_march2022.xlsx",
    ),
}

HOUSEBUILDING_LA_SHEETS = {
    "starts": "UK_Starts",
    "completions": "UK_Completions",
}

HOUSEBUILDING_LA_SKIPROWS = 5
