"""Streamlit: ML backtests — time-series rolling forecast evaluation + LA benchmark residuals."""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from chart_theme import ST_WIDTH

from housing_analytics.forward_hpi import (
    SHEET1_GEOGRAPHIES,
    best_models_from_ts_backtest_json,
    forward_forecast_hpi_levels,
)

from ons_uk_hpi_monthly_config import UK_HPI_MONTHLY_EDITIONS

from streamlit_io import PROCESSED_DIR, load_processed_csv
from streamlit_page_helpers import ogl_attribution_expander

_GLOB_TS = "ts_backtest_*.json"
_GLOB_BENCH_CSV = "la_benchmark_*_residuals.csv"


@st.cache_data(ttl=120)
def _read_json(path_str: str) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def _glob_processed(pattern: str) -> list[Path]:
    return sorted(PROCESSED_DIR.glob(pattern), key=lambda x: x.name)


_HPI_DATASETS = frozenset({"uk_hpi_monthly", "uk_hpi_annual"})
_UK_AGG = frozenset({"United Kingdom", "Great Britain"})
# Always offer these horizons in the UI; rows appear only if a matching JSON exists.
_PRESET_HORIZONS: tuple[int, ...] = (1, 2, 3, 6, 9, 12, 18, 24, 36, 48, 120)


def _geo_scope(geography: str) -> str:
    g = str(geography).strip()
    if g in _UK_AGG:
        return "UK aggregate"
    if g.startswith("Northern Ireland") or g in {"England", "Wales", "Scotland"}:
        return "Country"
    return "English region"


