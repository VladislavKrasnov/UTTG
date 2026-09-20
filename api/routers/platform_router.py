from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.utils import build_meta
from core.cache import valkey_client
from core.capabilities import configured_providers
from core.rate_limit import RateLimiter
from storage.database import get_db
from storage.models import ProviderHealth

router = APIRouter(tags=["Platform"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Process liveness only; dependency health belongs to readiness."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    checks: dict[str, bool] = {"database": False, "valkey": False}
    try:
        await db.execute(select(1))
        checks["database"] = True
        checks["valkey"] = bool(await valkey_client.ping())
    except Exception:
        # Do not disclose internal addresses, credentials, or driver errors.
        pass
    if not all(checks.values()):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "NOT_READY",
                "message": "One or more required dependencies are unavailable",
            },
        )
    return {"status": "ready", "dependencies": checks}


@router.get("/version")
async def version_info() -> dict[str, str]:
    return {"version": "0.1.0", "api_version": "v1"}


@router.get("/capabilities", dependencies=[Depends(RateLimiter("public_light"))])
async def capabilities(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    rows = (await db.execute(select(ProviderHealth))).scalars().all()
    health = {row.id: row for row in rows}
    return {
        "capabilities": {
            provider: {
                "status": health[provider].status if provider in health else "not_yet_ingested",
                "last_success_at": health[provider].last_success_at if provider in health else None,
            }
            for provider in sorted(configured_providers())
        }
    }


@router.get("/providers", dependencies=[Depends(RateLimiter("public_light"))])
async def providers(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    configured = configured_providers()
    rows = (
        (await db.execute(select(ProviderHealth).where(ProviderHealth.id.in_(configured))))
        .scalars()
        .all()
    )
    data = [
        {
            "id": r.id,
            "status": r.status,
            "last_success_at": r.last_success_at,
            "last_error_at": r.last_error_at,
        }
        for r in rows
    ]
    meta = await build_meta("/providers", db, [r.id for r in rows])
    return APIResponse(data=data, meta=meta).model_dump()


@router.get("/providers/{provider_id}", dependencies=[Depends(RateLimiter("public_light"))])
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if provider_id not in configured_providers():
        raise HTTPException(status_code=404, detail="Provider not found")
    row = (
        await db.execute(select(ProviderHealth).where(ProviderHealth.id == provider_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")
    meta = await build_meta(f"/providers/{provider_id}", db, [provider_id])
    return APIResponse(
        data={"id": row.id, "status": row.status, "last_success_at": row.last_success_at},
        meta=meta,
    ).model_dump()
