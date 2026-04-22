"""Map stable dataset IDs to allowed filenames under data/processed/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ons_ee_fiveyear_config import EE_DATA_SHEETS, EE_FIVEYEAR_EDITIONS
from ons_epc_config import EPC_DATA_SHEETS, EPC_EDITIONS
from ons_housebuilding_country_config import HOUSEBUILDING_COUNTRY_EDITIONS
from ons_housebuilding_la_config import HOUSEBUILDING_LA_EDITIONS
from ons_house_m2_room_config import HOUSE_M2_DATA_SHEETS, HOUSE_M2_ROOM_EDITIONS
from ons_house_price_explorer_config import (
    HOUSE_PRICE_EXPLORER_DATA_SHEETS,
    HOUSE_PRICE_EXPLORER_EDITIONS,
    HOUSE_PRICE_EXPLORER_SHEET_SLUGS,
)
from ons_mainfuel_config import MAINFUEL_DATA_SHEETS, MAINFUEL_EDITIONS
from ons_median_eescore_config import MEDIAN_EESCORE_DATA_SHEETS, MEDIAN_EESCORE_EDITIONS
from ons_median_price_admin_config import (
    MEDIAN_PRICE_ALL_ADMIN_EDITIONS,
    MEDIAN_PRICE_ADMIN_DATA_SHEETS,
    MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS,
    MEDIAN_PRICE_NEW_ADMIN_EDITIONS,
)
from ons_national_park_hpssa_config import NATIONAL_PARK_HPSSA_DATA_SHEETS, NATIONAL_PARK_HPSSA_EDITIONS
from ons_price_earnings_ratio_config import PRICE_EARNINGS_RATIO_DATA_SHEETS, PRICE_EARNINGS_RATIO_EDITIONS
from ons_price_newbuild_workplace_earnings_ratio_config import (
    NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS,
)
from ons_price_residence_earnings_ratio_config import (
    PRICE_RESIDENCE_EARNINGS_RATIO_DATA_SHEETS,
    PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS,
)
from ons_private_rental_index_config import PRIVATE_RENTAL_INDEX_EDITIONS
from ons_uk_hpi_monthly_config import UK_HPI_DATA_SHEETS, UK_HPI_MONTHLY_EDITIONS
from ons_vacant_second_homes_config import VACANT_SECOND_HOMES_DATA_SHEETS, VACANT_SECOND_HOMES_EDITIONS

from housing_api.settings import resolved_processed_dir


@dataclass(frozen=True)
class DatasetMeta:
    id: str
    title: str
    family: str
    """Routing for filters / charts: housebuilding_la | housebuilding_country | generic."""
    filename: str
    """Basename under data/processed/."""


def _tid(name: str) -> str:
    return f"{name}_tidy.parquet"


def build_registry() -> dict[str, DatasetMeta]:
    reg: dict[str, DatasetMeta] = {}

    reg["uk_housing_starts"] = DatasetMeta(
        id="uk_housing_starts",
        title="UK housing starts (bundled workbook, tidy)",
        family="generic",
        filename="uk_housing_starts_tidy.parquet",
    )

    reg["joined_la_housing_market_snapshot"] = DatasetMeta(
        id="joined_la_housing_market_snapshot",
        title="Joined LA housing market snapshot (Lane A)",
        family="generic",
        filename="joined_la_housing_market_snapshot.parquet",
    )

    reg["region_housing_market_snapshot"] = DatasetMeta(
        id="region_housing_market_snapshot",
        title="Region housing market snapshot (Lane B)",
        family="generic",
        filename="region_housing_market_snapshot.parquet",
    )

    for ed in HOUSEBUILDING_LA_EDITIONS:
        fn = _tid(f"ons_housebuilding_la_{ed}")
        rid = fn.replace("_tidy.parquet", "")
        reg[rid] = DatasetMeta(
            id=rid,
            title=f"ONS house building by local authority ({HOUSEBUILDING_LA_EDITIONS[ed].label})",
            family="housebuilding_la",
            filename=fn,
        )

    for ed in HOUSEBUILDING_COUNTRY_EDITIONS:
        fn = _tid(f"ons_housebuilding_country_{ed}")
        rid = fn.replace("_tidy.parquet", "")
        reg[rid] = DatasetMeta(
            id=rid,
            title=f"ONS house building by country ({HOUSEBUILDING_COUNTRY_EDITIONS[ed].label})",
            family="housebuilding_country",
            filename=fn,
        )

    for ed in EPC_EDITIONS:
        for sheet in EPC_DATA_SHEETS:
            stem = f"ons_epc_bands_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS EPC bands table {sheet} ({EPC_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in EE_FIVEYEAR_EDITIONS:
        for sheet in EE_DATA_SHEETS:
            stem = f"ons_ee_fiveyear_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS five-year rolling energy efficiency table {sheet} ({EE_FIVEYEAR_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in MAINFUEL_EDITIONS:
        for sheet in MAINFUEL_DATA_SHEETS:
            stem = f"ons_mainfuel_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS main fuel / central heating table {sheet} ({MAINFUEL_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in MEDIAN_EESCORE_EDITIONS:
        for sheet in MEDIAN_EESCORE_DATA_SHEETS:
            stem = f"ons_median_eescore_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS median EPC score table {sheet} ({MEDIAN_EESCORE_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in HOUSE_M2_ROOM_EDITIONS:
        for sheet in HOUSE_M2_DATA_SHEETS:
            stem = f"ons_house_m2_room_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS house price per m² / per room {sheet} ({HOUSE_M2_ROOM_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in UK_HPI_MONTHLY_EDITIONS:
        for sheet in UK_HPI_DATA_SHEETS:
            stem = f"ons_uk_hpi_monthly_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS UK HPI monthly worksheet {sheet} ({UK_HPI_MONTHLY_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS:
        for sheet in MEDIAN_PRICE_ADMIN_DATA_SHEETS:
            stem = f"ons_median_price_existing_admin_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS median price (existing) {sheet} ({MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in MEDIAN_PRICE_ALL_ADMIN_EDITIONS:
        for sheet in MEDIAN_PRICE_ADMIN_DATA_SHEETS:
            stem = f"ons_median_price_all_admin_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS median price (all dwellings) {sheet} ({MEDIAN_PRICE_ALL_ADMIN_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in MEDIAN_PRICE_NEW_ADMIN_EDITIONS:
        for sheet in MEDIAN_PRICE_ADMIN_DATA_SHEETS:
            stem = f"ons_median_price_new_admin_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS median price (new build) {sheet} ({MEDIAN_PRICE_NEW_ADMIN_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in PRICE_EARNINGS_RATIO_EDITIONS:
        for sheet in PRICE_EARNINGS_RATIO_DATA_SHEETS:
            stem = f"ons_price_earnings_ratio_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS price / workplace earnings {sheet} ({PRICE_EARNINGS_RATIO_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS:
        for sheet in PRICE_RESIDENCE_EARNINGS_RATIO_DATA_SHEETS:
            stem = f"ons_price_residence_earnings_ratio_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS price / residence earnings {sheet} ({PRICE_RESIDENCE_EARNINGS_RATIO_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS:
        for sheet in PRICE_EARNINGS_RATIO_DATA_SHEETS:
            stem = f"ons_price_newbuild_workplace_earnings_ratio_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS new-build price / workplace earnings {sheet} ({NEWBUILD_WORKPLACE_PRICE_EARNINGS_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in PRIVATE_RENTAL_INDEX_EDITIONS:
        fn = _tid(f"ons_private_rental_index_{ed}")
        rid = fn.replace("_tidy.parquet", "")
        reg[rid] = DatasetMeta(
            id=rid,
            title=f"ONS private rental price index and YoY change ({PRIVATE_RENTAL_INDEX_EDITIONS[ed].label})",
            family="price_index",
            filename=fn,
        )

    for ed in NATIONAL_PARK_HPSSA_EDITIONS:
        for sheet in NATIONAL_PARK_HPSSA_DATA_SHEETS:
            stem = f"ons_national_park_hpssa_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS national park HPSSA {sheet} ({NATIONAL_PARK_HPSSA_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in HOUSE_PRICE_EXPLORER_EDITIONS:
        for sheet in HOUSE_PRICE_EXPLORER_DATA_SHEETS:
            slug = HOUSE_PRICE_EXPLORER_SHEET_SLUGS[sheet]
            stem = f"ons_house_price_explorer_{ed}_{slug}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=f"ONS House Price Explorer {sheet} ({HOUSE_PRICE_EXPLORER_EDITIONS[ed].label})",
                family="generic",
                filename=fn,
            )

    for ed in VACANT_SECOND_HOMES_EDITIONS:
        for sheet in VACANT_SECOND_HOMES_DATA_SHEETS:
            stem = f"ons_vacant_second_homes_{ed}_{sheet}"
            fn = _tid(stem)
            rid = fn.replace("_tidy.parquet", "")
            reg[rid] = DatasetMeta(
                id=rid,
                title=(
                    f"ONS Census 2021 vacant dwellings and second homes (no usual residents) "
                    f"table {sheet} ({VACANT_SECOND_HOMES_EDITIONS[ed].label})"
                ),
                family="generic",
                filename=fn,
            )

    return reg


REGISTRY: dict[str, DatasetMeta] = build_registry()


def safe_processed_path(repo_root: Path, meta: DatasetMeta) -> Path | None:
    """Resolve path under data/processed only; return None if traversal or bad layout."""
    processed = resolved_processed_dir(repo_root)
    target = (processed / meta.filename).resolve()
    try:
        target.relative_to(processed)
    except ValueError:
        return None
    return target