@st.cache_data(ttl=120)
def _hpi_backtest_rows() -> pd.DataFrame:
    rows: list[dict] = []
    for path in _glob_processed(_GLOB_TS):
        try:
            doc = _read_json(str(path))
        except (OSError, json.JSONDecodeError):
            continue
        meta = doc.get("meta") or {}
        if meta.get("dataset") not in _HPI_DATASETS:
            continue
        geo = meta.get("geography")
        if not geo:
            continue
        summ = doc.get("summary") or {}
        best = summ.get("best_model_mae")
        mae_best = None
        for r in summ.get("summary_by_model", []):
            if r.get("model") == best and r.get("mae") is not None:
                mae_best = float(r["mae"])
                break
        rows.append(
            {
                "file": path.name,
                "geography": geo,
                "geo_scope": _geo_scope(geo),
                "dataset": meta.get("dataset"),
                "edition": meta.get("edition"),
                "horizon": meta.get("horizon"),
                "seasonal_period": meta.get("seasonal_period"),
                "min_train": meta.get("min_train"),
                "annual_rule": meta.get("annual_rule"),
                "n_windows": doc.get("n_windows"),
                "best_model_mae": best,
                "mae_best_model": mae_best,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["geo_scope", "geography", "file"]).reset_index(drop=True)


def _render_regional_tab() -> None:
    top = st.columns([4, 1])
    with top[0]:
        st.markdown(
            "Compare **rolling backtest summaries** for **UK HPI** across **countries** "
            "(England, Wales, Scotland, Northern Ireland), **UK/GB aggregates**, and **English regions**. "
            "Each row comes from one `ts_backtest_*.json` file whose `meta.geography` is set."
        )
    with top[1]:
        if st.button("Reload reports", help="Clear cached JSON scans after you add files under data/processed/"):
            st.cache_data.clear()
            st.rerun()

    st.code(
        "# Monthly (sheet 1) for every area:\n"
        "python scripts/sweep_hpi_geographies.py --edition march2026 --horizon 1\n"
        "# Annual (same geographies):\n"
        "python scripts/sweep_hpi_geographies.py --edition march2026 --horizon 1 --frequency annual",
        language="bash",
    )
    st.caption("Uses sheet **1** in the HPI workbook (same as default `run_ts_forecast.py`).")

    df = _hpi_backtest_rows()
    if df.empty:
        st.info(
            "No HPI backtest JSONs with `meta.geography` found. "
            "Generate per-area reports with `scripts/sweep_hpi_geographies.py` "
            'or run `run_ts_forecast.py` with `--geography "England"` (etc.) and `-o`.'
        )
        return

    editions = sorted(df["edition"].dropna().astype(str).unique())
    default_ed = "march2026" if "march2026" in editions else editions[0]
    e_idx = editions.index(default_ed) if default_ed in editions else 0
    e_sel = st.selectbox("Edition", options=editions, index=e_idx)
    sub_ed = df[df["edition"].astype(str) == str(e_sel)].copy()

    from_disk = set()
    for x in sub_ed["horizon"].dropna().unique().tolist():
        try:
            from_disk.add(int(float(x)))
        except (TypeError, ValueError):
            continue
    h_opts = sorted(from_disk | set(_PRESET_HORIZONS))
    h_sel = st.selectbox(
        "Horizon",
        options=h_opts,
        format_func=str,
        help="Includes common steps even if you have not generated JSON for that horizon yet.",
    )
    sub = sub_ed[pd.to_numeric(sub_ed["horizon"], errors="coerce") == float(h_sel)].copy()

    ds_opts = sorted(sub_ed["dataset"].dropna().astype(str).unique())
    ds = st.multiselect("Dataset", options=ds_opts, default=ds_opts)
    sub = sub[sub["dataset"].astype(str).isin(ds)] if ds else sub

    scope_opts = ["UK aggregate", "Country", "English region"]
    scope = st.multiselect("Area type", options=scope_opts, default=scope_opts)
    sub = sub[sub["geo_scope"].isin(scope)] if scope else sub

    st.subheader("Summary by geography")
    show = sub[
        [
            "geo_scope",
            "geography",
            "dataset",
            "horizon",
            "n_windows",
            "best_model_mae",
            "mae_best_model",
            "file",
        ]
    ].copy()
    if show.empty:
        st.warning(
            f"No reports for **edition {e_sel}**, **horizon {h_sel}**, and the selected dataset(s) / area types. "
            f"Run the commands above (monthly and/or annual), then click **Reload reports**. "
            f"If you only need **monthly** or **annual**, clear the other dataset in the filter."
        )
        diag = sub_ed.assign(h=pd.to_numeric(sub_ed["horizon"], errors="coerce"))
        if not diag.empty:
            avail = (
                diag.groupby(["dataset", "h", "geo_scope"], dropna=False)
                .size()
                .reset_index(name="n_reports")
                .sort_values(["dataset", "h", "geo_scope"])
            )
            with st.expander("What exists on disk for this edition? (before filters)"):
                st.dataframe(avail, width=ST_WIDTH)
                st.caption(
                    "If **h** never equals your chosen horizon, run `sweep_hpi_geographies.py` with that `--horizon`. "
                    "English regions need the full sweep (nine regions plus countries/UK rows are separate files)."
                )
    st.dataframe(show, width=ST_WIDTH, height=min(420, 38 * (max(len(show), 1) + 1)))

    chart_df = show.dropna(subset=["mae_best_model", "geography"]).copy()
    if not chart_df.empty:
        ch = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("mae_best_model:Q", title="MAE (best model)"),
                y=alt.Y("geography:N", title=None, sort="-x"),
                color=alt.Color("geo_scope:N", title="Area type"),
                tooltip=["geography", "geo_scope", "best_model_mae", "mae_best_model", "n_windows", "file"],
            )
            .properties(height=max(120, 22 * len(chart_df)))
        )
        st.altair_chart(ch, width=ST_WIDTH)
    elif not show.empty:
        st.caption("No numeric MAE for the current filters (empty windows or missing `summary_by_model`).")


_MODEL_CHOICES = ("seasonal_naive", "ets", "sarimax", "lagged_hgbr")
_SHEET_LABELS = {
    "1": "Index (ONS HPI)",
    "2": "Average price (£)",
    "3": "Annual % change",
    "7": "Monthly % change",
}


@st.cache_data(ttl=120)
def _forward_forecast_table(
    processed_dir_str: str,
    edition: str,
    sheet: str,
    frequency: str,
    annual_rule: str,
    horizon: int,
    models_tuple: tuple[str, ...],
    geographies_tuple: tuple[str, ...],
) -> pd.DataFrame:
    rows: list[dict] = []
    root = Path(processed_dir_str)
    for g in geographies_tuple:
        for m in models_tuple:
            try:
                r = forward_forecast_hpi_levels(
                    root,
                    edition=edition,
                    sheet=sheet,
                    geography=g,
                    frequency=frequency,
                    annual_rule=annual_rule,
                    model_name=m,
                    horizon=horizon,
                )
            except (FileNotFoundError, ValueError, OSError) as e:
                rows.append(
                    {
                        "geography": g,
                        "model": m,
                        "pct_change": None,
                        "last_level": None,
                        "forecast_end": None,
                        "n_obs": None,
                        "error": str(e),
                    }
                )
                continue
            err = r.get("error")
            rows.append(
                {
                    "geography": g,
                    "model": m,
                    "pct_change": r.get("pct_change"),
                    "last_level": r.get("last_level"),
                    "forecast_end": r.get("forecast_end"),
                    "n_obs": r.get("n_obs"),
                    "error": err,
                }
            )
    return pd.DataFrame(rows)


