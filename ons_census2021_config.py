"""Census 2021 topic summary datasets (ONS CMD API) — pinned IDs and versions.

See bulletin: Population and household estimates, England and Wales: Census 2021, unrounded data.
Downloads resolve via GET .../datasets/{TS}/editions/2021/versions/{v} (xls + csv hrefs).
"""

from __future__ import annotations

from dataclasses import dataclass

API_BASE = "https://api.beta.ons.gov.uk/v1"

BULLETIN_URL = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/"
    "populationestimates/bulletins/populationandhouseholdestimatesenglandandwales/"
    "census2021unroundeddata"
)


def human_dataset_page(dataset_id: str, edition: str, version: int) -> str:
    return f"https://www.ons.gov.uk/datasets/{dataset_id}/editions/{edition}/versions/{version}"


@dataclass(frozen=True)
class CensusTopicSummary:
    """One Census 2021 topic summary table (lower tier local authorities geography)."""

    key: str
    dataset_id: str
    edition: str
    pinned_version: int
    label: str
    bulletin_url: str


# Pinned versions differ per TS; bump when ONS republishes.
CENSUS_DATASETS: dict[str, CensusTopicSummary] = {
    "sex_ts008": CensusTopicSummary(
        key="sex_ts008",
        dataset_id="TS008",
        edition="2021",
        pinned_version=4,
        label="Sex (lower tier local authorities)",
        bulletin_url=BULLETIN_URL,
    ),
    "age_ts007": CensusTopicSummary(
        key="age_ts007",
        dataset_id="TS007",
        edition="2021",
        pinned_version=3,
        label="Age by single year (lower tier local authorities)",
        bulletin_url=BULLETIN_URL,
    ),
    "sex_age_ts009": CensusTopicSummary(
        key="sex_age_ts009",
        dataset_id="TS009",
        edition="2021",
        pinned_version=2,
        label="Sex by single year of age (lower tier local authorities)",
        bulletin_url=BULLETIN_URL,
    ),
    "households_ts041": CensusTopicSummary(
        key="households_ts041",
        dataset_id="TS041",
        edition="2021",
        pinned_version=1,
        label="Number of households (lower tier local authorities)",
        bulletin_url=BULLETIN_URL,
    ),
    "density_ts006": CensusTopicSummary(
        key="density_ts006",
        dataset_id="TS006",
        edition="2021",
        pinned_version=4,
        label="Population density (lower tier local authorities)",
        bulletin_url=BULLETIN_URL,
    ),
}

POPULATION_DERIVED_STEM = "census2021_la_population_2021"
