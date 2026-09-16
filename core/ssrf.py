from __future__ import annotations

import asyncio
import ipaddress
import socket

import httpx

_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)


async def validate_webhook_url(url: str) -> str:
    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Webhook URL must use HTTP or HTTPS")
    if parsed.userinfo:
        raise ValueError("Webhook URL credentials are forbidden")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Webhook URL port must be 80 or 443")
    if not parsed.host:
        raise ValueError("Webhook URL host is required")

    try:
        addresses = await asyncio.get_running_loop().run_in_executor(
            None,
            _resolve_addresses,
            parsed.host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
        )
    except OSError as exc:
        raise ValueError("Webhook hostname cannot be resolved") from exc

    if not addresses or any(_blocked(address) for address in addresses):
        raise ValueError("Webhook URL resolves to a blocked network")
    return str(parsed)


def _resolve_addresses(host: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    return {
        ipaddress.ip_address(item[4][0])
        for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    }


def _blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(address in network for network in _BLOCKED_NETWORKS)
