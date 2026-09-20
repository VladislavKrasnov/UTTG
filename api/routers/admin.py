from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.utils import build_meta
from core.rate_limit import RateLimiter
from storage.database import get_db
from storage.models import EndpointMetricBucket, ProviderHealth, WebhookDelivery

router = APIRouter(tags=["Admin"])

_SOURCES = [
    "space-track",
    "celestrak",
    "nasa-neows",
    "noaa-swpc",
    "the-space-devs",
    "jpl-horizons",
    "esa",
]


@router.get(
    "/admin/providers/status",
    dependencies=[Depends(RateLimiter("public_expensive"))],
    include_in_schema=False,
)
async def admin_providers_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    rows = (await db.execute(select(ProviderHealth))).scalars().all()
    data = [
        {
            "id": r.id,
            "status": r.status,
            "last_success_at": r.last_success_at,
            "last_error_at": r.last_error_at,
            "error_message": r.error_message,
        }
        for r in rows
    ]
    meta = await build_meta("/admin/providers/status", db, _SOURCES)
    return APIResponse(data=data, meta=meta).model_dump()


@router.get(
    "/admin/analytics/endpoints",
    dependencies=[Depends(RateLimiter("public_expensive"))],
    include_in_schema=False,
)
async def admin_analytics(
    start: datetime | None = None,
    end: datetime | None = None,
    interval: Literal["minute", "hour", "day"] = "hour",
    route: str | None = Query(default=None, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    end_at = end or datetime.now(UTC)
    start_at = start or end_at - timedelta(hours=24)
    if end_at <= start_at or end_at - start_at > timedelta(days=31):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail={
                "code": "QUERY_COST_EXCEEDED",
                "message": "Analytics range must be positive and no longer than 31 days",
            },
        )

    total_deliveries = (
        await db.execute(select(func.count()).select_from(WebhookDelivery))
    ).scalar() or 0
    successful_deliveries = (
        await db.execute(
            select(func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.success.is_(True))
        )
    ).scalar() or 0

    bucket = func.date_trunc(interval, EndpointMetricBucket.bucket).label("bucket")
    statement = (
        select(
            bucket,
            EndpointMetricBucket.route,
            EndpointMetricBucket.method,
            func.sum(EndpointMetricBucket.request_count).label("request_count"),
            (
                func.sum(EndpointMetricBucket.duration_sum_ms)
                / func.nullif(func.sum(EndpointMetricBucket.request_count), 0)
            ).label("average_duration_ms"),
            func.max(EndpointMetricBucket.duration_max_ms).label("max_duration_ms"),
            func.sum(EndpointMetricBucket.server_error_count).label("server_errors"),
            func.sum(EndpointMetricBucket.response_bytes).label("response_bytes"),
            func.sum(EndpointMetricBucket.cache_hit_count).label("cache_hits"),
        )
        .where(
            EndpointMetricBucket.bucket >= start_at,
            EndpointMetricBucket.bucket < end_at,
        )
        .group_by(bucket, EndpointMetricBucket.route, EndpointMetricBucket.method)
        .order_by(bucket.desc())
        .limit(5000)
    )
    if route:
        statement = statement.where(EndpointMetricBucket.route == route)
    rows = (await db.execute(statement)).all()

    meta = await build_meta("/admin/analytics/endpoints", db, _SOURCES)
    return APIResponse(
        data={
            "access_mode": "public_ip_rate_limited",
            "webhook_deliveries_total": total_deliveries,
            "webhook_deliveries_success": successful_deliveries,
            "webhook_delivery_success_rate": round(successful_deliveries / total_deliveries, 4)
            if total_deliveries
            else None,
            "series": [
                {
                    "bucket": row.bucket,
                    "route": row.route,
                    "method": row.method,
                    "request_count": row.request_count,
                    "average_duration_ms": round(float(row.average_duration_ms or 0), 3),
                    "max_duration_ms": round(float(row.max_duration_ms or 0), 3),
                    "server_errors": int(row.server_errors or 0),
                    "response_bytes": int(row.response_bytes or 0),
                    "cache_hits": int(row.cache_hits or 0),
                }
                for row in rows
            ],
        },
        meta=meta,
    ).model_dump()
