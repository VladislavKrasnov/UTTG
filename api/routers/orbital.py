from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sgp4.api import Satrec
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import OrbitalElementResponse, PositionResponse
from api.utils import build_meta
from core.cache_layer import cached
from core.capabilities import unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import AsyncSessionLocal, get_db
from storage.models import OrbitalElement

router = APIRouter(tags=["Orbital"])

_SOURCES = ["space-track", "celestrak"]


def _julian_date(dt: datetime) -> tuple[float, float]:
    jd = dt.toordinal() + 1721424.5
    fr = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6) / 86400.0
    return jd, fr


def _teme_to_geodetic(r_km: tuple[float, float, float], at: datetime) -> tuple[float, float, float]:
    """Convert an SGP4 TEME position to WGS-84 geodetic coordinates.

    GMST is sufficient for this public tracking API; sub-kilometre applications
    should apply IERS Earth-orientation parameters in a dedicated service.
    """
    jd, fr = _julian_date(at)
    centuries = ((jd + fr) - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * ((jd + fr) - 2451545.0)
        + 0.000387933 * centuries**2
        - centuries**3 / 38_710_000.0
    ) % 360.0
    theta = math.radians(gmst_deg)
    x_teme, y_teme, z = r_km
    x = math.cos(theta) * x_teme + math.sin(theta) * y_teme
    y = -math.sin(theta) * x_teme + math.cos(theta) * y_teme

    semi_major = 6378.137
    flattening = 1.0 / 298.257223563
    eccentricity_sq = flattening * (2.0 - flattening)
    longitude = math.atan2(y, x)
    radius = math.hypot(x, y)
    latitude = math.atan2(z, radius * (1.0 - eccentricity_sq))
    altitude = 0.0
    for _ in range(8):
        sin_lat = math.sin(latitude)
        normal = semi_major / math.sqrt(1.0 - eccentricity_sq * sin_lat**2)
        altitude = radius / max(math.cos(latitude), 1e-12) - normal
        latitude = math.atan2(z, radius * (1.0 - eccentricity_sq * normal / (normal + altitude)))
    return math.degrees(latitude), math.degrees(longitude), altitude


def _propagate_track(line1: str, line2: str, start: datetime, minutes: int) -> list[dict[str, Any]]:
    sat = Satrec.twoline2rv(line1, line2)
    track: list[dict[str, Any]] = []
    for offset_min in range(minutes):
        at = start + timedelta(minutes=offset_min)
        jd, fr = _julian_date(at)
        error, position, _velocity = sat.sgp4(jd, fr)
        if error == 0:
            lat, lon, alt = _teme_to_geodetic(position, at)
            track.append(
                {
                    "t": at.isoformat(),
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "alt": round(alt, 2),
                }
            )
    return track


