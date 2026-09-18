from __future__ import annotations

import logging
import time
from typing import Any, cast

import httpx
import valkey.asyncio as valkey_async

from core.settings import settings

logger = logging.getLogger(__name__)

_vc: valkey_async.Valkey | None = None


def _get_valkey() -> valkey_async.Valkey:
    global _vc
    if _vc is None:
        _vc = valkey_async.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
    return _vc


class SpaceTrackClient:
    """
    Space-Track.org API client.

    Hard quotas per Terms of Service (https://www.space-track.org/documentation):
    - Global: < 30 requests/minute, < 300 requests/hour
    - GP (TLE per object): 1/hour
    - SATCAT (per object): 1/day
    - Boxscore: 1/day after 17:00 UTC
    - 60-day Decay: 1/week on Wednesdays after 17:00 UTC
    All limits are enforced locally via Valkey atomic counters before any HTTP call.
    """

    _BASE = "https://www.space-track.org"
    _LOGIN = "/ajaxauth/login"
    _QUERY = "/basicspacedata/query"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._BASE,
            timeout=30.0,
            follow_redirects=False,
            trust_env=False,
        )
        self._authenticated = False

    async def _guard_global(self) -> None:
        vc = _get_valkey()
        min_key = f"upstream:spacetrack:global:min:{int(time.time() // 60)}"
        hr_key = f"upstream:spacetrack:global:hr:{int(time.time() // 3600)}"

        min_cnt = await vc.incr(min_key)
        if min_cnt == 1:
            await vc.expire(min_key, 120)
        hr_cnt = await vc.incr(hr_key)
        if hr_cnt == 1:
            await vc.expire(hr_key, 7200)

        if min_cnt > 29 or hr_cnt > 299:
            raise RuntimeError("Space-Track upstream budget exhausted (30/min, 300/hr)")

    async def _authenticate(self) -> None:
        if not settings.space_track_identity or not settings.space_track_password:
            raise ValueError("UTTG_SPACE_TRACK_IDENTITY / UTTG_SPACE_TRACK_PASSWORD not set")
        await self._guard_global()
        resp = await self._client.post(
            self._LOGIN,
            data={
                "identity": settings.space_track_identity,
                "password": settings.space_track_password,
            },
        )
        resp.raise_for_status()
        self._authenticated = True

    async def _get(self, path: str) -> list[dict[str, Any]]:
        if not self._authenticated:
            await self._authenticate()
        await self._guard_global()
        resp = await self._client.get(self._QUERY + path)
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    async def get_gp(self, norad_id: int) -> list[dict[str, Any]]:
        vc = _get_valkey()
        lock = f"upstream:spacetrack:gp:{norad_id}"
        if await vc.get(lock):
            raise RuntimeError(f"GP cooldown active for NORAD {norad_id} (1/hr)")
        result = await self._get(
            f"/class/gp/NORAD_CAT_ID/{norad_id}/decay_date/null-val/epoch/>now-10/orderby/EPOCH%20desc/limit/1/format/json"
        )
        await vc.set(lock, "1", ex=3600)
        return result

    async def get_satcat(self) -> list[dict[str, Any]]:
        vc = _get_valkey()
        lock = "upstream:spacetrack:satcat:daily"
        if await vc.get(lock):
            raise RuntimeError("SATCAT cooldown active (1/day)")
        result = await self._get("/class/satcat/orderby/NORAD_CAT_ID/format/json")
        await vc.set(lock, "1", ex=86400)
        return result

    async def get_decay(self) -> list[dict[str, Any]]:
        vc = _get_valkey()
        lock = "upstream:spacetrack:decay:weekly"
        if await vc.get(lock):
            raise RuntimeError("Decay cooldown active (1/week)")
        result = await self._get("/class/decay/MSG_EPOCH/>now-8/source/60day_msg/format/json")
        await vc.set(lock, "1", ex=604800)
        return result

    async def close(self) -> None:
        await self._client.aclose()
