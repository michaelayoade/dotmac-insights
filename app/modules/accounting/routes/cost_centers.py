"""
Cost Centers routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str, form_int,
)
from app.services.accounting import FiscalService
from app.services.accounting.fiscal_types import CostCenterCreateData, CostCenterUpdateData
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def _get_fiscal_service(db: DB, user: SessionUser) -> FiscalService:
    return FiscalService(db, user)


def get_parent_cost_center_options(service: FiscalService, exclude_id: Optional[int] = None) -> list:
    """Get cost centers that can be parents (groups)."""
    centers = service.list_parent_cost_centers(exclude_id=exclude_id)
    return [{"value": str(cc.id), "label": cc.cost_center_name} for cc in centers]


@router.get("/cost-centers", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def cost_centers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Cost centers list page."""
    service = _get_fiscal_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_cost_centers_paginated(
            search=q,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cost_centers = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Cost Centers", "href": "/accounting/cost-centers", "current": True},
    ])
    context["cost_centers"] = cost_centers
    context["stats"] = service.get_cost_center_stats()
    context["current_search"] = q
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/cost_centers/partials/cost_centers_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/cost_centers/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/cost-centers/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def cost_centers_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Cost centers table HTMX partial."""
    service = _get_fiscal_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_cost_centers_paginated(
            search=q,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cost_centers = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["cost_centers"] = cost_centers
    context["current_search"] = q
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/cost_centers/partials/cost_centers_table.html")
    return HTMLResponse(template.render(context))


@router.get("/cost-centers/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def cost_center_new_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New cost center form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Cost Centers", "href": "/accounting/cost-centers"},
        {"label": "New Cost Center", "href": "/accounting/cost-centers/new", "current": True},
    ])
    service = _get_fiscal_service(db, user)
    context["parent_options"] = get_parent_cost_center_options(service)

    template = templates.get_template("modules/accounting/templates/cost_centers/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/cost-centers", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def cost_center_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create new cost center."""
    form = await request.form()
    await validate_csrf(request)

    errors = {}
    if not form_str(form, "cost_center_name"):
        errors["cost_center_name"] = "Cost center name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/invoices"},
            {"label": "Cost Centers", "href": "/accounting/cost-centers"},
            {"label": "New Cost Center", "href": "/accounting/cost-centers/new", "current": True},
        ])
        context["errors"] = errors
        context["form_data"] = dict(form)
        service = _get_fiscal_service(db, user)
        context["parent_options"] = get_parent_cost_center_options(service)
        template = templates.get_template("modules/accounting/templates/cost_centers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Get parent name if parent_id provided
    parent_name = None
    parent_id = form_int(form, "parent_id")
    if parent_id is not None:
        service = _get_fiscal_service(db, user)
        try:
            parent = service.get_cost_center(parent_id)
            parent_name = parent.cost_center_name
        except NotFoundError:
            parent_name = None

    service = _get_fiscal_service(db, user)
    cost_center = service.create_cost_center(
        CostCenterCreateData(
            cost_center_name=form_str(form, "cost_center_name"),
            cost_center_number=form_str(form, "cost_center_code") or None,
            parent_cost_center=parent_name,
            disabled=not bool(form_str(form, "is_active")),
        )
    )
    db.commit()

    set_flash(response, "Cost center created successfully", "success")
    return RedirectResponse(url="/accounting/cost-centers", status_code=303)


@router.get("/cost-centers/{cc_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def cost_center_edit_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    cc_id: int,
):
    """Edit cost center form."""
    service = _get_fiscal_service(db, user)
    try:
        cost_center = service.get_cost_center(cc_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cost center not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Cost Centers", "href": "/accounting/cost-centers"},
        {"label": "Edit", "href": f"/accounting/cost-centers/{cc_id}/edit", "current": True},
    ])
    context["cost_center"] = cost_center
    context["parent_options"] = get_parent_cost_center_options(service, exclude_id=cc_id)

    template = templates.get_template("modules/accounting/templates/cost_centers/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/cost-centers/{cc_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def cost_center_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    cc_id: int,
):
    """Update cost center."""
    service = _get_fiscal_service(db, user)
    try:
        cost_center = service.get_cost_center(cc_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Cost center not found") from exc

    form = await request.form()
    await validate_csrf(request)

    errors = {}
    if not form_str(form, "cost_center_name"):
        errors["cost_center_name"] = "Cost center name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/invoices"},
            {"label": "Cost Centers", "href": "/accounting/cost-centers"},
            {"label": "Edit", "href": f"/accounting/cost-centers/{cc_id}/edit", "current": True},
        ])
        context["cost_center"] = cost_center
        context["errors"] = errors
        context["form_data"] = dict(form)
        context["parent_options"] = get_parent_cost_center_options(service, exclude_id=cc_id)
        template = templates.get_template("modules/accounting/templates/cost_centers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Get parent name if parent_id provided
    parent_name = None
    parent_id = form_int(form, "parent_id")
    if parent_id is not None:
        try:
            parent = service.get_cost_center(parent_id)
            parent_name = parent.cost_center_name
        except NotFoundError:
            parent_name = None

    service.update_cost_center(
        cc_id,
        CostCenterUpdateData(
            cost_center_name=form_str(form, "cost_center_name"),
            cost_center_number=form_str(form, "cost_center_code") or None,
            parent_cost_center=parent_name,
            disabled=not bool(form_str(form, "is_active")),
        ),
    )
    db.commit()

    set_flash(response, "Cost center updated successfully", "success")
    return RedirectResponse(url="/accounting/cost-centers", status_code=303)
