"""Streamlit: LA choropleth — house building, median price, affordability, Lane A/B snapshots, or regional EPC proxy."""

from __future__ import annotations

import copy
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
import folium
import streamlit as st
from chart_theme import ST_WIDTH
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

from housing_data.epc_region_la_proxy import epc_band_c_per_la_from_lookup
from housing_data.la_map_context import (
    merge_lane_a_snapshot_columns,
    pick_mf2a_mains_gas_column,
    region_snapshot_metric_columns,
    snapshot_tooltip_strings,
)
from housing_data.median_price_la import latest_median_price_existing_la, latest_median_price_new_la
from housing_data.price_earnings_snapshot import latest_affordability_ratio_la_only
from ons_epc_config import EPC_EDITIONS
from ons_housebuilding_la_config import HOUSEBUILDING_LA_EDITIONS
from ons_median_price_admin_config import MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS, MEDIAN_PRICE_NEW_ADMIN_EDITIONS
from ons_price_earnings_ratio_config import PRICE_EARNINGS_RATIO_EDITIONS
from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

_REPO = Path(__file__).resolve().parents[1]
_GEO = _REPO / "data" / "geo"
_LAD_LOOKUP = _REPO / "data" / "reference" / "lad_to_region_england.csv"
_LA_SNAPSHOT = "joined_la_housing_market_snapshot"
_REG_SNAPSHOT = "region_housing_market_snapshot"

_MAP_HEIGHT = 720
_QUANTILE_COLORS = ["#ffffcc", "#fed976", "#fd8d3c", "#f03b20", "#bd0026"]
_NO_DATA_COLOR = "#e8e8e8"
_PYDECK_MAX_FEATURES = 450


def _lad_geo_path() -> Path | None:
    for name in ("lad_uk_wgs84.geojson", "lad_england.geojson", "minimal_lad_demo.geojson"):
        cand = _GEO / name
        if cand.is_file():
            return cand
    return None


def _region_geo_path() -> Path | None:
    cand = _GEO / "regions_uk_wgs84.geojson"
    return cand if cand.is_file() else None


def _norm_region(x: object) -> str:
    return str(x).strip().upper()


def _detect_code_key(props: dict) -> str:
    for k in ("LAD22CD", "LAD21CD", "lad_code"):
        if k in props and props[k]:
            return k
    return "lad_code"


def _geojson_bounds(gj: dict) -> list[list[float]]:
    lons: list[float] = []
    lats: list[float] = []

    def walk(coords: object) -> None:
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            if isinstance(coords[0], (int, float)):
                lon, lat = float(coords[0]), float(coords[1])
                lons.append(lon)
                lats.append(lat)
            else:
                for c in coords:
                    walk(c)

    for feat in gj.get("features") or []:
        geom = feat.get("geometry") or {}
        walk(geom.get("coordinates"))
    if not lons or not lats:
        return [[49.5, -8.0], [61.0, 2.0]]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def _norm_lad(x: object) -> str:
    return str(x).strip().upper()


def _load_hb(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


def _load_pop(path_str: str) -> pd.DataFrame:
    return load_processed_parquet(path_str)


@st.cache_data
def _geojson_text(path_str: str) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def _quantile_colors(series: pd.Series, n_bins: int = 5) -> tuple[dict[str, str], list[float] | None]:
    s = series.dropna()
    if s.empty:
        return {}, None
    if len(s) == 1:
        v = float(s.iloc[0])
        return {str(s.index[0]): _QUANTILE_COLORS[0]}, [v, v]
    n_bins = max(2, min(n_bins, len(s)))
    try:
        cats = pd.qcut(s, q=n_bins, duplicates="drop")
    except ValueError:
        return {str(k): _QUANTILE_COLORS[0] for k in s.index}, None
    codes = cats.cat.codes.clip(lower=0)
    pal = _QUANTILE_COLORS
    out: dict[str, str] = {}
    for lad, code in zip(s.index.astype(str), codes):
        ci = int(code)
        ci = min(ci, len(pal) - 1)
        out[str(lad)] = pal[ci]
    edges: list[float] = []
    for iv in cats.cat.categories:
        edges.append(float(iv.left))
    if cats.cat.categories is not None and len(cats.cat.categories) > 0:
        edges.append(float(cats.cat.categories[-1].right))
    return out, edges or None


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) != 6:
        return 200, 200, 200
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _fmt_num(x: float | None, *, per_1000: bool) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if per_1000:
        return f"{x:,.2f}"
    return f"{x:,.0f}"


