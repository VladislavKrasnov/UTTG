from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from api.routers import (
    admin,
    earth_observation,
    events,
    insights,
    launch,
    neo,
    orbital,
    platform_router,
    satellite,
    space_weather,
    webhooks,
)
from core.analytics import (
    RequestAnalyticsMiddleware,
    start_analytics_writer,
    stop_analytics_writer,
)
from core.capabilities import require_capability
from core.errors import install_error_handlers
from core.http import RequestBodyLimitMiddleware, SecurityHeadersMiddleware
from core.metrics import PrometheusMiddleware
from core.metrics import router as metrics_router
from core.openapi import custom_openapi
from core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await start_analytics_writer()
    try:
        yield
    finally:
        await stop_analytics_writer()


app = FastAPI(
    title="Unified Technical Telemetry Gateway (UTTG)",
    description="High-load REST API gateway for lawful public and user-authorized space telemetry.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
    default_response_class=ORJSONResponse,
)

app.include_router(metrics_router)
install_error_handlers(app)

app.openapi = lambda: custom_openapi(app)  # type: ignore[method-assign]

app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestAnalyticsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestBodyLimitMiddleware, maximum_bytes=settings.request_body_max_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "Idempotency-Key", "X-Request-Id"],
)

app.include_router(platform_router.router, prefix="/v1")
# Static insight paths must be registered before dynamic identifiers such as
# /launches/{launch_id} and /neos/{neo_id}.
app.include_router(insights.router, prefix="/v1")
app.include_router(
    satellite.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Satellite"))],
)
app.include_router(
    orbital.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Orbital"))],
)
app.include_router(
    launch.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Launch"))],
)
app.include_router(
    space_weather.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Space Weather"))],
)
app.include_router(
    neo.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Neo"))],
)
app.include_router(
    events.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Events"))],
)
app.include_router(
    earth_observation.router,
    prefix="/v1",
    dependencies=[Depends(require_capability("Earth Observation"))],
)
app.include_router(webhooks.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")

FastAPIInstrumentor.instrument_app(app)
