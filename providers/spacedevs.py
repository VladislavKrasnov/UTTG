from typing import Any, cast

from providers.transport import ProviderTransport


class SpaceDevsClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "the-space-devs",
            "https://ll.thespacedevs.com/2.2.0",
            concurrency=1,
        )

    async def get_upcoming_launches(self, limit: int = 100) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise ValueError("Launch query limit must be between 1 and 100")
        params = {"limit": limit, "mode": "list"}
        return cast(
            dict[str, Any],
            await self._transport.get_json("/launch/upcoming/", params),
        )

    async def close(self) -> None:
        await self._transport.close()
