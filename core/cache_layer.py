from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

import valkey.asyncio as valkey_async

from core.settings import settings

_READ_LUA = """
local lock_key = KEYS[1]
local data_key = KEYS[2]
local ttl = tonumber(ARGV[1])
local stale = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local token = ARGV[4]
local value = redis.call('HGET', data_key, 'v')
local stored_at = tonumber(redis.call('HGET', data_key, 't'))
if stored_at then
    local age = now - stored_at
    if age <= ttl then
        return {value, tostring(age), 'fresh'}
    end
    if age <= stale then
        if redis.call('SET', lock_key, token, 'NX', 'EX', 15) then
            return {value, tostring(age), 'revalidate'}
        end
        return {value, tostring(age), 'stale'}
    end
end
if redis.call('SET', lock_key, token, 'NX', 'EX', 15) then
    return {false, '0', 'miss_leader'}
end
return {false, '0', 'miss_wait'}
"""

_STORE_LUA = """
local data_key = KEYS[1]
local lock_key = KEYS[2]
local token = ARGV[1]
local value = ARGV[2]
local now = ARGV[3]
local stale = tonumber(ARGV[4])
if redis.call('GET', lock_key) ~= token then
    return 0
end
redis.call('HSET', data_key, 'v', value, 't', now)
redis.call('EXPIRE', data_key, stale)
redis.call('DEL', lock_key)
return 1
"""

_UNLOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_valkey: valkey_async.Valkey | None = None
_background_tasks: set[asyncio.Task[Any]] = set()


class CacheBusyError(RuntimeError):
    pass


class CacheValueTooLargeError(RuntimeError):
    pass


def _get_valkey() -> valkey_async.Valkey:
    global _valkey
    if _valkey is None:
        _valkey = valkey_async.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
    return _valkey


async def _eval(client: valkey_async.Valkey, *args: Any) -> Any:
    """Bridge Valkey's sync/async union stubs to the async client used here."""
    operation = cast(Awaitable[Any], client.eval(*args))
    return await operation


async def _hget(client: valkey_async.Valkey, key: str, field: str) -> Any:
    operation = cast(Awaitable[Any], client.hget(key, field))
    return await operation


async def cached(
    cache_key: str,
    compute: Callable[[], Awaitable[Any]],
    ttl: int = 60,
    stale: int = 300,
) -> tuple[Any, str, int]:
    if ttl <= 0 or stale < ttl:
        raise ValueError("Cache stale duration must be greater than or equal to TTL")

    valkey = _get_valkey()
    data_key = f"cache:v1:{cache_key}"
    lock_key = f"cache:v1:lock:{cache_key}"
    token = uuid.uuid4().hex
    now = int(time.time())
    result = await _eval(
        valkey, _READ_LUA, 2, lock_key, data_key, str(ttl), str(stale), str(now), token
    )
    raw_value, raw_age, raw_state = result
    state = raw_state.decode() if isinstance(raw_state, bytes) else str(raw_state)
    age = int(raw_age)

    if raw_value is not None:
        value = json.loads(raw_value.decode() if isinstance(raw_value, bytes) else raw_value)
        if state == "revalidate":
            _schedule_refresh(valkey, compute, data_key, lock_key, token, stale)
        return value, "fresh" if state == "fresh" else "stale", age

    if state == "miss_wait":
        deadline = asyncio.get_running_loop().time() + settings.cache_wait_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.025)
            raw_value = await _hget(valkey, data_key, "v")
            if raw_value is not None:
                value = json.loads(
                    raw_value.decode() if isinstance(raw_value, bytes) else raw_value
                )
                return value, "fresh", 0
        raise CacheBusyError("Cache fill is still in progress")

    return await _compute_and_store(valkey, compute, data_key, lock_key, token, stale)


def _schedule_refresh(
    valkey: valkey_async.Valkey,
    compute: Callable[[], Awaitable[Any]],
    data_key: str,
    lock_key: str,
    token: str,
    stale: int,
) -> None:
    if len(_background_tasks) >= settings.cache_background_refresh_limit:
        task: asyncio.Task[Any] = asyncio.create_task(
            _eval(valkey, _UNLOCK_LUA, 1, lock_key, token)
        )
    else:
        task = asyncio.create_task(
            _compute_and_store(valkey, compute, data_key, lock_key, token, stale)
        )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _compute_and_store(
    valkey: valkey_async.Valkey,
    compute: Callable[[], Awaitable[Any]],
    data_key: str,
    lock_key: str,
    token: str,
    stale: int,
) -> tuple[Any, str, int]:
    try:
        value = await asyncio.wait_for(
            compute(),
            timeout=settings.cache_compute_timeout_seconds,
        )
        serialized = json.dumps(value, default=str, separators=(",", ":"))
        if len(serialized.encode()) > settings.cache_max_value_bytes:
            raise CacheValueTooLargeError("Response exceeds the configured cache value limit")
        await _eval(
            valkey,
            _STORE_LUA,
            2,
            data_key,
            lock_key,
            token,
            serialized,
            str(int(time.time())),
            str(stale),
        )
        return value, "fresh", 0
    except Exception:
        await _eval(valkey, _UNLOCK_LUA, 1, lock_key, token)
        raise


async def invalidate(cache_key: str) -> None:
    await _get_valkey().delete(f"cache:v1:{cache_key}", f"cache:v1:lock:{cache_key}")
