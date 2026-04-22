"""Deterministic helpers for the Housing insights briefing Streamlit page.

Pure pandas + pathlib (no Streamlit). Chart construction stays in ``pages/24_*``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from housing_data.geo_ids import norm_lad
from housing_data.periods import pe_year_from_period
from housing_data.housebuilding_la import sorted_financial_years

# Ordered domain for ``color=region`` so charts stay consistent (England & Wales regions + Wales).
REGION_COLOR_DOMAIN: list[str] = [
    "North East",
    "North West",
    "Yorkshire and The Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Wales",
]
REGION_COLOR_RANGE: list[str] = [
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#E69F00",
    "#009E73",
    "#56B4E9",
    "#F0E442",
    "#000000",
    "#999999",
    "#882255",
]

PRESET_NATIONAL = "national"
PRESET_LONDON_COMMUTER = "london_commuter"
PRESET_NORTH = "north"
PRESET_CUSTOM = "custom"

LONDON_COMMUTER_REGIONS: frozenset[str] = frozenset({"London", "South East", "East of England"})
NORTH_REGIONS: frozenset[str] = frozenset({"North East", "North West", "Yorkshire and The Humber"})

EW_HB_REGIONS: frozenset[str] = frozenset(REGION_COLOR_DOMAIN)

# Fixed watchlist for optional median-price small multiples (entry tab).
WATCHLIST_LA_NAMES: tuple[str, ...] = ("Manchester", "Birmingham", "Westminster", "Cornwall")

ENTRY_PRESSURE_NOTE = (
    "Count of local authorities where the change in lower-quartile house price (table 6a) exceeds "
    "the change in median house price (table 5a) over the same horizon — a proxy for lower-end "
    "price pressure, not an ONS first-time-buyer definition."
)


def admin_year_from_period(label: object) -> int | None:
    """Calendar year from HPSSA-style ``Year ending Dec YYYY`` labels."""
    s = str(label).strip()
    m = re.match(r"Year ending Dec (\d{4})$", s)
    return int(m.group(1)) if m else None


def preset_region_filter(preset: str, custom_regions: Sequence[str]) -> frozenset[str] | None:
    """Return allowed ``country_region_name`` values, or ``None`` for no filter (England & Wales LAs)."""
    if preset == PRESET_NATIONAL:
        return None
    if preset == PRESET_LONDON_COMMUTER:
        return LONDON_COMMUTER_REGIONS
    if preset == PRESET_NORTH:
        return NORTH_REGIONS
    if preset == PRESET_CUSTOM:
        if not custom_regions:
            return None
        return frozenset(str(x).strip() for x in custom_regions if str(x).strip())
    return None


def _file_sig(path: Path) -> str:
    if not path.is_file():
        return f"{path.name}:missing"
    st = path.stat()
    return f"{path.name}:{st.st_mtime_ns}:{st.st_size}"


def insights_parquet_paths(
    root: Path,
    *,
    pe_ed: str,
    hb_la_ed: str,
    hb_country_ed: str,
    hpi_ed: str,
    median_ed: str,
    epc_ed: str,
    ee_ed: str,
    census_stem: str,
) -> list[Path]:
    root = Path(root)
    paths: list[Path] = [
        root / f"ons_price_earnings_ratio_{pe_ed}_5a_tidy.parquet",
        root / f"ons_price_earnings_ratio_{pe_ed}_5b_tidy.parquet",
        root / f"ons_price_earnings_ratio_{pe_ed}_5c_tidy.parquet",
        root / f"ons_price_earnings_ratio_{pe_ed}_6a_tidy.parquet",
        root / f"ons_price_earnings_ratio_{pe_ed}_1c_tidy.parquet",
        root / f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet",
        root / f"ons_housebuilding_country_{hb_country_ed}_tidy.parquet",
        root / f"ons_uk_hpi_monthly_{hpi_ed}_1_tidy.parquet",
        root / f"ons_median_price_existing_admin_{median_ed}_2a_tidy.parquet",
        root / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet",
        root / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet",
        root / f"{census_stem}.parquet",
        root / "joined_la_housing_market_snapshot.parquet",
    ]
    return paths


def insights_inputs_snapshot(
    root: Path | str,
    *,
    pe_ed: str,
    hb_la_ed: str,
    hb_country_ed: str,
    hpi_ed: str,
    median_ed: str,
    epc_ed: str,
    ee_ed: str,
    census_stem: str,
) -> str:
    """Concatenate mtime/size (or ``missing``) for every Parquet the briefing may read."""
    root_p = Path(root)
    return "|".join(_file_sig(p) for p in insights_parquet_paths(
        root_p,
        pe_ed=pe_ed,
        hb_la_ed=hb_la_ed,
        hb_country_ed=hb_country_ed,
        hpi_ed=hpi_ed,
        median_ed=median_ed,
        epc_ed=epc_ed,
        ee_ed=ee_ed,
        census_stem=census_stem,
    ))


def _load_pe_la(root: Path, edition: str, sheet: str) -> pd.DataFrame | None:
    p = root / f"ons_price_earnings_ratio_{edition}_{sheet}_tidy.parquet"
    if not p.is_file():
        return None
    df = pd.read_parquet(p)
    sub = df[df["geography_level"].astype(str) == "local_authority"].copy()
    sub["pe_year"] = sub["period_label"].map(pe_year_from_period)
    sub = sub[sub["pe_year"].notna()]
    sub["lad_code"] = sub["local_authority_code"].map(norm_lad)
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    return sub


def horizon_year_bounds_from_common_years(years: Iterable[int], horizon_years: int) -> tuple[int, int] | None:
    """Last ``horizon_years`` distinct calendar years (inclusive) from a non-empty year set."""
    ys = sorted({int(y) for y in years})
    if not ys:
        return None
    y_max = ys[-1]
    n = max(1, int(horizon_years))
    y_min = ys[max(0, len(ys) - n)]
    return y_min, y_max


def common_pe_years(d5a: pd.DataFrame, d5b: pd.DataFrame, d5c: pd.DataFrame) -> set[int]:
    a = {int(x) for x in d5a["pe_year"].dropna().unique()}
    b = {int(x) for x in d5b["pe_year"].dropna().unique()}
    c = {int(x) for x in d5c["pe_year"].dropna().unique()}
    return a & b & c


def la_pe_horizon_table(
    d5a: pd.DataFrame,
    d5b: pd.DataFrame,
    d5c: pd.DataFrame,
    y_min: int,
    y_max: int,
    region_allow: frozenset[str] | None,
) -> pd.DataFrame:
    """One row per LA with Δ median price, Δ earnings, Δ ratio over [y_min, y_max]."""

    def _pivot_endpoints(df: pd.DataFrame, col: str) -> pd.DataFrame:
        sub = df[df["pe_year"].isin([y_min, y_max])].copy()
        p = sub.pivot_table(index="lad_code", columns="pe_year", values="value", aggfunc="first")
        if y_min not in p.columns or y_max not in p.columns:
            return pd.DataFrame(columns=["lad_code", col])
        out = p[[y_min, y_max]].copy()
        out.columns = [f"_{y_min}", f"_{y_max}"]
        out = out.reset_index()
        out[col] = out[f"_{y_max}"] - out[f"_{y_min}"]
        return out[["lad_code", col]]

    p_a = _pivot_endpoints(d5a, "delta_median_price")
    p_b = _pivot_endpoints(d5b, "delta_earnings")
    p_c = _pivot_endpoints(d5c, "delta_ratio")
    meta = (
        d5a[d5a["pe_year"] == y_max][["lad_code", "local_authority_name", "country_region_name"]]
        .drop_duplicates("lad_code", keep="first")
        .rename(columns={"local_authority_name": "la_name", "country_region_name": "region"})
    )
    out = meta.merge(p_a, on="lad_code", how="inner").merge(p_b, on="lad_code", how="inner").merge(p_c, on="lad_code", how="inner")
    if region_allow is not None:
        out = out[out["region"].isin(region_allow)]
    return out


def entry_pressure_count(d5a: pd.DataFrame, d6a: pd.DataFrame, y_min: int, y_max: int) -> int:
    """LAs where Δ(6a LQ price) > Δ(5a median price), same paired years."""
    p5 = la_pe_horizon_table(d5a, d5a, d5a, y_min, y_max, None)  # wrong - need only price deltas from 5a and 6a
    # Rebuild minimal deltas for 5a median and 6a LQ only
    def delta_sheet(df: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
        sub = df[df["pe_year"].isin([y0, y1])].copy()
        p = sub.pivot_table(index="lad_code", columns="pe_year", values="value", aggfunc="first")
        if y0 not in p.columns or y1 not in p.columns:
            return pd.DataFrame(columns=["lad_code", "delta"])
        out = (p[y1] - p[y0]).rename("delta").reset_index()
        return out

    d_med = delta_sheet(d5a, y_min, y_max).rename(columns={"delta": "d_median_price"})
    d_lq = delta_sheet(d6a, y_min, y_max).rename(columns={"delta": "d_lq_price"})
    m = d_med.merge(d_lq, on="lad_code", how="inner")
    m = m.dropna(subset=["d_median_price", "d_lq_price"])
    return int((m["d_lq_price"] > m["d_median_price"]).sum())


def entry_pressure_count_filtered(
    d5a: pd.DataFrame,
    d6a: pd.DataFrame,
    y_min: int,
    y_max: int,
    region_allow: frozenset[str] | None,
) -> int:
    """Like ``entry_pressure_count`` but restricted to LAs whose region passes the preset filter."""
    d5a_f = d5a.copy()
    d6a_f = d6a.copy()
    if region_allow is not None:
        r5 = d5a_f[d5a_f["pe_year"] == y_max][["lad_code", "country_region_name"]].drop_duplicates("lad_code")
        codes = set(r5[r5["country_region_name"].isin(region_allow)]["lad_code"])
        d5a_f = d5a_f[d5a_f["lad_code"].isin(codes)]
        d6a_f = d6a_f[d6a_f["lad_code"].isin(codes)]
    return entry_pressure_count(d5a_f, d6a_f, y_min, y_max)


def ew_ratio_horizon_values(df1c: pd.DataFrame, y_min: int, y_max: int) -> tuple[float | None, float | None]:
    """England & Wales median ratio (table 1c) at horizon endpoints."""
    sub = df1c[
        (df1c["geography_level"].astype(str) == "region")
        & (df1c["name"].astype(str) == "England and Wales")
        & (df1c["period_label"].astype(str) != "5-Year Average")
    ].copy()
    sub["pe_year"] = sub["period_label"].map(pe_year_from_period)
    sub = sub[sub["pe_year"].notna()]
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    row_min = sub[sub["pe_year"] == y_min].drop_duplicates("pe_year")
    row_max = sub[sub["pe_year"] == y_max].drop_duplicates("pe_year")
    v0 = float(row_min["value"].iloc[0]) if len(row_min) else None
    v1 = float(row_max["value"].iloc[0]) if len(row_max) else None
    return v0, v1


def epc_c_plus_by_region(epc1a: pd.DataFrame) -> pd.DataFrame:
    """Sum % of dwellings in EPC bands A–C per ``country_or_region_name`` (C or better)."""
    df = epc1a.copy()
    df["epc_band"] = df["epc_band"].astype(str).str.upper().str.strip()
    df["percentage"] = pd.to_numeric(df["percentage"], errors="coerce")
    df = df[df["epc_band"].isin(list("ABC"))]
    g = df.groupby("country_or_region_name", as_index=False)["percentage"].sum(min_count=1)
    g = g.rename(columns={"country_or_region_name": "region", "percentage": "epc_c_plus_pct"})
    return g.sort_values("epc_c_plus_pct", ascending=False)


def hb_region_supply_change(
    hb: pd.DataFrame,
    *,
    n_fy: int,
    measure: str,
    region_allow: frozenset[str] | None,
) -> tuple[str | None, float | None, str | None, str | None]:
    """Region with largest change in summed ``measure`` (``starts`` / ``completed``) over last ``n_fy`` FYs."""
    v = hb.copy()
    v = v[v["measure"].astype(str).str.lower() == measure.lower()]
    v = v[~v["Region or Country Name"].isin(["Scotland", "Northern Ireland"])]
    if region_allow is not None:
        v = v[v["Region or Country Name"].isin(region_allow & EW_HB_REGIONS)]
    else:
        v = v[v["Region or Country Name"].isin(EW_HB_REGIONS)]
    years = sorted_financial_years(v["financial_year"])
    if len(years) < 2:
        return None, None, None, None
    span = years[-min(n_fy, len(years)) :]
    y0, y1 = span[0], span[-1]
    def _tot(y: str) -> pd.Series:
        s = v[v["financial_year"].astype(str) == y].groupby("Region or Country Name")["dwellings"].sum(min_count=1)
        return s
    t0, t1 = _tot(y0), _tot(y1)
    joined = pd.DataFrame({"a": t0, "b": t1}).fillna(0)
    joined["delta"] = joined["b"] - joined["a"]
    if joined.empty:
        return None, None, y0, y1
    top = joined.sort_values("delta", ascending=False).head(1)
    reg = str(top.index[0])
    d = float(top["delta"].iloc[0])
    return reg, d, y0, y1


def hb_region_supply_change_between(
    hb: pd.DataFrame,
    fy0: str,
    fy1: str,
    *,
    measure: str,
    region_allow: frozenset[str] | None,
) -> tuple[str | None, float | None, str | None, str | None]:
    """Largest regional change in summed ``measure`` between two financial year labels."""
    v = hb.copy()
    v = v[v["measure"].astype(str).str.lower() == measure.lower()]
    v = v[~v["Region or Country Name"].isin(["Scotland", "Northern Ireland"])]
    if region_allow is not None:
        v = v[v["Region or Country Name"].isin(region_allow & EW_HB_REGIONS)]
    else:
        v = v[v["Region or Country Name"].isin(EW_HB_REGIONS)]
    years = sorted_financial_years(v["financial_year"])
    if fy0 not in years or fy1 not in years:
        return None, None, fy0, fy1

    def _tot(y: str) -> pd.Series:
        return v[v["financial_year"].astype(str) == y].groupby("Region or Country Name")["dwellings"].sum(min_count=1)

    t0, t1 = _tot(fy0), _tot(fy1)
    joined = pd.DataFrame({"a": t0, "b": t1}).fillna(0)
    joined["delta"] = joined["b"] - joined["a"]
    if joined.empty:
        return None, None, fy0, fy1
    top = joined.sort_values("delta", ascending=False).head(1)
    return str(top.index[0]), float(top["delta"].iloc[0]), fy0, fy1


# When both years exist in 5a∩5b∩5c, prefer this calendar window for LA affordability / entry / regional 1c index.
DEFAULT_PE_ANCHOR_YEARS: tuple[int, int] = (2021, 2025)
# Regional starts hero and supply tab: these FYs when present in the LA house-building file.
DEFAULT_SUPPLY_COMPARE_FY: tuple[str, str] = ("2020-2021", "2024-2025")


def build_insights_payload(
    processed_root: str | Path,
    *,
    pe_ed: str,
    hb_la_ed: str,
    hb_country_ed: str,
    hpi_ed: str,
    median_ed: str,
    epc_ed: str,
    ee_ed: str,
    census_stem: str,
    preset: str,
    custom_regions: Sequence[str],
    horizon_years: int,
    pe_anchor_years: tuple[int, int] | None = DEFAULT_PE_ANCHOR_YEARS,
    supply_compare_fy: tuple[str, str] | None = DEFAULT_SUPPLY_COMPARE_FY,
) -> dict[str, Any]:
    """Assemble meta, per-tab missing-file lists, hero metrics, chart/table frames, and findings."""
    root = Path(processed_root)
    region_allow = preset_region_filter(preset, custom_regions)

    missing: dict[str, list[str]] = {k: [] for k in ("affordability", "entry", "regions", "supply", "energy")}

    def _need(tab: str, name: str) -> None:
        missing[tab].append(name)

    paths = {
        "5a": root / f"ons_price_earnings_ratio_{pe_ed}_5a_tidy.parquet",
        "5b": root / f"ons_price_earnings_ratio_{pe_ed}_5b_tidy.parquet",
        "5c": root / f"ons_price_earnings_ratio_{pe_ed}_5c_tidy.parquet",
        "6a": root / f"ons_price_earnings_ratio_{pe_ed}_6a_tidy.parquet",
        "1c": root / f"ons_price_earnings_ratio_{pe_ed}_1c_tidy.parquet",
        "hb_la": root / f"ons_housebuilding_la_{hb_la_ed}_tidy.parquet",
        "epc1a": root / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet",
        "ee1c": root / f"ons_ee_fiveyear_{ee_ed}_1c_tidy.parquet",
        "median2a": root / f"ons_median_price_existing_admin_{median_ed}_2a_tidy.parquet",
        "census": root / f"{census_stem}.parquet",
        "joined": root / "joined_la_housing_market_snapshot.parquet",
    }

    for sheet in ("5a", "5b", "5c"):
        if not paths[sheet].is_file():
            _need("affordability", paths[sheet].name)
            _need("entry", paths[sheet].name)
    if not paths["6a"].is_file():
        _need("entry", paths["6a"].name)
    if not paths["1c"].is_file():
        _need("regions", paths["1c"].name)
    if not paths["hb_la"].is_file():
        _need("supply", paths["hb_la"].name)
    if not paths["epc1a"].is_file():
        _need("energy", paths["epc1a"].name)

    d5a = _load_pe_la(root, pe_ed, "5a") if paths["5a"].is_file() else None
    d5b = _load_pe_la(root, pe_ed, "5b") if paths["5b"].is_file() else None
    d5c = _load_pe_la(root, pe_ed, "5c") if paths["5c"].is_file() else None
    d6a = _load_pe_la(root, pe_ed, "6a") if paths["6a"].is_file() else None

    y_bounds: tuple[int, int] | None = None
    horizon_label = "Horizon unavailable (missing price/earnings tables or years)."
    if d5a is not None and d5b is not None and d5c is not None:
        common = common_pe_years(d5a, d5b, d5c)
        if pe_anchor_years is not None:
            a0, a1 = int(pe_anchor_years[0]), int(pe_anchor_years[1])
            if a0 in common and a1 in common:
                y_bounds = (a0, a1)
        if y_bounds is None:
            y_bounds = horizon_year_bounds_from_common_years(common, horizon_years)
        if y_bounds:
            y_min, y_max = y_bounds
            horizon_label = f"Price/earnings horizon: **{y_min}**–**{y_max}** (calendar years aligned across tables 5a–5c)."

    y_min = y_bounds[0] if y_bounds else None
    y_max = y_bounds[1] if y_bounds else None

    # --- Affordability table + scatter frame
    aff_df = pd.DataFrame()
    aff_region_agg = pd.DataFrame()
    if d5a is not None and d5b is not None and d5c is not None and y_min is not None and y_max is not None:
        aff_df = la_pe_horizon_table(d5a, d5b, d5c, y_min, y_max, region_allow)
        if not aff_df.empty:
            aff_region_agg = (
                aff_df.groupby("region", as_index=False)
                .agg(
                    delta_median_price=("delta_median_price", "median"),
                    delta_ratio=("delta_ratio", "median"),
                )
                .sort_values("region")
            )

    # --- Entry barrier: Δ6a − Δ5a
    entry_df = pd.DataFrame()
    entry_watchlist_long = pd.DataFrame()
    if d5a is not None and d6a is not None and y_min is not None and y_max is not None:

        def _delta_only(df: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
            sub = df[df["pe_year"].isin([y0, y1])].copy()
            p = sub.pivot_table(index="lad_code", columns="pe_year", values="value", aggfunc="first")
            if y0 not in p.columns or y1 not in p.columns:
                return pd.DataFrame(columns=["lad_code", "delta"])
            out = (p[y1] - p[y0]).rename("delta").reset_index()
            return out

        d_med = _delta_only(d5a, y_min, y_max).rename(columns={"delta": "delta_median_price"})
        d_lq = _delta_only(d6a, y_min, y_max).rename(columns={"delta": "delta_lq_price"})
        meta = (
            d5a[d5a["pe_year"] == y_max][["lad_code", "local_authority_name", "country_region_name"]]
            .drop_duplicates("lad_code", keep="first")
            .rename(columns={"local_authority_name": "la_name", "country_region_name": "region"})
        )
        entry_df = meta.merge(d_med, on="lad_code", how="inner").merge(d_lq, on="lad_code", how="inner")
        entry_df["entry_gap"] = entry_df["delta_lq_price"] - entry_df["delta_median_price"]
        if region_allow is not None:
            entry_df = entry_df[entry_df["region"].isin(region_allow)]
        entry_df = entry_df.sort_values("entry_gap", ascending=False)

        # Optional watchlist median prices (2a)
        if paths["median2a"].is_file():
            m2 = pd.read_parquet(paths["median2a"])
            m2 = m2[(m2["geography_level"].astype(str) == "local_authority") & (m2["dwelling_class"].astype(str) == "existing")]
            m2["ay"] = m2["period_label"].map(admin_year_from_period)
            m2 = m2[m2["ay"].notna()]
            m2["lad_code"] = m2["local_authority_code"].map(norm_lad)
            m2["median_price_gbp"] = pd.to_numeric(m2["median_price_gbp"], errors="coerce")
            names = set(WATCHLIST_LA_NAMES)
            m2 = m2[m2["local_authority_name"].isin(names)]
            if y_min is not None and y_max is not None:
                m2 = m2[m2["ay"].between(int(y_min), int(y_max))]
            entry_watchlist_long = m2[
                ["lad_code", "local_authority_name", "ay", "median_price_gbp"]
            ].sort_values(["local_authority_name", "ay"])

    # --- Regions: PE 1c regional ratio normalised to 100 at first period in window
    regions_long = pd.DataFrame()
    if paths["1c"].is_file() and y_min is not None and y_max is not None:
        pe1c = pd.read_parquet(paths["1c"])
        reg = pe1c[pe1c["geography_level"].astype(str) == "region"].copy()
        reg = reg[reg["period_label"].astype(str) != "5-Year Average"]
        reg["pe_year"] = reg["period_label"].map(pe_year_from_period)
        reg = reg[reg["pe_year"].notna()]
        reg["pe_year"] = reg["pe_year"].astype(int)
        reg = reg[(reg["pe_year"] >= y_min) & (reg["pe_year"] <= y_max)]
        reg["value"] = pd.to_numeric(reg["value"], errors="coerce")
        # Exclude aggregate rows; keep standard regions + Wales
        keep_names = set(REGION_COLOR_DOMAIN)
        reg = reg[reg["name"].astype(str).isin(keep_names)]
        if region_allow is not None:
            reg = reg[reg["name"].isin(region_allow)]
        if not reg.empty:
            base = reg[reg["pe_year"] == y_min].drop_duplicates(subset=["name"])[["name", "value"]].rename(
                columns={"value": "base_ratio"}
            )
            reg = reg.merge(base, on="name", how="inner")
            reg["base_ratio"] = reg["base_ratio"].replace(0, pd.NA)
            reg["index_norm"] = 100.0 * reg["value"] / reg["base_ratio"]
            regions_long = reg.rename(columns={"name": "region"})[
                ["region", "pe_year", "value", "index_norm"]
            ].sort_values(["region", "pe_year"])

    # --- Supply: paired totals latest FY vs start FY in window (same count as horizon_years)
    supply_bars = pd.DataFrame()
    supply_note = ""
    hb = pd.read_parquet(paths["hb_la"]) if paths["hb_la"].is_file() else None
    pop_by_lad: dict[str, float] = {}
    if paths["census"].is_file():
        pop = pd.read_parquet(paths["census"])
        pop_by_lad = {
            str(r["lad_code"]).strip().upper(): float(r["population"])
            for _, r in pop.iterrows()
            if pd.notna(r.get("population"))
        }

    if hb is not None:
        fy_all = sorted_financial_years(hb["financial_year"])
        if len(fy_all) >= 1:
            y_f0: str | None = None
            y_f1: str | None = None
            if supply_compare_fy is not None:
                s0, s1 = str(supply_compare_fy[0]), str(supply_compare_fy[1])
                if s0 in fy_all and s1 in fy_all:
                    y_f0, y_f1 = s0, s1
            if y_f0 is None or y_f1 is None:
                n_fy = max(2, min(int(horizon_years), len(fy_all)))
                span = fy_all[-n_fy:]
                y_f0, y_f1 = span[0], span[-1]
            supply_note = f"Financial years **{y_f0}** to **{y_f1}** (house building LA, summed to region)."
            sub = hb[~hb["Region or Country Name"].isin(["Scotland", "Northern Ireland"])]
            if region_allow is not None:
                sub = sub[sub["Region or Country Name"].isin(region_allow & EW_HB_REGIONS)]
            else:
                sub = sub[sub["Region or Country Name"].isin(EW_HB_REGIONS)]
            rows: list[dict[str, Any]] = []
            for m_label, m_key in (("Starts", "starts"), ("Completions", "completed")):
                for y in (y_f0, y_f1):
                    chunk = sub[(sub["financial_year"].astype(str) == y) & (sub["measure"].astype(str).str.lower() == m_key)]
                    by_reg = chunk.groupby("Region or Country Name", as_index=False)["dwellings"].sum(min_count=1)
                    for _, rr in by_reg.iterrows():
                        rows.append(
                            {
                                "region": rr["Region or Country Name"],
                                "financial_year": y,
                                "measure": m_label,
                                "dwellings": float(rr["dwellings"]),
                            }
                        )
            supply_bars = pd.DataFrame(rows)
            if pop_by_lad:
                supply_note += " Census 2021 LA population is available for per-capita work on other pages; this tab uses raw regional sums."

    # --- Energy: stacked EPC bands by region (latest snapshot in 1a — no time in file)
    energy_stack = pd.DataFrame()
    epc_rank = pd.DataFrame()
    if paths["epc1a"].is_file():
        e1 = pd.read_parquet(paths["epc1a"])
        energy_stack = e1.copy()
        if region_allow is not None:
            energy_stack = energy_stack[energy_stack["country_or_region_name"].isin(region_allow)]
        epc_rank = epc_c_plus_by_region(e1)
        if region_allow is not None:
            epc_rank = epc_rank[epc_rank["region"].isin(region_allow)]

    # --- Optional joined snapshot (energy tab exploratory)
    joined_flag = pd.DataFrame()
    if paths["joined"].is_file():
        j = pd.read_parquet(paths["joined"])
        cols = [c for c in ("lad_code", "region_name", "pe_affordability_ratio", "la_name") if c in j.columns]
        if len(cols) >= 2:
            joined_flag = j[cols].head(200)

    # --- Hero metrics
    hero: dict[str, Any] = {
        "ew_ratio_start": None,
        "ew_ratio_end": None,
        "ew_ratio_delta_str": None,
        "entry_pressure_n": None,
        "entry_pressure_caption": ENTRY_PRESSURE_NOTE,
        "supply_region": None,
        "supply_delta": None,
        "supply_measure": "starts",
        "supply_fy0": None,
        "supply_fy1": None,
        "epc_best_region": None,
        "epc_best_pct": None,
        "epc_worst_region": None,
        "epc_worst_pct": None,
    }

    if paths["1c"].is_file() and y_min is not None and y_max is not None:
        pe1c_full = pd.read_parquet(paths["1c"])
        v0, v1 = ew_ratio_horizon_values(pe1c_full, y_min, y_max)
        hero["ew_ratio_start"] = v0
        hero["ew_ratio_end"] = v1
        if v0 is not None and v1 is not None:
            hero["ew_ratio_delta_str"] = f"{v1 - v0:+.2f} vs {y_min}"

    if d5a is not None and d6a is not None and y_min is not None and y_max is not None:
        hero["entry_pressure_n"] = entry_pressure_count_filtered(d5a, d6a, y_min, y_max, region_allow)

    if hb is not None:
        reg: str | None = None
        d: float | None = None
        f0: str | None = None
        f1: str | None = None
        if supply_compare_fy is not None:
            s0, s1 = str(supply_compare_fy[0]), str(supply_compare_fy[1])
            reg, d, f0, f1 = hb_region_supply_change_between(
                hb, s0, s1, measure="starts", region_allow=region_allow
            )
        if reg is None or d is None:
            reg, d, f0, f1 = hb_region_supply_change(
                hb, n_fy=max(2, int(horizon_years)), measure="starts", region_allow=region_allow
            )
        hero["supply_region"] = reg
        hero["supply_delta"] = d
        hero["supply_fy0"] = f0
        hero["supply_fy1"] = f1

    if not epc_rank.empty:
        hero["epc_best_region"] = str(epc_rank.iloc[0]["region"])
        hero["epc_best_pct"] = float(epc_rank.iloc[0]["epc_c_plus_pct"])
        hero["epc_worst_region"] = str(epc_rank.iloc[-1]["region"])
        hero["epc_worst_pct"] = float(epc_rank.iloc[-1]["epc_c_plus_pct"])

    preset_labels = {
        PRESET_NATIONAL: "National (England & Wales)",
        PRESET_LONDON_COMMUTER: "London commuter belt (London, South East, East of England)",
        PRESET_NORTH: "North of England (North East, North West, Yorkshire and The Humber)",
        PRESET_CUSTOM: "Custom regions",
    }
    meta = {
        "preset_label": preset_labels.get(preset, preset),
        "horizon_label": horizon_label,
        "horizon_years": int(horizon_years),
        "y_min": y_min,
        "y_max": y_max,
        "editions": (
            f"PE `{pe_ed}` · HB LA `{hb_la_ed}` · HB country `{hb_country_ed}` · "
            f"HPI `{hpi_ed}` · Median admin `{median_ed}` · EPC `{epc_ed}` · EE `{ee_ed}`"
        ),
        "census_stem": census_stem,
    }

    # --- Findings (deterministic): per-tab lists + combined list for backward compatibility
    disclaimer = (
        "Findings describe published statistics and defined rules, not causal explanations."
    )

    aff_line: str | None = None
    if not aff_df.empty:
        worst = aff_df.sort_values("delta_ratio", ascending=False).iloc[0]
        aff_line = (
            f"**Affordability (LA Δ ratio):** **{worst['la_name']}** had the largest rise in median "
            f"price-to-earnings ratio (Δ ratio **{worst['delta_ratio']:+.2f}**) over **{y_min}**–**{y_max}** "
            "(ONS tables 5a–5c, workplace-based)."
        )

    entry_line: str | None = None
    if hero.get("entry_pressure_n") is not None:
        entry_line = (
            f"**Entry pressure:** **{int(hero['entry_pressure_n'])}** local authorities show larger growth in "
            "lower-quartile prices than in median prices (tables **6a** vs **5a**), same horizon as affordability."
        )

    entry_extra: str | None = None
    if not entry_df.empty:
        er0 = entry_df.iloc[0]
        entry_extra = (
            f"**Largest entry gap (Δ6a lower quartile − Δ5a median):** **{er0['la_name']}** "
            f"(**£{float(er0['entry_gap']):,.0f}**; Δ LQ **£{float(er0['delta_lq_price']):,.0f}**, "
            f"Δ median **£{float(er0['delta_median_price']):,.0f}**)."
        )

    supply_line: str | None = None
    if hero.get("supply_region") and hero.get("supply_delta") is not None and hero.get("supply_fy0"):
        supply_line = (
            f"**Regional starts change:** **{hero['supply_region']}** saw the largest change in **starts** "
            f"(**{hero['supply_delta']:+.0f}** dwellings) from **{hero['supply_fy0']}** to **{hero['supply_fy1']}** "
            "(LA rows summed to region; England & Wales regions only)."
        )

    supply_extra_starts: str | None = None
    supply_extra_comp: str | None = None
    if not supply_bars.empty and hero.get("supply_fy1"):
        fy1 = str(hero["supply_fy1"])
        sb = supply_bars.copy()
        sb["measure_u"] = sb["measure"].astype(str).str.lower()
        st_sub = sb[(sb["financial_year"].astype(str) == fy1) & (sb["measure_u"].str.contains("start"))]
        if not st_sub.empty:
            mx = st_sub.nlargest(1, "dwellings").iloc[0]
            supply_extra_starts = (
                f"**Starts volume ({fy1}):** **{mx['region']}** records the highest summed starts "
                f"(**{float(mx['dwellings']):,.0f}** dwellings)."
            )
        co_sub = sb[(sb["financial_year"].astype(str) == fy1) & (sb["measure_u"].str.contains("compl"))]
        if not co_sub.empty:
            mx2 = co_sub.nlargest(1, "dwellings").iloc[0]
            supply_extra_comp = (
                f"**Completions volume ({fy1}):** **{mx2['region']}** leads on summed completions "
                f"(**{float(mx2['dwellings']):,.0f}** dwellings)."
            )

    energy_line: str | None = None
    energy_spread: str | None = None
    if hero.get("epc_best_region") and hero.get("epc_worst_region"):
        energy_line = (
            f"**EPC bands A–C (table 1a):** highest combined share in **{hero['epc_best_region']}** "
            f"({hero['epc_best_pct']:.1f}%), lowest in **{hero['epc_worst_region']}** ({hero['epc_worst_pct']:.1f}%)."
        )
        if hero.get("epc_best_pct") is not None and hero.get("epc_worst_pct") is not None:
            energy_spread = (
                f"**Regional spread (A–C):** **{float(hero['epc_best_pct']) - float(hero['epc_worst_pct']):.1f}** "
                "percentage points between the top and bottom English/Welsh regions in this snapshot."
            )

    regions_lines: list[str] = []
    if not regions_long.empty and y_min is not None and y_max is not None:
        last = regions_long[regions_long["pe_year"] == y_max].dropna(subset=["value"])
        if not last.empty:
            topv = last.nlargest(1, "value").iloc[0]
            regions_lines.append(
                f"**Ratio level ({y_max}):** highest workplace price-to-earnings ratio among regions shown: "
                f"**{topv['region']}** (**{float(topv['value']):.2f}**; ONS table **1c**)."
            )
        r0 = regions_long[regions_long["pe_year"] == y_min][["region", "value"]].rename(columns={"value": "v0"})
        r1 = regions_long[regions_long["pe_year"] == y_max][["region", "value"]].rename(columns={"value": "v1"})
        mrg = r0.merge(r1, on="region", how="inner")
        if not mrg.empty:
            mrg["delta_v"] = mrg["v1"] - mrg["v0"]
            mxr = mrg.nlargest(1, "delta_v").iloc[0]
            regions_lines.append(
                f"**Ratio change ({y_min}→{y_max}):** largest rise in published ratio: **{mxr['region']}** "
                f"(Δ **{float(mxr['delta_v']):+.2f}**)."
            )
        idx_last = regions_long[regions_long["pe_year"] == y_max].dropna(subset=["index_norm"])
        if not idx_last.empty:
            topi = idx_last.nlargest(1, "index_norm").iloc[0]
            regions_lines.append(
                f"**Indexed series ({y_min}=100):** by **{y_max}**, **{topi['region']}** sits highest on the "
                f"rebased track (**{float(topi['index_norm']):.1f}** vs base year)."
            )

    aff_region_line: str | None = None
    if not aff_region_agg.empty:
        mxp = aff_region_agg.nlargest(1, "delta_ratio").iloc[0]
        aff_region_line = (
            f"**Regional median of LAs (Δ ratio):** **{mxp['region']}** shows the largest median Δ ratio across "
            f"its local authorities (**{float(mxp['delta_ratio']):+.2f}**)."
        )

    overview: list[str] = []
    if aff_line:
        overview.append(aff_line)
    if aff_region_line:
        overview.append(aff_region_line)
    overview.extend([x for x in (entry_line, supply_line, energy_line) if x])
    overview.append(disclaimer)

    findings_by_tab: dict[str, list[str]] = {
        "affordability": overview,
        "entry": [x for x in (entry_line, entry_extra) if x] + [disclaimer],
        "regions": regions_lines + [disclaimer],
        "supply": [x for x in (supply_line, supply_extra_starts, supply_extra_comp) if x] + [disclaimer],
        "energy": [x for x in (energy_line, energy_spread) if x] + [disclaimer],
    }

    findings: list[str] = list(overview)

    return {
        "meta": meta,
        "missing": missing,
        "hero": hero,
        "findings_by_tab": findings_by_tab,
        "tables": {
            "affordability": aff_df,
            "affordability_region": aff_region_agg,
            "entry": entry_df,
            "regions": regions_long,
            "supply": supply_bars,
            "energy": epc_rank,
        },
        "energy_stack_raw": energy_stack,
        "entry_watchlist": entry_watchlist_long,
        "joined_preview": joined_flag,
        "findings": findings,
        "supply_note": supply_note,
        "paths": {k: str(v) for k, v in paths.items()},
    }
