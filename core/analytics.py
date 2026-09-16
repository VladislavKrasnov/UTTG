from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.settings import settings
from storage.database import AsyncSessionLocal
from storage.models import EndpointMetricBucket

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[dict[str, Any]] | None = None
_writer_task: asyncio.Task[None] | None = None


def _get_queue() -> asyncio.Queue[dict[str, Any]]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=settings.analytics_queue_size)
    return _queue


async def start_analytics_writer() -> None:
    global _writer_task
    if _writer_task is None or _writer_task.done():
        _writer_task = asyncio.create_task(_writer())


async def stop_analytics_writer() -> None:
    global _writer_task
    if _writer_task is None:
        return
    queue = _get_queue()
    try:
        await asyncio.wait_for(queue.join(), timeout=max(2.0, settings.analytics_flush_seconds * 4))
    except TimeoutError:
        logger.warning(
            "Timed out draining request analytics queue", extra={"pending": queue.qsize()}
        )
    finally:
        _writer_task.cancel()
        try:
            await _writer_task
        except asyncio.CancelledError:
            pass
    _writer_task = None


async def _writer() -> None:
    queue = _get_queue()
    while True:
        first = await queue.get()
        batch = [first]
        deadline = asyncio.get_running_loop().time() + settings.analytics_flush_seconds
        while len(batch) < settings.analytics_batch_size:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                batch.append(await asyncio.wait_for(queue.get(), timeout=remaining))
            except TimeoutError:
                break
        try:
            aggregated = _aggregate(batch)
            async with AsyncSessionLocal() as session:
                statement = insert(EndpointMetricBucket).values(aggregated)
                statement = statement.on_conflict_do_update(
                    index_elements=["bucket", "route", "method"],
                    set_={
                        "request_count": EndpointMetricBucket.request_count
                        + statement.excluded.request_count,
                        "server_error_count": EndpointMetricBucket.server_error_count
                        + statement.excluded.server_error_count,
                        "duration_sum_ms": EndpointMetricBucket.duration_sum_ms
                        + statement.excluded.duration_sum_ms,
                        "duration_max_ms": func.greatest(
                            EndpointMetricBucket.duration_max_ms,
                            statement.excluded.duration_max_ms,
                        ),
                        "response_bytes": EndpointMetricBucket.response_bytes
                        + statement.excluded.response_bytes,
                        "cache_hit_count": EndpointMetricBucket.cache_hit_count
                        + statement.excluded.cache_hit_count,
                    },
                )
                await session.execute(statement)
                await session.commit()
        except Exception:
            logger.exception(
                "Request analytics batch write failed", extra={"batch_size": len(batch)}
            )
        finally:
            for _ in batch:
                queue.task_done()


class RequestAnalyticsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        request_id = _request_id(scope)
        state["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500
        response_bytes = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = getattr(scope.get("route"), "path", scope.get("path", "unknown"))
            metric = {
                "timestamp": datetime.now(UTC),
                "route": str(route)[:255],
                "method": str(scope.get("method", "UNKNOWN"))[:8],
                "status_code": status_code,
                "duration_ms": (time.perf_counter() - started) * 1000,
                "response_bytes": response_bytes,
                "cache_state": state.get("cache_state"),
            }
            try:
                _get_queue().put_nowait(metric)
            except asyncio.QueueFull:
                logger.warning("Request analytics queue full; metric dropped")


def _aggregate(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[datetime, str, str], dict[str, Any]] = {}
    for metric in batch:
        timestamp = metric["timestamp"].replace(second=0, microsecond=0)
        key = (timestamp, metric["route"], metric["method"])
        row = buckets.setdefault(
            key,
            {
                "bucket": timestamp,
                "route": metric["route"],
                "method": metric["method"],
                "request_count": 0,
                "server_error_count": 0,
                "duration_sum_ms": 0.0,
                "duration_max_ms": 0.0,
                "response_bytes": 0,
                "cache_hit_count": 0,
            },
        )
        row["request_count"] += 1
        row["server_error_count"] += int(metric["status_code"] >= 500)
        row["duration_sum_ms"] += metric["duration_ms"]
        row["duration_max_ms"] = max(row["duration_max_ms"], metric["duration_ms"])
        row["response_bytes"] += metric["response_bytes"]
        row["cache_hit_count"] += int(metric.get("cache_state") == "fresh")
    return list(buckets.values())


def _request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            candidate = str(value.decode(errors="ignore"))
            if 1 <= len(candidate) <= 128 and all(
                char.isalnum() or char in "-_." for char in candidate
            ):
                return candidate
    return str(uuid.uuid4())
