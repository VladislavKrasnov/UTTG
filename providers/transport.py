from __future__ import annotations

import asyncio
from typing import Any

import httpx
import valkey.asyncio as valkey_async

from core.settings import settings


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderResponseTooLargeError(RuntimeError):
    pass


class ProviderQuotaError(RuntimeError):
    pass


class ProviderRequestError(RuntimeError):
    pass


class ProviderTransport:
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        concurrency: int = 4,
        maximum_response_bytes: int = 8_000_000,
    ) -> None:
        self.provider_id = provider_id
        self.maximum_response_bytes = maximum_response_bytes
        self._semaphore = asyncio.Semaphore(concurrency)
        self._valkey = valkey_async.from_url(  # type: ignore[no-untyped-call]
            settings.valkey_url
        )
        self._client = httpx.AsyncClient(
            base_url=base_url,
            proxy=settings.http_proxy,
            timeout=httpx.Timeout(30.0, connect=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            headers={"User-Agent": "UTTG/0.1 (+https://github.com/VladislavKrasnov/UTTG)"},
            follow_redirects=False,
            trust_env=False,
        )
        self._direct_client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(30.0, connect=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            headers={"User-Agent": "UTTG/0.1 (+https://github.com/VladislavKrasnov/UTTG)"},
            follow_redirects=False,
            trust_env=False,
        ) if settings.http_proxy else self._client

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        circuit_key = f"provider:{self.provider_id}:circuit-open"
        if await self._circuit_is_open(circuit_key):
            raise ProviderUnavailableError(f"Provider circuit is open: {self.provider_id}")

        async with self._semaphore:
            for attempt in range(3):
                try:
                    payload = await self._read_json(path, params)
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
                    await asyncio.sleep(0.2 * (2**attempt))
        raise ProviderUnavailableError(f"Provider request failed: {self.provider_id}")

    async def _read_json(self, path: str, params: dict[str, Any] | None) -> Any:
        try:
            return await self._read_json_with_client(self._client, path, params)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if self._client is not self._direct_client:
                return await self._read_json_with_client(self._direct_client, path, params)
            raise

    async def _read_json_with_client(self, client: httpx.AsyncClient, path: str, params: dict[str, Any] | None) -> Any:
        async with client.stream("GET", path, params=params) as response:
            if response.status_code == 429:
                await self._record_failure()
                raise ProviderQuotaError(f"Provider quota exceeded: {self.provider_id}")
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    f"Provider temporarily failed: {self.provider_id} ({response.status_code})"
                )
            if response.status_code >= 400:
                raise ProviderRequestError(
                    f"Provider rejected request: {self.provider_id} ({response.status_code})"
                )
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > self.maximum_response_bytes:
                raise ProviderResponseTooLargeError(self.provider_id)
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > self.maximum_response_bytes:
                    raise ProviderResponseTooLargeError(self.provider_id)
                chunks.append(chunk)
        return httpx.Response(200, content=b"".join(chunks)).json()

    async def _record_failure(self) -> None:
        try:
            key = f"provider:{self.provider_id}:failures"
            failures = await self._valkey.incr(key)
            if failures == 1:
                await self._valkey.expire(key, 60)
            if failures >= 5:
                await self._valkey.set(f"provider:{self.provider_id}:circuit-open", "1", ex=30)
        except Exception:
            # Circuit state is an optimization. Ingestion must still report the
            # original provider failure when Valkey is temporarily unavailable.
            return

    async def _clear_failures(self) -> None:
        try:
            await self._valkey.delete(f"provider:{self.provider_id}:failures")
        except Exception:
            return

    async def _circuit_is_open(self, key: str) -> bool:
        try:
            return bool(await self._valkey.exists(key))
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
        if self._direct_client is not self._client:
            await self._direct_client.aclose()
        await self._valkey.aclose()