def _render_forward_tab() -> None:
    st.markdown(
        "**One-shot forecast** from the **full history** in the tidy Parquet: implied **% change** from the "
        "latest observation to the **end of the chosen horizon** (same model family as backtests). "
        "Not a macro scenario—rates, incomes, and policy are not modeled."
    )

    ed_keys = list(UK_HPI_MONTHLY_EDITIONS.keys())
    edition = st.selectbox(
        "Edition",
        options=ed_keys,
        format_func=lambda k: f"{k} ({UK_HPI_MONTHLY_EDITIONS[k].label})",
        index=ed_keys.index("march2026") if "march2026" in ed_keys else 0,
        key="fwd_edition",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        sheet = st.selectbox(
            "Worksheet",
            options=["1", "2", "3", "7"],
            format_func=lambda s: f"{s} — {_SHEET_LABELS.get(s, s)}",
            index=0,
            key="fwd_sheet",
        )
    with c2:
        frequency = st.radio("Frequency", options=("monthly", "annual"), horizontal=True, key="fwd_freq")
    with c3:
        if frequency == "annual":
            annual_rule = st.selectbox("Annual aggregation", options=("last", "mean"), key="fwd_arule")
        else:
            annual_rule = "last"
            st.caption("Annual aggregation applies when frequency is **annual**.")

    pq = PROCESSED_DIR / f"ons_uk_hpi_monthly_{edition}_{sheet}_tidy.parquet"
    if not pq.is_file():
        st.warning(
            f"No `{pq.name}` found. Run `python ons_uk_hpi_monthly_etl.py --edition {edition}` "
            f"(or `--transform-only` with your workbook) first."
        )

    horizon = st.number_input(
        "Forecast horizon (steps)",
        min_value=1,
        max_value=120,
        value=12,
        help="Months ahead if monthly; years ahead if annual.",
        key="fwd_horizon",
    )
    default_geo = [g for g in ("United Kingdom", "England", "London", "South East") if g in SHEET1_GEOGRAPHIES]
    geographies = st.multiselect(
        "Geographies",
        options=list(SHEET1_GEOGRAPHIES),
        default=default_geo or ["United Kingdom"],
        key="fwd_geo",
    )

    ctx_key = (
        f"{edition}|{sheet}|{frequency}|{annual_rule}|{int(horizon)}|"
        f"{','.join(sorted(geographies)) if geographies else ''}"
    )
    if st.session_state.get("fwd_model_ctx") != ctx_key:
        sm = best_models_from_ts_backtest_json(
            PROCESSED_DIR,
            edition=edition,
            sheet=sheet,
            frequency=frequency,
            annual_rule=annual_rule,
            horizon=int(horizon),
            geographies=list(geographies),
        )
        st.session_state.fwd_models = sm if sm else ["ets", "sarimax"]
        st.session_state.fwd_model_ctx = ctx_key

    models = st.multiselect(
        "Models",
        options=list(_MODEL_CHOICES),
        key="fwd_models",
        help="Defaults to **best_model_mae** from a matching `ts_backtest_*.json` (same edition, sheet, horizon, "
        "frequency, annual rule, and geography) when available; otherwise ETS + SARIMAX.",
    )

    if not models or not geographies:
        st.info("Select at least one model and one geography.")
        return

    df = _forward_forecast_table(
        str(PROCESSED_DIR.resolve()),
        edition,
        sheet,
        frequency,
        annual_rule,
        int(horizon),
        tuple(sorted(models)),
        tuple(sorted(geographies)),
    )

    unit = "months" if frequency == "monthly" else "years"
    sheet_note = _SHEET_LABELS.get(sheet, sheet)
    level_df = df[df["forecast_end"].notna() & df["last_level"].notna()].copy()

    st.subheader("Predicted levels at end of horizon")
    if level_df.empty:
        st.info("No predicted levels for this combination (see full results below for errors).")
    else:
        step_label = f"{horizon} {'month' if unit == 'months' else 'year'}{'s' if horizon != 1 else ''} ahead"
        if sheet == "2":
            price_caption = (
                f"**Average price (£)** from ONS worksheet 2 — **last observed** vs **model prediction** after **{step_label}**."
            )
        elif sheet == "1":
            price_caption = (
                f"**HPI index** (worksheet 1) — **last observed** vs **model prediction** after **{step_label}** "
                "(not a cash house price unless you select worksheet 2)."
            )
        else:
            price_caption = (
                f"**Last observed** vs **predicted value** at end of **{step_label}** for worksheet **{sheet}**."
            )
        st.caption(price_caption)

        disp = level_df[
            ["geography", "model", "last_level", "forecast_end", "pct_change", "n_obs"]
        ].copy()
        last_h = "Last observed (£)" if sheet == "2" else "Last observed (index)" if sheet == "1" else "Last observed"
        pred_h = f"Predicted after {step_label}" + (" (£)" if sheet == "2" else " (index)" if sheet == "1" else "")
        disp = disp.rename(
            columns={
                "last_level": last_h,
                "forecast_end": pred_h,
                "pct_change": "% change vs last",
                "n_obs": "Observations",
            }
        )
        fmt_last = "%.0f" if sheet == "2" else "%.2f"
        fmt_pred = "%.0f" if sheet == "2" else "%.2f"
        col_cfg: dict = {
            last_h: st.column_config.NumberColumn(last_h, format=fmt_last),
            pred_h: st.column_config.NumberColumn(pred_h, format=fmt_pred),
            "% change vs last": st.column_config.NumberColumn("% change vs last", format="%.2f"),
            "Observations": st.column_config.NumberColumn("Observations", format="%d"),
        }
        st.dataframe(
            disp,
            width=ST_WIDTH,
            column_config=col_cfg,
            hide_index=True,
        )

    st.subheader("Charts")
    plot_df = df[df["pct_change"].notna()].copy()
    ch_level = None
    if not level_df.empty:
        y_title = "Predicted value (£)" if sheet == "2" else "Predicted index level" if sheet == "1" else "Predicted value"
        ch_level = (
            alt.Chart(level_df)
            .mark_bar()
            .encode(
                x=alt.X("geography:N", title="Geography", sort=list(geographies)),
                y=alt.Y("forecast_end:Q", title=y_title),
                color=alt.Color("model:N", title="Model"),
                xOffset=alt.XOffset("model:N"),
                tooltip=["geography", "model", "last_level", "forecast_end", "pct_change", "n_obs"],
            )
            .properties(
                title=f"Predicted level at horizon ({horizon} {unit}) · {sheet_note}",
                height=max(280, 28 * len(geographies)),
            )
        )
    if plot_df.empty and ch_level is None:
        st.info("No successful forecasts for this combination (check the full table below).")
    else:
        c_pct, c_lvl = st.columns(2)
        with c_pct:
            if plot_df.empty:
                st.caption("No % change chart (no successful runs).")
            else:
                ch = (
                    alt.Chart(plot_df)
                    .mark_bar()
                    .encode(
                        x=alt.X("geography:N", title="Geography", sort=list(geographies)),
                        y=alt.Y("pct_change:Q", title="% change vs last observation"),
                        color=alt.Color("model:N", title="Model"),
                        xOffset=alt.XOffset("model:N"),
                        tooltip=["geography", "model", "pct_change", "last_level", "forecast_end", "n_obs"],
                    )
                    .properties(
                        title=(
                            f"% change to end of horizon ({horizon} {unit}) · {sheet_note} · {edition} · {frequency}"
                        ),
                        height=max(260, 26 * len(geographies)),
                    )
                )
                st.altair_chart(ch, use_container_width=True)
        with c_lvl:
            if ch_level is None:
                st.caption("No predicted-level chart (no successful level forecasts).")
            else:
                st.altair_chart(ch_level, use_container_width=True)

    st.subheader("Full results")
    show = df.copy()
    if "error" in show.columns:
        show["error"] = show["error"].apply(lambda x: "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x))
    st.dataframe(show, width=ST_WIDTH)

    with st.expander("How to read this"):
        st.markdown(
            f"""
- **{sheet_note}** (worksheet **{sheet}**): sheet **1** is the published **index**, not cash prices; sheet **2** is **£** average price (ONS definitions).
- The **Predicted levels** table and **level chart** show **last observed** and **forecast at the end of the selected horizon** (same step count as **Forecast horizon**).
- **% change** = (forecast at step **{horizon}** ÷ last observed level − 1) × 100, using **all** history to fit the model.
- Long horizons are **illustrative**; prefer short horizons and rolling backtests on the other tabs for skill assessment.
"""
        )


def _render_overview_tab() -> None:
    st.markdown(
        "This page visualises **offline backtests** already written to `data/processed/`. "
        "It does not train models in the browser. Use the tabs for **rolling time-series evaluation**, "
        "**UK HPI by region and country**, **forward index change**, and **cross-sectional LA benchmarks** against Lane A features."
    )
    st.subheader("Generate outputs")
    st.markdown("**Time series — UK HPI monthly, UK-wide (default)**")
    st.code(
        'python scripts/run_ts_forecast.py --dataset hpi --edition march2026 --geography "United Kingdom"',
        language="bash",
    )
    st.markdown("**Short horizons (validate before trusting long runs)** — compare models at h=3, 6, 12 months:")
    st.code("python scripts/sweep_hpi_short_horizons.py --edition march2026 --horizons 3,6,12", language="bash")
    st.markdown("**All sheet-1 geographies (countries + English regions + UK/GB)** — feed the **By region & country** tab:")
    st.code("python scripts/sweep_hpi_geographies.py --edition march2026 --horizon 3", language="bash")
    st.markdown("**Annual HPI (preferred for a ~10-year story)** — calendar-year series, `--horizon 10` = ten annual steps:")
    st.code(
        "python scripts/run_ts_forecast.py --dataset hpi --edition march2026 --frequency annual "
        '--annual-rule last --geography "United Kingdom" --horizon 10',
        language="bash",
    )
    st.caption(
        "`--annual-rule last` uses the last month in each calendar year (typically December); "
        "`mean` averages months within each year. Default `--min-train` is 36 for monthly; "
        "for annual it is chosen automatically (up to 15 years) so at least one rolling window can complete, "
        "or lower if the series is short (see `meta.min_train` in the JSON report)."
    )
    st.markdown("**Local authority benchmark (residuals + CV JSON)** — drivers across areas; not a substitute for the time-series backtest above.")
    st.code(
        "python scripts/run_la_benchmark.py --target median_price_existing_gbp --model elastic_net",
        language="bash",
    )
    st.caption(
        "Requires `joined_la_housing_market_snapshot.parquet` (see `joins/build_la_housing_market_snapshot.py`). "
        "Adjust flags to match your processed Parquet editions and targets."
    )
    st.markdown("**Forward forecast JSON export** — same full-history logic as the **Forward index change** tab:")
    st.code(
        "python scripts/export_hpi_forward_forecast.py --edition march2026 --horizon 12 "
        '--models ets --geographies "United Kingdom,England"',
        language="bash",
    )
    st.subheader("Interpretation")
    st.markdown(
        """
- **Time series:** Models are compared on walk-forward windows (MAE, RMSE, MAPE, MASE vs seasonal naive). Each report includes **`best_model_mae`** (lowest mean MAE in `summary_by_model`). Pick the model that wins on short horizons before interpreting long horizons.
- **LA benchmark:** **Residual** = actual − predicted. Positive means the observed median price was **above** what cross-sectional features predicted (not necessarily “overpriced” — see model limits). Use this to discuss **why** levels differ across areas, not to forecast the national price **path**.
"""
    )
    with st.expander("Long horizons, scenarios, and limits"):
        st.markdown(
            """
- **Monthly forecasts over many years (e.g. 120 months)** are **illustrative** only: errors compound, and the ONS HPI slice does not encode future rates, incomes, policy, or shocks. Present wide uncertainty or scenario bands, not a single point as “the” price path.
- **Ten-year narratives** are better grounded with **annual** frequency and a **small step count** (e.g. `--frequency annual --horizon 10`) after you have validated models on **short monthly horizons**.
- Prefer **low / mid / high** growth or index **scenarios** for decade-scale views rather than one extrapolated line.
"""
        )
    ogl_attribution_expander()


def _render_ts_tab(ts_files: list[Path]) -> None:
    if not ts_files:
        st.warning(
            f"No `{_GLOB_TS}` files in `data/processed/`. Example:\n\n"
            '`python scripts/run_ts_forecast.py --dataset hpi --edition march2026 --geography "United Kingdom"`.'
        )
        return

    pick_ts = st.selectbox(
        "Backtest report",
        options=ts_files,
        format_func=lambda p: p.name,
        index=next((i for i, p in enumerate(ts_files) if "march2026" in p.name), 0),
        help="JSON written by `scripts/run_ts_forecast.py`.",
    )
    rep = _read_json(str(pick_ts))
    meta = rep.get("meta", {})
    summ = rep.get("summary", {})
    rows = summ.get("summary_by_model", [])
    best_json = summ.get("best_model_mae")

    st.caption(
        f"Dataset **{meta.get('dataset', '—')}** · edition **{meta.get('edition', '—')}** · "
        f"geography **{meta.get('geography', meta.get('sector', '—'))}** · "
        f"seasonal period **{meta.get('seasonal_period', '—')}** · "
        f"horizon **{meta.get('horizon', '—')}** · windows **{rep.get('n_windows', '—')}**"
        + (f" · **best_model_mae** `{best_json}`" if best_json else "")
    )

    if rows:
        sdf = pd.DataFrame(rows)
        if "mae" in sdf.columns and pd.api.types.is_numeric_dtype(sdf["mae"]):
            best_idx = sdf["mae"].idxmin()
            best = sdf.loc[best_idx]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rolling windows", f"{rep.get('n_windows', '—')}")
            m2.metric("Forecast horizon", f"{meta.get('horizon', '—')}")
            m3.metric("Best model (lowest MAE)", str(best["model"]))
            m4.metric("MAE", f"{float(best['mae']):.6g}")
        else:
            m1, m2 = st.columns(2)
            m1.metric("Rolling windows", f"{rep.get('n_windows', '—')}")
            m2.metric("Forecast horizon", f"{meta.get('horizon', '—')}")

        st.subheader("Error metrics by model")
        st.dataframe(sdf, width=ST_WIDTH)
        melt = sdf.melt(
            id_vars=["model"],
            value_vars=["mae", "rmse", "mape", "mase_vs_naive"],
            var_name="metric",
            value_name="value",
        )
        ch = (
            alt.Chart(melt)
            .mark_bar()
            .encode(
                x=alt.X("model:N", title="Model", sort=None),
                y=alt.Y("value:Q", title=""),
                column=alt.Column("metric:N", title=None, spacing=10),
                color=alt.Color("model:N", legend=None),
            )
            .properties(height=260, width=alt.Step(50))
            .resolve_scale(y="independent")
        )
        st.altair_chart(ch, width=ST_WIDTH)
    else:
        st.info("No `summary_by_model` in this report (empty backtest windows).")

    if meta:
        with st.expander("Full metadata (JSON)"):
            st.json(meta)

    win_path = pick_ts.with_suffix(".windows.csv")
    st.divider()
    st.subheader("Per-window metrics")
    if win_path.is_file():
        wdf = load_processed_csv(str(win_path))
        st.caption(f"`{win_path.name}` — **{len(wdf):,}** rows (showing first 50).")
        st.dataframe(wdf.head(50), width=ST_WIDTH, height=320)
        st.download_button(
            "Download full windows CSV",
            data=win_path.read_bytes(),
            file_name=win_path.name,
            mime="text/csv",
        )
    else:
        st.caption(f"No companion file `{pick_ts.with_suffix('.windows.csv').name}`.")


def _render_la_tab(bench_csvs: list[Path]) -> None:
    if not bench_csvs:
        st.warning(
            f"No `{_GLOB_BENCH_CSV}` in `data/processed/`. Example:\n\n"
            "`python scripts/run_la_benchmark.py --target median_price_existing_gbp --model elastic_net`."
        )
        return

    pick_b = st.selectbox(
        "Residuals export",
        options=bench_csvs,
        format_func=lambda p: p.name,
        index=next((i for i, p in enumerate(bench_csvs) if "elastic_net" in p.name and "median_price" in p.name), 0),
        help="CSV from `scripts/run_la_benchmark.py`.",
    )
    rdf = load_processed_csv(str(pick_b))
    st.caption(
        "**Residual** = actual − predicted (positive ⇒ median price **higher** than the model expected from features). "
        + (str(rdf["residual_definition"].iloc[0]) if "residual_definition" in rdf.columns else "")
    )

    cv_path = pick_b.parent / f"{pick_b.stem.replace('_residuals', '')}_cv.json"
    st.subheader("Cross-validation (region-held-out)")
    if cv_path.is_file():
        cv_doc = _read_json(str(cv_path))
        cv_scores = pd.DataFrame(cv_doc.get("cv_scores", []))
        if not cv_scores.empty:
            st.dataframe(cv_scores, width=ST_WIDTH)
            m1, m2, m3 = st.columns(3)
            m1.metric("Mean MAE (£, across folds)", f"{cv_scores['mae'].mean():,.0f}")
            m2.metric("Mean R² (across folds)", f"{cv_scores['r2'].mean():.4f}")
            if "mape" in cv_scores.columns:
                m3.metric("Mean MAPE (across folds)", f"{cv_scores['mape'].mean():.4f}")
        else:
            st.info("`cv_scores` array is empty in the JSON file.")
    else:
        st.info(
            f"No `{cv_path.name}`. Re-run `scripts/run_la_benchmark.py` to emit `la_benchmark_<target>_<model>_cv.json`."
        )

    st.divider()
    st.subheader("Out-of-fold fit")

    rdf = rdf.copy()
    rdf["actual"] = pd.to_numeric(rdf["actual"], errors="coerce")
    rdf["predicted"] = pd.to_numeric(rdf["predicted"], errors="coerce")
    rdf["residual"] = pd.to_numeric(rdf["residual"], errors="coerce")
    plot = rdf.dropna(subset=["actual", "predicted"])

    if not plot.empty:
        lo = float(plot["actual"].min())
        hi = float(plot["actual"].max())
        diag = pd.DataFrame({"v": [lo, hi]})
        scatter = (
            alt.Chart(plot)
            .mark_circle(size=48, opacity=0.55)
            .encode(
                x=alt.X("actual:Q", title="Actual median price (£)"),
                y=alt.Y("predicted:Q", title="Predicted (£)"),
                tooltip=["lad_code", "la_name", "region_name", "actual", "predicted", "residual"],
            )
            .properties(height=400)
        )
        line = alt.Chart(diag).mark_line(color="gray", strokeDash=[5, 5]).encode(x="v:Q", y="v:Q")
        st.markdown("**Actual vs predicted** (diagonal = perfect point forecast).")
        st.altair_chart(scatter + line, width=ST_WIDTH)

        hist = (
            alt.Chart(plot)
            .mark_bar()
            .encode(
                alt.X("residual:Q", bin=alt.Bin(maxbins=40), title="Residual (actual − predicted) £"),
                y=alt.Y("count():Q", title="Local authorities"),
                color=alt.value("#4c78a8"),
            )
            .properties(height=280)
        )
        st.markdown("**Residual distribution**")
        st.altair_chart(hist, width=ST_WIDTH)

    st.subheader("Extreme residuals")
    left, right = st.columns(2)
    with left:
        st.markdown("Highest residuals (above model expectation)")
        st.dataframe(
            rdf.sort_values("residual", ascending=False).head(15),
            width=ST_WIDTH,
        )
    with right:
        st.markdown("Lowest residuals (below model expectation)")
        st.dataframe(
            rdf.sort_values("residual", ascending=True).head(15),
            width=ST_WIDTH,
        )

    st.download_button(
        "Download residuals CSV",
        data=pick_b.read_bytes(),
        file_name=pick_b.name,
        mime="text/csv",
    )


def main() -> None:
    st.set_page_config(page_title="ML predictions & backtests", layout="wide")
    st.title("ML predictions & backtests")
    st.caption(
        "Rolling time-series backtests (`run_ts_forecast.py`), optional **`sweep_hpi_geographies.py`** for all HPI areas, "
        "**Forward index change** (exploratory one-shot % change vs last observation), and LA cross-section benchmarks "
        "(`run_la_benchmark.py`). Outputs must exist under `data/processed/`."
    )
    st.divider()

    ts_files = _glob_processed(_GLOB_TS)
    bench_csvs = _glob_processed(_GLOB_BENCH_CSV)

    t_overview, t_ts, t_regional, t_forward, t_la = st.tabs(
        [
            "Overview",
            "Time series backtest",
            "By region & country",
            "Forward index change",
            "LA benchmark",
        ]
    )

    with t_overview:
        _render_overview_tab()

    with t_ts:
        _render_ts_tab(ts_files)

    with t_regional:
        _render_regional_tab()

    with t_forward:
        _render_forward_tab()

    with t_la:
        _render_la_tab(bench_csvs)


main()
