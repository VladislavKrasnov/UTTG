from __future__ import annotations

import hashlib
import hmac
import ipaddress
from typing import cast

from fastapi import Request

from core.settings import settings


def _fingerprint_ip(ip: str) -> str:
    return hmac.new(
        settings.ip_fingerprint_secret.encode(), ip.encode(), hashlib.sha256
    ).hexdigest()


def _resolve_client_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    trusted = [value.strip() for value in settings.trusted_proxies.split(",") if value.strip()]
    if _trusted_proxy(direct, trusted):
        forwarded = request.headers.get("X-Forwarded-For", "")
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    return direct


def _trusted_proxy(address: str, trusted: list[str]) -> bool:
    try:
        client_address = ipaddress.ip_address(address)
    except ValueError:
        return address in trusted
    for value in trusted:
        try:
            if client_address in ipaddress.ip_network(value, strict=False):
                return True
        except ValueError:
            if address == value:
                return True
    return False


async def get_current_client(request: Request) -> dict[str, str]:
    """Return a privacy-preserving, IP-scoped public client identity.

    UTTG intentionally has no application authentication layer. The digest is
    used only for Valkey rate-limit keys and webhook ownership; the raw address
    is never persisted.
    """
    cached_client = getattr(request.state, "client_identity", None)
    if cached_client is not None:
        return cast(dict[str, str], cached_client)

    ip = _resolve_client_ip(request)
    client = {"type": "ip", "id": _fingerprint_ip(ip)}
    request.state.client_identity = client
    request.state.ip_fingerprint = client["id"]
    return client
