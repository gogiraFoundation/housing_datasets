"""ONS: Median price paid for administrative geographies (all, existing, or newly built dwellings)."""

from __future__ import annotations

from ons_epc_config import EpcEdition

EXISTING_DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "medianhousepricesforadministrativegeographiesexistingdwellings"
)

NEW_DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "medianhousepricesforadministrativegeographiesnewlybuiltdwellings"
)

ALL_DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "medianhousepricesforadministrativegeographies"
)

_BASE_EXISTING = "/peoplepopulationandcommunity/housing/datasets/medianhousepricesforadministrativegeographiesexistingdwellings"
_BASE_NEW = "/peoplepopulationandcommunity/housing/datasets/medianhousepricesforadministrativegeographiesnewlybuiltdwellings"
_BASE_ALL = "/peoplepopulationandcommunity/housing/datasets/medianhousepricesforadministrativegeographies"

# Edition keys match ONS folder names where possible.
# ONS removed .../current/... downloads; the "current" key aliases the latest pinned edition (update when ONS adds a newer folder).
MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current (latest pinned release)",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/yearendingseptember2025/medianpricepaidforadministrativegeographiesexisting.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_current.xlsx",
    ),
    "yearendingseptember2025": EpcEdition(
        key="yearendingseptember2025",
        label="Year ending September 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/yearendingseptember2025/medianpricepaidforadministrativegeographiesexisting.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_yearendingseptember2025.xlsx",
    ),
    "yearendingmarch2025": EpcEdition(
        key="yearendingmarch2025",
        label="Year ending March 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/yearendingmarch2025/medianpricepaidforadministrativegeographiesexisting.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_yearendingmarch2025.xlsx",
    ),
    "yearendingseptember2024": EpcEdition(
        key="yearendingseptember2024",
        label="Year ending September 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/yearendingseptember2024/medianhousepricesforadministrativegeographiesexistingdwellings.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_yearendingseptember2024.xlsx",
    ),
    "yearendingmarch2024": EpcEdition(
        key="yearendingmarch2024",
        label="Year ending March 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/yearendingmarch2024/medianhousepricesforadministrativegeographiesexistingdwellings.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_yearendingmarch2024.xlsx",
    ),
    "2023": EpcEdition(
        key="2023",
        label="2023",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_EXISTING}/2023/hpssamedianpriceexistbyadmingeo.xlsx",
        dataset_page_url=EXISTING_DATASET_PAGE,
        suggested_filename="ons_median_price_existing_admin_2023.xlsx",
    ),
}

MEDIAN_PRICE_NEW_ADMIN_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current (latest pinned release)",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/yearendingseptember2025/medianpricepaidforadministrativegeographiesnew.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_current.xlsx",
    ),
    "yearendingseptember2025": EpcEdition(
        key="yearendingseptember2025",
        label="Year ending September 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/yearendingseptember2025/medianpricepaidforadministrativegeographiesnew.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_yearendingseptember2025.xlsx",
    ),
    "yearendingmarch2025": EpcEdition(
        key="yearendingmarch2025",
        label="Year ending March 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/yearendingmarch2025/medianpricepaidforadministrativegeographiesnew.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_yearendingmarch2025.xlsx",
    ),
    "yearendingseptember2024": EpcEdition(
        key="yearendingseptember2024",
        label="Year ending September 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/yearendingseptember2024/medianhousepricesforadministrativegeographiesnewlybuiltdwellings.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_yearendingseptember2024.xlsx",
    ),
    "yearendingmarch2024": EpcEdition(
        key="yearendingmarch2024",
        label="Year ending March 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/yearendingmarch2024/medianhousepricesforadministrativegeographiesnewlybuiltdwellings.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_yearendingmarch2024.xlsx",
    ),
    "2023": EpcEdition(
        key="2023",
        label="2023",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_NEW}/2023/hpssamedianpricenewbyadmingeo.xlsx",
        dataset_page_url=NEW_DATASET_PAGE,
        suggested_filename="ons_median_price_new_admin_2023.xlsx",
    ),
}

# All-dwellings workbook: ONS used ``medianhousepricesforadministrativegeographies.xlsx`` up to year ending
# September 2024; from year ending March 2025 the download is ``medianpricepaidforadministrativegeographies.xlsx``.
_ALL_XLSX_FROM_MARCH2025 = "medianpricepaidforadministrativegeographies.xlsx"
_ALL_XLSX_LEGACY = "medianhousepricesforadministrativegeographies.xlsx"

MEDIAN_PRICE_ALL_ADMIN_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current (latest pinned release)",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/yearendingseptember2025/{_ALL_XLSX_FROM_MARCH2025}",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_current.xlsx",
    ),
    "yearendingseptember2025": EpcEdition(
        key="yearendingseptember2025",
        label="Year ending September 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/yearendingseptember2025/{_ALL_XLSX_FROM_MARCH2025}",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_yearendingseptember2025.xlsx",
    ),
    "yearendingmarch2025": EpcEdition(
        key="yearendingmarch2025",
        label="Year ending March 2025",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/yearendingmarch2025/{_ALL_XLSX_FROM_MARCH2025}",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_yearendingmarch2025.xlsx",
    ),
    "yearendingseptember2024": EpcEdition(
        key="yearendingseptember2024",
        label="Year ending September 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/yearendingseptember2024/{_ALL_XLSX_LEGACY}",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_yearendingseptember2024.xlsx",
    ),
    "yearendingmarch2024": EpcEdition(
        key="yearendingmarch2024",
        label="Year ending March 2024",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/yearendingmarch2024/{_ALL_XLSX_LEGACY}",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_yearendingmarch2024.xlsx",
    ),
    "2023": EpcEdition(
        key="2023",
        label="2023",
        source_url=f"https://www.ons.gov.uk/file?uri={_BASE_ALL}/2023/hpssamedianpriceallbyadmingeo.xlsx",
        dataset_page_url=ALL_DATASET_PAGE,
        suggested_filename="ons_median_price_all_admin_2023.xlsx",
    ),
}

MEDIAN_PRICE_ADMIN_DATA_SHEETS = tuple(
    f"{row}{col}" for row in ("1", "2", "3", "4") for col in ("a", "b", "c", "d", "e")
)

MEDIAN_PRICE_ADMIN_HEADER_ROW = 2
