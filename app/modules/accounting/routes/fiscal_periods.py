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
    is_htmx_request, HTTPException, set_flash,
    FiscalPeriod, FiscalPeriodStatus, FiscalYear, GLEntry,
    func, datetime, Decimal, selectinload,
)

router = APIRouter()


def get_fiscal_period_stats(db) -> dict:
    """Calculate fiscal period statistics."""
    now = datetime.utcnow().date()

    total_periods = db.query(func.count(FiscalPeriod.id)).scalar() or 0
    open_periods = db.query(func.count(FiscalPeriod.id)).filter(
        FiscalPeriod.status == FiscalPeriodStatus.OPEN
    ).scalar() or 0
    closed_periods = db.query(func.count(FiscalPeriod.id)).filter(
        FiscalPeriod.status.in_([FiscalPeriodStatus.SOFT_CLOSED, FiscalPeriodStatus.HARD_CLOSED])
    ).scalar() or 0

    # Current period
    current_period = db.query(FiscalPeriod).filter(
        FiscalPeriod.start_date <= now,
        FiscalPeriod.end_date >= now,
    ).first()

    return {
        "total_periods": total_periods,
        "open_periods": open_periods,
        "closed_periods": closed_periods,
        "current_period": current_period,
    }


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
    query = db.query(FiscalPeriod)

    # Filter by year
    if year:
        fiscal_year = db.query(FiscalYear).filter(FiscalYear.year == year).first()
        if fiscal_year:
            query = query.filter(FiscalPeriod.fiscal_year_id == fiscal_year.id)

    # Filter by status
    if status:
        try:
            period_status = FiscalPeriodStatus(status)
            query = query.filter(FiscalPeriod.status == period_status)
        except ValueError:
            pass

    periods = query.order_by(FiscalPeriod.start_date.desc()).all()

    # Get fiscal years for filter
    fiscal_years = db.query(FiscalYear).filter(FiscalYear.disabled == False).order_by(FiscalYear.year.desc()).all()
    year_options = [{"value": fy.year, "label": fy.year} for fy in fiscal_years]

    # Status options
    status_options = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in FiscalPeriodStatus]

    stats = get_fiscal_period_stats(db)

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
    period = db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()

    if not period:
        raise HTTPException(status_code=404, detail="Fiscal period not found")

    # Get GL entry counts for this period
    gl_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.posting_date >= period.start_date,
        GLEntry.posting_date <= period.end_date,
        GLEntry.is_cancelled == False,
    ).scalar() or 0

    # Get totals for this period
    period_debit = db.query(func.sum(GLEntry.debit)).filter(
        GLEntry.posting_date >= period.start_date,
        GLEntry.posting_date <= period.end_date,
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    period_credit = db.query(func.sum(GLEntry.credit)).filter(
        GLEntry.posting_date >= period.start_date,
        GLEntry.posting_date <= period.end_date,
        GLEntry.is_cancelled == False,
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods"},
        {"label": period.period_name, "href": f"/accounting/fiscal-periods/{period_id}", "current": True},
    ])
    context["period"] = period
    context["gl_count"] = gl_count
    context["period_debit"] = period_debit
    context["period_credit"] = period_credit

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
    period = db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Fiscal period not found")

    if period.status == FiscalPeriodStatus.HARD_CLOSED:
        set_flash(response, "This period is permanently closed and cannot be modified.", "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    period.status = FiscalPeriodStatus.SOFT_CLOSED
    period.closed_at = datetime.utcnow()
    period.closed_by_id = user.id
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
    period = db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Fiscal period not found")

    if period.status == FiscalPeriodStatus.HARD_CLOSED:
        set_flash(response, "This period is permanently closed and cannot be reopened.", "error")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    if period.status == FiscalPeriodStatus.OPEN:
        set_flash(response, "This period is already open.", "warning")
        return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)

    period.status = FiscalPeriodStatus.OPEN
    period.closed_at = None
    period.closed_by_id = None
    db.commit()

    set_flash(response, f"Period {period.period_name} has been reopened.", "success")
    return RedirectResponse(url=f"/accounting/fiscal-periods/{period_id}", status_code=303)
