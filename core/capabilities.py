from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException

from core.settings import settings

_TAG_PROVIDERS: dict[str, tuple[str, ...]] = {
    "Satellite": ("space-track", "celestrak"),
    "Orbital": ("space-track", "celestrak"),
    "Neo": ("nasa-neows",),
    "Space Weather": ("noaa-swpc",),
    "Launch": ("the-space-devs",),
    "Events": ("space-track",),
    "Earth Observation": ("esa",),
}

_UNAVAILABLE_PATHS: frozenset[str] = frozenset(
    {
        "/v1/satellites/{norad_id}/passes",
        "/v1/catalog/changes",
        "/v1/missions/{mission_id}",
        "/v1/launch-vehicles",
        "/v1/launch-sites",
        "/v1/agencies",
        "/v1/fireballs",
        "/v1/bodies/{body_id}",
        "/v1/ephemeris",
        "/v1/object-events",
        "/v1/reentries",
        "/v1/reentries/{event_id}",
        "/v1/events",
        "/v1/events/{event_id}",
        "/v1/space-weather/solar-flares",
        "/v1/space-weather/cmes",
        "/v1/space-weather/solar-particle-events",
        "/v1/space-weather/radiation-storms",
        "/v1/space-weather/alerts",
        "/v1/space-weather/events",
        "/v1/earth-observation/products",
        "/v1/earth-observation/products/{product_id}",
        "/v1/earth-observation/instruments",
    }
)


def configured_providers() -> frozenset[str]:
    providers: set[str] = set()
    if settings.space_track_identity and settings.space_track_password:
        providers.add("space-track")
    if settings.enable_celestrak:
        providers.add("celestrak")
    if settings.nasa_api_key:
        providers.add("nasa-neows")
    if settings.enable_jpl:
        providers.add("jpl-horizons")
    if settings.enable_noaa_swpc:
        providers.add("noaa-swpc")
    if settings.enable_space_devs_public_api or settings.the_space_devs_api_key:
        providers.add("the-space-devs")
    if settings.enable_esa:
        providers.add("esa")
    return frozenset(providers)


def providers_for_tag(tag: str) -> tuple[str, ...]:
    configured = configured_providers()
    return tuple(provider for provider in _TAG_PROVIDERS.get(tag, ()) if provider in configured)


def tag_enabled(tag: str) -> bool:
    required = _TAG_PROVIDERS.get(tag)
    return required is None or bool(providers_for_tag(tag))


def require_capability(tag: str) -> Callable[[], Awaitable[None]]:
    async def dependency() -> None:
        if not tag_enabled(tag):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "ENDPOINT_DISABLED",
                    "message": f"No configured provider supports the {tag} capability",
                },
            )

    return dependency


async def unavailable_endpoint() -> None:
    raise HTTPException(
        status_code=503,
        detail={
            "code": "ENDPOINT_DISABLED",
            "message": "This capability has no complete production implementation",
        },
    )
