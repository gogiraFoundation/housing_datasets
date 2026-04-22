from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from housing_api.auth import enforce_metrics_auth, verify_api_key
from housing_api.constants import API_PREFIX
from housing_api.data_access import (
    compute_etag,
    dataframe_to_json_records,
    dataset_disk_meta,
    load_manifest,
    manifest_row_for_file,
    parquet_num_rows,
    read_parquet_all,
    validate_columns_subset,
)
from housing_api.generic_parquet import read_parquet_page_duckdb
from housing_api.logging_config import configure_logging
from housing_api.metrics import PrometheusSimpleMiddleware, metrics_response
from housing_api.registry import REGISTRY, DatasetMeta, safe_processed_path
from housing_api.settings import (
    allow_large_generic_reads,
    default_page_limit,
    enable_docs,
    enable_metrics,
    generic_large_row_threshold,
    max_export_json_rows,
    max_export_rows,
    max_page_limit,
    repo_root as env_repo_root,
    use_duckdb_generic_pages,
)
from housing_data.housebuilding_country import (
    filter_housebuilding_country,
    prepare_housebuilding_country_df,
)
from housing_data.housebuilding_la import (
    chart_to_vega_lite,
    filter_housebuilding_la,
    line_by_year_chart,
    prepare_housebuilding_la_df,
)

logger = logging.getLogger("housing_api")

_HTTP_422 = int(getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422))


def get_repo_root() -> Path:
    s = env_repo_root()
    if s:
        return Path(s).resolve()
    return Path(__file__).resolve().parents[1]


class DatasetSummary(BaseModel):
    id: str
    title: str
    family: str
    available: bool
    size_bytes: int | None = None
    columns: list[str] | None = None
    updated_at: str | None = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


class DatasetRowsResponse(BaseModel):
    dataset_id: str
    total_rows: int
    limit: int
    offset: int
    rows: list[dict[str, Any]]


def _parse_csv_list(raw: str | None) -> list[str] | None:
    if raw is None or raw.strip() == "":
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


def _parse_columns_param(raw: str | None) -> list[str] | None:
    cols = _parse_csv_list(raw)
    if not cols:
        return None
    return cols


def _generic_full_scan_guard(repo: Path, meta: DatasetMeta, path: Path, *, columns: list[str] | None) -> None:
    if meta.family != "generic":
        return
    thr = generic_large_row_threshold()
    if thr <= 0:
        return
    if allow_large_generic_reads():
        return
    if columns:
        return
    man = load_manifest(repo)
    rel = str(path.relative_to(repo))
    mrow = manifest_row_for_file(man, rel)
    n: int | None = None
    if mrow and isinstance(mrow.get("num_rows"), int):
        n = int(mrow["num_rows"])
    if n is None:
        n = parquet_num_rows(path)
    if n is None:
        return
    if n > thr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This dataset has about {n} rows; reading the full table without narrowing is not allowed. "
                "Pass comma-separated `columns` to project a subset, set HOUSING_API_ALLOW_LARGE_GENERIC=1 for "
                "trusted deployments, raise HOUSING_API_MAX_ROWS_WITHOUT_FILTERS, or use "
                "GET .../export?format=csv with an appropriate limit."
            ),
        )


def _coerce_page_limit(requested: int) -> int:
    cap = max_page_limit()
    if requested > cap:
        raise HTTPException(
            status_code=_HTTP_422,
            detail=f"limit exceeds maximum ({cap}); raise HOUSING_API_MAX_ROWS if appropriate.",
        )
    return requested


