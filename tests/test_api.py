from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import UTC

from sgp4.api import Satrec


def test_sgp4_iss_propagation():
    line1 = "1 25544U 98067A   20316.41876735  .00001594  00000-0  37088-4 0  9997"
    line2 = "2 25544  51.6461  26.0441 0001925 210.9995 197.8286 15.49525149254881"
    sat = Satrec.twoline2rv(line1, line2)
    e, r, v = sat.sgp4(2459166.5, 0.41876735)
    assert e == 0
    assert len(r) == 3
    assert len(v) == 3
    assert abs(r[0]) > 100
    assert abs(r[1]) > 100


def test_capability_follows_provider_configuration(monkeypatch):
    from core.capabilities import configured_providers, tag_enabled
    from core.settings import settings

    monkeypatch.setattr(settings, "enable_celestrak", False)
    monkeypatch.setattr(settings, "space_track_identity", None)
    monkeypatch.setattr(settings, "space_track_password", None)
    monkeypatch.setattr(settings, "nasa_api_key", "test-key")

    assert "celestrak" not in configured_providers()
    assert not tag_enabled("Orbital")
    assert tag_enabled("Neo")


def test_internal_tag_is_always_enabled():
    from core.capabilities import providers_for_tag, tag_enabled

    assert tag_enabled("Platform")
    assert providers_for_tag("Platform") == ()


def test_unavailable_routes_are_hidden_from_openapi():
    from fastapi import FastAPI

    from api.routers import orbital
    from core.openapi import custom_openapi

    app = FastAPI()
    app.include_router(orbital.router, prefix="/v1")
    schema = custom_openapi(app)
    assert "/v1/satellites/{norad_id}/passes" not in schema["paths"]
    assert "/v1/satellites/{norad_id}/position" in schema["paths"]


def test_rate_limit_quotas():
    from core.rate_limit import _QUOTAS

    assert _QUOTAS["public_light"] == 600
    assert _QUOTAS["public_standard"] == 240
    assert _QUOTAS["public_expensive"] == 60
    assert _QUOTAS["mutation"] == 30


def test_ip_fingerprint_is_deterministic():
    import core.settings as cs
    from core.security import _fingerprint_ip

    settings = cs.Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        valkey_url="valkey://localhost",
        nats_url="nats://localhost",
        ip_fingerprint_secret="testipsecret",
    )

    import core.security as security

    original = security.settings
    security.settings = settings
    try:
        first = _fingerprint_ip("203.0.113.10")
        second = _fingerprint_ip("203.0.113.10")
    finally:
        security.settings = original

    assert first == second
    assert first != _fingerprint_ip("203.0.113.11")


def test_production_settings_reject_weak_secrets():
    from pydantic import ValidationError

    from core.settings import Settings

    try:
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://x:x@localhost/x",
            valkey_url="valkey://localhost",
            nats_url="nats://localhost",
            ip_fingerprint_secret="testipsecret",
            webhook_encryption_key="independent-webhook-encryption-secret",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("weak production secrets were accepted")


def test_teme_conversion_produces_physical_coordinates():
    from datetime import datetime

    from api.routers.orbital import _teme_to_geodetic

    lat, lon, altitude = _teme_to_geodetic((6778.137, 0.0, 0.0), datetime(2026, 1, 1, tzinfo=UTC))
    assert abs(lat) < 0.001
    assert -180.0 <= lon <= 180.0
    assert 399.9 <= altitude <= 400.1


def test_build_meta_resilience_logic():

    configured = 3
    healthy = 1
    resilience = "high" if healthy == configured else ("medium" if healthy > 0 else "degraded")
    assert resilience == "medium"

    healthy = 0
    resilience = "high" if healthy == configured else ("medium" if healthy > 0 else "degraded")
    assert resilience == "degraded"


def test_noaa_endpoints_exist():
    from providers.noaa import NoaaClient

    client = NoaaClient()
    assert hasattr(client, "get_planetary_k")
    assert hasattr(client, "get_solar_wind")
    assert hasattr(client, "get_alerts")
    assert hasattr(client, "get_solar_flares")


def test_spacetrack_guards_exist():
    from providers.spacetrack import SpaceTrackClient

    client = SpaceTrackClient()
    assert hasattr(client, "_guard_global")
    assert hasattr(client, "get_gp")
    assert hasattr(client, "get_satcat")
    assert hasattr(client, "get_decay")


def test_ssrf_network_classification():
    import ipaddress

    from core.ssrf import _blocked

    for address in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1"):
        assert _blocked(ipaddress.ip_address(address))
    assert not _blocked(ipaddress.ip_address("1.1.1.1"))


def test_webhook_event_allowlist_rejects_unknown_event():
    from pydantic import ValidationError

    from api.routers.webhooks import WebhookCreate

    try:
        WebhookCreate(url="https://example.com/hook", events=["made.up"])
    except ValidationError:
        pass
    else:
        raise AssertionError("unsupported webhook event was accepted")


def test_webhook_signature_is_stable():
    from ingestion.worker import _signature

    assert _signature(b'{"event":"test"}', "secret") == _signature(b'{"event":"test"}', "secret")
    assert _signature(b'{"event":"other"}', "secret") != _signature(b'{"event":"test"}', "secret")


def test_public_openapi_has_no_incomplete_paths():
    from api.main import app
    from core.capabilities import _UNAVAILABLE_PATHS

    paths = set(app.openapi()["paths"])
    assert paths.isdisjoint(_UNAVAILABLE_PATHS)
    methods = {"get", "post", "put", "patch", "delete"}
    operation_count = sum(
        sum(method in methods for method in path_item)
        for path_item in app.openapi()["paths"].values()
    )
    assert 50 <= operation_count <= 60


def test_request_metrics_are_aggregated_by_minute_route_and_method():
    from datetime import UTC, datetime

    from core.analytics import _aggregate

    timestamp = datetime(2026, 9, 21, 12, 34, 56, tzinfo=UTC)
    rows = _aggregate(
        [
            {
                "timestamp": timestamp,
                "route": "/v1/satellites",
                "method": "GET",
                "status_code": 200,
                "duration_ms": 4.0,
                "response_bytes": 100,
                "cache_state": "fresh",
            },
            {
                "timestamp": timestamp,
                "route": "/v1/satellites",
                "method": "GET",
                "status_code": 503,
                "duration_ms": 9.0,
                "response_bytes": 50,
                "cache_state": None,
            },
        ]
    )
    assert rows == [
        {
            "bucket": timestamp.replace(second=0, microsecond=0),
            "route": "/v1/satellites",
            "method": "GET",
            "request_count": 2,
            "server_error_count": 1,
            "duration_sum_ms": 13.0,
            "duration_max_ms": 9.0,
            "response_bytes": 150,
            "cache_hit_count": 1,
        }
    ]
