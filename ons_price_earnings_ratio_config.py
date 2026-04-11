"""ONS: House price to workplace-based earnings ratio (median and lower quartiles, England and Wales)."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "ratioofhousepricetoworkplacebasedearningslowerquartileandmedian"
)

_BASE_CURRENT = (
    "/peoplepopulationandcommunity/housing/datasets/"
    "ratioofhousepricetoworkplacebasedearningslowerquartileandmedian/current"
)

PRICE_EARNINGS_RATIO_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current edition",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE_CURRENT}/aff1ratioofhousepricetoworkplacebasedearnings.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_price_earnings_ratio_current.xlsx",
    ),
}

# Data tables only (exclude Contents, Metadata, Terms and Conditions).
PRICE_EARNINGS_RATIO_DATA_SHEETS = tuple(f"{n}{c}" for n in range(1, 7) for c in ("a", "b", "c"))

# Second row of each sheet (0-based index 1) holds Code / Name (or LA hierarchy) and period headers.
PRICE_EARNINGS_RATIO_HEADER_ROW = 1
