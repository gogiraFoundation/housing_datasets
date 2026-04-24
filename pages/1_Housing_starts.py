"""Streamlit dashboard for UK local authority housing starts (tidy pipeline output)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from streamlit_io import PROCESSED_DIR, load_processed_csv, load_processed_parquet
from uk_local_authority_housing_data import DEFAULT_WORKBOOK, ID_COL_NAMES
TIDY_PARQUET = "uk_housing_starts_tidy.parquet"
TIDY_CSV = "uk_housing_starts_tidy.csv"


def _tidy_sources_snapshot(processed: Path) -> str:
    """Mtime/size so @st.cache_data invalidates when tidy outputs appear or change on disk."""
    parts: list[str] = []
    for name in (TIDY_PARQUET, TIDY_CSV):
        p = processed / name
        if p.is_file():
            stat = p.stat()
            parts.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
        else:
            parts.append(f"{name}:missing")
    return "|".join(parts)


def load_tidy(processed_dir_str: str, sources_snapshot: str) -> tuple[pd.DataFrame | None, str | None]:
    """Load tidy housing starts from Parquet (preferred) or CSV. Returns (df, source_label).

    Caching is handled inside ``load_processed_parquet`` / ``load_processed_csv`` (path + ``inputs_snapshot``).
    Do not wrap this function in ``@st.cache_data`` — that would double-cache the same data.
    The ``sources_snapshot`` string is passed through as ``inputs_snapshot`` on those loaders.
    """
    processed = Path(processed_dir_str)
    pq_path = processed / TIDY_PARQUET
    csv_path = processed / TIDY_CSV
    if pq_path.is_file():
        return load_processed_parquet(pq_path, inputs_snapshot=sources_snapshot), str(pq_path.name)
    if csv_path.is_file():
        return load_processed_csv(csv_path, inputs_snapshot=sources_snapshot), str(csv_path.name)
    return None, None


def _is_deployment_env() -> bool:
    return any(
        bool(os.environ.get(name))
        for name in ("DEPLOYMENT", "RENDER", "RAILWAY_ENVIRONMENT", "STREAMLIT_SHARING_MODE")
    )


def _try_build_tidy_dataset() -> tuple[bool, str | None]:
    """Best-effort build for deploy boots when tidy outputs are missing."""
    script = Path(__file__).resolve().parents[1] / "uk_local_authority_housing_data.py"
    if not script.is_file():
        return False, f"Pipeline script not found: {script}"
    cmd = [sys.executable, str(script)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"exit code {proc.returncode}"
    return False, detail


def _sorted_years(series: pd.Series) -> list[str]:
    years = series.dropna().astype(str).unique().tolist()
    return sorted(years)


def _streamlit_compat(df: pd.DataFrame) -> pd.DataFrame:
    """Nullable/extension dtypes from Parquet sometimes render as blank cells in st.dataframe."""
    out = df.copy()
    for col in out.columns:
        ser = out[col]
        dt = ser.dtype
        if pd.api.types.is_extension_array_dtype(dt):
            if isinstance(dt, (pd.Int64Dtype, pd.Float64Dtype, pd.Float32Dtype)) or (
                "Int" in str(dt) or "Float" in str(dt)
            ):
                out[col] = pd.to_numeric(ser, errors="coerce").astype("float64")
            elif str(dt).startswith("string[pyarrow]") or str(dt) == "string":
                out[col] = ser.astype("object").where(ser.notna(), None)
    return out


def main() -> None:
    st.set_page_config(
        page_title="UK housing starts",
        layout="wide",
    )
    st.title("UK local authority housing starts")
    st.caption(
        "Housing starts by local authority and financial year, from the tidy pipeline output under "
        "`data/processed/`."
    )
    st.divider()

    snap = _tidy_sources_snapshot(PROCESSED_DIR)
    df, source_name = load_tidy(str(PROCESSED_DIR), snap)

    if df is None:
        build_error: str | None = None
        if _is_deployment_env():
            with st.spinner("No tidy dataset found. Building deployment parquet now..."):
                built, build_error = _try_build_tidy_dataset()
            if built:
                snap = _tidy_sources_snapshot(PROCESSED_DIR)
                df, source_name = load_tidy(str(PROCESSED_DIR), snap)
                if df is not None:
                    st.success("Built and loaded tidy housing starts data for deployment.")

        if df is None:
            if build_error:
                st.warning(f"Auto-build attempt failed: {build_error}")
        st.warning("No tidy dataset found in `data/processed/`.")
        st.info(
            f"Run the pipeline from the repository root, for example:\n\n"
            f"`python uk_local_authority_housing_data.py`\n\n"
            f"The default input workbook is `{DEFAULT_WORKBOOK.name}` next to the pipeline script. "
            f"If that file is missing, use `-i` to point to your `.xlsx` file."
        )
        return

    st.sidebar.success(f"Loaded **{source_name}**")

    for col in ID_COL_NAMES:
        if col not in df.columns:
            st.error(f"Expected column {col!r} in tidy data.")
            return

    if "financial_year" not in df.columns or "starts" not in df.columns:
        st.error("Expected columns `financial_year` and `starts` in tidy data.")
        return

    df = df.copy()
    df["starts"] = pd.to_numeric(df["starts"], errors="coerce").astype("float64")
    df["financial_year"] = df["financial_year"].astype(str)

    all_years = _sorted_years(df["financial_year"])
    if not all_years:
        st.warning("No financial years in the dataset.")
        return

    regions = sorted(df["Region or Country Name"].dropna().astype(str).unique())
    las = sorted(df["Local Authority Name"].dropna().astype(str).unique())

    st.sidebar.subheader("Filters")
    region_pick = st.sidebar.multiselect(
        "Region or country",
        options=regions,
        default=[],
        help="Leave empty to include all regions.",
    )
    la_pick = st.sidebar.multiselect(
        "Local authority",
        options=las,
        default=[],
        help="Leave empty to include all local authorities.",
    )

    y_min = st.sidebar.selectbox("Financial year from", options=all_years, index=0)
    y_max = st.sidebar.selectbox(
        "Financial year to",
        options=all_years,
        index=len(all_years) - 1,
    )
    if all_years.index(y_min) > all_years.index(y_max):
        y_min, y_max = y_max, y_min

    year_span = [y for y in all_years if all_years.index(y_min) <= all_years.index(y) <= all_years.index(y_max)]

    filtered = df[df["financial_year"].isin(year_span)]
    if region_pick:
        filtered = filtered[filtered["Region or Country Name"].isin(region_pick)]
    if la_pick:
        filtered = filtered[filtered["Local Authority Name"].isin(la_pick)]

    if filtered.empty:
        st.info("No rows match the current filters.")
        return

    total_starts = filtered["starts"].sum(skipna=True)
    n_la = filtered["Local Authority Name"].nunique()
    n_years = filtered["financial_year"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total starts (filtered)", int(total_starts) if pd.notna(total_starts) else "—")
    c2.metric("Local authorities in view", f"{n_la:,}")
    c3.metric("Financial years in view", f"{n_years:,}")

    by_year = filtered.groupby("financial_year", as_index=False)["starts"].sum(min_count=1)
    by_year["financial_year"] = by_year["financial_year"].astype(str)
    by_year["starts"] = pd.to_numeric(by_year["starts"], errors="coerce").astype("float64")
    fy_order = {y: i for i, y in enumerate(all_years)}
    by_year["_ord"] = by_year["financial_year"].map(lambda x: fy_order.get(x, 9999))
    by_year = by_year.sort_values("_ord").drop(columns=["_ord"])

    if by_year["starts"].notna().any():
        line = (
            alt.Chart(by_year)
            .mark_line(point=True)
            .encode(
                x=alt.X("financial_year:N", title="Financial year", sort=all_years),
                y=alt.Y("starts:Q", title="Starts (sum)"),
                tooltip=[
                    "financial_year",
                    alt.Tooltip("starts", format=",.0f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(line, width=ST_WIDTH)
    else:
        st.warning("No numeric starts to plot for the selected filters.")

    la_totals_all = (
        filtered.groupby("Local Authority Name", as_index=False)
        .agg(
            total_starts=("starts", "sum"),
            region=("Region or Country Name", "first"),
        )
        .sort_values("total_starts", ascending=False, na_position="last")
    )
    la_totals_all = la_totals_all.rename(
        columns={"region": "Region or country", "total_starts": "Total starts (filtered period)"},
    )
    display_cols = ["Local Authority Name", "Region or country", "Total starts (filtered period)"]
    la_totals_all = la_totals_all[display_cols]
    la_totals_all = _streamlit_compat(la_totals_all)

    st.subheader("All local authorities")
    st.caption("One row per local authority matching your filters, sorted by total starts (highest first).")
    st.dataframe(
        la_totals_all,
        width=ST_WIDTH,
        height=max(180, min(600, 36 + 35 * len(la_totals_all))),
        column_config={
            "Total starts (filtered period)": st.column_config.NumberColumn(
                label="Total starts (filtered period)",
                format="%.0f",
            ),
        },
        hide_index=True,
    )

    n_la_filtered = len(la_totals_all)
    max_top = max(1, n_la_filtered)
    st.subheader("Bar chart (optional)")
    top_n = st.slider(
        "How many local authorities to include in the chart",
        min_value=1,
        max_value=max_top,
        value=max_top,
        help="Defaults to all. Reduce this if the chart is too tall.",
    )
    la_totals = (
        filtered.groupby("Local Authority Name", as_index=False)["starts"]
        .sum(min_count=1)
        .dropna(subset=["starts"])
        .nlargest(top_n, "starts")
    )
    la_totals["starts"] = pd.to_numeric(la_totals["starts"], errors="coerce").astype("float64")
    if not la_totals.empty:
        max_starts = float(la_totals["starts"].max())
        x_upper = max_starts * 1.08 if max_starts > 0 else 1.0
        bar = (
            alt.Chart(la_totals)
            .mark_bar()
            .encode(
                x=alt.X("starts:Q", title="Total starts", scale=alt.Scale(domain=[0.0, x_upper], nice=False)),
                y=alt.Y("Local Authority Name:N", sort="-x", title=""),
                tooltip=["Local Authority Name", alt.Tooltip("starts", format=",.0f")],
            )
            .properties(height=min(8000, max(120, 22 * len(la_totals))))
        )
        st.altair_chart(bar, width=ST_WIDTH)

    st.subheader("Filtered data (all rows)")
    st.dataframe(
        _streamlit_compat(filtered),
        width=ST_WIDTH,
        height=max(220, min(600, 120 + 28 * min(len(filtered), 25))),
    )

    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered data as CSV",
        data=csv_bytes,
        file_name="uk_housing_starts_filtered.csv",
        mime="text/csv",
    )

    st.caption(
        "Validate figures against your source workbook before using them for decisions. "
        "Other dashboard pages that use ONS data include licence text under **Open Government Licence and attribution**."
    )


main()