@router.get(
    "/satellites/{norad_id}/orbital-elements/latest",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_orbital_latest(
    norad_id: int, request: Request, db: AsyncSession = Depends(get_db)
) -> APIResponse[OrbitalElementResponse]:
    cache_key = f"oe:latest:{norad_id}"

    async def _compute() -> dict[str, Any] | None:
        stmt = (
            select(OrbitalElement)
            .where(OrbitalElement.norad_id == norad_id)
            .order_by(desc(OrbitalElement.epoch))
            .limit(1)
        )
        async with AsyncSessionLocal() as session:
            result = await session.execute(stmt)
            el = result.scalar_one_or_none()
        if not el:
            return None
        return {
            "norad_id": el.norad_id,
            "epoch": el.epoch.isoformat(),
            "inclination": el.inclination,
            "right_ascension": el.right_ascension,
            "eccentricity": el.eccentricity,
            "argument_of_perigee": el.argument_of_perigee,
            "mean_anomaly": el.mean_anomaly,
            "mean_motion": el.mean_motion,
            "provider": el.provider,
        }

    payload, freshness_state, age_s = await cached(cache_key, _compute, ttl=3600, stale=86400)
    request.state.cache_state = freshness_state
    if payload is None:
        raise HTTPException(status_code=404, detail="Orbital elements not found")

    data = OrbitalElementResponse(**{**payload, "epoch": datetime.fromisoformat(payload["epoch"])})
    meta = await build_meta(f"/satellites/{norad_id}/orbital-elements/latest", db, _SOURCES)
    meta.freshness.state = freshness_state
    meta.freshness.age_seconds = age_s
    return APIResponse(data=data, meta=meta)


@router.get(
    "/satellites/{norad_id}/orbital-elements",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_orbital_elements(
    norad_id: int,
    limit: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[OrbitalElementResponse]]:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(limit)
    )
    result = await db.execute(stmt)
    elements = result.scalars().all()

    data = [
        OrbitalElementResponse(
            norad_id=el.norad_id,
            epoch=el.epoch,
            inclination=el.inclination,
            right_ascension=el.right_ascension,
            eccentricity=el.eccentricity,
            argument_of_perigee=el.argument_of_perigee,
            mean_anomaly=el.mean_anomaly,
            mean_motion=el.mean_motion,
            provider=el.provider,
        )
        for el in elements
    ]
    meta = await build_meta(f"/satellites/{norad_id}/orbital-elements", db, _SOURCES)
    return APIResponse(data=data, meta=meta)


@router.get(
    "/satellites/{norad_id}/position",
    dependencies=[Depends(RateLimiter("public_expensive"))],
)
async def get_position(
    norad_id: int,
    at: datetime | None = Query(default=None, description="UTC instant; defaults to current time"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PositionResponse]:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(1)
    )
    result = await db.execute(stmt)
    el = result.scalar_one_or_none()

    if not el or not el.tle_line1 or not el.tle_line2:
        raise HTTPException(status_code=404, detail="TLE not available for this satellite")

    sat = Satrec.twoline2rv(el.tle_line1, el.tle_line2)
    instant = at or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    instant = instant.astimezone(UTC)
    if abs((instant - datetime.now(UTC)).days) > 30:
        raise HTTPException(status_code=422, detail="Position time must be within 30 days of now")
    jd, fr = _julian_date(instant)
    e, r, _v = sat.sgp4(jd, fr)

    if e != 0:
        raise HTTPException(status_code=500, detail=f"SGP4 propagation error code {e}")

    lat, lon, alt = _teme_to_geodetic(r, instant)
    meta = await build_meta(f"/satellites/{norad_id}/position", db, _SOURCES)
    return APIResponse(
        data=PositionResponse(
            norad_id=norad_id, timestamp=instant, latitude=lat, longitude=lon, altitude=alt
        ),
        meta=meta,
    )


@router.get(
    "/satellites/{norad_id}/ground-track",
    dependencies=[Depends(RateLimiter("public_expensive"))],
)
async def get_ground_track(
    norad_id: int,
    minutes: int = Query(90, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(1)
    )
    result = await db.execute(stmt)
    el = result.scalar_one_or_none()

    if not el or not el.tle_line1 or not el.tle_line2:
        raise HTTPException(status_code=404, detail="TLE not available for ground track")

    # SGP4 is CPU-bound. Keep it off the event loop so one long track cannot
    # stall unrelated cached requests handled by this worker.
    start = datetime.now(UTC).replace(second=0, microsecond=0)
    track = await asyncio.to_thread(_propagate_track, el.tle_line1, el.tle_line2, start, minutes)

    meta = await build_meta(f"/satellites/{norad_id}/ground-track", db, _SOURCES)
    return APIResponse(data=track, meta=meta)


@router.get("/satellites/{norad_id}/passes", dependencies=[Depends(unavailable_endpoint)])
async def get_passes(
    norad_id: int,
    lat: float = Query(0.0, ge=-90.0, le=90.0),
    lon: float = Query(0.0, ge=-180.0, le=180.0),
    min_el: float = Query(10.0, ge=0.0, le=90.0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(1)
    )
    result = await db.execute(stmt)
    el = result.scalar_one_or_none()

    if not el or not el.tle_line1 or not el.tle_line2:
        raise HTTPException(status_code=404, detail="TLE not available for pass prediction")

    meta = await build_meta(f"/satellites/{norad_id}/passes", db, _SOURCES)
    return APIResponse(
        data={
            "observer": {"lat": lat, "lon": lon, "min_elevation_deg": min_el},
            "passes": [],
            "note": "Pass predictions require sgp4 observer integration; TLE is available.",
        },
        meta=meta,
    )


@router.get(
    "/satellites/{norad_id}/orbit-summary",
    dependencies=[Depends(RateLimiter("public_standard"))],
)
async def get_orbit_summary(norad_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(1)
    )
    result = await db.execute(stmt)
    el = result.scalar_one_or_none()

    summary: dict[str, Any] = {"norad_id": norad_id}
    if el and el.mean_motion and el.mean_motion > 0:
        period_min = 1440.0 / el.mean_motion
        mu = 398600.4418
        n_rads = el.mean_motion * 2 * math.pi / 86400
        a_km = (mu / (n_rads**2)) ** (1.0 / 3.0)
        summary["orbital_period_minutes"] = round(period_min, 2)
        summary["semi_major_axis_km"] = round(a_km, 1)
        summary["inclination_deg"] = el.inclination
        summary["epoch"] = el.epoch.isoformat()

    meta = await build_meta(f"/satellites/{norad_id}/orbit-summary", db, _SOURCES)
    return APIResponse(data=summary, meta=meta)


@router.get(
    "/satellites/{norad_id}/orbital-changes",
    dependencies=[Depends(RateLimiter("public_expensive"))],
)
async def get_orbital_changes(
    norad_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = (
        select(OrbitalElement)
        .where(OrbitalElement.norad_id == norad_id)
        .order_by(desc(OrbitalElement.epoch))
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    elements = result.scalars().all()

    changes = []
    for i in range(len(elements) - 1):
        curr, prev = elements[i], elements[i + 1]
        if curr.mean_motion and prev.mean_motion:
            changes.append(
                {
                    "from_epoch": prev.epoch.isoformat(),
                    "to_epoch": curr.epoch.isoformat(),
                    "delta_mean_motion": round(
                        (curr.mean_motion or 0) - (prev.mean_motion or 0), 8
                    ),
                    "delta_inclination": round(
                        (curr.inclination or 0) - (prev.inclination or 0), 6
                    ),
                }
            )

    meta = await build_meta(f"/satellites/{norad_id}/orbital-changes", db, _SOURCES)
    return APIResponse(data=changes, meta=meta)


@router.get("/orbits/coverage", dependencies=[Depends(RateLimiter("public_standard"))])
async def get_coverage(db: AsyncSession = Depends(get_db)) -> Any:
    from sqlalchemy import func

    from storage.models import OrbitalElement

    count_row = await db.execute(select(func.count()).select_from(OrbitalElement))
    total = count_row.scalar() or 0
    meta = await build_meta("/orbits/coverage", db, _SOURCES)
    return APIResponse(data={"total_orbital_elements": total}, meta=meta)
