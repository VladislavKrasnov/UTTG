from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import valkey.asyncio as valkey_async
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from core.capabilities import configured_providers
from core.queue import close_nats, connect_nats, ensure_event_stream, nc
from core.settings import settings
from providers.celestrak import CelestrakClient
from providers.nasa import NasaClient
from providers.noaa import NoaaClient
from providers.spacedevs import SpaceDevsClient
from providers.spacetrack import SpaceTrackClient
from storage.database import AsyncSessionLocal
from storage.models import (
    CloseApproach,
    Launch,
    NearEarthObject,
    OrbitalElement,
    ProviderHealth,
    Satellite,
    SolarWind,
    SpaceWeatherIndex,
    Webhook,
)

logger = logging.getLogger(__name__)


async def _publish_event(event_name: str, data: dict[str, Any]) -> None:
    try:
        async with AsyncSessionLocal() as session:
            webhooks = (
                (await session.execute(select(Webhook).where(Webhook.active.is_(True))))
                .scalars()
                .all()
            )
        jetstream = nc.jetstream()
        for webhook in webhooks:
            if event_name not in set(json.loads(webhook.events)):
                continue
            envelope = json.dumps(
                {"webhook_id": webhook.id, "event": event_name, "data": data},
                default=str,
                separators=(",", ":"),
            ).encode()
            await jetstream.publish("events.webhooks.outbound", envelope)
    except Exception:
        logger.exception("Failed to publish webhook event", extra={"event": event_name})


