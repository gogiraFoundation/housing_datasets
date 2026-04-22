"""Streamlit: cluster local authorities on scaled Lane A indicators (k-means / hierarchical)."""

from __future__ import annotations

import json

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from streamlit_io import PROCESSED_DIR, load_processed_parquet
from streamlit_page_helpers import ogl_attribution_expander

from housing_analytics.clustering import cluster_local_authorities

_LA_STEM = "joined_la_housing_market_snapshot"
_REG_STEM = "region_housing_market_snapshot"


def main() -> None:
    st.set_page_config(page_title="LA clustering", layout="wide")
    st.title("Local authority clustering")
    st.caption(
        "K-means or hierarchical (Ward) clustering on **median-imputed**, **standardised** numeric columns "
        "from the Lane A snapshot. For exploration and policy grouping — **not** a forecast."
    )
    st.divider()
    ogl_attribution_expander()
    with st.expander("How to build input data"):
        st.markdown(
            f"Run `python joins/build_la_housing_market_snapshot.py` → "
            f"`data/processed/{_LA_STEM}.parquet`."
        )

    qp = st.query_params
    mode = st.sidebar.radio(
        "Clustering grain",
        ("Local authority (Lane A)", "Region (Lane B)"),
        index=0 if str(qp.get("grain", "la")) == "la" else 1,
    )
    st.query_params["grain"] = "la" if mode.startswith("Local") else "region"

    path = PROCESSED_DIR / (f"{_LA_STEM}.parquet" if mode.startswith("Local") else f"{_REG_STEM}.parquet")
    if not path.is_file():
        st.warning(f"Missing `{path.name}`. Run the join script above.")
        return

    df = load_processed_parquet(str(path))
    if mode.startswith("Region"):
        df = df.rename(columns={"region_code": "lad_code", "region_name": "la_name"}).copy()
    elif mode.startswith("Local"):
        merge_reg = st.sidebar.checkbox(
            "Add Lane B PRPI/HPI overlap metrics (by region_name)",
            value=False,
            help="Merges region-level overlap columns onto each LA for clustering; same geography as Lane B snapshot.",
        )
        if merge_reg:
            reg_p = PROCESSED_DIR / f"{_REG_STEM}.parquet"
            if reg_p.is_file():
                reg = load_processed_parquet(str(reg_p))
                extra = [c for c in ("hpi_growth_overlap_pct", "prpi_growth_overlap_pct", "hpi_minus_prpi_growth_pp") if c in reg.columns]
                if extra and "region_name" in df.columns:
                    df = df.merge(reg[["region_name", *extra]], on="region_name", how="left")
            else:
                st.caption(f"No `{_REG_STEM}.parquet`; run the join script to enable overlap metrics.")
    if len(df) < 4:
        st.warning("Need at least 4 rows to run clustering.")
        return

    meta = {}
    mp = PROCESSED_DIR / (f"{_LA_STEM}.meta.json" if mode.startswith("Local") else f"{_REG_STEM}.meta.json")
    if mp.is_file():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    if meta.get("caveat"):
        st.info(meta["caveat"])

    c1, c2, c3 = st.columns(3)
    method = c1.selectbox(
        "Method",
        ("kmeans", "agglomerative"),
        index=0 if str(qp.get("method", "kmeans")) == "kmeans" else 1,
        format_func=lambda x: x.replace("_", " "),
    )
    max_clusters = min(12, max(3, len(df) - 1)) if len(df) > 3 else 3
    default_clusters = int(qp.get("k", 5))
    n_clusters = c2.slider("Number of clusters", min_value=3, max_value=max_clusters, value=min(max(3, default_clusters), max_clusters))
    random_state = c3.number_input("Random seed (k-means / PCA)", min_value=0, value=int(qp.get("seed", 0)), step=1)
    st.query_params["method"] = method
    st.query_params["k"] = str(int(n_clusters))
    st.query_params["seed"] = str(int(random_state))

    try:
        result = cluster_local_authorities(
            df,
            n_clusters=int(n_clusters),
            method=method,
            random_state=int(random_state),
            pca_components=2,
        )
    except Exception as e:
        st.error(str(e))
        return

    labelled = result.frame.copy()
    if result.silhouette is not None:
        st.metric("Silhouette (higher is more separated)", f"{result.silhouette:.3f}")

    plot_df = labelled.copy()
    plot_df["cluster_id"] = plot_df["cluster_id"].astype(str)

    if result.pca_2d is not None and len(result.pca_2d) == len(plot_df):
        plot_df["pca_x"] = result.pca_2d[:, 0]
        plot_df["pca_y"] = result.pca_2d[:, 1]
        ch = (
            alt.Chart(plot_df)
            .mark_circle(size=60, opacity=0.7)
            .encode(
                x=alt.X("pca_x:Q", title="PCA 1"),
                y=alt.Y("pca_y:Q", title="PCA 2"),
                color=alt.Color("cluster_id:N", title="Cluster"),
                tooltip=[c for c in ["lad_code", "la_name", "cluster_id", "region_name"] if c in plot_df.columns],
            )
            .properties(height=420)
        )
        st.altair_chart(ch, width=ST_WIDTH)
    else:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        qx = str(qp.get("xcol", "")).strip()
        qy = str(qp.get("ycol", "")).strip()
        xi = num_cols.index(qx) if qx in num_cols else 0
        xcol = st.selectbox("X axis (numeric)", options=num_cols, index=xi)
        st.query_params["xcol"] = str(xcol)
        y_opts = [c for c in num_cols if c != xcol]
        if not y_opts:
            st.error("Need at least two numeric columns for scatter fallback.")
            return
        yi = y_opts.index(qy) if qy in y_opts else min(1, len(y_opts) - 1)
        ycol = st.selectbox("Y axis (numeric)", options=y_opts, index=yi)
        st.query_params["ycol"] = str(ycol)
        plot_df[xcol] = pd.to_numeric(plot_df[xcol], errors="coerce")
        plot_df[ycol] = pd.to_numeric(plot_df[ycol], errors="coerce")
        ch = (
            alt.Chart(plot_df.dropna(subset=[xcol, ycol]))
            .mark_circle(size=50, opacity=0.65)
            .encode(
                x=alt.X(f"{xcol}:Q"),
                y=alt.Y(f"{ycol}:Q"),
                color=alt.Color("cluster_id:N", title="Cluster"),
                tooltip=["lad_code", "la_name", "cluster_id"],
            )
            .properties(height=420)
        )
        st.altair_chart(ch, width=ST_WIDTH)

    st.subheader("Clusters")
    show = labelled.sort_values(["cluster_id", "la_name"] if "la_name" in labelled.columns else ["cluster_id"])
    st.dataframe(show, width=ST_WIDTH, height=min(650, 120 + 28 * min(len(show), 25)))

    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button("Download cluster assignments (CSV)", data=csv_bytes, file_name="la_clusters.csv", mime="text/csv")


main()
