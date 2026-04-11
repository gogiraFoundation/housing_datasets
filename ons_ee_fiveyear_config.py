"""ONS: Energy efficiency of housing, England and Wales, five years rolling — edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

# Same dataclass as EPC bands (key, label, source_url, dataset_page_url, suggested_filename).

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "energyefficiencyofhousingenglandandwalesfiveyearsrolling"
)

EE_FIVEYEAR_EDITIONS: dict[str, EpcEdition] = {
    "march2025": EpcEdition(
        key="march2025",
        label="March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "energyefficiencyofhousingenglandandwalesfiveyearsrolling/march2025/"
            "energyefficiencyofhousingenglandandwalesfiverollingyears.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_ee_fiveyear_march2025.xlsx",
    ),
    "march2024": EpcEdition(
        key="march2024",
        label="March 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "energyefficiencyofhousingenglandandwalesfiveyearsrolling/march2024/"
            "energyefficiencyofhousingenglandandwalesfiverollingyears.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_ee_fiveyear_march2024.xlsx",
    ),
    "march2023": EpcEdition(
        key="march2023",
        label="March 2023",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "energyefficiencyofhousingenglandandwalesfiveyearsrolling/march2023/"
            "energyefficiencyofhousingenglandandwalesfiverollingyearsuptomarch2023.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_ee_fiveyear_march2023.xlsx",
    ),
    "march2022": EpcEdition(
        key="march2022",
        label="March 2022",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "energyefficiencyofhousingenglandandwalesfiveyearsrolling/march2022/"
            "energyefficiencyofhousingenglandandwalesfiverollingyearsuptomarch2022.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_ee_fiveyear_march2022.xlsx",
    ),
}

# Same preamble rows as other ONS housing EPC workbooks.
EE_TABLE_SKIPROWS = 4

# Data sheets only (not Cover / Contents / Notes).
EE_DATA_SHEETS = (
    "1a",
    "1b",
    "1c",
    "1d",
    "2a",
    "2b",
    "3a",
    "3b",
    "3c",
    "3d",
    "3e",
    "3f",
    "3g",
    "3h",
)

# This workbook lists region *name* before *code* (unlike Individual EPC Bands).
EE_ID_HEADERS = ("Country or region name", "Country or region code")
