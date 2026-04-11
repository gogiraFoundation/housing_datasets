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

    la_path = PROCESSED_DIR / f"{_LA_STEM}.parquet"
    if not la_path.is_file():
        st.warning(f"Missing `{la_path.name}`. Run the join script above.")
        return

    df = load_processed_parquet(str(la_path))
    meta = {}
    mp = PROCESSED_DIR / f"{_LA_STEM}.meta.json"
    if mp.is_file():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    if meta.get("caveat"):
        st.info(meta["caveat"])

    c1, c2, c3 = st.columns(3)
    method = c1.selectbox("Method", ("kmeans", "agglomerative"), format_func=lambda x: x.replace("_", " "))
    n_clusters = c2.slider("Number of clusters", min_value=3, max_value=12, value=5)
    random_state = c3.number_input("Random seed (k-means / PCA)", min_value=0, value=0, step=1)

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
                tooltip=["lad_code", "la_name", "cluster_id", "region_name"],
            )
            .properties(height=420)
        )
        st.altair_chart(ch, width=ST_WIDTH)
    else:
        xcol = st.selectbox("X axis (numeric)", options=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])])
        ycol = st.selectbox(
            "Y axis (numeric)",
            options=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != xcol],
        )
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
