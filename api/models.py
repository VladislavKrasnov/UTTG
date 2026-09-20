from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class FreshnessMeta(BaseModel):
    state: str = Field(..., description="fresh | stale | expired")
    age_seconds: int
    target_ttl_seconds: int
    max_stale_seconds: int


class ProviderCoverageMeta(BaseModel):
    configured_provider_count: int
    healthy_provider_count: int
    independent_provider_count: int
    resilience: str = Field(..., description="high | medium | limited")


class ResponseMeta(BaseModel):
    resource: str
    canonical_schema_version: str = "v1"
    requested_at: datetime
    last_updated_at: datetime
    freshness: FreshnessMeta
    provider_coverage: ProviderCoverageMeta
    sources: list[str]
    partial: bool
    warnings: list[str]


class APIResponse[T](BaseModel):
    data: T
    meta: ResponseMeta
