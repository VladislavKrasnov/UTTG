from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import FreshnessMeta, ProviderCoverageMeta, ResponseMeta
from core.cache_layer import cached
from core.capabilities import configured_providers
from storage.database import AsyncSessionLocal
from storage.models import ProviderHealth


async def build_meta(
    resource: str,
    db: AsyncSession,
    sources: list[str],
    ttl: int = 3600,
    max_stale: int = 86400,
) -> ResponseMeta:
    configured_sources = [source for source in sources if source in configured_providers()]

    async def load_health() -> dict[str, dict[str, str | None]]:
        async with AsyncSessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(ProviderHealth).where(ProviderHealth.id.in_(configured_sources))
                    )
                )
                .scalars()
                .all()
            )
        return {
            row.id: {
                "status": row.status,
                "last_success_at": (
                    row.last_success_at.isoformat() if row.last_success_at is not None else None
                ),
            }
            for row in rows
        }

    health_map, _, _ = await cached(
        f"provider-health:{','.join(sorted(configured_sources))}",
        load_health,
        ttl=30,
        stale=300,
    )
    configured = len(configured_sources)
    healthy = sum(
        1 for source in configured_sources if health_map.get(source, {}).get("status") == "active"
    )
    independent = configured

    if configured >= 2 and healthy >= 2:
        resilience = "high"
    elif configured >= 2 and healthy == 1:
        resilience = "medium"
    else:
        resilience = "limited"

    now = datetime.now(UTC)
    last_success_values = [
        datetime.fromisoformat(str(source_health["last_success_at"]))
        for source_health in health_map.values()
        if source_health.get("last_success_at")
    ]
    last_updated = max(last_success_values, default=now)
    return ResponseMeta(
        resource=resource,
        requested_at=now,
        last_updated_at=last_updated,
        freshness=FreshnessMeta(
            state="fresh",
            age_seconds=0,
            target_ttl_seconds=ttl,
            max_stale_seconds=max_stale,
        ),
        provider_coverage=ProviderCoverageMeta(
            configured_provider_count=configured,
            healthy_provider_count=healthy,
            independent_provider_count=independent,
            resilience=resilience,
        ),
        sources=configured_sources,
        partial=healthy < configured,
        warnings=[
            f"Provider '{source}' is not active"
            for source in configured_sources
            if health_map.get(source, {}).get("status") != "active"
        ],
    )
