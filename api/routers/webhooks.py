from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from api.models import APIResponse
from api.utils import build_meta
from core.cache import valkey_client
from core.rate_limit import RateLimiter
from core.security import get_current_client
from core.settings import settings
from core.ssrf import validate_webhook_url
from core.webhook_secrets import encrypt_webhook_secret
from storage.database import get_db
from storage.models import Webhook, WebhookDelivery

router = APIRouter(tags=["Webhooks"])
_SOURCES: list[str] = []
_ALLOWED_EVENTS = {
    "launch.updated",
    "object.updated",
    "space_weather.alert",
    "provider.degraded",
}


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[str] = Field(min_length=1, max_length=20)
    secret: str | None = Field(default=None, min_length=16, max_length=256)

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: list[str]) -> list[str]:
        normalized = sorted(set(events))
        unsupported = set(normalized) - _ALLOWED_EVENTS
        if unsupported:
            raise ValueError(f"Unsupported webhook events: {', '.join(sorted(unsupported))}")
        return normalized


class WebhookPatch(BaseModel):
    url: HttpUrl | None = None
    events: list[str] | None = Field(default=None, min_length=1, max_length=20)
    active: bool | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: list[str] | None) -> list[str] | None:
        if events is None:
            return None
        normalized = sorted(set(events))
        unsupported = set(normalized) - _ALLOWED_EVENTS
        if unsupported:
            raise ValueError(f"Unsupported webhook events: {', '.join(sorted(unsupported))}")
        return normalized


def _owner_statement(webhook_id: str, client: dict[str, str]) -> Select[tuple[Webhook]]:
    return select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.owner_ip_fingerprint == client["id"],
    )


@router.post(
    "/webhooks",
    dependencies=[Depends(RateLimiter("mutation"))],
    status_code=201,
)
async def create_webhook(
    body: WebhookCreate,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    url = await validate_webhook_url(str(body.url))
    existing_count = (
        await db.execute(
            select(func.count())
            .select_from(Webhook)
            .where(Webhook.owner_ip_fingerprint == client["id"], Webhook.active.is_(True))
        )
    ).scalar_one()
    if existing_count >= settings.webhook_max_per_ip:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "WEBHOOK_LIMIT_REACHED",
                "message": "Active webhook limit reached for this IP address",
            },
        )
    idempotency_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    idempotency_storage_key = f"idempotency:webhook-create:{client['id']}:{idempotency_digest}"
    claimed = await valkey_client.set(
        idempotency_storage_key,
        "1",
        ex=86400,
        nx=True,
    )
    if not claimed:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "message": "Request already submitted"},
        )

    signing_secret = body.secret or secrets.token_urlsafe(32)
    webhook = Webhook(
        id=str(uuid.uuid4()),
        url=url,
        events=json.dumps(body.events, separators=(",", ":")),
        secret_hash=hashlib.sha256(signing_secret.encode()).hexdigest(),
        secret_ciphertext=encrypt_webhook_secret(signing_secret),
        owner_ip_fingerprint=client["id"],
        active=True,
    )
    try:
        db.add(webhook)
        await db.commit()
    except Exception:
        await db.rollback()
        await valkey_client.delete(idempotency_storage_key)
        raise

    meta = await build_meta("/webhooks", db, _SOURCES)
    return APIResponse(
        data={
            "id": webhook.id,
            "url": webhook.url,
            "events": body.events,
            "active": webhook.active,
            "signing_secret": signing_secret,
        },
        meta=meta,
    ).model_dump()


@router.get(
    "/webhooks",
    dependencies=[
        Depends(RateLimiter("public_standard")),
    ],
)
async def list_webhooks(
    limit: int = Query(50, ge=1, le=100),
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(Webhook)
                .where(Webhook.owner_ip_fingerprint == client["id"])
                .order_by(Webhook.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    data = [
        {"id": row.id, "url": row.url, "events": json.loads(row.events), "active": row.active}
        for row in rows
    ]
    return APIResponse(data=data, meta=await build_meta("/webhooks", db, _SOURCES)).model_dump()


@router.get(
    "/webhooks/{webhook_id}",
    dependencies=[
        Depends(RateLimiter("public_standard")),
    ],
)
async def get_webhook(
    webhook_id: str,
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = (await db.execute(_owner_statement(webhook_id, client))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    data = {"id": row.id, "url": row.url, "events": json.loads(row.events), "active": row.active}
    return APIResponse(
        data=data,
        meta=await build_meta(f"/webhooks/{webhook_id}", db, _SOURCES),
    ).model_dump()


@router.patch(
    "/webhooks/{webhook_id}",
    dependencies=[Depends(RateLimiter("mutation"))],
)
async def update_webhook(
    webhook_id: str,
    body: WebhookPatch,
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = (await db.execute(_owner_statement(webhook_id, client))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if body.url is not None:
        row.url = await validate_webhook_url(str(body.url))
    if body.events is not None:
        row.events = json.dumps(body.events, separators=(",", ":"))
    if body.active is not None:
        row.active = body.active
    await db.commit()
    return APIResponse(
        data={"id": row.id, "active": row.active},
        meta=await build_meta(f"/webhooks/{webhook_id}", db, _SOURCES),
    ).model_dump()


@router.delete(
    "/webhooks/{webhook_id}",
    dependencies=[Depends(RateLimiter("mutation"))],
)
async def delete_webhook(
    webhook_id: str,
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = (await db.execute(_owner_statement(webhook_id, client))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    row.active = False
    await db.commit()
    return APIResponse(
        data={"id": webhook_id, "active": False},
        meta=await build_meta(f"/webhooks/{webhook_id}", db, _SOURCES),
    ).model_dump()


@router.get(
    "/webhooks/{webhook_id}/deliveries",
    dependencies=[
        Depends(RateLimiter("public_standard")),
    ],
)
async def list_deliveries(
    webhook_id: str,
    limit: int = Query(50, ge=1, le=100),
    client: dict[str, str] = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    webhook = (await db.execute(_owner_statement(webhook_id, client))).scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    rows = (
        (
            await db.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.webhook_id == webhook_id)
                .order_by(WebhookDelivery.attempted_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    data = [
        {
            "id": row.id,
            "status_code": row.status_code,
            "attempt": row.attempt,
            "attempted_at": row.attempted_at,
            "success": row.success,
        }
        for row in rows
    ]
    return APIResponse(
        data=data,
        meta=await build_meta(f"/webhooks/{webhook_id}/deliveries", db, _SOURCES),
    ).model_dump()
