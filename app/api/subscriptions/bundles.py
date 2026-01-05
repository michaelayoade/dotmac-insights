"""Data Bundle API Endpoints.

REST API for managing data bundle products and customer bundles.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_or_none
from app.database import get_db
from app.services.subscriptions.data_bundles import DataBundleService
from app.services.subscriptions.data_bundle_types import (
    BundleAnalytics,
    BundlePurchaseRequest,
    BundleProductCreate,
    BundleProductResponse,
    BundleProductUpdate,
    BundleStatusResponse,
    BundleType,
    CustomerBundleResponse,
    ExhaustionResult,
    ProductRevenue,
    UsageRecordRequest,
    UsageSummary,
)

router = APIRouter(prefix="/bundles", tags=["Data Bundles"])


# =============================================================================
# Response Schemas
# =============================================================================

class PaginatedProductsResponse(BaseModel):
    """Paginated list of bundle products."""
    items: List[BundleProductResponse]
    total: int
    limit: int
    offset: int


class PurchaseResponse(BaseModel):
    """Response after purchasing a bundle."""
    success: bool
    bundle: CustomerBundleResponse
    message: str


class ActivateResponse(BaseModel):
    """Response after activating a bundle."""
    success: bool
    bundle: CustomerBundleResponse


class CancelResponse(BaseModel):
    """Response after cancelling a bundle."""
    success: bool
    bundle: CustomerBundleResponse


class UsageResponse(BaseModel):
    """Response after recording usage."""
    success: bool
    mb_recorded: int
    bundle_id: int


# =============================================================================
# Product Endpoints
# =============================================================================

@router.post(
    "/products",
    response_model=BundleProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bundle product",
)
async def create_product(
    data: BundleProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Create a new data bundle product template."""
    service = DataBundleService(db)
    try:
        product = await service.create_product(data)
        await db.commit()
        return BundleProductResponse.model_validate(product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/products",
    response_model=PaginatedProductsResponse,
    summary="List bundle products",
)
async def list_products(
    active_only: bool = Query(True, description="Filter to active products only"),
    portal_visible_only: bool = Query(False, description="Filter to customer-visible products"),
    bundle_type: Optional[str] = Query(None, description="Filter by bundle type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """List all data bundle products with optional filtering."""
    service = DataBundleService(db)
    products, total = await service.list_products(
        active_only=active_only,
        portal_visible_only=portal_visible_only,
        bundle_type=bundle_type,
        category=category,
        limit=limit,
        offset=offset,
    )
    return PaginatedProductsResponse(
        items=[BundleProductResponse.model_validate(p) for p in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/products/{product_id}",
    response_model=BundleProductResponse,
    summary="Get bundle product",
)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get a specific bundle product by ID."""
    service = DataBundleService(db)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Bundle product not found")
    return BundleProductResponse.model_validate(product)


@router.patch(
    "/products/{product_id}",
    response_model=BundleProductResponse,
    summary="Update bundle product",
)
async def update_product(
    product_id: int,
    data: BundleProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Update an existing bundle product."""
    service = DataBundleService(db)
    try:
        product = await service.update_product(product_id, data)
        if not product:
            raise HTTPException(status_code=404, detail="Bundle product not found")
        await db.commit()
        return BundleProductResponse.model_validate(product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bundle product",
)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Delete a bundle product (only if no active bundles)."""
    service = DataBundleService(db)
    try:
        deleted = await service.delete_product(product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Bundle product not found")
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Customer Bundle Endpoints
# =============================================================================

@router.post(
    "/subscriptions/{subscription_id}/purchase",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Purchase bundle",
)
async def purchase_bundle(
    subscription_id: int,
    request: BundlePurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Purchase a data bundle for a subscription."""
    service = DataBundleService(db)
    try:
        bundle = await service.purchase_bundle(subscription_id, request)
        await db.commit()

        # Refresh to get relationships
        bundle = await service.get_bundle(bundle.id)

        return PurchaseResponse(
            success=True,
            bundle=service._bundle_to_response(bundle),
            message=f"Successfully purchased {bundle.product.name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/subscriptions/{subscription_id}/status",
    response_model=BundleStatusResponse,
    summary="Get bundle status",
)
async def get_bundle_status(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get current bundle status for a subscription."""
    service = DataBundleService(db)
    return await service.get_bundle_status(subscription_id)


@router.post(
    "/{bundle_id}/activate",
    response_model=ActivateResponse,
    summary="Activate bundle",
)
async def activate_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Activate a pending bundle."""
    service = DataBundleService(db)
    try:
        bundle = await service.activate_bundle(bundle_id)
        if not bundle:
            raise HTTPException(status_code=404, detail="Bundle not found")
        await db.commit()

        bundle = await service.get_bundle(bundle_id)
        return ActivateResponse(
            success=True,
            bundle=service._bundle_to_response(bundle),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{bundle_id}/cancel",
    response_model=CancelResponse,
    summary="Cancel bundle",
)
async def cancel_bundle(
    bundle_id: int,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Cancel an active or pending bundle."""
    service = DataBundleService(db)
    try:
        bundle = await service.cancel_bundle(bundle_id, reason)
        if not bundle:
            raise HTTPException(status_code=404, detail="Bundle not found")
        await db.commit()

        bundle = await service.get_bundle(bundle_id)
        return CancelResponse(
            success=True,
            bundle=service._bundle_to_response(bundle),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{bundle_id}",
    response_model=CustomerBundleResponse,
    summary="Get bundle",
)
async def get_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get a specific customer bundle."""
    service = DataBundleService(db)
    bundle = await service.get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return service._bundle_to_response(bundle)


# =============================================================================
# Usage Endpoints
# =============================================================================

@router.post(
    "/usage",
    response_model=UsageResponse,
    summary="Record usage",
)
async def record_usage(
    request: UsageRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Record data usage for a subscription.

    Typically called by RADIUS accounting or usage polling.
    """
    service = DataBundleService(db)
    mb_recorded = await service.record_usage(request)

    if mb_recorded is None:
        raise HTTPException(
            status_code=404,
            detail="No active bundle for subscription",
        )

    await db.commit()

    # Get active bundle for response
    bundle = await service.get_active_bundle(request.subscription_id)

    return UsageResponse(
        success=True,
        mb_recorded=mb_recorded,
        bundle_id=bundle.id if bundle else 0,
    )


@router.get(
    "/subscriptions/{subscription_id}/usage",
    response_model=UsageSummary,
    summary="Get usage summary",
)
async def get_usage_summary(
    subscription_id: int,
    start_date: datetime = Query(..., description="Period start"),
    end_date: datetime = Query(..., description="Period end"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get usage summary for a subscription over a date range."""
    service = DataBundleService(db)
    return await service.get_usage_summary(subscription_id, start_date, end_date)


# =============================================================================
# Exhaustion Endpoints
# =============================================================================

@router.post(
    "/{bundle_id}/handle-exhaustion",
    response_model=ExhaustionResult,
    summary="Handle exhaustion",
)
async def handle_exhaustion(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Manually trigger exhaustion handling for a bundle.

    Normally this happens automatically when usage is recorded.
    This endpoint is for testing or manual intervention.
    """
    service = DataBundleService(db)
    result = await service.handle_exhaustion(bundle_id)
    await db.commit()
    return result


# =============================================================================
# Analytics Endpoints
# =============================================================================

@router.get(
    "/analytics",
    response_model=BundleAnalytics,
    summary="Get bundle analytics",
)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get bundle analytics overview."""
    service = DataBundleService(db)
    return await service.get_analytics()


@router.get(
    "/analytics/revenue",
    response_model=List[ProductRevenue],
    summary="Get revenue by product",
)
async def get_revenue_by_product(
    start_date: datetime = Query(..., description="Period start"),
    end_date: datetime = Query(..., description="Period end"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Get revenue breakdown by product for a period."""
    service = DataBundleService(db)
    return await service.get_product_revenue(start_date, end_date)
