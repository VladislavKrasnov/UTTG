from typing import Any, cast

from providers.transport import ProviderTransport


class NoaaClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "noaa-swpc",
            "https://services.swpc.noaa.gov/json",
            concurrency=2,
        )

    async def get_planetary_k(self) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            await self._transport.get_json("/planetary_k_index_1m.json"),
        )

    async def get_solar_wind(self) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            await self._transport.get_json("/rtsw/rtsw_wind_1m.json"),
        )

    async def get_alerts(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], await self._transport.get_json("/alerts.json"))

    async def get_solar_flares(self) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            await self._transport.get_json("/goes/primary/xrays-7-day.json"),
        )

    async def close(self) -> None:
        await self._transport.close()
