from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable, Coroutine, Iterator, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import valkey.asyncio as valkey_async
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from core.capabilities import configured_providers
from core.queue import close_nats, connect_nats, ensure_event_stream, nc
from core.settings import settings
from providers.celestrak import CelestrakClient, CelestrakNotModifiedError
from providers.jpl import JplClient
from providers.launch_records import UpcomingLaunch
from providers.nasa import NasaClient
from providers.noaa import NoaaClient
from providers.rocketlaunch import RocketLaunchLiveClient
from providers.spacedevs import SpaceDevsClient
from providers.spacetrack import SpaceTrackClient
from providers.transport import (
    ProviderQuotaError,
    ProviderRequestError,
    ProviderResponseTooLargeError,
    ProviderUnavailableError,
)
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

_FIRST_RETRY_SECONDS = 60
_RUNNING_LEASE_SECONDS = 900
_GEOMAGNETIC_STORM_KP = 5.0
_SELF_DESCRIBING_ERRORS = (
    ProviderQuotaError,
    ProviderRequestError,
    ProviderResponseTooLargeError,
    ProviderUnavailableError,
)

Job = Callable[[], Awaitable[None]]


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


def _safe_error(exc: BaseException) -> str:
    if isinstance(exc, _SELF_DESCRIBING_ERRORS):
        return f"{type(exc).__name__}: {exc}"[:300]
    return type(exc).__name__


async def _provider_health(provider_id: str, status: str, error: str | None = None) -> None:
    try:
        await _write_provider_health(provider_id, status, error)
    except Exception:
        logger.exception("Failed to record provider health", extra={"provider": provider_id})


async def _write_provider_health(provider_id: str, status: str, error: str | None) -> None:
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


def _retry_delay(consecutive_failures: int, interval_seconds: int) -> float:
    exponential = float(_FIRST_RETRY_SECONDS * 2 ** min(consecutive_failures - 1, 10))
    return min(exponential, interval_seconds) * random.uniform(0.8, 1.2)


async def _acquire_slot(valkey: valkey_async.Valkey, lock_key: str, lease_seconds: int) -> float:
    try:
        if await valkey.set(lock_key, "1", ex=lease_seconds, nx=True):
            return 0.0
        return float(max(await valkey.ttl(lock_key), 5))
    except Exception:
        logger.exception("Scheduler lock store unavailable", extra={"lock": lock_key})
        return float(_FIRST_RETRY_SECONDS)


async def _hold_slot(valkey: valkey_async.Valkey, lock_key: str, seconds: float) -> None:
    try:
        await valkey.set(lock_key, "1", ex=max(int(seconds), 1))
    except Exception:
        logger.exception("Scheduler lock store unavailable", extra={"lock": lock_key})


async def _run_guarded(
    valkey: valkey_async.Valkey,
    provider_id: str | None,
    job_name: str,
    interval_seconds: int,
    job: Job,
) -> None:
    lock_key = f"scheduler:lock:{job_name}"
    consecutive_failures = 0
    while True:
        wait_seconds = await _acquire_slot(valkey, lock_key, _RUNNING_LEASE_SECONDS)
        if wait_seconds:
            await asyncio.sleep(wait_seconds)
            continue
        try:
            await job()
        except Exception as exc:
            consecutive_failures += 1
            error = _safe_error(exc)
            delay = _retry_delay(consecutive_failures, interval_seconds)
            logger.warning(
                "Ingestion job %s failed (%s), attempt %d, retry in %.0f s",
                job_name,
                error,
                consecutive_failures,
                delay,
            )
            if provider_id:
                await _provider_health(provider_id, "error", error)
            await _publish_event(
                "provider.degraded",
                {"provider": provider_id or job_name, "job": job_name, "error": error},
            )
            await _hold_slot(valkey, lock_key, delay)
            await asyncio.sleep(delay)
            continue
        consecutive_failures = 0
        await _hold_slot(valkey, lock_key, interval_seconds)
        logger.info("Ingestion job %s succeeded, next run in %d s", job_name, interval_seconds)
        if provider_id:
            await _provider_health(provider_id, "active")
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
    except CelestrakNotModifiedError:
        logger.info("CelesTrak data unchanged since the previous download")
        return
    finally:
        await client.close()
    if not records:
        raise ProviderUnavailableError("CelesTrak returned no parsable element sets")

    satellites = list(
        {
            record.norad_id: {
                "norad_id": record.norad_id,
                "cospar_id": record.cospar_id,
                "name": record.name,
            }
            for record in records
        }.values()
    )
    elements = [
        {
            "id": uuid4(),
            "norad_id": record.norad_id,
            "epoch": record.epoch,
            "inclination": record.inclination,
            "right_ascension": record.right_ascension,
            "eccentricity": record.eccentricity,
            "argument_of_perigee": record.argument_of_perigee,
            "mean_anomaly": record.mean_anomaly,
            "mean_motion": record.mean_motion,
            "tle_line1": record.tle_line1,
            "tle_line2": record.tle_line2,
            "provider": "celestrak",
        }
        for record in records
    ]
    async with AsyncSessionLocal() as session:
        for batch in _batches(satellites, 1000):
            statement = insert(Satellite).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=["norad_id"],
                set_={
                    "cospar_id": statement.excluded.cospar_id,
                    "name": statement.excluded.name,
                },
            )
            await session.execute(statement)
        for batch in _batches(elements, 1000):
            await session.execute(
                insert(OrbitalElement)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["norad_id", "provider", "epoch"])
            )
        await session.commit()
    logger.info("CelesTrak orbital ingestion complete", extra={"records": len(elements)})
    await _publish_event("object.updated", {"provider": "celestrak", "count": len(elements)})