def _fmt_map_value(x: float | None, *, metric: str, per_1000: bool) -> str:
    """Format values for tooltips and KPIs by metric."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if metric == "house_building":
        return _fmt_num(x, per_1000=per_1000)
    if metric == "median_price_existing":
        return f"£{x:,.0f}"
    if metric == "median_price_new":
        return f"£{x:,.0f}"
    if metric == "affordability_ratio":
        return f"{x:,.2f}"
    if metric == "house_building_mainfuel":
        return f"{x:,.1f}%"
    if metric == "lane_b_region":
        return f"{x:,.3g}"
    if metric == "epc_band_c_regional":
        return f"{x:,.1f}%"
    return f"{x:,.3g}"


def _fmt_legend_number(x: float, *, metric: str, per_1000: bool) -> str:
    """Format numeric bin edges for the colour key (no NaN)."""
    if metric == "house_building":
        return _fmt_num(x, per_1000=per_1000)
    if metric == "median_price_existing":
        return f"£{x:,.0f}"
    if metric == "median_price_new":
        return f"£{x:,.0f}"
    if metric == "affordability_ratio":
        return f"{x:,.2f}"
    if metric == "house_building_mainfuel":
        return f"{x:,.1f}%"
    if metric == "lane_b_region":
        return f"{x:,.3g}"
    if metric == "epc_band_c_regional":
        return f"{x:,.1f}%"
    return f"{x:,.3g}"


def _quantile_legend_rows(
    bin_edges: list[float] | None,
    palette: list[str],
    *,
    metric: str,
    per_eff: bool,
) -> tuple[list[tuple[str, str]], bool]:
    """(colour hex, range label) per quantile band; bool = show gradient strip."""
    if bin_edges is None or len(bin_edges) < 2:
        return [(palette[0], "Single band — little variation in the current selection")], True
    n = len(bin_edges) - 1
    rows: list[tuple[str, str]] = []
    for i in range(n):
        lo, hi = float(bin_edges[i]), float(bin_edges[i + 1])
        col = palette[min(i, len(palette) - 1)]
        if lo == hi:
            label = f"≈ {_fmt_legend_number(lo, metric=metric, per_1000=per_eff)}"
        else:
            a = _fmt_legend_number(lo, metric=metric, per_1000=per_eff)
            b = _fmt_legend_number(hi, metric=metric, per_1000=per_eff)
            label = f"{a} – {b}"
        rows.append((col, label))
    return rows, True


def _legend_html_block(
    rows: list[tuple[str, str]],
    *,
    no_data_hex: str,
    palette: list[str],
    show_gradient: bool,
) -> str:
    """HTML for discrete swatches + optional YlOrRd-style gradient strip."""
    n_bands = len(rows)
    band_phrase = (
        f"<strong>{n_bands}</strong> equal-count band{'s' if n_bands != 1 else ''}"
    )
    parts: list[str] = [
        '<div style="font-size:0.72rem; font-weight:600; margin-bottom:0.2rem;">Colour key (quantile bands)</div>',
        '<p style="font-size:0.65rem; line-height:1.35; color:#444; margin:0 0 0.3rem 0;">'
        f"Each colour is one of {band_phrase} of local authorities (by count), "
        "from lowest to highest mapped value in the current filter — band widths are not equal numeric ranges."
        "</p>",
    ]
    sw = []
    for col, lab in rows:
        safe = html.escape(lab)
        sw.append(
            f'<div style="display:flex; align-items:center; gap:0.35rem; margin:0.06rem 0;">'
            f'<span style="display:inline-block; width:0.85rem; height:0.85rem; border-radius:2px; '
            f'background:{html.escape(col)}; border:1px solid rgba(0,0,0,0.25); flex-shrink:0;"></span>'
            f'<span style="font-size:0.68rem; line-height:1.25;">{safe}</span></div>'
        )
    parts.append('<div style="display:flex; flex-direction:column; gap:0;">' + "".join(sw) + "</div>")
    parts.append(
        f'<div style="display:flex; align-items:center; gap:0.35rem; margin-top:0.3rem;">'
        f'<span style="display:inline-block; width:0.85rem; height:0.85rem; border-radius:2px; '
        f'background:{html.escape(no_data_hex)}; border:1px solid rgba(0,0,0,0.2); flex-shrink:0;"></span>'
        f'<span style="font-size:0.68rem;">No data in selection / outside filter</span></div>'
    )
    if show_gradient and len(palette) >= 2:
        grad = ", ".join(palette)
        parts.append(
            '<div style="margin-top:0.35rem;">'
            '<div style="font-size:0.65rem; font-weight:600; margin-bottom:0.12rem;">Scale (low → high)</div>'
            f'<div style="height:10px; border-radius:2px; border:1px solid #ccc; '
            f'background:linear-gradient(90deg, {grad});"></div>'
            '<div style="display:flex; justify-content:space-between; font-size:0.62rem; color:#555; margin-top:0.1rem;">'
            '<span>Lower</span><span>Higher</span></div></div>'
        )
    return '<div style="padding:0.35rem 0.45rem; background:#f8f9fa; border-radius:4px; border:1px solid #e9ecef;">' + "".join(
        parts
    ) + "</div>"


def _lane_a_snapshot_metric_columns(df: pd.DataFrame) -> list[str]:
    skip = {
        "lad_code",
        "la_name",
        "region_code",
        "region_name",
        "supply_financial_year",
        "median_price_period_label",
        "median_price_new_period_label",
    }
    out: list[str] = []
    for c in df.columns:
        if c in skip:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            out.append(c)
    return sorted(set(out))


def _load_lad_region_lookup() -> pd.DataFrame:
    if not _LAD_LOOKUP.is_file():
        return pd.DataFrame()
    lu = pd.read_csv(_LAD_LOOKUP)
    lu["lad_code"] = lu["lad_code"].map(_norm_lad)
    return lu


def _render_region_lane_b_map() -> None:
    """Lane B snapshot choropleth on region polygons (honest regional shading)."""
    use_3d = st.sidebar.checkbox(
        "3D extruded view (Pydeck)",
        value=False,
        help="Extrudes polygons by mapped value.",
    )
    geo_path = _region_geo_path()
    if geo_path is None:
        st.error(
            "Missing `data/geo/regions_uk_wgs84.geojson`. Run: `python scripts/download_region_boundaries.py`"
        )
        return
    reg_p = PROCESSED_DIR / f"{_REG_SNAPSHOT}.parquet"
    if not reg_p.is_file():
        st.warning(
            f"Missing `{reg_p.name}`. Run `python joins/build_la_housing_market_snapshot.py` "
            "after upstream ETLs."
        )
        return
    reg = load_processed_parquet(str(reg_p))
    reg["region_code"] = reg["region_code"].map(_norm_region)
    metric_cols = region_snapshot_metric_columns(reg)
    if not metric_cols:
        st.error("No numeric columns in region snapshot.")
        return
    val_col = st.sidebar.selectbox(
        "Region snapshot column",
        options=metric_cols,
        format_func=lambda c: c.replace("_", " "),
    )
    reg["value"] = pd.to_numeric(reg[val_col], errors="coerce")
    display = reg.dropna(subset=["value"]).copy()
    display["lad_code"] = display["region_code"]
    display["la_name"] = display["region_name"].astype(str)
    display["region"] = display["region_name"].astype(str)
    display["dwellings_raw"] = np.nan
    metric = "lane_b_region"
    period_note = f"Lane B · **{val_col}**"
    meta_p = PROCESSED_DIR / f"{_REG_SNAPSHOT}.meta.json"
    if meta_p.is_file():
        try:
            mj = json.loads(meta_p.read_text(encoding="utf-8"))
            period_note += (
                f" · supply FY **{mj.get('supply_financial_year', '—')}** · "
                f"EE window **{mj.get('ee_rolling_period', '—')}**"
            )
            if mj.get("caveat"):
                st.info(str(mj["caveat"])[:800] + ("…" if len(str(mj["caveat"])) > 800 else ""))
        except (OSError, json.JSONDecodeError):
            pass

    regions_all = sorted(display["region"].dropna().astype(str).unique().tolist())
    region_pick = st.sidebar.multiselect(
        "Regions / nations (empty = all)",
        options=regions_all,
        default=[],
    )
    if region_pick:
        display = display[display["region"].isin(region_pick)]

    top_n = st.sidebar.slider("Top / bottom N in table", min_value=3, max_value=30, value=10)

    val_series = display.set_index("lad_code")["value"]
    code_to_color, bin_edges = _quantile_colors(val_series, n_bins=5)
    vm = display["value"]
    median_v = float(vm.median(skipna=True)) if vm.notna().any() else float("nan")
    mean_v = float(vm.mean(skipna=True)) if vm.notna().any() else float("nan")
    per_eff = False

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Regions (filtered)", f"{len(display):,}")
    m2.metric("Median (mapped value)", _fmt_map_value(median_v, metric=metric, per_1000=per_eff))
    m3.metric("Mean (mapped value)", _fmt_map_value(mean_v, metric=metric, per_1000=per_eff))
    m4.metric("Period / note", period_note or "—")

    st.subheader(f"Lane B region snapshot — {val_col.replace('_', ' ')}")

    leg_rows, show_grad = _quantile_legend_rows(
        bin_edges, _QUANTILE_COLORS, metric=metric, per_eff=per_eff
    )
    st.markdown(
        _legend_html_block(
            leg_rows,
            no_data_hex=_NO_DATA_COLOR,
            palette=_QUANTILE_COLORS,
            show_gradient=show_grad,
        ),
        unsafe_allow_html=True,
    )

    raw_g = json.loads(_geojson_text(str(geo_path)))
    gj = copy.deepcopy(raw_g)
    feats = gj.get("features") or []
    key_prop = _detect_code_key((feats[0].get("properties") or {})) if feats else "lad_code"

    name_by_lad = display.set_index("lad_code")["la_name"].to_dict()
    val_by_lad = display.set_index("lad_code")["value"].to_dict()
    raw_by_lad = display.set_index("lad_code")["dwellings_raw"].to_dict()

    vmin = float(vm.min(skipna=True)) if vm.notna().any() else 0.0
    vmax = float(vm.max(skipna=True)) if vm.notna().any() else 1.0
    vspan = max(vmax - vmin, 1e-9)

    for feat in feats:
        props = feat.setdefault("properties", {})
        code = props.get(key_prop)
        if code is None:
            code = props.get("lad_code")
        code_s = _norm_lad(code) if code is not None else ""
        nm = name_by_lad.get(code_s) or props.get("region_name") or ""
        props["tooltip_name"] = str(nm)
        props["tooltip_code"] = code_s or "—"
        props["tooltip_fy"] = period_note
        v = val_by_lad.get(code_s)
        v_clean = None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        props["tooltip_value"] = _fmt_map_value(v_clean, metric=metric, per_1000=per_eff)
        raw_v = raw_by_lad.get(code_s)
        raw_clean = None if raw_v is None or (isinstance(raw_v, float) and np.isnan(raw_v)) else float(raw_v)
        props["tooltip_raw"] = _fmt_num(raw_clean, per_1000=False)
        fill = code_to_color.get(code_s, _NO_DATA_COLOR)
        fr, fg, fb = _hex_to_rgb(fill)
        props["fill_r"], props["fill_g"], props["fill_b"] = fr, fg, fb
        if v_clean is not None:
            props["elevation"] = float((v_clean - vmin) / vspan * 250_000.0)
        else:
            props["elevation"] = 0.0

    tooltip = folium.GeoJsonTooltip(
        fields=["tooltip_name", "tooltip_code", "tooltip_value", "tooltip_fy"],
        aliases=["Region", "Code", "Mapped value", "Period / note"],
        sticky=True,
        localize=False,
    )

    def style_function(feature: dict) -> dict:
        props = feature.get("properties") or {}
        code = props.get(key_prop) or props.get("lad_code")
        code_s = _norm_lad(code) if code is not None else ""
        fill = code_to_color.get(code_s, _NO_DATA_COLOR)
        return {
            "fillColor": fill,
            "color": "#333333",
            "weight": 0.35,
            "fillOpacity": 0.82,
        }

    def highlight_function(_feature: dict) -> dict:
        return {"weight": 2.0, "color": "#111111", "fillOpacity": 0.92}

    if use_3d:
        try:
            import pydeck as pdk
        except ImportError:
            st.error("Install **pydeck** for 3D view: `pip install pydeck`")
            use_3d = False

    if use_3d:
        gj_deck = copy.deepcopy(gj)
        deck_feats = gj_deck.get("features") or []
        if len(deck_feats) > _PYDECK_MAX_FEATURES:
            st.warning(
                f"3D view: using first {_PYDECK_MAX_FEATURES} of {len(deck_feats)} features for performance."
            )
            gj_deck["features"] = deck_feats[:_PYDECK_MAX_FEATURES]
        view_state = pdk.ViewState(latitude=54.2, longitude=-2.5, zoom=5.5, pitch=45.0, bearing=0)
        layer = pdk.Layer(
            "GeoJsonLayer",
            data=gj_deck,
            extruded=True,
            get_elevation="properties.elevation",
            elevation_scale=1,
            get_fill_color="[properties.fill_r, properties.fill_g, properties.fill_b, 200]",
            stroked=True,
            get_line_color=[80, 80, 80],
            line_width_min_pixels=0.4,
            pickable=True,
            auto_highlight=True,
        )
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=pdk.map_styles.CARTO_LIGHT,
            tooltip={
                "html": (
                    "<b>{properties.tooltip_name}</b><br/>"
                    "{properties.tooltip_code}<br/>"
                    "{properties.tooltip_value}"
                ),
                "style": {"color": "white"},
            },
        )
        st.pydeck_chart(deck, width="stretch", height=_MAP_HEIGHT)
    else:
        m = folium.Map(tiles="cartodbpositron", zoom_start=6, location=[54.2, -2.5])
        Fullscreen().add_to(m)
        folium.GeoJson(
            data=gj,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=tooltip,
        ).add_to(m)
        bounds = _geojson_bounds(gj)
        m.fit_bounds(bounds, padding=(20, 20))
        st_folium(m, use_container_width=True, height=_MAP_HEIGHT)

    if bin_edges:
        edge_txt = " → ".join(f"{e:,.3g}" for e in bin_edges[:6])
        if len(bin_edges) > 6:
            edge_txt += " …"
        st.caption(
            f"Numeric bin edges (approx.): {edge_txt}. "
            "Polygons outside the filtered list stay **grey** unless they have a value in the selection."
        )
    else:
        st.caption(
            "Little variation in the selection — see the colour key. "
            "Polygons outside the filtered list stay **grey** unless they have a value in the selection."
        )

    ranked = display.dropna(subset=["value"]).sort_values("value", ascending=False)
    top = ranked.head(top_n)
    bottom = ranked.tail(top_n).sort_values("value", ascending=True)
    export_cols = [c for c in ranked.columns if c not in ("dwellings_raw",)]
    label_entity = "Region"
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Top {top_n}** (highest mapped value)")
        show = top[export_cols].rename(
            columns={
                "la_name": label_entity,
                "lad_code": "Code",
                "region": "Nation / grouping",
                "value": "Mapped value",
            }
        )
        st.dataframe(show, width=ST_WIDTH, hide_index=True)
        st.download_button(
            "Download CSV (top)",
            data=show.to_csv(index=False).encode("utf-8"),
            file_name="map_top_lane_b_region.csv",
            mime="text/csv",
        )
    with col_b:
        st.markdown(f"**Bottom {top_n}** (lowest mapped value)")
        show_b = bottom[export_cols].rename(
            columns={
                "la_name": label_entity,
                "lad_code": "Code",
                "region": "Nation / grouping",
                "value": "Mapped value",
            }
        )
        st.dataframe(show_b, width=ST_WIDTH, hide_index=True)
        st.download_button(
            "Download CSV (bottom)",
            data=show_b.to_csv(index=False).encode("utf-8"),
            file_name="map_bottom_lane_b_region.csv",
            mime="text/csv",
        )


def main() -> None:
    st.set_page_config(page_title="Map — local authority", layout="wide")
    st.title("Map: housing choropleth (LA and region)")
    st.caption(
        "LA GeoJSON under `data/geo/` — run `python scripts/download_lad_boundaries.py` for UK LAD polygons. "
        "Region Lane B map uses `regions_uk_wgs84.geojson` — run `python scripts/download_region_boundaries.py`."
    )
    st.divider()
    ogl_attribution_expander()

    geog_mode = st.sidebar.radio(
        "Geography",
        options=("la", "region_lane_b"),
        format_func=lambda k: {
            "la": "Local authorities",
            "region_lane_b": "Regions (Lane B snapshot)",
        }[k],
        horizontal=True,
    )
    if geog_mode == "region_lane_b":
        _render_region_lane_b_map()
        return

    metric = st.sidebar.selectbox(
        "Map metric",
        options=(
            "house_building",
            "house_building_mainfuel",
            "median_price_existing",
            "median_price_new",
            "affordability_ratio",
            "lane_a_snapshot",
            "epc_band_c_regional",
        ),
        format_func=lambda k: {
            "house_building": "House building (starts / completions)",
            "house_building_mainfuel": "House building × main fuel (joined LA supply + fuel %)",
            "median_price_existing": "Median price — existing dwellings (HPSSA 2a)",
            "median_price_new": "Median price — new dwellings (HPSSA 2a)",
            "affordability_ratio": "Affordability ratio (price ÷ earnings, table 5c)",
            "lane_a_snapshot": "Lane A snapshot — pick any numeric column",
            "epc_band_c_regional": "EPC band C % (regional value on LA areas — see note)",
        }[k],
    )

    geo_path = _lad_geo_path()
    if geo_path is None:
        st.error("No GeoJSON found under `data/geo/`. See `data/geo/README.md`.")
        return

    lookup_df = _load_lad_region_lookup()
    use_3d = st.sidebar.checkbox(
        "3D extruded view (Pydeck)",
        value=False,
        help="Extrudes polygons by mapped value. Large GeoJSONs may be slow; capped for performance.",
    )

    # --- Build display (lad, la_name, region, value, dwellings_raw optional) ---
    per_1000 = False
    fy = ""
    measure = "starts"
    period_note = ""
    hb_ed = ""
    med_ed = ""
    med_new_ed = ""
    pe_ed = ""
    epc_ed = ""
    val_col_lane_a: str | None = None
    hb_mf_meta_note = ""

    if metric == "house_building":
        hb_ed = st.sidebar.selectbox(
            "House building edition",
            list(HOUSEBUILDING_LA_EDITIONS.keys()),
            format_func=lambda k: HOUSEBUILDING_LA_EDITIONS[k].label,
        )
        pq = PROCESSED_DIR / f"ons_housebuilding_la_{hb_ed}_tidy.parquet"
        if not pq.is_file():
            st.warning(f"Missing `{pq.name}`. Run: `python ons_housebuilding_la_etl.py --edition {hb_ed}`")
            return
        hb = _load_hb(str(pq))
        hb["financial_year"] = hb["financial_year"].astype(str)
        hb["measure"] = hb["measure"].astype(str).str.lower()
        years = sorted(hb["financial_year"].dropna().unique().tolist())
        if not years:
            st.error("No financial years in house-building file.")
            return
        pop_path = PROCESSED_DIR / "census2021_la_population_2021.parquet"
        has_pop = pop_path.is_file()
        fy = st.sidebar.selectbox("Financial year", options=years, index=len(years) - 1)
        measure = st.sidebar.radio("Measure", options=["starts", "completions"], horizontal=True)
        per_1000 = st.sidebar.checkbox(
            "Per 1,000 residents (Census 2021)",
            value=False,
            help="Uses `census2021_la_population_2021.parquet` (England & Wales LAs only).",
            disabled=not has_pop,
        )
        if not has_pop and per_1000:
            per_1000 = False

        sub = hb[(hb["financial_year"] == fy) & (hb["measure"] == measure)].copy()
        sub["lad"] = sub["Local Authority Code"].map(_norm_lad)
        sub["dwellings"] = pd.to_numeric(sub["dwellings"], errors="coerce")
        agg = (
            sub.groupby("lad", as_index=False)
            .agg(
                dwellings=("dwellings", "sum"),
                la_name=("Local Authority Name", "first"),
                region=("Region or Country Name", "first"),
            )
        )
        display = agg.rename(columns={"lad": "lad_code"})
        if per_1000 and has_pop:
            pop = _load_pop(str(pop_path))
            pop["lad_code"] = pop["lad_code"].map(_norm_lad)
            pop["population"] = pd.to_numeric(pop["population"], errors="coerce")
            display = display.merge(pop[["lad_code", "population"]], on="lad_code", how="left")
            display["value"] = np.where(
                display["population"].notna() & (display["population"] > 0),
                display["dwellings"] / display["population"] * 1000.0,
                np.nan,
            )
        else:
            display["value"] = display["dwellings"]
        display["dwellings_raw"] = display["dwellings"]
        period_note = f"Financial year **{fy}**"

    elif metric == "house_building_mainfuel":
        mf_paths = sorted(PROCESSED_DIR.glob("joined_la_housebuilding_mainfuel_*.parquet"))
        if not mf_paths:
            st.warning(
                "No `joined_la_housebuilding_mainfuel_*.parquet` found. "
                "Run `python joins/build_joined_la_housebuilding_mainfuel.py`."
            )
            return
        labels = [p.stem.replace("joined_la_housebuilding_mainfuel_", "") for p in mf_paths]
        pick_i = st.sidebar.selectbox(
            "Joined file (house building edition × main fuel edition)",
            options=list(range(len(mf_paths))),
            format_func=lambda i: labels[int(i)],
        )
        jpath = mf_paths[int(pick_i)]
        jdf = load_processed_parquet(jpath.name)
        if "lad_code" not in jdf.columns:
            jdf = jdf.copy()
            jdf["lad_code"] = jdf["Local Authority Code"].map(_norm_lad)
        jdf["financial_year"] = jdf["financial_year"].astype(str)
        jdf["measure"] = jdf["measure"].astype(str).str.lower()
        years = sorted(jdf["financial_year"].dropna().unique().tolist())
        if not years:
            st.error("No financial years in joined house building × main fuel file.")
            return
        fy = st.sidebar.selectbox("Financial year", options=years, index=len(years) - 1)
        measure = st.sidebar.radio("Measure", options=["starts", "completions"], horizontal=True)
        sub = jdf[(jdf["financial_year"] == fy) & (jdf["measure"] == measure)].copy()
        if sub.empty:
            st.error("No rows for the selected financial year and measure.")
            return
        fuel_rows = sub.drop_duplicates(
            subset=["mainfuel_sheet", "fuel_or_method", "dwelling_class"], keep="first"
        )
        fuel_choices: list[tuple[str, str, str | float]] = []
        for _, fr in fuel_rows.iterrows():
            sheet = str(fr["mainfuel_sheet"])
            fuel = str(fr["fuel_or_method"])
            dc = fr["dwelling_class"]
            dc_s = "" if pd.isna(dc) else str(dc)
            fuel_choices.append((sheet, fuel, dc_s))
        fuel_choices.sort(key=lambda t: (t[0], t[1], t[2]))

        def _fuel_label(t: tuple[str, str, str | float]) -> str:
            sheet, fuel, dc_s = t
            return f"{sheet} · {fuel}" + (f" · {dc_s}" if dc_s else "")

        fidx = st.sidebar.selectbox(
            "Main fuel breakdown",
            options=list(range(len(fuel_choices))),
            format_func=lambda i: _fuel_label(fuel_choices[int(i)]),
        )
        fs, ff, fdc = fuel_choices[int(fidx)]
        sel = sub[sub["mainfuel_sheet"].astype(str) == fs].copy()
        sel = sel[sel["fuel_or_method"].astype(str) == ff]
        if fdc == "":
            sel = sel[sel["dwelling_class"].isna() | (sel["dwelling_class"].astype(str).str.strip() == "")]
        else:
            sel = sel[sel["dwelling_class"].astype(str).str.strip() == fdc]
        if sel.empty:
            st.error("No rows for the selected fuel breakdown (check dwelling class filter).")
            return
        sel["mainfuel_pct"] = pd.to_numeric(sel["mainfuel_pct"], errors="coerce")
        sel["dwellings"] = pd.to_numeric(sel["dwellings"], errors="coerce")
        display = (
            sel.groupby("lad_code", as_index=False)
            .agg(
                value=("mainfuel_pct", "first"),
                dwellings_raw=("dwellings", "first"),
                la_name=("Local Authority Name", "first"),
                region=("Region or Country Name", "first"),
            )
        )
        display["region"] = display["region"].fillna("—")
        period_note = f"FY **{fy}** · **{measure}** · mapped: main fuel % · {_fuel_label((fs, ff, fdc))}"
        meta_side = jpath.with_suffix(".meta.json")
        if meta_side.is_file():
            try:
                mj = json.loads(meta_side.read_text(encoding="utf-8"))
                hb_mf_meta_note = str(mj.get("caveat", ""))
                if hb_mf_meta_note:
                    period_note += f" · {hb_mf_meta_note[:120]}"
            except (OSError, json.JSONDecodeError):
                pass

    elif metric == "median_price_existing":
        med_ed = st.sidebar.selectbox(
            "Median price (existing) edition",
            list(MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS.keys()),
            format_func=lambda k: MEDIAN_PRICE_EXISTING_ADMIN_EDITIONS[k].label,
        )
        mp = PROCESSED_DIR / f"ons_median_price_existing_admin_{med_ed}_2a_tidy.parquet"
        if not mp.is_file():
            st.warning(f"Missing `{mp.name}`. Run: `python ons_median_price_admin_etl.py --dataset existing --edition {med_ed}`")
            return
        med = load_processed_parquet(f"ons_median_price_existing_admin_{med_ed}_2a_tidy.parquet")
        df, pl = latest_median_price_existing_la(med)
        if df.empty:
            st.error("No local-authority median price rows in file.")
            return
        display = df.merge(
            lookup_df[["lad_code", "region_name"]],
            on="lad_code",
            how="left",
        )
        display["region"] = display["region_name"].fillna("—")
        display = display.drop(columns=["region_name"], errors="ignore")
        display["dwellings_raw"] = np.nan
        period_note = f"Median existing · **{pl}**" if pl else ""

    elif metric == "median_price_new":
        med_new_ed = st.sidebar.selectbox(
            "Median price (new) edition",
            list(MEDIAN_PRICE_NEW_ADMIN_EDITIONS.keys()),
            format_func=lambda k: MEDIAN_PRICE_NEW_ADMIN_EDITIONS[k].label,
        )
        mp = PROCESSED_DIR / f"ons_median_price_new_admin_{med_new_ed}_2a_tidy.parquet"
        if not mp.is_file():
            st.warning(
                f"Missing `{mp.name}`. Run: `python ons_median_price_admin_etl.py --dataset new --edition {med_new_ed}`"
            )
            return
        med = load_processed_parquet(f"ons_median_price_new_admin_{med_new_ed}_2a_tidy.parquet")
        df, pl = latest_median_price_new_la(med)
        if df.empty:
            st.error("No local-authority median price (new) rows in file.")
            return
        display = df.merge(
            lookup_df[["lad_code", "region_name"]],
            on="lad_code",
            how="left",
        )
        display["region"] = display["region_name"].fillna("—")
        display = display.drop(columns=["region_name"], errors="ignore")
        display["dwellings_raw"] = np.nan
        period_note = f"Median new · **{pl}**" if pl else ""

    elif metric == "affordability_ratio":
        pe_ed = st.sidebar.selectbox(
            "Price / earnings edition",
            list(PRICE_EARNINGS_RATIO_EDITIONS.keys()),
            format_func=lambda k: PRICE_EARNINGS_RATIO_EDITIONS[k].label,
        )
        df, pl, y = latest_affordability_ratio_la_only(PROCESSED_DIR, pe_ed)
        if df.empty:
            st.warning(
                f"Could not build affordability snapshot. Run `python ons_price_earnings_ratio_etl.py --edition {pe_ed}` "
                "so tables 5a–5c exist."
            )
            return
        display = df.merge(lookup_df[["lad_code", "region_name"]], on="lad_code", how="left")
        display["region"] = display["region_name"].fillna("—")
        display = display.drop(columns=["region_name"], errors="ignore")
        display["dwellings_raw"] = np.nan
        period_note = f"Ratio (5c) · year **{y}** · **{pl}**" if pl else ""

    elif metric == "lane_a_snapshot":
        snap_p = PROCESSED_DIR / f"{_LA_SNAPSHOT}.parquet"
        if not snap_p.is_file():
            st.warning(
                f"Missing `{snap_p.name}`. Run `python joins/build_la_housing_market_snapshot.py` "
                "to use Lane A snapshot metrics on the map."
            )
            return
        snap = load_processed_parquet(str(snap_p))
        snap["lad_code"] = snap["lad_code"].map(_norm_lad)
        metric_cols = _lane_a_snapshot_metric_columns(snap)
        if not metric_cols:
            st.error("No numeric columns found in Lane A snapshot.")
            return
        val_col = st.sidebar.selectbox("Snapshot column", options=metric_cols, format_func=lambda c: c.replace("_", " "))
        val_col_lane_a = val_col
        snap["value"] = pd.to_numeric(snap[val_col], errors="coerce")
        cols = ["lad_code", "la_name", "value"]
        if "region_name" in snap.columns:
            cols.append("region_name")
        display = snap[cols].dropna(subset=["value"]).copy()
        if "region_name" in display.columns:
            display["region"] = display["region_name"].astype(str)
            display = display.drop(columns=["region_name"], errors="ignore")
        elif not lookup_df.empty:
            display = display.merge(lookup_df[["lad_code", "region_name"]], on="lad_code", how="left")
            display["region"] = display["region_name"].fillna("—")
            display = display.drop(columns=["region_name"], errors="ignore")
        else:
            display["region"] = "—"
        display["dwellings_raw"] = np.nan
        meta_p = PROCESSED_DIR / f"{_LA_SNAPSHOT}.meta.json"
        period_note = f"Lane A snapshot · **{val_col}**"
        if meta_p.is_file():
            try:
                mj = json.loads(meta_p.read_text(encoding="utf-8"))
                period_note += f" · FY **{mj.get('supply_financial_year', '—')}**"
            except (OSError, json.JSONDecodeError):
                pass

    else:
        epc_ed = st.sidebar.selectbox(
            "EPC bands edition",
            list(EPC_EDITIONS.keys()),
            format_func=lambda k: EPC_EDITIONS[k].label,
        )
        epc_path = PROCESSED_DIR / f"ons_epc_bands_{epc_ed}_1a_tidy.parquet"
        if not epc_path.is_file():
            st.warning(f"Missing `{epc_path.name}`. Run: `python ons_epc_etl.py --edition {epc_ed}`")
            return
        if lookup_df.empty:
            st.error(f"Missing LAD lookup at `{_LAD_LOOKUP}`.")
            return
        epc = load_processed_parquet(f"ons_epc_bands_{epc_ed}_1a_tidy.parquet")
        display = epc_band_c_per_la_from_lookup(epc, lookup_df)
        display["region"] = display["region_name"].astype(str)
        display["dwellings_raw"] = np.nan
        period_note = "EPC **band C %** (England & Wales regions; constant within each region)"

    snap_full = pd.DataFrame()
    mains_gas_col: str | None = None
    lane_a_ctx = False
    snap_p = PROCESSED_DIR / f"{_LA_SNAPSHOT}.parquet"
    if snap_p.is_file():
        snap_full = load_processed_parquet(str(snap_p))
        snap_full["lad_code"] = snap_full["lad_code"].map(_norm_lad)
        mains_gas_col = pick_mf2a_mains_gas_column(list(snap_full.columns))
        excl = val_col_lane_a if metric == "lane_a_snapshot" else None
        display = merge_lane_a_snapshot_columns(display, snap_full, exclude_duplicate_of=excl)
        lane_a_ctx = any(
            c in display.columns
            for c in (
                "median_price_existing_gbp",
                "supply_starts",
                "vacant_dwellings_count",
                "pe_affordability_ratio",
            )
        ) or bool(mains_gas_col)

    regions_all = sorted(display["region"].dropna().astype(str).unique().tolist())
    region_pick = st.sidebar.multiselect(
        "Regions / nations (empty = all)",
        options=regions_all,
        default=[],
    )
    if region_pick:
        display = display[display["region"].isin(region_pick)]

    top_n = st.sidebar.slider("Top / bottom N in table", min_value=3, max_value=30, value=10)

    val_series = display.set_index("lad_code")["value"]
    code_to_color, bin_edges = _quantile_colors(val_series, n_bins=5)

    if metric == "house_building":
        total_raw = float(display["dwellings_raw"].sum(skipna=True))
    elif metric == "house_building_mainfuel":
        total_raw = float(display["dwellings_raw"].sum(skipna=True))
    else:
        total_raw = float("nan")
    vm = display["value"]
    median_v = float(vm.median(skipna=True)) if vm.notna().any() else float("nan")
    mean_v = float(vm.mean(skipna=True)) if vm.notna().any() else float("nan")
    per_eff = per_1000 if metric == "house_building" else False

    m1, m2, m3, m4 = st.columns(4)
    if metric == "house_building":
        m1.metric(f"Total {measure} (filtered)", f"{total_raw:,.0f}" if not np.isnan(total_raw) else "—")
    elif metric == "house_building_mainfuel":
        m1.metric(f"Total {measure} (dwellings, filtered)", f"{total_raw:,.0f}" if not np.isnan(total_raw) else "—")
    else:
        m1.metric("Rows (filtered LAs)", f"{len(display):,}")
    m2.metric("Median per LA (mapped value)", _fmt_map_value(median_v, metric=metric, per_1000=per_eff))
    m3.metric("Mean per LA (mapped value)", _fmt_map_value(mean_v, metric=metric, per_1000=per_eff))
    m4.metric("Period / note", period_note or "—")

    if metric == "epc_band_c_regional":
        st.warning(
            "**EPC:** ONS table 1a is published at **country/region** only. Each LA polygon is coloured with its "
            "region’s **band C %** (same colour for all LAs in that region). Not LA stock estimates."
        )

    title_map = {
        "house_building": f"{measure.title()} — {fy}" + (" (per 1,000 residents)" if per_1000 else ""),
        "house_building_mainfuel": f"Main fuel % — {fy} · {measure}",
        "median_price_existing": "Median price existing (£)",
        "median_price_new": "Median price new build (£)",
        "affordability_ratio": "Affordability ratio (house price ÷ workplace earnings)",
        "lane_a_snapshot": "Lane A snapshot column (per LA)",
        "epc_band_c_regional": "EPC band C — % of dwellings (regional value on LA map)",
    }
    st.subheader(title_map[metric])
    if metric == "house_building_mainfuel" and hb_mf_meta_note:
        st.caption(hb_mf_meta_note)

    leg_rows, show_grad = _quantile_legend_rows(
        bin_edges, _QUANTILE_COLORS, metric=metric, per_eff=per_eff
    )
    st.markdown(
        _legend_html_block(
            leg_rows,
            no_data_hex=_NO_DATA_COLOR,
            palette=_QUANTILE_COLORS,
            show_gradient=show_grad,
        ),
        unsafe_allow_html=True,
    )

    raw_g = json.loads(_geojson_text(str(geo_path)))
    gj = copy.deepcopy(raw_g)
    feats = gj.get("features") or []
    key_prop = _detect_code_key((feats[0].get("properties") or {})) if feats else "lad_code"

    name_by_lad = display.set_index("lad_code")["la_name"].to_dict()
    val_by_lad = display.set_index("lad_code")["value"].to_dict()
    raw_by_lad = display.set_index("lad_code")["dwellings_raw"].to_dict()
    disp_tooltip = display.drop_duplicates(subset=["lad_code"], keep="first")
    disp_by_lad = disp_tooltip.set_index("lad_code") if not disp_tooltip.empty else pd.DataFrame()

    vmin = float(vm.min(skipna=True)) if vm.notna().any() else 0.0
    vmax = float(vm.max(skipna=True)) if vm.notna().any() else 1.0
    vspan = max(vmax - vmin, 1e-9)

    for feat in feats:
        props = feat.setdefault("properties", {})
        code = props.get(key_prop)
        if code is None:
            code = props.get("lad_code")
        code_s = _norm_lad(code) if code is not None else ""
        nm = name_by_lad.get(code_s) or props.get("LAD22NM") or props.get("LAD21NM") or ""
        props["tooltip_name"] = str(nm)
        props["tooltip_code"] = code_s or "—"
        props["tooltip_fy"] = fy if metric == "house_building" else period_note
        v = val_by_lad.get(code_s)
        v_clean = None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        props["tooltip_value"] = _fmt_map_value(v_clean, metric=metric, per_1000=per_eff)
        raw_v = raw_by_lad.get(code_s)
        raw_clean = None if raw_v is None or (isinstance(raw_v, float) and np.isnan(raw_v)) else float(raw_v)
        if metric == "house_building":
            props["tooltip_raw"] = _fmt_num(raw_clean, per_1000=per_eff)
        elif metric == "house_building_mainfuel":
            props["tooltip_raw"] = _fmt_num(raw_clean, per_1000=False) if raw_clean is not None else "—"
        else:
            props["tooltip_raw"] = "—"
        if lane_a_ctx and code_s and not disp_by_lad.empty and code_s in disp_by_lad.index:
            rr = disp_by_lad.loc[code_s]
            if isinstance(rr, pd.DataFrame):
                rr = rr.iloc[0]
            tw = snapshot_tooltip_strings(rr, mains_gas_col=mains_gas_col)
        else:
            tw = {k: "—" for k in ("snap_prices", "snap_supply", "snap_fuel", "snap_more")}
        props["snap_prices"] = tw["snap_prices"]
        props["snap_supply"] = tw["snap_supply"]
        props["snap_fuel"] = tw["snap_fuel"]
        props["snap_more"] = tw["snap_more"]
        fill = code_to_color.get(code_s, _NO_DATA_COLOR)
        fr, fg, fb = _hex_to_rgb(fill)
        props["fill_r"], props["fill_g"], props["fill_b"] = fr, fg, fb
        if v_clean is not None:
            props["elevation"] = float((v_clean - vmin) / vspan * 250_000.0)
        else:
            props["elevation"] = 0.0

    tip_fields = ["tooltip_name", "tooltip_code", "tooltip_value", "tooltip_raw", "tooltip_fy"]
    tip_aliases = ["Local authority", "Code", "Mapped value", "Raw / secondary", "Period / note"]
    if lane_a_ctx:
        tip_fields += ["snap_prices", "snap_supply", "snap_fuel", "snap_more"]
        tip_aliases += [
            "Lane A — prices",
            "Lane A — supply",
            "Lane A — main fuel",
            "Lane A — afford. / vacant",
        ]
    tooltip = folium.GeoJsonTooltip(
        fields=tip_fields,
        aliases=tip_aliases,
        sticky=True,
        localize=False,
    )

    def style_function(feature: dict) -> dict:
        props = feature.get("properties") or {}
        code = props.get(key_prop) or props.get("lad_code")
        code_s = _norm_lad(code) if code is not None else ""
        fill = code_to_color.get(code_s, _NO_DATA_COLOR)
        return {
            "fillColor": fill,
            "color": "#333333",
            "weight": 0.35,
            "fillOpacity": 0.82,
        }

    def highlight_function(_feature: dict) -> dict:
        return {"weight": 2.0, "color": "#111111", "fillOpacity": 0.92}

    if use_3d:
        try:
            import pydeck as pdk
        except ImportError:
            st.error("Install **pydeck** for 3D view: `pip install pydeck`")
            use_3d = False

    if use_3d:
        gj_deck = copy.deepcopy(gj)
        deck_feats = gj_deck.get("features") or []
        if len(deck_feats) > _PYDECK_MAX_FEATURES:
            st.warning(
                f"3D view: using first {_PYDECK_MAX_FEATURES} of {len(deck_feats)} features for performance."
            )
            gj_deck["features"] = deck_feats[:_PYDECK_MAX_FEATURES]
        view_state = pdk.ViewState(latitude=54.2, longitude=-2.5, zoom=5.5, pitch=45.0, bearing=0)
        layer = pdk.Layer(
            "GeoJsonLayer",
            data=gj_deck,
            extruded=True,
            get_elevation="properties.elevation",
            elevation_scale=1,
            get_fill_color="[properties.fill_r, properties.fill_g, properties.fill_b, 200]",
            stroked=True,
            get_line_color=[80, 80, 80],
            line_width_min_pixels=0.4,
            pickable=True,
            auto_highlight=True,
        )
        deck_html = (
            "<b>{properties.tooltip_name}</b><br/>"
            "{properties.tooltip_code}<br/>"
            "<b>{properties.tooltip_value}</b><br/>"
            "<small>Raw: {properties.tooltip_raw}</small><br/>"
            "<small>{properties.tooltip_fy}</small>"
        )
        if lane_a_ctx:
            deck_html += (
                "<br/><hr style='border-color:#666;margin:0.25rem 0;'/>"
                "<small>{properties.snap_prices}</small><br/>"
                "<small>{properties.snap_supply}</small><br/>"
                "<small>{properties.snap_fuel}</small><br/>"
                "<small>{properties.snap_more}</small>"
            )
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=pdk.map_styles.CARTO_LIGHT,
            tooltip={"html": deck_html, "style": {"color": "white"}},
        )
        st.pydeck_chart(deck, width="stretch", height=_MAP_HEIGHT)
    else:
        m = folium.Map(tiles="cartodbpositron", zoom_start=6, location=[54.2, -2.5])
        Fullscreen().add_to(m)
        folium.GeoJson(
            data=gj,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=tooltip,
        ).add_to(m)
        bounds = _geojson_bounds(gj)
        m.fit_bounds(bounds, padding=(20, 20))
        st_folium(m, use_container_width=True, height=_MAP_HEIGHT)

    if bin_edges:
        edge_txt = " → ".join(f"{e:,.3g}" for e in bin_edges[:6])
        if len(bin_edges) > 6:
            edge_txt += " …"
        st.caption(
            f"Numeric bin edges (approx.): {edge_txt}. "
            "Polygons outside the filtered regions stay **grey** unless they have a value in the selection."
        )
    else:
        st.caption(
            "Little variation in the selection — see the colour key. "
            "Polygons outside the filtered regions stay **grey** unless they have a value in the selection."
        )

    ranked = display.dropna(subset=["value"]).sort_values("value", ascending=False)
    top = ranked.head(top_n)
    bottom = ranked.tail(top_n).sort_values("value", ascending=True)
    base_export = ["la_name", "lad_code", "region", "value"]
    extra_export = [c for c in ranked.columns if c not in base_export and c != "dwellings_raw"]
    export_cols = base_export + extra_export
    export_cols = [c for c in export_cols if c in ranked.columns]
    ren = {
        "la_name": "Local authority",
        "lad_code": "Code",
        "region": "Region / nation",
        "value": "Mapped value",
    }

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Top {top_n}** (highest mapped value)")
        show = top[export_cols].rename(columns=ren)
        st.dataframe(show, width=ST_WIDTH, hide_index=True)
        st.download_button(
            "Download CSV (top)",
            data=show.to_csv(index=False).encode("utf-8"),
            file_name=f"map_top_{metric}.csv",
            mime="text/csv",
        )
    with col_b:
        st.markdown(f"**Bottom {top_n}** (lowest mapped value)")
        show_b = bottom[export_cols].rename(columns=ren)
        st.dataframe(show_b, width=ST_WIDTH, hide_index=True)
        st.download_button(
            "Download CSV (bottom)",
            data=show_b.to_csv(index=False).encode("utf-8"),
            file_name=f"map_bottom_{metric}.csv",
            mime="text/csv",
        )
    full_csv = ranked[export_cols].rename(columns=ren)
    st.download_button(
        "Download CSV (all filtered LAs)",
        data=full_csv.to_csv(index=False).encode("utf-8"),
        file_name=f"map_all_filtered_{metric}.csv",
        mime="text/csv",
    )


main()
