from __future__ import annotations

import asyncio
from typing import Any

import httpx
import orjson
import valkey.asyncio as valkey_async

from core.settings import settings

_USER_AGENT = "UTTG/0.2 (+https://github.com/VladislavKrasnov/UTTG)"
_CIRCUIT_FAILURE_THRESHOLD = 5
_CIRCUIT_FAILURE_WINDOW_SECONDS = 300
_CIRCUIT_OPEN_SECONDS = 600


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderResponseTooLargeError(RuntimeError):
    pass


class ProviderQuotaError(RuntimeError):
    pass


class ProviderRequestError(RuntimeError):
    pass


def _build_client(
    base_url: str, concurrency: int, proxy: str | None, headers: dict[str, str]
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        proxy=proxy,
        timeout=httpx.Timeout(60.0, connect=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
        headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "gzip", **headers},
        follow_redirects=False,
        trust_env=False,
    )


class ProviderTransport:
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        concurrency: int = 4,
        maximum_response_bytes: int = 8_000_000,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.maximum_response_bytes = maximum_response_bytes
        self._semaphore = asyncio.Semaphore(concurrency)
        self._valkey = valkey_async.from_url(  # type: ignore[no-untyped-call]
            settings.valkey_url
        )
        extra_headers = headers or {}
        self._clients = [_build_client(base_url, concurrency, None, extra_headers)]
        if settings.http_proxy:
            self._clients.insert(
                0, _build_client(base_url, concurrency, settings.http_proxy, extra_headers)
            )

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return orjson.loads(await self.get_bytes(path, params))

    async def get_text(self, path: str, params: dict[str, Any] | None = None) -> str:
        return (await self.get_bytes(path, params)).decode("utf-8", errors="replace")

    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        if await self._circuit_is_open():
            raise ProviderUnavailableError(f"Provider circuit is open: {self.provider_id}")

        async with self._semaphore:
            for attempt in range(3):
                try:
                    payload = await self._read_with_fallback(path, params)
                    await self._clear_failures()
                    return payload
                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                    ProviderUnavailableError,
                ):
                    if attempt == 2:
                        await self._record_failure()
                        raise
                    await asyncio.sleep(0.5 * (2**attempt))
                except (ProviderQuotaError, ProviderRequestError):
                    await self._record_failure()
                    raise
        raise ProviderUnavailableError(f"Provider request failed: {self.provider_id}")

    async def _read_with_fallback(self, path: str, params: dict[str, Any] | None) -> bytes:
        last_client = self._clients[-1]
        for client in self._clients:
            try:
                return await self._read(client, path, params)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError):
                if client is last_client:
                    raise
        raise ProviderUnavailableError(f"No transport configured: {self.provider_id}")

    async def _read(
        self, client: httpx.AsyncClient, path: str, params: dict[str, Any] | None
    ) -> bytes:
        async with client.stream("GET", path, params=params) as response:
            status = response.status_code
            if status == 429:
                raise ProviderQuotaError(f"Provider quota exceeded: {self.provider_id}")
            if status >= 500:
                raise ProviderUnavailableError(
                    f"Provider temporarily failed: {self.provider_id} ({status})"
                )
            if status >= 400:
                raise ProviderRequestError(
                    f"Provider rejected request: {self.provider_id} ({status})"
                )
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > self.maximum_response_bytes:
                raise ProviderResponseTooLargeError(self.provider_id)
            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                buffer += chunk
                if len(buffer) > self.maximum_response_bytes:
                    raise ProviderResponseTooLargeError(self.provider_id)
        return bytes(buffer)

    async def _record_failure(self) -> None:
        try:
            key = f"provider:{self.provider_id}:failures"
            failures = await self._valkey.incr(key)
            if failures == 1:
                await self._valkey.expire(key, _CIRCUIT_FAILURE_WINDOW_SECONDS)
            if failures >= _CIRCUIT_FAILURE_THRESHOLD:
                await self._valkey.set(
                    f"provider:{self.provider_id}:circuit-open", "1", ex=_CIRCUIT_OPEN_SECONDS
                )
        except Exception:
            # Circuit state is an optimization. Ingestion must still report the
            # original provider failure when Valkey is temporarily unavailable.
            return

    async def _clear_failures(self) -> None:
        try:
            await self._valkey.delete(f"provider:{self.provider_id}:failures")
        except Exception:
            return

    async def _circuit_is_open(self) -> bool:
        try:
            return bool(await self._valkey.exists(f"provider:{self.provider_id}:circuit-open"))
        except Exception:
            return False

    async def close(self) -> None:
        for client in self._clients:
            await client.aclose()
        await self._valkey.aclose()
