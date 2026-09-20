from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import CloseApproachResponse, NearEarthObjectResponse
from api.utils import build_meta
from core.capabilities import unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import get_db
from storage.models import CloseApproach, NearEarthObject

router = APIRouter(tags=["Neo"])
_SOURCES = ["nasa-neows"]


def _neo_response(neo: NearEarthObject) -> NearEarthObjectResponse:
    return NearEarthObjectResponse(
        id=neo.id,
        name=neo.name,
        absolute_magnitude_h=neo.absolute_magnitude_h,
        estimated_diameter_min_km=neo.estimated_diameter_min_km,
        estimated_diameter_max_km=neo.estimated_diameter_max_km,
        is_potentially_hazardous=neo.is_potentially_hazardous,
        is_sentry_object=neo.is_sentry_object,
    )


@router.get("/neos", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_neos(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[NearEarthObjectResponse]]:
    statement = select(NearEarthObject).order_by(NearEarthObject.id).limit(limit)
    if cursor:
        statement = statement.where(NearEarthObject.id > cursor)
    objects = (await db.execute(statement)).scalars().all()
    return APIResponse(
        data=[_neo_response(neo) for neo in objects],
        meta=await build_meta("/neos", db, _SOURCES),
    )


@router.get(
    "/neos/close-approaches",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_neo_approaches(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[CloseApproachResponse]]:
    approaches = (
        (
            await db.execute(
                select(CloseApproach)
                .order_by(CloseApproach.close_approach_date.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    data = [
        CloseApproachResponse(
            neo_id=approach.neo_id,
            close_approach_date=approach.close_approach_date,
            relative_velocity_kms=approach.relative_velocity_kms,
            miss_distance_au=approach.miss_distance_au,
            orbiting_body=approach.orbiting_body,
        )
        for approach in approaches
    ]
    return APIResponse(
        data=data,
        meta=await build_meta("/neos/close-approaches", db, _SOURCES),
    )


@router.get("/neos/{neo_id}", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_neo(
    neo_id: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[NearEarthObjectResponse]:
    neo = (
        await db.execute(select(NearEarthObject).where(NearEarthObject.id == neo_id))
    ).scalar_one_or_none()
    if neo is None:
        raise HTTPException(status_code=404, detail="Near Earth Object not found")
    return APIResponse(
        data=_neo_response(neo),
        meta=await build_meta(f"/neos/{neo_id}", db, _SOURCES),
    )


@router.get("/fireballs", dependencies=[Depends(unavailable_endpoint)])
async def get_fireballs() -> Any:
    raise AssertionError


@router.get("/bodies/{body_id}", dependencies=[Depends(unavailable_endpoint)])
async def get_body(body_id: str) -> Any:
    raise AssertionError


@router.get("/ephemeris", dependencies=[Depends(unavailable_endpoint)])
async def get_ephemeris() -> Any:
    raise AssertionError