async def _ingest_space_weather() -> None:
    client = NoaaClient()
    try:
        indices, winds = await asyncio.gather(client.get_planetary_k(), client.get_solar_wind())
    finally:
        await client.close()
    if not indices and not winds:
        raise ProviderUnavailableError("NOAA SWPC returned no valid observations")

    async with AsyncSessionLocal() as session:
        if indices:
            statement = insert(SpaceWeatherIndex).values(
                [
                    {"id": uuid4(), "timestamp": item.timestamp, "kp_index": item.kp_index}
                    for item in indices
                ]
            )
            statement = statement.on_conflict_do_update(
                index_elements=["timestamp"],
                set_={"kp_index": statement.excluded.kp_index},
            )
            await session.execute(statement)
        if winds:
            statement = insert(SolarWind).values(
                [{"id": uuid4(), **asdict(item)} for item in winds]
            )
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
    if indices and indices[-1].kp_index >= _GEOMAGNETIC_STORM_KP:
        await _publish_event(
            "space_weather.alert",
            {"provider": "noaa-swpc", "kp_index": indices[-1].kp_index},
        )


async def _store_close_approaches(
    provider_id: str, objects: Sequence[dict[str, Any]], approaches: Sequence[dict[str, Any]]
) -> None:
    async with AsyncSessionLocal() as session:
        for batch in _batches(list(objects), 1000):
            statement = insert(NearEarthObject).values(batch)
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
        for batch in _batches(list(approaches), 1000):
            statement = insert(CloseApproach).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=["neo_id", "close_approach_date", "orbiting_body"],
                set_={
                    "relative_velocity_kms": statement.excluded.relative_velocity_kms,
                    "miss_distance_au": statement.excluded.miss_distance_au,
                },
            )
            await session.execute(statement)
        await session.commit()
    logger.info("Close-approach ingestion complete", extra={"objects": len(objects)})
    await _publish_event("object.updated", {"provider": provider_id, "count": len(objects)})


async def _ingest_jpl_close_approaches() -> None:
    client = JplClient()
    try:
        records, hazardous, sentry = await asyncio.gather(
            client.get_close_approaches(),
            client.get_hazardous_designations(),
            client.get_sentry_designations(),
        )
    finally:
        await client.close()
    objects = {
        record.designation: {
            "id": record.designation,
            "name": record.name,
            "absolute_magnitude_h": record.absolute_magnitude_h,
            "estimated_diameter_min_km": record.diameter_min_km,
            "estimated_diameter_max_km": record.diameter_max_km,
            "is_potentially_hazardous": record.designation in hazardous,
            "is_sentry_object": record.designation in sentry,
        }
        for record in records
    }
    approaches = list(
        {
            (record.designation, record.approach_at): {
                "id": uuid4(),
                "neo_id": record.designation,
                "close_approach_date": record.approach_at,
                "relative_velocity_kms": record.relative_velocity_kms,
                "miss_distance_au": record.miss_distance_au,
                "orbiting_body": "Earth",
            }
            for record in records
        }.values()
    )
    await _store_close_approaches("jpl-ssd", list(objects.values()), approaches)


