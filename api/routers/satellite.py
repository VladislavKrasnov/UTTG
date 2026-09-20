from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.utils import build_meta
from core.cache_layer import cached
from core.capabilities import unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import AsyncSessionLocal, get_db
from storage.models import Satellite

router = APIRouter(tags=["Satellite"])


@router.get("/satellites/{norad_id}", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_satellite(
    norad_id: int, request: Request, db: AsyncSession = Depends(get_db)
) -> APIResponse[dict[str, Any]]:
    async def load_satellite() -> dict[str, Any] | None:
        async with AsyncSessionLocal() as session:
            satellite = (
                await session.execute(select(Satellite).where(Satellite.norad_id == norad_id))
            ).scalar_one_or_none()
            if satellite is None:
                return None
            return {
                "norad_id": satellite.norad_id,
                "cospar_id": satellite.cospar_id,
                "name": satellite.name,
                "operator": satellite.operator,
                "country": satellite.country,
                "object_type": satellite.object_type,
                "orbit_class": satellite.orbit_class,
                "status": satellite.status,
            }

    data, cache_state, _ = await cached(
        f"satellite:{norad_id}",
        load_satellite,
        ttl=3600,
        stale=86400,
    )
    request.state.cache_state = cache_state
    if data is None:
        raise HTTPException(status_code=404, detail="Satellite not found")

    meta = await build_meta(f"/satellites/{norad_id}", db, ["space-track", "celestrak"])
    return APIResponse(data=data, meta=meta)


@router.get("/satellites", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_satellites(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[dict[str, Any]]]:
    async def load_satellites() -> list[dict[str, Any]]:
        statement = select(Satellite).limit(limit)
        if cursor:
            statement = statement.where(Satellite.norad_id > cursor)
        statement = statement.order_by(Satellite.norad_id.asc())
        async with AsyncSessionLocal() as session:
            satellites = (await session.execute(statement)).scalars().all()
            return [
                {
                    "norad_id": satellite.norad_id,
                    "cospar_id": satellite.cospar_id,
                    "name": satellite.name,
                    "operator": satellite.operator,
                    "country": satellite.country,
                    "object_type": satellite.object_type,
                    "orbit_class": satellite.orbit_class,
                    "status": satellite.status,
                }
                for satellite in satellites
            ]

    data, cache_state, _ = await cached(
        f"satellites:{cursor or 0}:{limit}",
        load_satellites,
        ttl=300,
        stale=3600,
    )
    request.state.cache_state = cache_state

    meta = await build_meta("/satellites", db, ["space-track", "celestrak"])
    return APIResponse(data=data, meta=meta)


@router.get(
    "/satellites/by-cospar/{cospar_id}",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_satellite_cospar(
    cospar_id: str, db: AsyncSession = Depends(get_db)
) -> APIResponse[dict[str, Any]]:
    stmt = select(Satellite).where(Satellite.cospar_id == cospar_id)
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()

    if not s:
        raise HTTPException(status_code=404, detail="Satellite not found")

    data = {
        "norad_id": s.norad_id,
        "cospar_id": s.cospar_id,
        "name": s.name,
        "operator": s.operator,
        "country": s.country,
        "object_type": s.object_type,
        "orbit_class": s.orbit_class,
        "status": s.status,
    }
    meta = await build_meta(f"/satellites/by-cospar/{cospar_id}", db, ["space-track", "celestrak"])
    return APIResponse(data=data, meta=meta)


@router.get(
    "/satellites/{norad_id}/identifiers",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_satellite_identifiers(norad_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    satellite = (
        await db.execute(select(Satellite).where(Satellite.norad_id == norad_id))
    ).scalar_one_or_none()
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    meta = await build_meta(f"/satellites/{norad_id}/identifiers", db, ["space-track"])
    return APIResponse(
        data={"norad_id": satellite.norad_id, "cospar_id": satellite.cospar_id}, meta=meta
    )


@router.get(
    "/satellites/{norad_id}/metadata", dependencies=[Depends(RateLimiter("public_standard"))]
)
async def get_satellite_metadata(norad_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    satellite = (
        await db.execute(select(Satellite).where(Satellite.norad_id == norad_id))
    ).scalar_one_or_none()
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    meta = await build_meta(f"/satellites/{norad_id}/metadata", db, ["space-track"])
    return APIResponse(
        data={
            "norad_id": satellite.norad_id,
            "name": satellite.name,
            "operator": satellite.operator,
            "country": satellite.country,
            "object_type": satellite.object_type,
            "orbit_class": satellite.orbit_class,
            "updated_at": satellite.updated_at,
        },
        meta=meta,
    )


@router.get("/satellites/{norad_id}/status", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_satellite_status(norad_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    satellite = (
        await db.execute(select(Satellite).where(Satellite.norad_id == norad_id))
    ).scalar_one_or_none()
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    meta = await build_meta(f"/satellites/{norad_id}/status", db, ["space-track"])
    return APIResponse(data={"norad_id": satellite.norad_id, "status": satellite.status}, meta=meta)


@router.get("/catalog/changes", dependencies=[Depends(unavailable_endpoint)])
async def get_catalog_changes(db: AsyncSession = Depends(get_db)) -> Any:
    meta = await build_meta("/catalog/changes", db, ["space-track"])
    return APIResponse(data=[], meta=meta)
