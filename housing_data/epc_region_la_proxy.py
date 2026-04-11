"""Map regional EPC band shares onto LA rows for choropleths (same value per LA in region)."""

from __future__ import annotations

import pandas as pd

from housing_data.geo_ids import norm_lad


def epc_band_c_per_la_from_lookup(
    epc_1a: pd.DataFrame,
    lad_lookup: pd.DataFrame,
) -> pd.DataFrame:
    """Band C % from EPC 1a (region rows) joined to each LAD via ``region_code``."""
    epc = epc_1a[epc_1a["epc_band"].astype(str).str.upper() == "C"].copy()
    epc["percentage"] = pd.to_numeric(epc["percentage"], errors="coerce")
    reg = epc[["country_or_region_code", "percentage", "country_or_region_name"]].rename(
        columns={"percentage": "value", "country_or_region_name": "epc_region_name"}
    )
    lu = lad_lookup.copy()
    lu["lad_code"] = lu["lad_code"].map(norm_lad)
    merged = lu.merge(reg, left_on="region_code", right_on="country_or_region_code", how="left")
    return merged[
        ["lad_code", "local_authority_district_name", "region_name", "region_code", "value", "epc_region_name"]
    ].rename(columns={"local_authority_district_name": "la_name"})
