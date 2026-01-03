"""
Fiscal Periods routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs,
    HTTPException, set_flash,
    FiscalPeriodStatus,
)
from app.services.accounting import FiscalService
from app.services.accounting.fiscal_types import FiscalPeriodFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.period_manager import PeriodManager, PeriodError

router = APIRouter()


@router.get("/fiscal-periods", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def fiscal_periods_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    year: Optional[str] = Query(None, description="Filter by fiscal year"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Fiscal periods list page."""
    fiscal_service = FiscalService(db, user)
    filters = FiscalPeriodFilters(year=year, status=status)
    try:
        periods = fiscal_service.list_fiscal_periods(filters)
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        filters.status = None
        periods = fiscal_service.list_fiscal_periods(filters)

    # Get fiscal years for filter
    fiscal_years = fiscal_service.list_fiscal_years(include_disabled=False)
    year_options = [{"value": fy.year, "label": fy.year} for fy in fiscal_years]

    # Status options
    status_options = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in FiscalPeriodStatus]

    stats = fiscal_service.get_fiscal_period_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods", "current": True},
    ])
    context["periods"] = periods
    context["year_options"] = year_options
    context["status_options"] = status_options
    context["current_year"] = year or ""
    context["current_status"] = status or ""
    context["stats"] = stats

    template = templates.get_template("modules/accounting/templates/fiscal_periods/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/fiscal-periods/{period_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def fiscal_period_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Fiscal period detail page."""
    fiscal_service = FiscalService(db, user)
    try:
        period = fiscal_service.get_fiscal_period(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    totals = fiscal_service.get_fiscal_period_totals(period)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods"},
        {"label": period.period_name, "href": f"/accounting/fiscal-periods/{period_id}", "current": True},
    ])
    context["period"] = period
    context["gl_count"] = totals["gl_count"]
    context["period_debit"] = totals["period_debit"]
    context["period_credit"] = totals["period_credit"]

    template = templates.get_template("modules/accounting/templates/fiscal_periods/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.post("/fiscal-periods/{period_id}/close", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def fiscal_period_close(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    period_id: int,
):
    """Close a fiscal period (soft close)."""
    fiscal_service = FiscalService(db, user)
    try:
        period = fiscal_service.get_fiscal_period(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if period.status == FiscalPeriodStatus.HARD_CLOSED:
        set_flash(response, "This period is permanently closed and cannot be modified.", "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    manager = PeriodManager(db)
    try:
        manager.close_period(period_id, user.id, soft_close=True)
    except PeriodError as exc:
        set_flash(response, str(exc), "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)
    db.commit()

    set_flash(response, f"Period {period.period_name} has been closed.", "success")
    return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)


@router.post("/fiscal-periods/{period_id}/reopen", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def fiscal_period_reopen(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    period_id: int,
):
    """Reopen a soft-closed fiscal period."""
    fiscal_service = FiscalService(db, user)
    try:
        period = fiscal_service.get_fiscal_period(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if period.status == FiscalPeriodStatus.HARD_CLOSED:
        set_flash(response, "This period is permanently closed and cannot be reopened.", "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    if period.status == FiscalPeriodStatus.OPEN:
        set_flash(response, "This period is already open.", "warning")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    manager = PeriodManager(db)
    try:
        manager.reopen_period(period_id, user.id)
    except PeriodError as exc:
        set_flash(response, str(exc), "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)
    db.commit()

    set_flash(response, f"Period {period.period_name} has been reopened.", "success")
    return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)