async def _provider_health(provider_id: str, status: str, error: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(select(ProviderHealth).where(ProviderHealth.id == provider_id))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None:
            row = ProviderHealth(id=provider_id, status=status)
            session.add(row)
        row.status = status
        if status == "active":
            row.last_success_at = now
            row.error_message = None
        else:
            row.last_error_at = now
            row.error_message = error[:1000] if error else None
        await session.commit()


async def _run_guarded(
    valkey: valkey_async.Valkey,
    provider_id: str,
    job_name: str,
    interval_seconds: int,
    job: Callable[[], Awaitable[None]],
) -> None:
    while True:
        lock_key = f"scheduler:lock:{job_name}"
        acquired = await valkey.set(
            lock_key,
            "1",
            ex=max(interval_seconds - 30, 30),
            nx=True,
        )
        if acquired:
            try:
                await job()
                await _provider_health(provider_id, "active")
            except Exception as exc:
                safe_error = type(exc).__name__
                await _provider_health(provider_id, "error", safe_error)
                await _publish_event(
                    "provider.degraded",
                    {"provider": provider_id, "job": job_name, "error": safe_error},
                )
                logger.exception("Provider ingestion failed", extra={"provider_id": provider_id})
        await asyncio.sleep(interval_seconds)


async def _ingest_satcat() -> None:
    client = SpaceTrackClient()
    try:
        records = await client.get_satcat()
    finally:
        await client.close()
    values = [
        {
            "norad_id": int(record["NORAD_CAT_ID"]),
            "cospar_id": record.get("INTLDES"),
            "name": (record.get("SATNAME") or "").strip(),
            "country": record.get("COUNTRY"),
            "object_type": record.get("OBJECT_TYPE"),
            "orbit_class": None,
            "status": "decayed" if record.get("DECAY") else "active",
        }
        for record in records
        if str(record.get("NORAD_CAT_ID", "")).isdigit()
    ]
    async with AsyncSessionLocal() as session:
        for batch in _batches(values, 500):
            statement = insert(Satellite).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=["norad_id"],
                set_={
                    "cospar_id": statement.excluded.cospar_id,
                    "name": statement.excluded.name,
                    "country": statement.excluded.country,
                    "object_type": statement.excluded.object_type,
                    "status": statement.excluded.status,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info("Space-Track SATCAT ingestion complete", extra={"records": len(values)})
    await _publish_event("object.updated", {"provider": "space-track", "count": len(values)})


async def _ingest_orbital_elements() -> None:
    client = CelestrakClient()
    try:
        records = await client.get_group("active")
    finally:
        await client.close()

    satellites: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    for record in records:
        catalog_id = record.get("NORAD_CAT_ID")
        epoch_value = record.get("EPOCH")
        if not str(catalog_id).isdigit() or not epoch_value:
            continue
        epoch = _parse_datetime(str(epoch_value))
        norad_id = int(str(catalog_id))
        satellites.append(
            {
                "norad_id": norad_id,
                "cospar_id": record.get("OBJECT_ID"),
                "name": record.get("OBJECT_NAME") or str(norad_id),
                "object_type": record.get("OBJECT_TYPE"),
            }
        )
        elements.append(
            {
                "id": uuid4(),
                "norad_id": norad_id,
                "epoch": epoch,
                "inclination": _float(record.get("INCLINATION")),
                "right_ascension": _float(record.get("RA_OF_ASC_NODE")),
                "eccentricity": _float(record.get("ECCENTRICITY")),
                "argument_of_perigee": _float(record.get("ARG_OF_PERICENTER")),
                "mean_anomaly": _float(record.get("MEAN_ANOMALY")),
                "mean_motion": _float(record.get("MEAN_MOTION")),
                "tle_line1": record.get("TLE_LINE1"),
                "tle_line2": record.get("TLE_LINE2"),
                "provider": "celestrak",
            }
        )

    async with AsyncSessionLocal() as session:
        for batch in _batches(satellites, 500):
            statement = insert(Satellite).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=["norad_id"],
                set_={
                    "cospar_id": statement.excluded.cospar_id,
                    "name": statement.excluded.name,
                    "object_type": statement.excluded.object_type,
                },
            )
            await session.execute(statement)
        for batch in _batches(elements, 300):
            statement = insert(OrbitalElement).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=["norad_id", "provider", "epoch"],
                set_={
                    "inclination": statement.excluded.inclination,
                    "right_ascension": statement.excluded.right_ascension,
                    "eccentricity": statement.excluded.eccentricity,
                    "argument_of_perigee": statement.excluded.argument_of_perigee,
                    "mean_anomaly": statement.excluded.mean_anomaly,
                    "mean_motion": statement.excluded.mean_motion,
                    "tle_line1": statement.excluded.tle_line1,
                    "tle_line2": statement.excluded.tle_line2,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info("CelesTrak orbital ingestion complete", extra={"records": len(elements)})
    await _publish_event("object.updated", {"provider": "celestrak", "count": len(elements)})


async def _ingest_space_weather() -> None:
    client = NoaaClient()
    try:
        index_records, wind_records = await asyncio.gather(
            client.get_planetary_k(),
            client.get_solar_wind(),
        )
    finally:
        await client.close()

    indices_dict: dict[Any, dict[str, Any]] = {}
    for record in index_records:
        if not record.get("time_tag"):
            continue
        ts = _parse_datetime(str(record["time_tag"]))
        indices_dict[ts] = {
            "id": uuid4(),
            "timestamp": ts,
            "kp_index": _float(record.get("kp", 0)) or 0.0,
            "ap_index": _float(record.get("ap")),
        }
    indices = list(indices_dict.values())

    winds_dict: dict[Any, dict[str, Any]] = {}
    for record in wind_records:
        if not record.get("time_tag"):
            continue
        ts = _parse_datetime(str(record["time_tag"]))
        winds_dict[ts] = {
            "id": uuid4(),
            "timestamp": ts,
            "speed_km_s": _float(record.get("proton_speed", record.get("speed", 0))) or 0.0,
            "density_cm3": _float(record.get("proton_density", record.get("density", 0))) or 0.0,
            "temperature_k": _float(record.get("proton_temperature", record.get("temperature", 0)))
            or 0.0,
        }
    winds = list(winds_dict.values())
    async with AsyncSessionLocal() as session:
        if indices:
            statement = insert(SpaceWeatherIndex).values(indices)
            statement = statement.on_conflict_do_update(
                index_elements=["timestamp"],
                set_={
                    "kp_index": statement.excluded.kp_index,
                    "ap_index": statement.excluded.ap_index,
                },
            )
            await session.execute(statement)
        if winds:
            statement = insert(SolarWind).values(winds)
            statement = statement.on_conflict_do_update(
                index_elements=["timestamp"],
                set_={
                    "speed_km_s": statement.excluded.speed_km_s,
                    "density_cm3": statement.excluded.density_cm3,
                    "temperature_k": statement.excluded.temperature_k,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info(
        "NOAA SWPC ingestion complete",
        extra={"indices": len(indices), "solar_wind": len(winds)},
    )
    if indices and indices[0]["kp_index"] >= 5:
        await _publish_event(
            "space_weather.alert",
            {"provider": "noaa-swpc", "kp_index": indices[0]["kp_index"]},
        )


async def _ingest_neos() -> None:
    client = NasaClient()
    today = date.today()
    try:
        payload = await client.get_neo_feed(
            today.isoformat(), (today + timedelta(days=7)).isoformat()
        )
    finally:
        await client.close()

    objects: dict[str, dict[str, Any]] = {}
    approaches: list[dict[str, Any]] = []
    for daily_objects in payload.get("near_earth_objects", {}).values():
        for item in daily_objects:
            neo_id = str(item["id"])
            kilometers = item.get("estimated_diameter", {}).get("kilometers", {})
            objects[neo_id] = {
                "id": neo_id,
                "name": item.get("name") or neo_id,
                "absolute_magnitude_h": _float(item.get("absolute_magnitude_h")),
                "estimated_diameter_min_km": _float(kilometers.get("estimated_diameter_min")),
                "estimated_diameter_max_km": _float(kilometers.get("estimated_diameter_max")),
                "is_potentially_hazardous": bool(item.get("is_potentially_hazardous_asteroid")),
                "is_sentry_object": bool(item.get("is_sentry_object")),
            }
            for approach in item.get("close_approach_data", []):
                timestamp = approach.get("close_approach_date_full") or approach.get(
                    "close_approach_date"
                )
                if not timestamp:
                    continue
                approaches.append(
                    {
                        "id": uuid4(),
                        "neo_id": neo_id,
                        "close_approach_date": _parse_nasa_datetime(str(timestamp)),
                        "relative_velocity_kms": float(
                            approach.get("relative_velocity", {}).get("kilometers_per_second", 0)
                        ),
                        "miss_distance_au": float(
                            approach.get("miss_distance", {}).get("astronomical", 0)
                        ),
                        "orbiting_body": approach.get("orbiting_body") or "Earth",
                    }
                )

    async with AsyncSessionLocal() as session:
        if objects:
            statement = insert(NearEarthObject).values(list(objects.values()))
            statement = statement.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": statement.excluded.name,
                    "absolute_magnitude_h": statement.excluded.absolute_magnitude_h,
                    "estimated_diameter_min_km": statement.excluded.estimated_diameter_min_km,
                    "estimated_diameter_max_km": statement.excluded.estimated_diameter_max_km,
                    "is_potentially_hazardous": statement.excluded.is_potentially_hazardous,
                    "is_sentry_object": statement.excluded.is_sentry_object,
                },
            )
            await session.execute(statement)
        if approaches:
            statement = insert(CloseApproach).values(approaches)
            statement = statement.on_conflict_do_update(
                index_elements=["neo_id", "close_approach_date", "orbiting_body"],
                set_={
                    "relative_velocity_kms": statement.excluded.relative_velocity_kms,
                    "miss_distance_au": statement.excluded.miss_distance_au,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info("NASA NEO ingestion complete", extra={"objects": len(objects)})
    await _publish_event("object.updated", {"provider": "nasa-neows", "count": len(objects)})


async def _ingest_launches() -> None:
    client = SpaceDevsClient()
    try:
        payload = await client.get_upcoming_launches(100)
    finally:
        await client.close()
    values = [
        {
            "id": str(item["id"]),
            "name": item.get("name") or str(item["id"]),
            "status": (item.get("status") or {}).get("name"),
            "window_start": _parse_datetime(item["window_start"])
            if item.get("window_start")
            else None,
            "window_end": _parse_datetime(item["window_end"]) if item.get("window_end") else None,
            "provider": "the-space-devs",
        }
        for item in payload.get("results", [])
        if item.get("id")
    ]
    async with AsyncSessionLocal() as session:
        if values:
            statement = insert(Launch).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": statement.excluded.name,
                    "status": statement.excluded.status,
                    "window_start": statement.excluded.window_start,
                    "window_end": statement.excluded.window_end,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info("Launch ingestion complete", extra={"records": len(values)})
    await _publish_event("launch.updated", {"provider": "the-space-devs", "count": len(values)})


async def run_scheduler() -> None:
    await connect_nats()
    await ensure_event_stream()
    valkey = valkey_async.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
    providers = configured_providers()
    jobs: list[Awaitable[None]] = []
    if "space-track" in providers:
        jobs.append(_run_guarded(valkey, "space-track", "satcat", 86400, _ingest_satcat))
    if "celestrak" in providers:
        jobs.append(_run_guarded(valkey, "celestrak", "orbital", 3600, _ingest_orbital_elements))
    if "noaa-swpc" in providers:
        jobs.append(_run_guarded(valkey, "noaa-swpc", "space-weather", 300, _ingest_space_weather))
    if "nasa-neows" in providers:
        jobs.append(_run_guarded(valkey, "nasa-neows", "neos", 3600, _ingest_neos))
    if "the-space-devs" in providers:
        jobs.append(_run_guarded(valkey, "the-space-devs", "launches", 14400, _ingest_launches))

    try:
        if jobs:
            await asyncio.gather(*jobs)
        else:
            await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await valkey.aclose()
        await close_nats()


def _batches(values: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_nasa_datetime(value: str) -> datetime:
    for pattern in ("%Y-%b-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return _parse_datetime(value)


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = value.rstrip("Zz")
        return float(value)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())
