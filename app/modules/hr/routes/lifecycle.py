"""
HR Lifecycle Routes - Onboarding, Separation, Promotion, Transfer with SSR + HTMX.

Permission Requirements:
- hr:read - View lifecycle events
- hr:write - Create, update, manage lifecycle events

Uses LifecycleService for all business logic.
"""
from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.hr_lifecycle import BoardingStatus
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.hr.lifecycle import LifecycleService
from app.services.hr.lifecycle_types import (
    OnboardingFilters,
    SeparationFilters,
    PromotionFilters,
    TransferFilters,
)
from app.services.base import Pagination
from app.services.hr.errors import NotFoundError, ValidationError

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/lifecycle", tags=["hr-lifecycle"])
templates = get_template_env()


def get_boarding_status_options():
    """Get boarding status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in BoardingStatus
    ]


def _lifecycle_error_response(
    request: Request,
    response: Response,
    message: str,
    redirect_url: str,
):
    if is_htmx_request(request):
        htmx_toast(response, message, "error")
        response.headers["HX-Redirect"] = redirect_url
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "error")
    return RedirectResponse(url=redirect_url, status_code=303)


# =============================================================================
# ONBOARDING
# =============================================================================

@router.get("/onboarding", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def onboarding_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Onboarding list page."""
    service = LifecycleService(db, user)

    # Build filters - handle invalid status gracefully
    status_enum = None
    if status:
        try:
            status_enum = BoardingStatus(status)
        except ValueError:
            pass  # Invalid status value, ignore filter
    filters = OnboardingFilters(
        search=q,
        boarding_status=status_enum,
    )

    offset = (page - 1) * per_page
    pagination = Pagination(offset=offset, limit=per_page)

    result = service.list_onboardings(filters, pagination)
    onboardings = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["onboardings"] = onboardings
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_boarding_status_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/onboarding_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Onboarding"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Onboarding"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/onboarding_list.html")
    return HTMLResponse(template.render(context))


