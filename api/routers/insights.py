from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, select

from api.models import APIResponse
from api.utils import build_meta
from core.cache_layer import cached
from core.capabilities import require_capability
from core.rate_limit import RateLimiter
from storage.database import AsyncSessionLocal, get_db
from storage.models import (
    CloseApproach,
    Launch,
    NearEarthObject,
    OrbitalElement,
    Satellite,
    SatelliteDecay,
    SolarWind,
    SpaceWeatherIndex,
)

router = APIRouter()


async def _cached_data(
    request: Request,
    key: str,
    loader: Any,
    ttl: int,
    stale: int,
) -> Any:
    data, state, _age = await cached(key, loader, ttl=ttl, stale=stale)
    request.state.cache_state = state
    return data


async def _dimension(model_column: Any, limit: int) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(model_column.label("value"), func.count().label("count"))
                .where(model_column.is_not(None), model_column != "")
                .group_by(model_column)
                .order_by(desc("count"), model_column)
                .limit(limit)
            )
        ).all()
    return [{"value": row._mapping["value"], "count": int(row._mapping["count"])} for row in rows]


@router.get(
    "/catalog/summary",
    tags=["Satellite"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Satellite")),
    ],
)
async def catalog_summary(request: Request, db: Any = Depends(get_db)) -> Any:
    async def load() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            total, with_cospar, active = (
                await session.execute(
                    select(
                        func.count(),
                        func.count(Satellite.cospar_id),
                        func.count().filter(Satellite.status.in_(["active", "operational"])),
                    )
                )
            ).one()
        return {"total": total, "with_cospar_id": with_cospar, "active": active}

    data = await _cached_data(request, "catalog:summary", load, 300, 3600)
    return APIResponse(
        data=data,
        meta=await build_meta("/catalog/summary", db, ["space-track", "celestrak"]),
    )


def _dimension_route(path: str, column: Any, cache_name: str) -> None:
    async def handler(
        request: Request,
        limit: int = Query(100, ge=1, le=500),
        db: Any = Depends(get_db),
    ) -> Any:
        async def load() -> list[dict[str, Any]]:
            return await _dimension(column, limit)

        data = await _cached_data(request, f"catalog:{cache_name}:{limit}", load, 600, 3600)
        return APIResponse(
            data=data,
            meta=await build_meta(path, db, ["space-track", "celestrak"]),
        )

    router.add_api_route(
        path,
        handler,
        methods=["GET"],
        tags=["Satellite"],
        dependencies=[
            Depends(RateLimiter("public_standard")),
            Depends(require_capability("Satellite")),
        ],
        name=f"catalog_{cache_name}",
    )


_dimension_route("/catalog/countries", Satellite.country, "countries")
_dimension_route("/catalog/operators", Satellite.operator, "operators")
_dimension_route("/catalog/object-types", Satellite.object_type, "object-types")
_dimension_route("/catalog/statuses", Satellite.status, "statuses")
_dimension_route("/catalog/orbit-classes", Satellite.orbit_class, "orbit-classes")


