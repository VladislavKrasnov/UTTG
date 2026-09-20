from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import APIResponse
from api.schemas import EoCollectionResponse
from api.utils import build_meta
from core.capabilities import unavailable_endpoint
from core.rate_limit import RateLimiter
from storage.database import get_db
from storage.models import EarthObservationCollection

router = APIRouter(tags=["Earth Observation"])


@router.get(
    "/earth-observation/collections", dependencies=[Depends(RateLimiter("public_standard"))]
)
async def get_eo_collections(
    limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)
) -> APIResponse[list[EoCollectionResponse]]:
    stmt = select(EarthObservationCollection).limit(limit)
    result = await db.execute(stmt)
    collections = result.scalars().all()

    data = [EoCollectionResponse(id=c.id, name=c.name, provider=c.provider) for c in collections]
    return APIResponse(
        data=data, meta=await build_meta("/earth-observation/collections", db, ["esa"])
    )


@router.get("/earth-observation/products", dependencies=[Depends(unavailable_endpoint)])
async def get_eo_products(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(data=[], meta=await build_meta("/earth-observation/products", db, ["esa"]))


@router.get(
    "/earth-observation/products/{product_id}", dependencies=[Depends(unavailable_endpoint)]
)
async def get_eo_product(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/earth-observation/products/{product_id}", db, ["esa"])
    )


@router.get("/earth-observation/instruments", dependencies=[Depends(unavailable_endpoint)])
async def get_eo_instruments(db: AsyncSession = Depends(get_db)) -> Any:
    return APIResponse(
        data=[], meta=await build_meta("/earth-observation/instruments", db, ["esa"])
    )
