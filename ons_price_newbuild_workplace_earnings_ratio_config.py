"""ONS: House price (newly built dwellings) to workplace-based earnings ratio (England and Wales)."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "housepricenewlybuiltdwellingstoworkplacebasedearningsratio"
)

_BASE_CURRENT = (
    "/peoplepopulationandcommunity/housing/datasets/"
    "housepricenewlybuiltdwellingstoworkplacebasedearningsratio/current"
)

NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS: dict[str, EpcEdition] = {
    "current": EpcEdition(
        key="current",
        label="Current edition",
        source_url=(
            "https://www.ons.gov.uk/file?uri="
            f"{_BASE_CURRENT}/aff3ratioofhousepricenewlybuilttoworkplacebasedearnings.xlsx"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_price_newbuild_workplace_earnings_ratio_current.xlsx",
    ),
}
