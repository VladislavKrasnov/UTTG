from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import ReentryEventResponse
from api.utils import build_meta
from core.capabilities import unavailable_endpoint
from storage.database import get_db
from storage.models import ReentryEvent

router = APIRouter(tags=["Events"])


@router.get("/reentries", dependencies=[Depends(unavailable_endpoint)])
async def get_reentries(
    limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[ReentryEventResponse]]:
    stmt = select(ReentryEvent).order_by(desc(ReentryEvent.expected_reentry_time)).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()

    data = [
        ReentryEventResponse(
            id=e.id,
            norad_id=e.norad_id,
            expected_reentry_time=e.expected_reentry_time,
            latitude=e.latitude,
            longitude=e.longitude,
        )
        for e in events
    ]
    return APIResponse(data=data, meta=await build_meta("/reentries", db, ["space-track"]))


@router.get("/reentries/{event_id}", dependencies=[Depends(unavailable_endpoint)])
async def get_reentry(
    event_id: str, db: AsyncSession = Depends(get_db)
) -> APIResponse[ReentryEventResponse]:
    stmt = select(ReentryEvent).where(ReentryEvent.id == event_id)
    result = await db.execute(stmt)
    e = result.scalar_one_or_none()

    if not e:
        raise HTTPException(status_code=404, detail="Event not found")

    data = ReentryEventResponse(
        id=e.id,
        norad_id=e.norad_id,
        expected_reentry_time=e.expected_reentry_time,
        latitude=e.latitude,
        longitude=e.longitude,
    )
    return APIResponse(
        data=data, meta=await build_meta(f"/reentries/{event_id}", db, ["space-track"])
    )


@router.get("/object-events", dependencies=[Depends(unavailable_endpoint)])
async def get_object_events(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/object-events", db, ["space-track"]))


@router.get("/events", dependencies=[Depends(unavailable_endpoint)])
async def get_events(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/events", db, ["space-track"]))


@router.get("/events/{event_id}", dependencies=[Depends(unavailable_endpoint)])
async def get_event(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/events/{event_id}", db, ["space-track"]))
