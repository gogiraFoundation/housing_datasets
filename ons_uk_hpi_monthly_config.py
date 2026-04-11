"""ONS: UK House Price Index — monthly price statistics — edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/"
    "ukhousepriceindexmonthlypricestatistics"
)

UK_HPI_MONTHLY_EDITIONS: dict[str, EpcEdition] = {
    "march2026": EpcEdition(
        key="march2026",
        label="March 2026",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/"
            "ukhousepriceindexmonthlypricestatistics/25march2026/"
            "ukhousepriceindexmonthlypricestatistics.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_uk_hpi_monthly_march2026.xlsx",
    ),
    "february2026": EpcEdition(
        key="february2026",
        label="February 2026",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/"
            "ukhousepriceindexmonthlypricestatistics/18february2026/"
            "ukhousepriceindexmonthlypricestatistics.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_uk_hpi_monthly_february2026.xlsx",
    ),
    "january2026": EpcEdition(
        key="january2026",
        label="January 2026",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/"
            "ukhousepriceindexmonthlypricestatistics/21january2026/"
            "ukhousepriceindexmonthlypricestatistics.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_uk_hpi_monthly_january2026.xlsx",
    ),
}

# Data worksheets (exclude Cover, Contents, Notes).
UK_HPI_DATA_SHEETS = tuple(str(i) for i in range(1, 12))

UK_HPI_TIME_HEADER_ROW = 2
UK_HPI_SPLIT_HEADER_ROW = 4
UK_HPI_LA_HEADER_ROW = 2
