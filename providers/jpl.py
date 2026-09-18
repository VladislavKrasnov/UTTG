from typing import Any, cast

from providers.transport import ProviderTransport


class JplHorizonsClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "jpl-horizons",
            "https://ssd.jpl.nasa.gov",
            concurrency=2,
        )

    async def get_ephemeris(
        self,
        target: str,
        start_time: str,
        stop_time: str,
        step_size: str = "1 d",
    ) -> dict[str, Any]:
        if len(target) > 64 or len(start_time) > 64 or len(stop_time) > 64 or len(step_size) > 16:
            raise ValueError("JPL Horizons query parameter exceeds the configured limit")
        return cast(
            dict[str, Any],
            await self._transport.get_json(
                "/api/horizons.api",
                {
                    "format": "json",
                    "COMMAND": f"'{target}'",
                    "OBJ_DATA": "YES",
                    "MAKE_EPHEM": "YES",
                    "EPHEM_TYPE": "VECTORS",
                    "CENTER": "500@399",
                    "START_TIME": start_time,
                    "STOP_TIME": stop_time,
                    "STEP_SIZE": step_size,
                },
            ),
        )

    async def close(self) -> None:
        await self._transport.close()
