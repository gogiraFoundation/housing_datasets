"""Streamlit: browse processed dataset IDs from the API registry."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from housing_api.registry import REGISTRY, DatasetMeta
from streamlit_io import PROCESSED_DIR
from streamlit_page_helpers import ogl_attribution_expander


def _etl_hint(meta: DatasetMeta) -> str:
    rid = meta.id
    if rid.startswith("joined_la_housing_market") or rid.startswith("region_housing_market"):
        return "`python joins/build_la_housing_market_snapshot.py`"
    if rid == "uk_housing_starts":
        return "`python uk_local_authority_housing_data.py` (bundled workbook)"
    if "private_rental_index" in rid:
        return "`python ons_private_rental_index_etl.py`"
    if "price_earnings_ratio" in rid and "residence" not in rid and "newbuild" not in rid:
        return "`python ons_price_earnings_ratio_etl.py`"
    if "price_residence" in rid or "residence_earnings" in rid:
        return "`python ons_price_residence_earnings_ratio_etl.py`"
    if "newbuild_workplace" in rid or "price_newbuild" in rid:
        return "`python ons_price_newbuild_workplace_earnings_ratio_etl.py`"
    if "uk_hpi_monthly" in rid:
        return "`python ons_uk_hpi_monthly_etl.py`"
    if "median_price" in rid:
        return "`python ons_median_price_admin_etl.py --dataset existing|new|all`"
    if "housebuilding_la" in rid:
        return "`python ons_housebuilding_la_etl.py`"
    if "housebuilding_country" in rid:
        return "`python ons_housebuilding_country_etl.py`"
    if "epc_bands" in rid:
        return "`python ons_epc_etl.py`"
    if "ee_fiveyear" in rid:
        return "`python ons_ee_fiveyear_etl.py`"
    if "mainfuel" in rid:
        return "`python ons_mainfuel_etl.py`"
    if "median_eescore" in rid:
        return "`python ons_median_eescore_etl.py`"
    if "house_price_explorer" in rid:
        return "`python ons_house_price_explorer_etl.py`"
    if "house_m2_room" in rid:
        return "`python ons_house_m2_room_etl.py`"
    if "vacant_second_homes" in rid:
        return "`python ons_vacant_second_homes_etl.py`"
    if "census2021" in rid or "population" in rid:
        return "`python ons_census2021_etl.py` (see README for dataset flags)"
    return "See **README.md** and `scripts/build_processed_manifest.py`"


def main() -> None:
    st.set_page_config(page_title="Browse datasets", layout="wide")
    st.title("Browse datasets (registry)")
    st.caption(
        "Stable **dataset IDs** and filenames from `housing_api/registry.py` — same catalogue the REST API uses. "
        "**Available** means the Parquet file exists under `data/processed/`."
    )
    st.divider()
    ogl_attribution_expander()

    rows: list[dict] = []
    for meta in sorted(REGISTRY.values(), key=lambda m: m.id):
        p = PROCESSED_DIR / meta.filename
        rows.append(
            {
                "id": meta.id,
                "title": meta.title,
                "family": meta.family,
                "filename": meta.filename,
                "available": p.is_file(),
                "typical_etl": _etl_hint(meta),
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, width=ST_WIDTH, height=min(720, 120 + 22 * min(len(df), 28)))
    st.download_button("Download catalogue as CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="registry_catalogue.csv", mime="text/csv")

    with st.expander("Build manifest (hashes and row counts)"):
        st.markdown(
            "Run `python scripts/build_processed_manifest.py` to refresh `data/processed/processed_manifest.json`."
        )


main()
