"""Pinned ONS Individual EPC Bands (England and Wales) edition URLs and labels.

This is the same suite ONS describes under energy efficiency / EPC statistics: **EPC bands**
(A–G) report the **distribution of dwellings by energy-efficiency rating band** (derived from
EPC scores). Editions (e.g. March 2025, ~39 KB xlsx) are released with the same contact and
release cycle as other Housing Analysis energy-efficiency datasets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpcEdition:
    """One published edition of the EPC bands workbook."""

    key: str
    label: str
    source_url: str
    dataset_page_url: str
    suggested_filename: str


DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "individualenergyperformancecertificateepcbandsenglandandwales"
)

EPC_EDITIONS: dict[str, EpcEdition] = {
    "march2025": EpcEdition(
        key="march2025",
        label="March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "individualenergyperformancecertificateepcbandsenglandandwales/march2025/"
            "individualepcbandsenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_epc_bands_march2025.xlsx",
    ),
    "march2024": EpcEdition(
        key="march2024",
        label="March 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "individualenergyperformancecertificateepcbandsenglandandwales/march2024/"
            "individualepcbandsenglandandwales.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_epc_bands_march2024.xlsx",
    ),
    "march2023": EpcEdition(
        key="march2023",
        label="March 2023",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
            "individualenergyperformancecertificateepcbandsenglandandwales/march2023/"
            "individualenergyperformancecertificateepcbandsenglandandwalesuptomarch2023.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_epc_bands_march2023.xlsx",
    ),
}

OGL_ATTRIBUTION = (
    "Contains public sector information licensed under the Open Government Licence v3.0. "
    "Source: Office for National Statistics."
)

USER_AGENT = "housing_datasets/1.0 (research; respectful use of ons.gov.uk)"

EPC_TABLE_SKIPROWS = 4

EPC_DATA_SHEETS = ("1a", "1b", "1c", "1d")

ID_HEADERS = ("Country or region code", "Country or region name")
