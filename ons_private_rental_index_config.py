"""ONS: Index of Private Housing Rental Prices — time-series CSV edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = "https://www.ons.gov.uk/datasets/index-private-housing-rental-prices"

PRIVATE_RENTAL_INDEX_EDITIONS: dict[str, EpcEdition] = {
    "v41": EpcEdition(
        key="v41",
        label="February 2024 (version 41)",
        source_url=(
            "https://download.ons.gov.uk/downloads/datasets/index-private-housing-rental-prices/"
            "editions/time-series/versions/41.csv"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_private_rental_index_v41.csv",
    ),
}
