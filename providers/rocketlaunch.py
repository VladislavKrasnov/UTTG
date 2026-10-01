from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from providers.launch_records import (
    UpcomingLaunch,
    bounded_text,
    known_site_coordinates,
    parse_timestamp,
)
from providers.transport import ProviderTransport

PROVIDER_ID = "rocketlaunch-live"
_MILES_PER_HOUR_TO_METRES_PER_SECOND = 0.44704


def _weather_summary(record: dict[str, Any]) -> str | None:
    condition = bounded_text(record.get("weather_condition"), 64)
    parts = [condition] if condition else []
    try:
        fahrenheit = float(record.get("weather_temp") or "")
        parts.append(f"{round((fahrenheit - 32.0) * 5.0 / 9.0)} °C")
    except ValueError:
        pass
    try:
        wind_mph = float(record.get("weather_wind_mph") or "")
        parts.append(f"wind {round(wind_mph * _MILES_PER_HOUR_TO_METRES_PER_SECOND)} m/s")
    except ValueError:
        pass
    return " · ".join(parts) or None


def _window_start(record: dict[str, Any]) -> tuple[datetime | None, bool]:
    exact = parse_timestamp(record.get("t0")) or parse_timestamp(record.get("win_open"))
    if exact:
        return exact, True
    try:
        return datetime.fromtimestamp(int(record.get("sort_date") or ""), UTC), False
    except (TypeError, ValueError, OverflowError):
        return None, False


def parse_rocketlaunch_launches(payload: dict[str, Any]) -> list[UpcomingLaunch]:
    launches: list[UpcomingLaunch] = []
    for record in payload.get("result") or []:
        if not isinstance(record, dict) or record.get("id") is None:
            continue
        window_start, exact = _window_start(record)
        if window_start is None:
            continue
        pad = record.get("pad") or {}
        location_record = pad.get("location") or {}
        location = bounded_text(
            ", ".join(
                part
                for part in (location_record.get("name"), location_record.get("country"))
                if isinstance(part, str) and part
            ),
            160,
        )
        latitude, longitude = known_site_coordinates(location)
        slug = record.get("slug")
        launches.append(
            UpcomingLaunch(
                id=f"rll-{record['id']}",
                name=bounded_text(record.get("name"), 200) or str(record["id"]),
                status="Scheduled" if exact else "TBD",
                window_start=window_start,
                window_end=parse_timestamp(record.get("win_close")),
                provider=PROVIDER_ID,
                operator=bounded_text((record.get("provider") or {}).get("name"), 120),
                vehicle=bounded_text((record.get("vehicle") or {}).get("name"), 120),
                pad=bounded_text(pad.get("name"), 120),
                location=location,
                latitude=latitude,
                longitude=longitude,
                mission_description=bounded_text(
                    record.get("mission_description") or record.get("launch_description"), 600
                ),
                weather_summary=_weather_summary(record),
                info_url=f"https://www.rocketlaunch.live/launch/{slug}"
                if isinstance(slug, str) and slug.replace("-", "").isalnum()
                else None,
            )
        )
    return launches


class RocketLaunchLiveClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            PROVIDER_ID,
            "https://fdo.rocketlaunch.live",
            concurrency=1,
            maximum_response_bytes=1_000_000,
        )

    async def get_upcoming_launches(self) -> list[UpcomingLaunch]:
        return parse_rocketlaunch_launches(
            cast(dict[str, Any], await self._transport.get_json("/json/launches/next/5"))
        )

    async def close(self) -> None:
        await self._transport.close()
