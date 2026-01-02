"""
Tax routes for accounting module.

Provides UI pages for:
- Tax codes management
- Tax filing periods
- Tax templates
- Tax dashboard
"""
from fastapi import APIRouter, Query
from datetime import date

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str, form_int, form_decimal,
    func, or_,
)

router = APIRouter()


# =============================================================================
# TAX CODES
# =============================================================================

def get_tax_code_stats(db) -> dict:
    """Calculate tax code statistics."""
    from app.models.tax import TaxCode, TaxType

    total = db.query(func.count(TaxCode.id)).scalar() or 0
    active = db.query(func.count(TaxCode.id)).filter(TaxCode.is_active == True).scalar() or 0
    sales = db.query(func.count(TaxCode.id)).filter(
        TaxCode.tax_type.in_([TaxType.SALES, TaxType.BOTH])
    ).scalar() or 0
    purchase = db.query(func.count(TaxCode.id)).filter(
        TaxCode.tax_type.in_([TaxType.PURCHASE, TaxType.BOTH])
    ).scalar() or 0

    return {
        "total": total,
        "active": active,
        "sales": sales,
        "purchase": purchase,
    }


@router.get("/tax-codes", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_codes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    tax_type: Optional[str] = Query(None),
    is_active: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax codes list page."""
    from app.models.tax import TaxCode, TaxType

    query = db.query(TaxCode)

    if q:
        query = query.filter(
            or_(
                TaxCode.code.ilike(f"%{q}%"),
                TaxCode.name.ilike(f"%{q}%"),
            )
        )

    if tax_type:
        try:
            tt = TaxType(tax_type.lower())
            query = query.filter(TaxCode.tax_type == tt)
        except ValueError:
            pass

    if is_active is not None:
        query = query.filter(TaxCode.is_active == (is_active == "true"))

    total = query.count()
    tax_codes = query.order_by(TaxCode.code).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Codes"},
    ])
    context["tax_codes"] = tax_codes
    context["stats"] = get_tax_code_stats(db)
    context["current_search"] = q
    context["current_type"] = tax_type
    context["current_active"] = is_active
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/tax/partials/tax_codes_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/tax/pages/codes_list.html")

    return HTMLResponse(template.render(context))


@router.get("/tax-codes/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_codes_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    tax_type: Optional[str] = Query(None),
    is_active: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax codes table HTMX partial."""
    from app.models.tax import TaxCode, TaxType

    query = db.query(TaxCode)

    if q:
        query = query.filter(
            or_(
                TaxCode.code.ilike(f"%{q}%"),
                TaxCode.name.ilike(f"%{q}%"),
            )
        )

    if tax_type:
        try:
            tt = TaxType(tax_type.lower())
            query = query.filter(TaxCode.tax_type == tt)
        except ValueError:
            pass

    if is_active is not None:
        query = query.filter(TaxCode.is_active == (is_active == "true"))

    total = query.count()
    tax_codes = query.order_by(TaxCode.code).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["tax_codes"] = tax_codes
    context["current_search"] = q
    context["current_type"] = tax_type
    context["current_active"] = is_active
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/tax/partials/tax_codes_table.html")
    return HTMLResponse(template.render(context))


@router.get("/tax-codes/{tc_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_code_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tc_id: int,
):
    """Tax code detail page."""
    from app.models.tax import TaxCode

    tax_code = db.query(TaxCode).filter(TaxCode.id == tc_id).first()
    if not tax_code:
        raise HTTPException(status_code=404, detail="Tax code not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Codes", "href": "/accounting/tax-codes"},
        {"label": tax_code.code},
    ])
    context["tax_code"] = tax_code

    template = templates.get_template("modules/accounting/templates/tax/pages/code_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TAX FILING PERIODS
# =============================================================================

def get_filing_stats(db) -> dict:
    """Calculate filing period statistics."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus

    today = date.today()
    month_start = date(today.year, today.month, 1)

    filed_this_month = db.query(func.count(TaxFilingPeriod.id)).filter(
        TaxFilingPeriod.filed_at >= month_start
    ).scalar() or 0

    return {
        "filed_this_month": filed_this_month,
    }


def get_filing_dashboard(db) -> dict:
    """Get tax filing dashboard data."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    today = date.today()

    # Get summary by tax type
    summary_by_type = {}
    for tax_type in TaxFilingType:
        open_periods = db.query(TaxFilingPeriod).filter(
            TaxFilingPeriod.tax_type == tax_type,
            TaxFilingPeriod.status.in_([TaxFilingStatus.OPEN, TaxFilingStatus.FILED]),
        ).all()

        total_outstanding = sum(p.outstanding_amount for p in open_periods)
        overdue_count = sum(1 for p in open_periods if p.is_overdue)

        if open_periods or total_outstanding > 0:
            summary_by_type[tax_type.value] = {
                "open_periods": len(open_periods),
                "total_outstanding": float(total_outstanding),
                "overdue_count": overdue_count,
            }

    # Get upcoming due dates
    upcoming = db.query(TaxFilingPeriod).filter(
        TaxFilingPeriod.status == TaxFilingStatus.OPEN,
        TaxFilingPeriod.due_date >= today,
    ).order_by(TaxFilingPeriod.due_date).limit(5).all()

    # Get overdue filings
    overdue = db.query(TaxFilingPeriod).filter(
        TaxFilingPeriod.status == TaxFilingStatus.OPEN,
        TaxFilingPeriod.due_date < today,
    ).order_by(TaxFilingPeriod.due_date).all()

    total_outstanding = sum(s["total_outstanding"] for s in summary_by_type.values())
    total_overdue_count = sum(s["overdue_count"] for s in summary_by_type.values())

    return {
        "summary_by_type": summary_by_type,
        "total_outstanding": total_outstanding,
        "total_overdue_count": total_overdue_count,
        "upcoming_due": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "outstanding": float(p.outstanding_amount),
            }
            for p in upcoming
        ],
        "overdue": [
            {
                "id": p.id,
                "tax_type": p.tax_type.value,
                "period_name": p.period_name,
                "due_date": p.due_date.isoformat(),
                "days_overdue": (today - p.due_date).days,
                "outstanding": float(p.outstanding_amount),
            }
            for p in overdue
        ],
    }


