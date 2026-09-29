from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from providers.transport import ProviderTransport

PROVIDER_ID = "jpl-ssd"
_DIAMETER_KM_COEFFICIENT = 1329.0
_HIGH_ALBEDO = 0.25
_LOW_ALBEDO = 0.05


@dataclass(frozen=True, slots=True)
class CloseApproachRecord:
    designation: str
    name: str
    approach_at: datetime
    miss_distance_au: float
    relative_velocity_kms: float
    absolute_magnitude_h: float | None
    diameter_min_km: float | None
    diameter_max_km: float | None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _diameter_from_magnitude(magnitude: float, albedo: float) -> float:
    return float(_DIAMETER_KM_COEFFICIENT / math.sqrt(albedo) * 10.0 ** (-magnitude / 5.0))


def parse_close_approaches(payload: dict[str, Any]) -> list[CloseApproachRecord]:
    fields = payload.get("fields") or []
    if not isinstance(fields, list):
        return []
    column = {name: index for index, name in enumerate(fields)}
    required = {"des", "cd", "dist", "v_rel"}
    if not required <= column.keys():
        return []
    records: list[CloseApproachRecord] = []
    for row in payload.get("data") or []:
        if not isinstance(row, list) or len(row) < len(fields):
            continue
        designation = str(row[column["des"]]).strip()[:64]
        distance = _number(row[column["dist"]])
        velocity = _number(row[column["v_rel"]])
        try:
            approach_at = datetime.strptime(str(row[column["cd"]]), "%Y-%b-%d %H:%M").replace(
                tzinfo=UTC
            )
        except ValueError:
            continue
        if not designation or distance is None or velocity is None:
            continue
        magnitude = _number(row[column["h"]]) if "h" in column else None
        measured = _number(row[column["diameter"]]) if "diameter" in column else None
        diameter_min: float | None
        diameter_max: float | None
        if measured is not None:
            diameter_min = diameter_max = measured
        elif magnitude is not None:
            diameter_min = _diameter_from_magnitude(magnitude, _HIGH_ALBEDO)
            diameter_max = _diameter_from_magnitude(magnitude, _LOW_ALBEDO)
        else:
            diameter_min = diameter_max = None
        name = str(row[column["fullname"]]).strip() if "fullname" in column else designation
        records.append(
            CloseApproachRecord(
                designation=designation,
                name=name[:128] or designation,
                approach_at=approach_at,
                miss_distance_au=distance,
                relative_velocity_kms=velocity,
                absolute_magnitude_h=magnitude,
                diameter_min_km=diameter_min,
                diameter_max_km=diameter_max,
            )
        )
    return records


def parse_designations(payload: dict[str, Any], key: str) -> frozenset[str]:
    data = payload.get("data") or []
    if data and isinstance(data[0], dict):
        return frozenset(str(item[key]).strip() for item in data if item.get(key))
    fields = payload.get("fields") or []
    if key not in fields:
        return frozenset()
    index = fields.index(key)
    return frozenset(str(row[index]).strip() for row in data if isinstance(row, list))


class JplClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            PROVIDER_ID,
            "https://ssd-api.jpl.nasa.gov",
            concurrency=1,
            maximum_response_bytes=4_000_000,
        )

    async def get_close_approaches(
        self, days: int = 30, maximum_distance_au: float = 0.05
    ) -> list[CloseApproachRecord]:
        if not 1 <= days <= 365 or not 0 < maximum_distance_au <= 0.5:
            raise ValueError("Unsupported close-approach window")
        return parse_close_approaches(
            cast(
                dict[str, Any],
                await self._transport.get_json(
                    "/cad.api",
                    {
                        "date-min": "now",
                        "date-max": f"+{days}",
                        "dist-max": str(maximum_distance_au),
                        "diameter": "true",
                        "fullname": "true",
                    },
                ),
            )
        )

    async def get_hazardous_designations(
        self, days: int = 30, maximum_distance_au: float = 0.05
    ) -> frozenset[str]:
        payload = await self._transport.get_json(
            "/cad.api",
            {
                "date-min": "now",
                "date-max": f"+{days}",
                "dist-max": str(maximum_distance_au),
                "pha": "true",
            },
        )
        return parse_designations(cast(dict[str, Any], payload), "des")

    async def get_sentry_designations(self) -> frozenset[str]:
        payload = await self._transport.get_json("/sentry.api")
        return parse_designations(cast(dict[str, Any], payload), "des")

    async def close(self) -> None:
        await self._transport.close()
