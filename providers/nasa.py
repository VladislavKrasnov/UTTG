from typing import Any, cast

from core.settings import settings
from providers.transport import ProviderTransport


class NasaClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "nasa-neows",
            "https://api.nasa.gov/neo/rest/v1",
            concurrency=4,
        )

    async def get_neo_feed(self, start_date: str, end_date: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._transport.get_json(
                "/feed",
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "api_key": settings.nasa_api_key,
                },
            ),
        )

    async def get_neo_lookup(self, asteroid_id: str) -> dict[str, Any]:
        if not asteroid_id.isdigit() or len(asteroid_id) > 32:
            raise ValueError("Invalid NASA asteroid identifier")
        return cast(
            dict[str, Any],
            await self._transport.get_json(
                f"/neo/{asteroid_id}",
                {"api_key": settings.nasa_api_key},
            ),
        )

    async def close(self) -> None:
        await self._transport.close()