@router.get("/tax/filing", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tax_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax filing periods list page."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    query = db.query(TaxFilingPeriod)

    if tax_type:
        try:
            tt = TaxFilingType(tax_type.lower())
            query = query.filter(TaxFilingPeriod.tax_type == tt)
        except ValueError:
            pass

    if status:
        try:
            st = TaxFilingStatus(status.lower())
            query = query.filter(TaxFilingPeriod.status == st)
        except ValueError:
            pass

    if year:
        query = query.filter(func.extract('year', TaxFilingPeriod.period_start) == year)

    total = query.count()
    periods = query.order_by(TaxFilingPeriod.due_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Get available years
    years_query = db.query(func.distinct(func.extract('year', TaxFilingPeriod.period_start))).all()
    years = sorted([int(y[0]) for y in years_query if y[0]], reverse=True)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing"},
    ])
    context["periods"] = periods
    context["stats"] = get_filing_stats(db)
    context["dashboard"] = get_filing_dashboard(db)
    context["years"] = years
    context["current_type"] = tax_type
    context["current_status"] = status
    context["current_year"] = year
    context["today"] = date.today()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/tax/partials/filing_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/tax/pages/filing_list.html")

    return HTMLResponse(template.render(context))


@router.get("/tax/filing/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tax_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax filing table HTMX partial."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus, TaxFilingType

    query = db.query(TaxFilingPeriod)

    if tax_type:
        try:
            tt = TaxFilingType(tax_type.lower())
            query = query.filter(TaxFilingPeriod.tax_type == tt)
        except ValueError:
            pass

    if status:
        try:
            st = TaxFilingStatus(status.lower())
            query = query.filter(TaxFilingPeriod.status == st)
        except ValueError:
            pass

    if year:
        query = query.filter(func.extract('year', TaxFilingPeriod.period_start) == year)

    total = query.count()
    periods = query.order_by(TaxFilingPeriod.due_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["periods"] = periods
    context["today"] = date.today()
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/tax/partials/filing_table.html")
    return HTMLResponse(template.render(context))


@router.get("/tax/filing/{period_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Tax filing period detail page."""
    from app.models.tax import TaxFilingPeriod, TaxPayment

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    payments = db.query(TaxPayment).filter(
        TaxPayment.filing_period_id == period_id
    ).order_by(TaxPayment.payment_date.desc()).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing", "href": "/accounting/tax/filing"},
        {"label": period.period_name},
    ])
    context["period"] = period
    context["payments"] = payments
    context["today"] = date.today()

    template = templates.get_template("modules/accounting/templates/tax/pages/filing_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/tax/filing/{period_id}/file", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_mark_filed(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Mark a tax filing period as filed."""
    from app.models.tax import TaxFilingPeriod, TaxFilingStatus
    from datetime import datetime, timezone

    period = db.query(TaxFilingPeriod).filter(TaxFilingPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Tax filing period not found")

    if period.status != TaxFilingStatus.OPEN:
        set_flash(response, f"Period is already {period.status.value}", "warning")
        return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)

    period.status = TaxFilingStatus.FILED
    period.filed_at = datetime.now(timezone.utc)
    period.filed_by_id = user.id
    db.commit()

    set_flash(response, "Tax period marked as filed", "success")

    if is_htmx_request(request):
        return RedirectResponse(url="/accounting/tax/filing", status_code=303)
    return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)
