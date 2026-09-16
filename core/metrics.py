from __future__ import annotations

import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

router = APIRouter()

REQUEST_COUNT = Counter(
    "uttg_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "uttg_request_latency_seconds",
    "Request latency seconds",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
CACHE_HIT = Counter("uttg_cache_hits_total", "Cache hits", ["endpoint"])
CACHE_MISS = Counter("uttg_cache_misses_total", "Cache misses", ["endpoint"])
ACTIVE_REQUESTS = Gauge("uttg_active_requests", "Active requests in flight")


class PrometheusMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ACTIVE_REQUESTS.inc()
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                state = scope.get("state", {})
                headers = list(message.get("headers", []))
                if "rl_limit" in state:
                    headers.extend(
                        [
                            (b"ratelimit-limit", str(state["rl_limit"]).encode()),
                            (b"ratelimit-remaining", str(state["rl_remaining"]).encode()),
                            (b"ratelimit-reset", str(state["rl_reset"]).encode()),
                        ]
                    )
                if state.get("cache_state"):
                    headers.append((b"x-cache-state", str(state["cache_state"]).encode()))
                headers.append(
                    (
                        b"x-response-time-ms",
                        str(round((time.perf_counter() - started) * 1000, 2)).encode(),
                    )
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            route = str(getattr(scope.get("route"), "path", scope.get("path", "unknown")))
            method = str(scope.get("method", "UNKNOWN"))
            REQUEST_COUNT.labels(method=method, endpoint=route, status=status_code).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=route).observe(elapsed)
            cache_state = scope.get("state", {}).get("cache_state")
            if cache_state == "fresh":
                CACHE_HIT.labels(endpoint=route).inc()
            elif cache_state:
                CACHE_MISS.labels(endpoint=route).inc()
            ACTIVE_REQUESTS.dec()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
