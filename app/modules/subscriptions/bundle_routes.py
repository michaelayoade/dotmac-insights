"""Data Bundle Web Routes.

Web UI routes for managing data bundle products and customer bundles.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database import get_db
from app.auth import get_current_user_or_none
from app.templates.environment import get_template_env
from app.modules.subscriptions._deps import get_context, BreadcrumbItem
from app.services.subscriptions.data_bundles import DataBundleService
from app.services.subscriptions.bundles_web_service import DataBundlesWebService
from app.services.subscriptions.data_bundle_types import (
    BundleProductCreate,
    BundleProductUpdate,
    BundleType,
    ExpiryType,
    ExhaustionAction,
)

router = APIRouter(prefix="/bundles", tags=["bundles-web"])
templates = get_template_env()


# =============================================================================
# Bundle Product List
# =============================================================================

@router.get("", response_class=HTMLResponse, name="bundles:list")
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def bundles_list(
    request: Request,
    active_only: bool = Query(True),
    bundle_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """List all data bundle products."""
    context = get_context(
        request,
        title="Data Bundles",
        breadcrumbs=[
            BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
            BreadcrumbItem(label="Data Bundles"),
        ],
        user=current_user,
    )

    service = DataBundleService(db)
    web_service = DataBundlesWebService(db)

    offset = (page - 1) * per_page
    products, total = await service.list_products(
        active_only=active_only,
        bundle_type=bundle_type,
        category=category,
        limit=per_page,
        offset=offset,
    )

    # Get analytics
    analytics = await service.get_analytics()

    context.update({
        "products": products,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "active_only": active_only,
        "bundle_type": bundle_type,
        "category": category,
        "analytics": analytics,
        "bundle_types": [t.value for t in BundleType],
    })

    return templates.TemplateResponse(
        "subscriptions/bundles/pages/list.html",
        context,
    )


# =============================================================================
# Bundle Product Designer (Create/Edit)
# =============================================================================

@router.get("/products/new", response_class=HTMLResponse, name="bundles:product_new")
async def product_form_new(
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Show form to create a new bundle product."""
    context = get_context(
        request,
        title="Create Bundle Product",
        breadcrumbs=[
            BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
            BreadcrumbItem(label="Data Bundles", url="/subscriptions/bundles"),
            BreadcrumbItem(label="New Product"),
        ],
        user=current_user,
    )

    # Get existing products for auto-renew dropdown
    service = DataBundleService(db)
    products, _ = await service.list_products(active_only=True, limit=100)

    context.update({
        "product": None,
        "is_edit": False,
        "bundle_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in BundleType],
        "expiry_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in ExpiryType],
        "exhaustion_actions": [{"value": a.value, "label": a.value.replace("_", " ").title()} for a in ExhaustionAction],
        "existing_products": products,
    })

    return templates.TemplateResponse(
        "subscriptions/bundles/pages/product_form.html",
        context,
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse, name="bundles:product_edit")
async def product_form_edit(
    request: Request,
    product_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Show form to edit an existing bundle product."""
    service = DataBundleService(db)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    context = get_context(
        request,
        title=f"Edit: {product.name}",
        breadcrumbs=[
            BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
            BreadcrumbItem(label="Data Bundles", url="/subscriptions/bundles"),
            BreadcrumbItem(label=product.name),
        ],
        user=current_user,
    )

    # Get existing products for auto-renew dropdown
    products, _ = await service.list_products(active_only=True, limit=100)

    context.update({
        "product": product,
        "is_edit": True,
        "bundle_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in BundleType],
        "expiry_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in ExpiryType],
        "exhaustion_actions": [{"value": a.value, "label": a.value.replace("_", " ").title()} for a in ExhaustionAction],
        "existing_products": [p for p in products if p.id != product_id],
    })

    return templates.TemplateResponse(
        "subscriptions/bundles/pages/product_form.html",
        context,
    )


@router.post("/products", response_class=HTMLResponse, name="bundles:product_create")
async def product_create(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    bundle_type: str = Form(...),
    price: float = Form(...),
    data_amount_mb: Optional[int] = Form(None),
    data_cap_mb: Optional[int] = Form(None),
    expiry_type: str = Form("strict"),
    validity_days: Optional[int] = Form(30),
    rollover_percent: Optional[int] = Form(0),
    exhaustion_action: str = Form("throttle"),
    throttle_speed_kbps: Optional[int] = Form(128),
    auto_renew_product_id: Optional[int] = Form(None),
    download_speed_kbps: Optional[int] = Form(None),
    upload_speed_kbps: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    is_active: bool = Form(True),
    customer_portal_visible: bool = Form(True),
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Create a new bundle product."""
    service = DataBundleService(db)

    try:
        data = BundleProductCreate(
            name=name,
            code=code,
            bundle_type=BundleType(bundle_type),
            price=price,
            data_amount_mb=data_amount_mb,
            data_cap_mb=data_cap_mb,
            expiry_type=ExpiryType(expiry_type),
            validity_days=validity_days,
            rollover_percent=rollover_percent,
            exhaustion_action=ExhaustionAction(exhaustion_action),
            throttle_speed_kbps=throttle_speed_kbps,
            auto_renew_product_id=auto_renew_product_id,
            download_speed_kbps=download_speed_kbps,
            upload_speed_kbps=upload_speed_kbps,
            description=description,
            category=category,
            is_active=is_active,
            customer_portal_visible=customer_portal_visible,
        )

        product = await web_service.create_product(data)

        return RedirectResponse(
            url=f"/subscriptions/bundles/products/{product.id}",
            status_code=303,
        )
    except ValueError as e:
        # Re-render form with error
        context = get_context(
            request,
            title="Create Bundle Product",
            breadcrumbs=[
                BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
                BreadcrumbItem(label="Data Bundles", url="/subscriptions/bundles"),
                BreadcrumbItem(label="New Product"),
            ],
            user=current_user,
        )

        products, _ = await service.list_products(active_only=True, limit=100)

        context.update({
            "product": None,
            "is_edit": False,
            "error": str(e),
            "form_data": {
                "name": name,
                "code": code,
                "bundle_type": bundle_type,
                "price": price,
                "data_amount_mb": data_amount_mb,
                "data_cap_mb": data_cap_mb,
                "expiry_type": expiry_type,
                "validity_days": validity_days,
                "rollover_percent": rollover_percent,
                "exhaustion_action": exhaustion_action,
                "throttle_speed_kbps": throttle_speed_kbps,
                "description": description,
                "category": category,
            },
            "bundle_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in BundleType],
            "expiry_types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in ExpiryType],
            "exhaustion_actions": [{"value": a.value, "label": a.value.replace("_", " ").title()} for a in ExhaustionAction],
            "existing_products": products,
        })

        return templates.TemplateResponse(
            "subscriptions/bundles/pages/product_form.html",
            context,
        )


@router.post("/products/{product_id}", response_class=HTMLResponse, name="bundles:product_update")
async def product_update(
    request: Request,
    product_id: int,
    name: str = Form(...),
    bundle_type: str = Form(...),
    price: float = Form(...),
    data_amount_mb: Optional[int] = Form(None),
    data_cap_mb: Optional[int] = Form(None),
    expiry_type: str = Form("strict"),
    validity_days: Optional[int] = Form(30),
    rollover_percent: Optional[int] = Form(0),
    exhaustion_action: str = Form("throttle"),
    throttle_speed_kbps: Optional[int] = Form(128),
    auto_renew_product_id: Optional[int] = Form(None),
    download_speed_kbps: Optional[int] = Form(None),
    upload_speed_kbps: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    is_active: bool = Form(True),
    customer_portal_visible: bool = Form(True),
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Update an existing bundle product."""
    service = DataBundleService(db)
    web_service = DataBundlesWebService(db)

    try:
        data = BundleProductUpdate(
            name=name,
            bundle_type=BundleType(bundle_type),
            price=price,
            data_amount_mb=data_amount_mb,
            data_cap_mb=data_cap_mb,
            expiry_type=ExpiryType(expiry_type),
            validity_days=validity_days,
            rollover_percent=rollover_percent,
            exhaustion_action=ExhaustionAction(exhaustion_action),
            throttle_speed_kbps=throttle_speed_kbps,
            auto_renew_product_id=auto_renew_product_id,
            download_speed_kbps=download_speed_kbps,
            upload_speed_kbps=upload_speed_kbps,
            description=description,
            category=category,
            is_active=is_active,
            customer_portal_visible=customer_portal_visible,
        )

        product = await web_service.update_product(product_id, data)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        return RedirectResponse(
            url=f"/subscriptions/bundles/products/{product.id}",
            status_code=303,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Bundle Product Detail
# =============================================================================

@router.get("/products/{product_id}", response_class=HTMLResponse, name="bundles:product_detail")
async def product_detail(
    request: Request,
    product_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Show bundle product details and stats."""
    service = DataBundleService(db)
    web_service = DataBundlesWebService(db)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    context = get_context(
        request,
        title=product.name,
        breadcrumbs=[
            BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
            BreadcrumbItem(label="Data Bundles", url="/subscriptions/bundles"),
            BreadcrumbItem(label=product.name),
        ],
        user=current_user,
    )

    # Get revenue for this product (last 30 days)
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    revenues = await service.get_product_revenue(month_ago, now)
    product_revenue = next((r for r in revenues if r.product_id == product_id), None)

    context.update({
        "product": product,
        "revenue": product_revenue,
    })

    return templates.TemplateResponse(
        "subscriptions/bundles/pages/product_detail.html",
        context,
    )


@router.post("/products/{product_id}/toggle", response_class=HTMLResponse, name="bundles:product_toggle")
async def product_toggle(
    request: Request,
    product_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Toggle product active status."""
    service = DataBundleService(db)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await web_service.toggle_product(product_id, not product.is_active)

    return RedirectResponse(
        url=request.headers.get("HX-Current-URL", "/subscriptions/bundles"),
        status_code=303,
    )


@router.delete("/products/{product_id}", response_class=HTMLResponse, name="bundles:product_delete")
async def product_delete(
    request: Request,
    product_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Delete a bundle product."""
    service = DataBundleService(db)
    web_service = DataBundlesWebService(db)
    try:
        deleted = await web_service.delete_product(product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product not found")
        return HTMLResponse(content="", status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Bundle Dashboard
# =============================================================================

@router.get("/dashboard", response_class=HTMLResponse, name="bundles:dashboard")
async def bundles_dashboard(
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Show bundle analytics dashboard."""
    context = get_context(
        request,
        title="Bundle Analytics",
        breadcrumbs=[
            BreadcrumbItem(label="Subscriptions", url="/subscriptions"),
            BreadcrumbItem(label="Data Bundles", url="/subscriptions/bundles"),
            BreadcrumbItem(label="Dashboard"),
        ],
        user=current_user,
    )

    service = DataBundleService(db)
    analytics = await service.get_analytics()

    context.update({
        "analytics": analytics,
    })

    return templates.TemplateResponse(
        "subscriptions/bundles/pages/dashboard.html",
        context,
    )
