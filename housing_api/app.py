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
    read_parquet_all,
)
from housing_api.logging_config import configure_logging
from housing_api.metrics import PrometheusSimpleMiddleware, metrics_response
from housing_api.registry import REGISTRY, DatasetMeta, safe_processed_path
from housing_api.settings import enable_docs, enable_metrics, repo_root as env_repo_root
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
) -> tuple[pd.DataFrame, list[str]]:
    """Load Parquet from disk, then apply family-specific filters in memory.

    Full-file reads are acceptable for current LA/country-scale Parquet sizes. For much larger
    files, consider predicate pushdown (e.g. PyArrow ``filters=`` on partitioned Parquet) or
    DuckDB scan with ``WHERE`` before ``LIMIT``.
    """
    path = safe_processed_path(repo, meta)
    if path is None or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset file not found")
    df = read_parquet_all(path)
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
        limit: int = Query(1000, ge=1, le=50_000),
        offset: int = Query(0, ge=0),
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
        )
        total = len(view)
        page = view.iloc[offset : offset + limit]
        rows = dataframe_to_json_records(page)
        path = safe_processed_path(root, meta)
        mtime = str(path.stat().st_mtime) if path and path.is_file() else "0"
        sig_parts = [
            meta.id,
            mtime,
            str(total),
            str(limit),
            str(offset),
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
            limit=limit,
            offset=offset,
            rows=rows,
        )

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}/export")
    async def export_dataset(
        dataset_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        root: Annotated[Path, Depends(get_repo_root)],
        format: str = Query("csv", pattern="^(csv|json)$"),
        limit: int = Query(100_000, ge=1, le=500_000),
        offset: int = Query(0, ge=0),
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
        )
        chunk = view.iloc[offset : offset + limit]
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
        )
        if view.empty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No rows for chart")
        ch = line_by_year_chart(view, year_order=years)
        return chart_to_vega_lite(ch)

    return application


app = create_app()
