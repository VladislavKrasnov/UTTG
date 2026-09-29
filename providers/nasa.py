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

    async def close(self) -> None:
        await self._transport.close()
