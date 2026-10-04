from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import LaunchResponse
from api.utils import build_meta
from core.capabilities import tag_sources, unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import get_db
from storage.models import Launch

router = APIRouter(tags=["Launch"])
_LAUNCH_SOURCES = tag_sources("Launch")


@router.get("/launches/upcoming", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_launches_upcoming(
    limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[LaunchResponse]]:
    stmt = (
        select(Launch)
        .where(Launch.window_start > datetime.now(UTC))
        .order_by(Launch.window_start.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    launches = result.scalars().all()

    data = [LaunchResponse.model_validate(launch) for launch in launches]
    return APIResponse(data=data, meta=await build_meta("/launches/upcoming", db, _LAUNCH_SOURCES))


@router.get("/launches", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_launches(
    limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[LaunchResponse]]:
    stmt = select(Launch).order_by(desc(Launch.window_start)).limit(limit)
    result = await db.execute(stmt)
    launches = result.scalars().all()

    data = [LaunchResponse.model_validate(launch) for launch in launches]
    return APIResponse(data=data, meta=await build_meta("/launches", db, _LAUNCH_SOURCES))


@router.get("/launches/{launch_id}", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_launch(
    launch_id: str, db: AsyncSession = Depends(get_db)
) -> APIResponse[LaunchResponse]:
    stmt = select(Launch).where(Launch.id == launch_id)
    result = await db.execute(stmt)
    launch = result.scalar_one_or_none()

    if not launch:
        raise HTTPException(status_code=404, detail="Launch not found")

    data = LaunchResponse.model_validate(launch)
    return APIResponse(
        data=data, meta=await build_meta(f"/launches/{launch_id}", db, _LAUNCH_SOURCES)
    )


@router.get("/missions/{mission_id}", dependencies=[Depends(unavailable_endpoint)])
async def get_mission(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/missions/{mission_id}", db, _LAUNCH_SOURCES)
    )


@router.get("/launch-vehicles", dependencies=[Depends(unavailable_endpoint)])
async def get_vehicles(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/launch-vehicles", db, _LAUNCH_SOURCES))


@router.get("/launch-sites", dependencies=[Depends(unavailable_endpoint)])
async def get_sites(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/launch-sites", db, _LAUNCH_SOURCES))


@router.get("/agencies", dependencies=[Depends(unavailable_endpoint)])
async def get_agencies(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/agencies", db, _LAUNCH_SOURCES))