@router.get(
    "/catalog/decays",
    tags=["Satellite"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Satellite")),
    ],
)
async def catalog_decays(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    db: Any = Depends(get_db),
) -> Any:
    async def load() -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(SatelliteDecay)
                        .order_by(SatelliteDecay.decay_date.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [
            {"norad_id": row.norad_id, "decay_date": row.decay_date, "confidence": row.confidence}
            for row in rows
        ]

    data = await _cached_data(request, f"catalog:decays:{limit}", load, 600, 3600)
    return APIResponse(data=data, meta=await build_meta("/catalog/decays", db, ["space-track"]))


@router.get(
    "/catalog/decays/{norad_id}",
    tags=["Satellite"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Satellite")),
    ],
)
async def catalog_decay(norad_id: int, db: Any = Depends(get_db)) -> Any:
    row = (
        await db.execute(select(SatelliteDecay).where(SatelliteDecay.norad_id == norad_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decay record not found")
    return APIResponse(
        data={"norad_id": row.norad_id, "decay_date": row.decay_date, "confidence": row.confidence},
        meta=await build_meta(f"/catalog/decays/{norad_id}", db, ["space-track"]),
    )


@router.get(
    "/orbits/latest-epochs",
    tags=["Orbital"],
    dependencies=[
        Depends(RateLimiter("public_expensive")),
        Depends(require_capability("Orbital")),
    ],
)
async def latest_orbit_epochs(
    limit: int = Query(100, ge=1, le=500), db: Any = Depends(get_db)
) -> Any:
    rows = (
        await db.execute(
            select(OrbitalElement.norad_id, func.max(OrbitalElement.epoch).label("epoch"))
            .group_by(OrbitalElement.norad_id)
            .order_by(desc("epoch"))
            .limit(limit)
        )
    ).all()
    return APIResponse(
        data=[{"norad_id": row.norad_id, "epoch": row.epoch} for row in rows],
        meta=await build_meta("/orbits/latest-epochs", db, ["space-track", "celestrak"]),
    )


@router.get(
    "/launches/next",
    tags=["Launch"],
    dependencies=[Depends(RateLimiter("public_light")), Depends(require_capability("Launch"))],
)
async def next_launch(db: Any = Depends(get_db)) -> Any:
    row = (
        await db.execute(
            select(Launch)
            .where(Launch.window_start >= datetime.now(UTC))
            .order_by(Launch.window_start)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No upcoming launch is available")
    return APIResponse(
        data={
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "window_start": row.window_start,
        },
        meta=await build_meta("/launches/next", db, ["the-space-devs"]),
    )


@router.get(
    "/launches/calendar",
    tags=["Launch"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Launch")),
    ],
)
async def launch_calendar(days: int = Query(30, ge=1, le=366), db: Any = Depends(get_db)) -> Any:
    start = datetime.now(UTC)
    end = start + timedelta(days=days)
    rows = (
        (
            await db.execute(
                select(Launch)
                .where(Launch.window_start >= start, Launch.window_start < end)
                .order_by(Launch.window_start)
                .limit(1000)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=[
            {"id": row.id, "name": row.name, "status": row.status, "window_start": row.window_start}
            for row in rows
        ],
        meta=await build_meta("/launches/calendar", db, ["the-space-devs"]),
    )


@router.get(
    "/launches/statistics",
    tags=["Launch"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Launch")),
    ],
)
async def launch_statistics(db: Any = Depends(get_db)) -> Any:
    rows = (
        await db.execute(
            select(Launch.status, func.count().label("count"))
            .group_by(Launch.status)
            .order_by(desc("count"))
        )
    ).all()
    return APIResponse(
        data={"by_status": [{"status": row.status, "count": row.count} for row in rows]},
        meta=await build_meta("/launches/statistics", db, ["the-space-devs"]),
    )


@router.get(
    "/space-weather/geomagnetic-indices/latest",
    tags=["Space Weather"],
    dependencies=[
        Depends(RateLimiter("public_light")),
        Depends(require_capability("Space Weather")),
    ],
)
async def latest_kp(db: Any = Depends(get_db)) -> Any:
    row = (
        await db.execute(
            select(SpaceWeatherIndex).order_by(desc(SpaceWeatherIndex.timestamp)).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No geomagnetic observation is available")
    return APIResponse(
        data={"timestamp": row.timestamp, "kp_index": row.kp_index, "ap_index": row.ap_index},
        meta=await build_meta("/space-weather/geomagnetic-indices/latest", db, ["noaa-swpc"]),
    )


@router.get(
    "/space-weather/solar-wind/latest",
    tags=["Space Weather"],
    dependencies=[
        Depends(RateLimiter("public_light")),
        Depends(require_capability("Space Weather")),
    ],
)
async def latest_wind(db: Any = Depends(get_db)) -> Any:
    row = (
        await db.execute(select(SolarWind).order_by(desc(SolarWind.timestamp)).limit(1))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No solar-wind observation is available")
    return APIResponse(
        data={
            "timestamp": row.timestamp,
            "speed_km_s": row.speed_km_s,
            "density_cm3": row.density_cm3,
            "temperature_k": row.temperature_k,
        },
        meta=await build_meta("/space-weather/solar-wind/latest", db, ["noaa-swpc"]),
    )


@router.get(
    "/space-weather/freshness",
    tags=["Space Weather"],
    dependencies=[
        Depends(RateLimiter("public_light")),
        Depends(require_capability("Space Weather")),
    ],
)
async def weather_freshness(db: Any = Depends(get_db)) -> Any:
    kp_time = (await db.execute(select(func.max(SpaceWeatherIndex.timestamp)))).scalar_one()
    wind_time = (await db.execute(select(func.max(SolarWind.timestamp)))).scalar_one()
    now = datetime.now(UTC)
    return APIResponse(
        data={
            "geomagnetic_observed_at": kp_time,
            "geomagnetic_age_seconds": int((now - kp_time).total_seconds()) if kp_time else None,
            "solar_wind_observed_at": wind_time,
            "solar_wind_age_seconds": int((now - wind_time).total_seconds()) if wind_time else None,
        },
        meta=await build_meta("/space-weather/freshness", db, ["noaa-swpc"]),
    )


@router.get(
    "/neos/statistics",
    tags=["Neo"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Neo")),
    ],
)
async def neo_statistics(db: Any = Depends(get_db)) -> Any:
    total, hazardous, sentry = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(NearEarthObject.is_potentially_hazardous.is_(True)),
                func.count().filter(NearEarthObject.is_sentry_object.is_(True)),
            )
        )
    ).one()
    return APIResponse(
        data={"total": total, "potentially_hazardous": hazardous, "sentry": sentry},
        meta=await build_meta("/neos/statistics", db, ["nasa-neows"]),
    )


@router.get(
    "/neos/hazardous",
    tags=["Neo"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Neo")),
    ],
)
async def hazardous_neos(limit: int = Query(100, ge=1, le=500), db: Any = Depends(get_db)) -> Any:
    rows = (
        (
            await db.execute(
                select(NearEarthObject)
                .where(NearEarthObject.is_potentially_hazardous.is_(True))
                .order_by(NearEarthObject.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=[
            {"id": row.id, "name": row.name, "absolute_magnitude_h": row.absolute_magnitude_h}
            for row in rows
        ],
        meta=await build_meta("/neos/hazardous", db, ["nasa-neows"]),
    )


@router.get(
    "/neos/close-approaches/upcoming",
    tags=["Neo"],
    dependencies=[
        Depends(RateLimiter("public_standard")),
        Depends(require_capability("Neo")),
    ],
)
async def upcoming_approaches(
    days: int = Query(30, ge=1, le=366),
    limit: int = Query(100, ge=1, le=500),
    db: Any = Depends(get_db),
) -> Any:
    start = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(CloseApproach)
                .where(
                    CloseApproach.close_approach_date >= start,
                    CloseApproach.close_approach_date < start + timedelta(days=days),
                )
                .order_by(CloseApproach.close_approach_date)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=[
            {
                "neo_id": row.neo_id,
                "close_approach_date": row.close_approach_date,
                "relative_velocity_kms": row.relative_velocity_kms,
                "miss_distance_au": row.miss_distance_au,
                "orbiting_body": row.orbiting_body,
            }
            for row in rows
        ],
        meta=await build_meta("/neos/close-approaches/upcoming", db, ["nasa-neows"]),
    )
