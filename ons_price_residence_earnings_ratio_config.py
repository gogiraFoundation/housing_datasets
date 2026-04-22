"""ONS: House price to residence-based earnings ratio (median and lower quartiles, England and Wales)."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "ratioofhousepricetoresidencebasedearningslowerquartileandmedian"
)

_BASE_CURRENT = (
    "/peoplepopulationandcommunity/housing/datasets/"
    "ratioofhousepricetoresidencebasedearningslowerquartileandmedian/current"
)

PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current edition",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE_CURRENT}/aff2ratioofhousepricetoresidencebasedearnings.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_price_residence_earnings_ratio_current.xlsx",
    ),
}

# Same layout as workplace-based affordability workbook (data tables 1a–6c only).
PRICE_RESIDENCE_EARNINGS_RATIO_DATA_SHEETS = tuple(f"{n}{c}" for n in range(1, 7) for c in ("a", "b", "c"))

PRICE_RESIDENCE_EARNINGS_RATIO_HEADER_ROW = 1