@router.get("/onboarding/{onboarding_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def onboarding_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    onboarding_id: int,
):
    """Onboarding detail page."""
    service = LifecycleService(db, user)

    try:
        onboarding = service.get_onboarding(onboarding_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Onboarding not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Onboarding - {onboarding.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Onboarding", "href": "/hr/lifecycle/onboarding"},
        {"label": onboarding.employee_name or f"#{onboarding.id}"},
    ])
    context["onboarding"] = onboarding

    template = templates.get_template("modules/hr/templates/lifecycle/pages/onboarding_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/onboarding/{onboarding_id}/start", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def onboarding_start(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    onboarding_id: int,
):
    """Start the onboarding process."""
    service = LifecycleService(db, user)
    try:
        service.start_onboarding(onboarding_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/onboarding/{onboarding_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Onboarding started.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/onboarding/{onboarding_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Onboarding started.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/onboarding/{onboarding_id}", status_code=303)


@router.post("/onboarding/{onboarding_id}/complete", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def onboarding_complete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    onboarding_id: int,
):
    """Complete the onboarding process."""
    service = LifecycleService(db, user)
    try:
        service.complete_onboarding(onboarding_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/onboarding/{onboarding_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Onboarding completed.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/onboarding/{onboarding_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Onboarding completed.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/onboarding/{onboarding_id}", status_code=303)


# =============================================================================
# SEPARATION
# =============================================================================

@router.get("/separation", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def separation_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Separation list page."""
    service = LifecycleService(db, user)

    # Build filters - handle invalid status gracefully
    status_enum = None
    if status:
        try:
            status_enum = BoardingStatus(status)
        except ValueError:
            pass  # Invalid status value, ignore filter
    filters = SeparationFilters(
        search=q,
        boarding_status=status_enum,
    )

    offset = (page - 1) * per_page
    pagination = Pagination(offset=offset, limit=per_page)

    result = service.list_separations(filters, pagination)
    separations = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["separations"] = separations
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_boarding_status_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/separation_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Separation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Separation"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/separation_list.html")
    return HTMLResponse(template.render(context))


@router.get("/separation/{separation_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def separation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    separation_id: int,
):
    """Separation detail page."""
    service = LifecycleService(db, user)

    try:
        separation = service.get_separation(separation_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Separation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Separation - {separation.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Separation", "href": "/hr/lifecycle/separation"},
        {"label": separation.employee_name or f"#{separation.id}"},
    ])
    context["separation"] = separation

    template = templates.get_template("modules/hr/templates/lifecycle/pages/separation_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/separation/{separation_id}/start", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def separation_start(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    separation_id: int,
):
    """Start the separation process."""
    service = LifecycleService(db, user)
    try:
        service.start_separation(separation_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/separation/{separation_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Separation started.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/separation/{separation_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Separation started.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/separation/{separation_id}", status_code=303)


@router.post("/separation/{separation_id}/complete", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def separation_complete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    separation_id: int,
):
    """Complete the separation process."""
    service = LifecycleService(db, user)
    try:
        service.complete_separation(separation_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/separation/{separation_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Separation completed.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/separation/{separation_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Separation completed.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/separation/{separation_id}", status_code=303)


# =============================================================================
# PROMOTIONS
# =============================================================================

@router.get("/promotions", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def promotions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Promotions list page."""
    service = LifecycleService(db, user)

    filters = PromotionFilters(search=q)

    offset = (page - 1) * per_page
    pagination = Pagination(offset=offset, limit=per_page)

    result = service.list_promotions(filters, pagination)
    promotions = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["promotions"] = promotions
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/promotions_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Promotions"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Promotions"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/promotions_list.html")
    return HTMLResponse(template.render(context))


@router.get("/promotions/{promotion_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def promotion_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    promotion_id: int,
):
    """Promotion detail page."""
    service = LifecycleService(db, user)

    try:
        promotion = service.get_promotion(promotion_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Promotion not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Promotion - {promotion.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Promotions", "href": "/hr/lifecycle/promotions"},
        {"label": promotion.employee_name or f"#{promotion.id}"},
    ])
    context["promotion"] = promotion

    template = templates.get_template("modules/hr/templates/lifecycle/pages/promotion_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/promotions/{promotion_id}/submit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def promotion_submit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    promotion_id: int,
):
    """Submit a promotion (make it official)."""
    service = LifecycleService(db, user)
    try:
        service.submit_promotion(promotion_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/promotions/{promotion_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Promotion submitted.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/promotions/{promotion_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Promotion submitted.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/promotions/{promotion_id}", status_code=303)


# =============================================================================
# TRANSFERS
# =============================================================================

@router.get("/transfers", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def transfers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Transfers list page."""
    service = LifecycleService(db, user)

    filters = TransferFilters(search=q)

    offset = (page - 1) * per_page
    pagination = Pagination(offset=offset, limit=per_page)

    result = service.list_transfers(filters, pagination)
    transfers = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["transfers"] = transfers
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/lifecycle/partials/transfers_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Transfers"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Transfers"},
    ])

    template = templates.get_template("modules/hr/templates/lifecycle/pages/transfers_list.html")
    return HTMLResponse(template.render(context))


@router.get("/transfers/{transfer_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def transfer_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    transfer_id: int,
):
    """Transfer detail page."""
    service = LifecycleService(db, user)

    try:
        transfer = service.get_transfer(transfer_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Transfer - {transfer.employee_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr"},
        {"label": "Lifecycle"},
        {"label": "Transfers", "href": "/hr/lifecycle/transfers"},
        {"label": transfer.employee_name or f"#{transfer.id}"},
    ])
    context["transfer"] = transfer

    template = templates.get_template("modules/hr/templates/lifecycle/pages/transfer_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/transfers/{transfer_id}/submit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def transfer_submit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    transfer_id: int,
):
    """Submit a transfer (make it official)."""
    service = LifecycleService(db, user)
    try:
        service.submit_transfer(transfer_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        return _lifecycle_error_response(
            request, response, str(exc), f"/hr/lifecycle/transfers/{transfer_id}"
        )

    if is_htmx_request(request):
        htmx_toast(response, "Transfer submitted.", "success")
        response.headers["HX-Redirect"] = f"/hr/lifecycle/transfers/{transfer_id}"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Transfer submitted.", "success")
    return RedirectResponse(url=f"/hr/lifecycle/transfers/{transfer_id}", status_code=303)