def _load_filtered_frame(
    repo: Path,
    meta: DatasetMeta,
    *,
    financial_year_min: str | None,
    financial_year_max: str | None,
    measure: str | None,
    region: str | None,
    local_authority: str | None,
    period_min: str | None,
    period_max: str | None,
    country_name: str | None,
    sector: str | None,
    frequency: str | None,
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Load Parquet from disk, then apply family-specific filters in memory."""
    path = safe_processed_path(repo, meta)
    if path is None or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")
    use_cols = columns if meta.family == "generic" else None
    df = read_parquet_all(path, columns=use_cols)
    if meta.family == "housebuilding_country":
        df = prepare_housebuilding_country_df(df)
        measures = _parse_csv_list(measure)
        countries = _parse_csv_list(country_name)
        sectors = _parse_csv_list(sector)
        freqs = _parse_csv_list(frequency)
        view, periods = filter_housebuilding_country(
            df,
            period_min=period_min,
            period_max=period_max,
            measures=measures,
            country_names=countries,
            sectors=sectors,
            frequencies=freqs,
        )
        return view, periods
    if meta.family == "housebuilding_la":
        df = prepare_housebuilding_la_df(df)
        measures = _parse_csv_list(measure)
        regions = _parse_csv_list(region)
        las = _parse_csv_list(local_authority)
        view, years = filter_housebuilding_la(
            df,
            financial_year_min=financial_year_min,
            financial_year_max=financial_year_max,
            measures=measures,
            regions=regions,
            local_authorities=las,
        )
        return view, years
    return df, []


def create_app() -> FastAPI:
    configure_logging()
    docs = enable_docs()
    dl = default_page_limit()
    application = FastAPI(
        title="Housing datasets API",
        version="1.0.0",
        openapi_url=f"{API_PREFIX}/openapi.json" if docs else None,
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=f"{API_PREFIX}/redoc" if docs else None,
    )

    @application.middleware("http")
    async def request_id_and_timing(request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000.0
        response.headers["X-Request-ID"] = rid
        client = getattr(request.state, "api_key_id", None)
        logger.info(
            "request",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "latency_ms": round(ms, 2),
                "client": client,
            },
        )
        return response

    if enable_metrics():
        application.add_middleware(PrometheusSimpleMiddleware)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/metrics")
    async def metrics(_: Annotated[None, Depends(enforce_metrics_auth)]):
        if not enable_metrics():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics disabled")
        return metrics_response()

    @application.get(f"{API_PREFIX}/datasets", response_model=DatasetListResponse)
    async def list_datasets(
        _: Annotated[str, Depends(verify_api_key)],
        root: Annotated[Path, Depends(get_repo_root)],
    ) -> DatasetListResponse:
        out: list[DatasetSummary] = []
        for meta in sorted(REGISTRY.values(), key=lambda m: m.id):
            avail, size, mtime, cols = dataset_disk_meta(root, meta)
            out.append(
                DatasetSummary(
                    id=meta.id,
                    title=meta.title,
                    family=meta.family,
                    available=avail,
                    size_bytes=size,
                    columns=cols,
                    updated_at=mtime,
                )
            )
        return DatasetListResponse(datasets=out)

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}", response_model=DatasetRowsResponse)
    async def get_dataset_rows(
        dataset_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        root: Annotated[Path, Depends(get_repo_root)],
        response: Response,
        limit: int = Query(dl, ge=1),
        offset: int = Query(0, ge=0),
        columns: str | None = None,
        financial_year_min: str | None = None,
        financial_year_max: str | None = None,
        measure: str | None = None,
        region: str | None = None,
        local_authority: str | None = None,
        period_min: str | None = None,
        period_max: str | None = None,
        country_name: str | None = None,
        sector: str | None = None,
        frequency: str | None = None,
        if_none_match: Annotated[str | None, Header()] = None,
    ) -> DatasetRowsResponse | Response:
        if dataset_id not in REGISTRY:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown dataset id")
        meta = REGISTRY[dataset_id]
        path = safe_processed_path(root, meta)
        if path is None or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")

        col_list = _parse_columns_param(columns)
        if col_list is not None and meta.family != "generic":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The `columns` query parameter is only supported for generic dataset families.",
            )
        try:
            col_list = validate_columns_subset(path, col_list)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        lim = _coerce_page_limit(limit)
        _generic_full_scan_guard(root, meta, path, columns=col_list)

        cols_key = ",".join(col_list) if col_list else ""

        if meta.family == "generic" and use_duckdb_generic_pages():
            try:
                total = parquet_num_rows(path)
                if total is None:
                    raise ValueError("no row count")
                page_df = read_parquet_page_duckdb(path, columns=col_list, limit=lim, offset=offset)
                rows = dataframe_to_json_records(page_df)
            except (ImportError, ModuleNotFoundError, ValueError, OSError) as ex:
                logger.warning("generic DuckDB read fell back to pandas: %s", ex)
                view, _ = _load_filtered_frame(
                    root,
                    meta,
                    financial_year_min=financial_year_min,
                    financial_year_max=financial_year_max,
                    measure=measure,
                    region=region,
                    local_authority=local_authority,
                    period_min=period_min,
                    period_max=period_max,
                    country_name=country_name,
                    sector=sector,
                    frequency=frequency,
                    columns=col_list,
                )
                total = len(view)
                page = view.iloc[offset : offset + lim]
                rows = dataframe_to_json_records(page)
        else:
            view, _year_order = _load_filtered_frame(
                root,
                meta,
                financial_year_min=financial_year_min,
                financial_year_max=financial_year_max,
                measure=measure,
                region=region,
                local_authority=local_authority,
                period_min=period_min,
                period_max=period_max,
                country_name=country_name,
                sector=sector,
                frequency=frequency,
                columns=col_list,
            )
            total = len(view)
            page = view.iloc[offset : offset + lim]
            rows = dataframe_to_json_records(page)

        mtime = str(path.stat().st_mtime)
        sig_parts = [
            meta.id,
            mtime,
            str(total),
            str(lim),
            str(offset),
            cols_key,
            financial_year_min or "",
            financial_year_max or "",
            measure or "",
            region or "",
            local_authority or "",
            period_min or "",
            period_max or "",
            country_name or "",
            sector or "",
            frequency or "",
        ]
        etag = compute_etag(sig_parts)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=60"
        if if_none_match and if_none_match.strip() == etag:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
        return DatasetRowsResponse(
            dataset_id=meta.id,
            total_rows=total,
            limit=lim,
            offset=offset,
            rows=rows,
        )

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}/export")
    async def export_dataset(
        dataset_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        root: Annotated[Path, Depends(get_repo_root)],
        format: str = Query("csv", pattern="^(csv|json)$"),
        limit: int | None = Query(None, ge=1),
        offset: int = Query(0, ge=0),
        columns: str | None = None,
        financial_year_min: str | None = None,
        financial_year_max: str | None = None,
        measure: str | None = None,
        region: str | None = None,
        local_authority: str | None = None,
        period_min: str | None = None,
        period_max: str | None = None,
        country_name: str | None = None,
        sector: str | None = None,
        frequency: str | None = None,
    ):
        if dataset_id not in REGISTRY:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown dataset id")
        meta = REGISTRY[dataset_id]
        path = safe_processed_path(root, meta)
        if path is None or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")

        col_list = _parse_columns_param(columns)
        if col_list is not None and meta.family != "generic":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The `columns` query parameter is only supported for generic dataset families.",
            )
        try:
            col_list = validate_columns_subset(path, col_list)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        max_csv = max_export_rows()
        max_json = max_export_json_rows()
        if format == "csv":
            lim = limit if limit is not None else min(100_000, max_csv)
            if lim > max_csv:
                raise HTTPException(
                    status_code=_HTTP_422,
                    detail=f"CSV export limit exceeds maximum ({max_csv}).",
                )
        else:
            lim = limit if limit is not None else max_json
            if lim > max_json:
                raise HTTPException(
                    status_code=_HTTP_422,
                    detail=f"JSON export limit exceeds maximum ({max_json}).",
                )

        _generic_full_scan_guard(root, meta, path, columns=col_list)

        view, _ = _load_filtered_frame(
            root,
            meta,
            financial_year_min=financial_year_min,
            financial_year_max=financial_year_max,
            measure=measure,
            region=region,
            local_authority=local_authority,
            period_min=period_min,
            period_max=period_max,
            country_name=country_name,
            sector=sector,
            frequency=frequency,
            columns=col_list,
        )
        chunk = view.iloc[offset : offset + lim]
        if format == "csv":
            buf = chunk.to_csv(index=False)
            return StreamingResponse(
                iter([buf]),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{dataset_id}.csv"'},
            )
        return JSONResponse(content={"rows": dataframe_to_json_records(chunk)})

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}/chart-spec")
    async def chart_spec(
        dataset_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        root: Annotated[Path, Depends(get_repo_root)],
        chart: str = Query("line_by_year", pattern="^line_by_year$"),
        financial_year_min: str | None = None,
        financial_year_max: str | None = None,
        measure: str | None = None,
        region: str | None = None,
        local_authority: str | None = None,
        period_min: str | None = None,
        period_max: str | None = None,
        country_name: str | None = None,
        sector: str | None = None,
        frequency: str | None = None,
    ) -> dict[str, Any]:
        if dataset_id not in REGISTRY:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown dataset id")
        meta = REGISTRY[dataset_id]
        if meta.family != "housebuilding_la":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No chart specs for this dataset family",
            )
        view, years = _load_filtered_frame(
            root,
            meta,
            financial_year_min=financial_year_min,
            financial_year_max=financial_year_max,
            measure=measure,
            region=region,
            local_authority=local_authority,
            period_min=period_min,
            period_max=period_max,
            country_name=country_name,
            sector=sector,
            frequency=frequency,
            columns=None,
        )
        if view.empty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No rows for chart")
        ch = line_by_year_chart(view, year_order=years)
        return chart_to_vega_lite(ch)

    return application


app = create_app()
