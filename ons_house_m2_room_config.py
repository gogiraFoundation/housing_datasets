"""ONS: House price per square metre and per room (England and Wales) — edition URLs."""

from __future__ import annotations

from ons_epc_config import EpcEdition

DATASET_PAGE = (
    "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/"
    "housepricepersquaremetreandhousepriceperroomenglandandwales"
)

HOUSE_M2_ROOM_EDITIONS: dict[str, EpcEdition] = {
    "2004to2016": EpcEdition(
        key="2004to2016",
        label="2004 to 2016",
        source_url=(
            "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/"
            "housepricepersquaremetreandhousepriceperroomenglandandwales/2004to2016/"
            "priceperareadata.xls"
        ),
        dataset_page_url=DATASET_PAGE,
        suggested_filename="ons_house_m2_room_2004to2016.xls",
    ),
}

# Data tables only (exclude cover "Content").
HOUSE_M2_DATA_SHEETS = tuple(f"Table{i}" for i in range(1, 13))

HOUSE_M2_HEADER_ROW = 3
