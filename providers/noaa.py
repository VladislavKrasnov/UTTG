from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from providers.transport import ProviderTransport

_OBSERVATION_LOOKBACK = timedelta(hours=3)


@dataclass(frozen=True, slots=True)
class GeomagneticObservation:
    timestamp: datetime
    kp_index: float


@dataclass(frozen=True, slots=True)
class SolarWindObservation:
    timestamp: datetime
    speed_km_s: float
    density_cm3: float
    temperature_k: float


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _recent(observed_at: datetime, newest: datetime) -> bool:
    return newest - observed_at <= _OBSERVATION_LOOKBACK


def parse_planetary_k(records: list[dict[str, Any]]) -> list[GeomagneticObservation]:
    parsed: dict[datetime, GeomagneticObservation] = {}
    for record in records:
        observed_at = _timestamp(record.get("time_tag"))
        kp = _finite(record.get("estimated_kp"))
        if kp is None:
            kp = _finite(record.get("kp_index"))
        if observed_at is None or kp is None or not 0.0 <= kp <= 9.0:
            continue
        parsed[observed_at] = GeomagneticObservation(observed_at, round(kp, 2))
    if len(parsed) < 2:
        return []
    parsed.pop(max(parsed))
    newest = max(parsed)
    return [item for at, item in sorted(parsed.items()) if _recent(at, newest)]


def parse_solar_wind(records: list[dict[str, Any]]) -> list[SolarWindObservation]:
    parsed: dict[datetime, SolarWindObservation] = {}
    for record in records:
        if record.get("active") is False:
            continue
        observed_at = _timestamp(record.get("time_tag"))
        speed = _finite(record.get("proton_speed"))
        density = _finite(record.get("proton_density"))
        temperature = _finite(record.get("proton_temperature"))
        if observed_at is None or speed is None or density is None or temperature is None:
            continue
        if not 100.0 <= speed <= 3000.0 or density < 0.0 or temperature < 0.0:
            continue
        parsed[observed_at] = SolarWindObservation(observed_at, speed, density, temperature)
    if not parsed:
        return []
    newest = max(parsed)
    return [item for at, item in sorted(parsed.items()) if _recent(at, newest)]


class NoaaClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "noaa-swpc",
            "https://services.swpc.noaa.gov/json",
            concurrency=2,
        )

    async def get_planetary_k(self) -> list[GeomagneticObservation]:
        return parse_planetary_k(
            cast(list[dict[str, Any]], await self._transport.get_json("/planetary_k_index_1m.json"))
        )

    async def get_solar_wind(self) -> list[SolarWindObservation]:
        return parse_solar_wind(
            cast(list[dict[str, Any]], await self._transport.get_json("/rtsw/rtsw_wind_1m.json"))
        )

    async def close(self) -> None:
        await self._transport.close()
