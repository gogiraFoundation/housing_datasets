"""ONS: House Price Statistics for Small Areas by national park (sales counts and prices)."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "housepricestatisticsforsmallareasbynationalpark"
)

_BASE = "/peoplepopulationandcommunity/housing/datasets/housepricestatisticsforsmallareasbynationalpark"

# Data tables only (exclude Cover, Contents).
NATIONAL_PARK_HPSSA_DATA_SHEETS = tuple(f"{row}{col}" for row in ("1", "2", "3") for col in ("a", "b", "c", "d", "e"))

# Row with Area Code / Area Name and period headers (same layout as HPSSA median price workbooks).
NATIONAL_PARK_HPSSA_HEADER_ROW = 2

NATIONAL_PARK_HPSSA_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current (latest pinned release)",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE}/yearendingseptember2025/housepricestatisticsnp.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_national_park_hpssa_current.xlsx",
    ),
    "yearendingseptember2025": EpcEdition(
        key="yearendingseptember2025",
        label="Year ending September 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE}/yearendingseptember2025/housepricestatisticsnp.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_national_park_hpssa_yearendingseptember2025.xlsx",
    ),
    "yearendingmarch2025": EpcEdition(
        key="yearendingmarch2025",
        label="Year ending March 2025",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE}/yearendingmarch2025/housepricenationalparks.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_national_park_hpssa_yearendingmarch2025.xlsx",
    ),
    "yearendingseptember2024": EpcEdition(
        key="yearendingseptember2024",
        label="Year ending September 2024",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE}/yearendingseptember2024/housepricestatisticsforsmallareasbynationalpark.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_national_park_hpssa_yearendingseptember2024.xlsx",
    ),
}
