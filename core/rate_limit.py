from __future__ import annotations

import time
from collections.abc import Awaitable
from typing import Any, cast

import valkey.asyncio as valkey_async
from fastapi import Depends, HTTPException, Request

from core.security import get_current_client
from core.settings import settings

_LUA_FIXED_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, ttl)
end
if count > limit then return {-1, limit} end
return {limit - count, limit}
"""

_QUOTAS: dict[str, int] = {
    "public_light": 600,
    "public_standard": 240,
    "public_expensive": 60,
    "mutation": 30,
}

_valkey: valkey_async.Valkey | None = None


def _get_valkey() -> valkey_async.Valkey:
    global _valkey
    if _valkey is None:
        _valkey = valkey_async.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
    return _valkey


class RateLimiter:
    __slots__ = ("limit_class",)

    def __init__(self, limit_class: str = "public_light") -> None:
        if limit_class not in _QUOTAS:
            raise ValueError(f"Unknown rate-limit class: {limit_class}")
        self.limit_class = limit_class

    async def __call__(
        self,
        request: Request,
        client: dict[str, str] = Depends(get_current_client),
    ) -> None:
        quota = _QUOTAS[self.limit_class]
        window_seconds = 60
        window = int(time.time() // window_seconds)
        # A single counter per IP/class/minute is O(1) in Valkey, unlike a
        # sorted-set sliding window which stores one item per request.
        key = f"rl:{self.limit_class}:{client['id']}:{window}"
        try:
            operation = cast(
                Awaitable[Any],
                _get_valkey().eval(
                    _LUA_FIXED_WINDOW,
                    1,
                    key,
                    str(quota),
                    str(window_seconds),
                ),
            )
            remaining, limit_value = await operation
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc

        remaining = int(remaining)
        limit_value = int(limit_value)
        reset_at = int(time.time()) + window_seconds
        request.state.rl_limit = limit_value
        request.state.rl_remaining = max(remaining, 0)
        request.state.rl_reset = reset_at

        if remaining < 0:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(window_seconds),
                    "RateLimit-Limit": str(limit_value),
                    "RateLimit-Remaining": "0",
                    "RateLimit-Reset": str(reset_at),
                },
            )
