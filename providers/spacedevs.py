from __future__ import annotations

from typing import Any, cast

from core.settings import settings
from providers.launch_records import UpcomingLaunch, bounded_text, coordinate, parse_timestamp
from providers.transport import ProviderTransport

PROVIDER_ID = "the-space-devs"


def parse_spacedevs_launches(payload: dict[str, Any]) -> list[UpcomingLaunch]:
    launches: list[UpcomingLaunch] = []
    for record in payload.get("results") or []:
        if not isinstance(record, dict) or not record.get("id"):
            continue
        window_start = parse_timestamp(record.get("net")) or parse_timestamp(
            record.get("window_start")
        )
        if window_start is None:
            continue
        pad = record.get("pad") or {}
        configuration = (record.get("rocket") or {}).get("configuration") or {}
        operator = (record.get("launch_service_provider") or {}).get("name")
        mission = record.get("mission") or {}
        launches.append(
            UpcomingLaunch(
                id=str(record["id"]),
                name=bounded_text(record.get("name"), 200) or str(record["id"]),
                status=bounded_text((record.get("status") or {}).get("abbrev"), 32),
                window_start=window_start,
                window_end=parse_timestamp(record.get("window_end")),
                provider=PROVIDER_ID,
                operator=bounded_text(operator, 120),
                vehicle=bounded_text(
                    configuration.get("full_name") or configuration.get("name"), 120
                ),
                pad=bounded_text(pad.get("name"), 120),
                location=bounded_text((pad.get("location") or {}).get("name"), 160),
                latitude=coordinate(pad.get("latitude"), 90.0),
                longitude=coordinate(pad.get("longitude"), 180.0),
                mission_description=bounded_text(mission.get("description"), 600),
                weather_summary=None,
                info_url=None,
            )
        )
    return launches


class SpaceDevsClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            PROVIDER_ID,
            "https://ll.thespacedevs.com/2.3.0",
            concurrency=1,
            headers={"Authorization": f"Token {settings.the_space_devs_api_key}"}
            if settings.the_space_devs_api_key
            else None,
        )

    async def get_upcoming_launches(self, limit: int = 30) -> list[UpcomingLaunch]:
        if limit < 1 or limit > 100:
            raise ValueError("Launch query limit must be between 1 and 100")
        params = {"limit": limit, "mode": "normal"}
        return parse_spacedevs_launches(
            cast(dict[str, Any], await self._transport.get_json("/launches/upcoming/", params))
        )

    async def close(self) -> None:
        await self._transport.close()
