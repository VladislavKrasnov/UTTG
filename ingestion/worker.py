from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select

from core.queue import close_nats, connect_nats, ensure_event_stream
from core.settings import settings
from core.ssrf import validate_webhook_url
from core.webhook_secrets import decrypt_webhook_secret
from storage.database import AsyncSessionLocal
from storage.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


def _signature(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def _record_delivery(
    webhook_id: str,
    payload: bytes,
    status_code: int | None,
    attempt: int,
    success: bool,
) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            WebhookDelivery(
                id=uuid.uuid4(),
                webhook_id=webhook_id,
                payload=payload.decode(),
                status_code=status_code,
                attempt=attempt,
                success=success,
                attempted_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _deliver_once(
    client: httpx.AsyncClient,
    webhook: Webhook,
    payload: bytes,
    event_name: str,
    delivery_id: str,
    attempt: int,
) -> bool:
    try:
        url = await validate_webhook_url(webhook.url)
        secret = decrypt_webhook_secret(webhook.secret_ciphertext or "")
    except ValueError as exc:
        logger.error("Webhook rejected", extra={"webhook_id": webhook.id, "reason": str(exc)})
        await _record_delivery(webhook.id, payload, None, attempt, False)
        return False

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "UTTG-Webhook/1.0",
        "X-UTTG-Delivery": delivery_id,
        "X-UTTG-Event": event_name,
        "X-UTTG-Timestamp": str(int(time.time())),
        "X-UTTG-Signature": _signature(payload, secret),
    }
    status_code: int | None = None
    success = False
    try:
        async with client.stream(
            "POST",
            url,
            content=payload,
            headers=headers,
            follow_redirects=False,
        ) as response:
            status_code = response.status_code
            success = 200 <= response.status_code < 300
    except httpx.HTTPError as exc:
        logger.warning(
            "Webhook delivery failed",
            extra={"webhook_id": webhook.id, "attempt": attempt, "reason": str(exc)},
        )

    await _record_delivery(webhook.id, payload, status_code, attempt, success)
    return success


async def _dispatch(
    client: httpx.AsyncClient,
    webhook: Webhook,
    event_name: str,
    event_data: dict[str, Any],
) -> bool:
    payload = json.dumps(
        {
            "event": event_name,
            "data": event_data,
            "created_at": datetime.now(UTC).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    if len(payload) > settings.webhook_max_body_bytes:
        logger.error("Webhook payload exceeds safety limit", extra={"webhook_id": webhook.id})
        return False

    delivery_id = str(uuid.uuid4())
    for attempt in range(1, settings.webhook_max_attempts + 1):
        if await _deliver_once(client, webhook, payload, event_name, delivery_id, attempt):
            return True
        if attempt < settings.webhook_max_attempts:
            await asyncio.sleep(min(2**attempt, 30))
    return False


async def _handle_message(client: httpx.AsyncClient, jetstream: Any, message: Any) -> None:
    try:
        envelope = json.loads(message.data)
        webhook_id = str(envelope["webhook_id"])
        event_name = str(envelope["event"])
        event_data = envelope.get("data", {})
        if not isinstance(event_data, dict):
            raise ValueError("Event data must be an object")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        await message.term()
        return

    async with AsyncSessionLocal() as session:
        webhook = (
            await session.execute(
                select(Webhook).where(Webhook.id == webhook_id, Webhook.active.is_(True))
            )
        ).scalar_one_or_none()

    if webhook is None or event_name not in set(json.loads(webhook.events)):
        await message.ack()
        return

    delivered = await _dispatch(client, webhook, event_name, event_data)
    if delivered:
        await message.ack()
        return

    await jetstream.publish(
        "events.webhooks.dlq",
        json.dumps(
            {"webhook_id": webhook_id, "event": event_name, "data": event_data},
            separators=(",", ":"),
        ).encode(),
    )
    await message.ack()


async def run_worker() -> None:
    await connect_nats()
    jetstream = await ensure_event_stream()

    subscription = await jetstream.pull_subscribe("events.webhooks.outbound", "webhook-workers")
    limits = httpx.Limits(
        max_connections=settings.webhook_delivery_concurrency,
        max_keepalive_connections=settings.webhook_delivery_concurrency,
    )
    timeout = httpx.Timeout(settings.webhook_timeout_seconds)
    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        try:
            while True:
                try:
                    messages = await subscription.fetch(
                        settings.webhook_batch_size,
                        timeout=1.0,
                    )
                    await asyncio.gather(
                        *(_handle_message(client, jetstream, message) for message in messages)
                    )
                except TimeoutError:
                    continue
                except Exception:
                    logger.exception("Webhook worker batch failed")
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await close_nats()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
