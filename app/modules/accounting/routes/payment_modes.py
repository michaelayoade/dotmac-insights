"""
Payment Modes routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str,
)
from app.models.accounting import PaymentModeType
from app.services.accounting import PaymentModeService
from app.services.accounting.payment_modes_types import (
    PaymentModeFilters,
    PaymentModeCreateData,
    PaymentModeUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def _get_service(db: DB, user: SessionUser) -> PaymentModeService:
    return PaymentModeService(db, user)


def _get_mode_type_options() -> list:
    """Get list of payment mode type options."""
    return [
        {"value": "", "label": "-- Select Type --"},
        {"value": "cash", "label": "Cash"},
        {"value": "bank", "label": "Bank"},
        {"value": "general", "label": "General"},
    ]


@router.get("/payment-modes", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_modes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    include_disabled: bool = Query(False, description="Include disabled"),
    mode_type: Optional[str] = Query(None, description="Mode type filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payment modes list page."""
    service = _get_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    # Parse mode type filter
    parsed_mode_type = None
    if mode_type:
        try:
            parsed_mode_type = PaymentModeType(mode_type.lower())
        except ValueError:
            pass

    filters = PaymentModeFilters(
        include_disabled=include_disabled,
        search=q,
        mode_type=parsed_mode_type,
    )

    result = service.list_payment_modes(filters, pagination)
    modes = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Modes", "href": None},
    ])
    context["page_title"] = "Payment Modes"
    context["modes"] = modes
    context["total"] = total
    context["current_search"] = q
    context["current_include_disabled"] = include_disabled
    context["current_mode_type"] = mode_type
    context["mode_type_options"] = _get_mode_type_options()
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=total,
        base_url="/accounting/payment-modes",
    )

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/payment_modes/partials/modes_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/payment_modes/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/payment-modes/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_modes_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    include_disabled: bool = Query(False, description="Include disabled"),
    mode_type: Optional[str] = Query(None, description="Mode type filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payment modes table partial (HTMX)."""
    service = _get_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    # Parse mode type filter
    parsed_mode_type = None
    if mode_type:
        try:
            parsed_mode_type = PaymentModeType(mode_type.lower())
        except ValueError:
            pass

    filters = PaymentModeFilters(
        include_disabled=include_disabled,
        search=q,
        mode_type=parsed_mode_type,
    )

    result = service.list_payment_modes(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["modes"] = result.items
    context["total"] = result.total
    context["current_search"] = q
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=result.total,
        base_url="/accounting/payment-modes",
    )

    template = templates.get_template("modules/accounting/templates/payment_modes/partials/modes_table.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-modes/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_form_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New payment mode form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Modes", "href": "/accounting/payment-modes"},
        {"label": "New", "href": None},
    ])
    context["page_title"] = "New Payment Mode"
    context["mode"] = None
    context["mode_type_options"] = _get_mode_type_options()
    context["is_edit"] = False

    template = templates.get_template("modules/accounting/templates/payment_modes/pages/form.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-modes/{mode_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_modes_detail(
    mode_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Payment mode detail page."""
    service = _get_service(db, user)

    try:
        mode = service.get_payment_mode(mode_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment mode not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Modes", "href": "/accounting/payment-modes"},
        {"label": mode.mode_of_payment, "href": None},
    ])
    context["page_title"] = f"Payment Mode: {mode.mode_of_payment}"
    context["mode"] = mode

    template = templates.get_template("modules/accounting/templates/payment_modes/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-modes/{mode_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_form_edit(
    mode_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Edit payment mode form."""
    service = _get_service(db, user)

    try:
        mode = service.get_payment_mode(mode_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment mode not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Modes", "href": "/accounting/payment-modes"},
        {"label": mode.mode_of_payment, "href": f"/accounting/payment-modes/{mode_id}"},
        {"label": "Edit", "href": None},
    ])
    context["page_title"] = f"Edit: {mode.mode_of_payment}"
    context["mode"] = mode
    context["mode_type_options"] = _get_mode_type_options()
    context["is_edit"] = True

    template = templates.get_template("modules/accounting/templates/payment_modes/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/payment-modes", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Create new payment mode."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    service = _get_service(db, user)

    mode_of_payment = form_str(form, "mode_of_payment")
    mode_type_str = form_str(form, "mode_type")
    enabled = form_str(form, "enabled") == "on"

    # Parse mode type
    mode_type = None
    if mode_type_str:
        try:
            mode_type = PaymentModeType(mode_type_str.lower())
        except ValueError:
            pass

    try:
        create_data = PaymentModeCreateData(
            mode_of_payment=mode_of_payment,
            mode_type=mode_type,
            enabled=enabled,
        )
        mode = service.create_payment_mode(create_data)
        db.commit()

        set_flash(response, "Payment mode created successfully", "success")
        return RedirectResponse(
            url=f"/accounting/payment-modes/{mode.id}",
            status_code=303,
        )
    except ValidationError as e:
        db.rollback()
        set_flash(response, str(e), "error")
        return RedirectResponse(
            url="/accounting/payment-modes/new",
            status_code=303,
        )


@router.post("/payment-modes/{mode_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_update(
    mode_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Update payment mode."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    service = _get_service(db, user)

    mode_of_payment = form_str(form, "mode_of_payment") or None
    mode_type_str = form_str(form, "mode_type")
    enabled = form_str(form, "enabled") == "on"

    # Parse mode type
    mode_type = None
    if mode_type_str:
        try:
            mode_type = PaymentModeType(mode_type_str.lower())
        except ValueError:
            pass

    try:
        update_data = PaymentModeUpdateData(
            mode_of_payment=mode_of_payment,
            mode_type=mode_type,
            enabled=enabled,
        )
        service.update_payment_mode(mode_id, update_data)
        db.commit()

        set_flash(response, "Payment mode updated successfully", "success")
        return RedirectResponse(
            url=f"/accounting/payment-modes/{mode_id}",
            status_code=303,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment mode not found")
    except ValidationError as e:
        db.rollback()
        set_flash(response, str(e), "error")
        return RedirectResponse(
            url=f"/accounting/payment-modes/{mode_id}/edit",
            status_code=303,
        )


@router.post("/payment-modes/{mode_id}/toggle", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_toggle(
    mode_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Toggle payment mode enabled/disabled status."""
    await validate_csrf(request, csrf_protect)

    service = _get_service(db, user)

    try:
        mode = service.get_payment_mode(mode_id)
        if mode.enabled:
            service.disable_payment_mode(mode_id)
            message = "Payment mode disabled"
        else:
            service.enable_payment_mode(mode_id)
            message = "Payment mode enabled"
        db.commit()
        set_flash(response, message, "success")
    except NotFoundError:
        set_flash(response, "Payment mode not found", "error")

    return RedirectResponse(url="/accounting/payment-modes", status_code=303)


@router.post("/payment-modes/{mode_id}/delete", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_modes_delete(
    mode_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Delete (disable) payment mode."""
    await validate_csrf(request, csrf_protect)

    service = _get_service(db, user)

    try:
        service.disable_payment_mode(mode_id)
        db.commit()
        set_flash(response, "Payment mode disabled successfully", "success")
    except NotFoundError:
        set_flash(response, "Payment mode not found", "error")

    return RedirectResponse(url="/accounting/payment-modes", status_code=303)
