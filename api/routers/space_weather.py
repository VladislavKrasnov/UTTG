from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import SolarWindResponse, SpaceWeatherIndexResponse
from api.utils import build_meta
from core.cache_layer import cached
from core.capabilities import unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import AsyncSessionLocal, get_db
from storage.models import SolarWind, SpaceWeatherIndex

router = APIRouter(tags=["Space Weather"])


@router.get("/space-weather/overview", dependencies=[Depends(RateLimiter("public_light"))])
async def get_sw_overview(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    async def load_overview() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            kp = (
                await session.execute(
                    select(SpaceWeatherIndex).order_by(desc(SpaceWeatherIndex.timestamp)).limit(1)
                )
            ).scalar_one_or_none()
            wind = (
                await session.execute(
                    select(SolarWind).order_by(desc(SolarWind.timestamp)).limit(1)
                )
            ).scalar_one_or_none()
        kp_value = kp.kp_index if kp else None
        condition = (
            "storm"
            if kp_value is not None and kp_value >= 5
            else "unsettled"
            if kp_value is not None and kp_value >= 4
            else "quiet"
            if kp_value is not None
            else "unknown"
        )
        return {
            "condition": condition,
            "kp_index": kp_value,
            "kp_observed_at": kp.timestamp if kp else None,
            "solar_wind_speed_km_s": wind.speed_km_s if wind else None,
            "solar_wind_observed_at": wind.timestamp if wind else None,
        }

    data, cache_state, _age = await cached(
        "space-weather:overview", load_overview, ttl=60, stale=600
    )
    request.state.cache_state = cache_state
    return APIResponse(
        data=data,
        meta=await build_meta("/space-weather/overview", db, ["noaa-swpc"]),
    )


@router.get(
    "/space-weather/geomagnetic-indices",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_sw_indices(
    limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[SpaceWeatherIndexResponse]]:
    stmt = select(SpaceWeatherIndex).order_by(desc(SpaceWeatherIndex.timestamp)).limit(limit)
    result = await db.execute(stmt)
    indices = result.scalars().all()

    data = [
        SpaceWeatherIndexResponse(timestamp=i.timestamp, kp_index=i.kp_index, ap_index=i.ap_index)
        for i in indices
    ]
    return APIResponse(
        data=data, meta=await build_meta("/space-weather/geomagnetic-indices", db, ["noaa-swpc"])
    )


@router.get("/space-weather/solar-wind", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_sw_wind(
    limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[SolarWindResponse]]:
    stmt = select(SolarWind).order_by(desc(SolarWind.timestamp)).limit(limit)
    result = await db.execute(stmt)
    winds = result.scalars().all()

    data = [
        SolarWindResponse(
            timestamp=w.timestamp,
            speed_km_s=w.speed_km_s,
            density_cm3=w.density_cm3,
            temperature_k=w.temperature_k,
        )
        for w in winds
    ]
    return APIResponse(
        data=data, meta=await build_meta("/space-weather/solar-wind", db, ["noaa-swpc"])
    )


@router.get("/space-weather/solar-flares", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_flares(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/space-weather/solar-flares", db, ["noaa-swpc"])
    )


@router.get("/space-weather/cmes", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_cmes(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/space-weather/cmes", db, ["noaa-swpc"]))


@router.get("/space-weather/solar-particle-events", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_spe(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/space-weather/solar-particle-events", db, ["noaa-swpc"])
    )


@router.get("/space-weather/radiation-storms", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_storms(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/space-weather/radiation-storms", db, ["noaa-swpc"])
    )


@router.get("/space-weather/alerts", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_alerts(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/space-weather/alerts", db, ["noaa-swpc"]))


@router.get("/space-weather/events", dependencies=[Depends(unavailable_endpoint)])
async def get_sw_events(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/space-weather/events", db, ["noaa-swpc"]))
