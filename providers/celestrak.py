from typing import Any, cast

from providers.transport import ProviderTransport


class CelestrakClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "celestrak",
            "https://celestrak.org",
            concurrency=2,
        )

    async def get_gp(self, catalog_number: int) -> list[dict[str, Any]]:
        if catalog_number <= 0 or catalog_number > 99_999_999:
            raise ValueError("Invalid NORAD catalog number")
        return cast(
            list[dict[str, Any]],
            await self._transport.get_json(
                "/NORAD/elements/gp.php",
                {"CATNR": catalog_number, "FORMAT": "JSON"},
            ),
        )

    async def get_group(self, group: str = "active") -> list[dict[str, Any]]:
        allowed_groups = {"active", "stations", "weather", "resource", "last-30-days"}
        if group not in allowed_groups:
            raise ValueError("Unsupported CelesTrak group")
        return cast(
            list[dict[str, Any]],
            await self._transport.get_json(
                "/NORAD/elements/gp.php",
                {"GROUP": group, "FORMAT": "JSON"},
            ),
        )

    async def close(self) -> None:
        await self._transport.close()