async def _ingest_nasa_neos() -> None:
    client = NasaClient()
    today = date.today()
    try:
        payload = await client.get_neo_feed(
            today.isoformat(), (today + timedelta(days=7)).isoformat()
        )
    finally:
        await client.close()

    objects: dict[str, dict[str, Any]] = {}
    approaches: dict[tuple[str, datetime, str], dict[str, Any]] = {}
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
                velocity = _float(
                    approach.get("relative_velocity", {}).get("kilometers_per_second")
                )
                distance = _float(approach.get("miss_distance", {}).get("astronomical"))
                if not timestamp or velocity is None or distance is None:
                    continue
                approach_at = _parse_nasa_datetime(str(timestamp))
                body = approach.get("orbiting_body") or "Earth"
                approaches[(neo_id, approach_at, body)] = {
                    "id": uuid4(),
                    "neo_id": neo_id,
                    "close_approach_date": approach_at,
                    "relative_velocity_kms": velocity,
                    "miss_distance_au": distance,
                    "orbiting_body": body,
                }
    await _store_close_approaches("nasa-neows", list(objects.values()), list(approaches.values()))


async def _fetch_spacedevs_launches() -> list[UpcomingLaunch]:
    client = SpaceDevsClient()
    try:
        return await client.get_upcoming_launches()
    finally:
        await client.close()


async def _fetch_rocketlaunch_launches() -> list[UpcomingLaunch]:
    client = RocketLaunchLiveClient()
    try:
        return await client.get_upcoming_launches()
    finally:
        await client.close()


_LAUNCH_SOURCES: tuple[tuple[str, Callable[[], Awaitable[list[UpcomingLaunch]]]], ...] = (
    ("the-space-devs", _fetch_spacedevs_launches),
    ("rocketlaunch-live", _fetch_rocketlaunch_launches),
)


async def _replace_upcoming_launches(launches: list[UpcomingLaunch]) -> None:
    values = [asdict(launch) for launch in launches]
    async with AsyncSessionLocal() as session:
        statement = insert(Launch).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=["id"],
            set_={
                column: statement.excluded[column]
                for column in values[0]
                if column not in {"id", "provider"}
            },
        )
        await session.execute(statement)
        await session.execute(
            delete(Launch).where(
                Launch.window_start >= datetime.now(UTC),
                Launch.id.not_in([launch.id for launch in launches]),
            )
        )
        await session.commit()


async def _ingest_launches() -> None:
    configured = configured_providers()
    failures: list[str] = []
    for provider_id, fetch in _LAUNCH_SOURCES:
        if provider_id not in configured:
            continue
        try:
            launches = await fetch()
            if not launches:
                raise ProviderUnavailableError(f"{provider_id} returned no upcoming launches")
            await _replace_upcoming_launches(launches)
        except Exception as exc:
            error = _safe_error(exc)
            failures.append(f"{provider_id}: {error}")
            await _provider_health(provider_id, "error", error)
            continue
        await _provider_health(provider_id, "active")
        logger.info(
            "Launch ingestion complete", extra={"provider": provider_id, "records": len(launches)}
        )
        await _publish_event("launch.updated", {"provider": provider_id, "count": len(launches)})
        return
    raise ProviderUnavailableError("; ".join(failures) or "No launch provider is configured")


async def run_scheduler() -> None:
    await connect_nats()
    await ensure_event_stream()
    valkey = valkey_async.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
    providers = configured_providers()
    jobs: list[Coroutine[Any, Any, None]] = []
    if "space-track" in providers:
        jobs.append(_run_guarded(valkey, "space-track", "satcat", 86400, _ingest_satcat))
    if "celestrak" in providers:
        jobs.append(_run_guarded(valkey, "celestrak", "orbital", 7200, _ingest_orbital_elements))
    if "noaa-swpc" in providers:
        jobs.append(_run_guarded(valkey, "noaa-swpc", "space-weather", 300, _ingest_space_weather))
    if "jpl-ssd" in providers:
        jobs.append(
            _run_guarded(valkey, "jpl-ssd", "close-approaches", 21600, _ingest_jpl_close_approaches)
        )
    if "nasa-neows" in providers:
        jobs.append(_run_guarded(valkey, "nasa-neows", "neos", 21600, _ingest_nasa_neos))
    if providers & {provider_id for provider_id, _ in _LAUNCH_SOURCES}:
        jobs.append(_run_guarded(valkey, None, "launches", 1800, _ingest_launches))

    try:
        if not jobs:
            await asyncio.Event().wait()
        async with asyncio.TaskGroup() as group:
            for job in jobs:
                group.create_task(job)
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
        return float(value)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())
