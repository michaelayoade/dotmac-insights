"""
Performance management web routes.

Provides SSR pages for KPI/KRA scorecards and performance reviews.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.models.performance import (
    EvaluationPeriod, EvaluationPeriodStatus, EvaluationPeriodType,
    EmployeeScorecardInstance, ScorecardInstanceStatus,
    ScorecardTemplate, KRADefinition, KPIDefinition
)

router = APIRouter(prefix="/performance", tags=["performance-web"])
templates = get_template_env()

RequirePerformanceRead = Depends(require_scope("performance:read"))
RequirePerformanceWrite = Depends(require_scope("performance:write"))


@router.get("", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def evaluation_periods_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    period_type: Optional[str] = Query(None, description="Filter by period type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Evaluation periods list page."""
    query = select(EvaluationPeriod)

    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                EvaluationPeriod.code.ilike(search),
                EvaluationPeriod.name.ilike(search),
            )
        )

    if status:
        try:
            status_enum = EvaluationPeriodStatus(status)
            query = query.where(EvaluationPeriod.status == status_enum)
        except ValueError:
            pass

    if period_type:
        try:
            type_enum = EvaluationPeriodType(period_type)
            query = query.where(EvaluationPeriod.period_type == type_enum)
        except ValueError:
            pass

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(EvaluationPeriod.start_date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    periods = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Performance Reviews"
    context["periods"] = periods
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["period_type_filter"] = period_type or ""

    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in EvaluationPeriodStatus
    ]
    context["period_type_options"] = [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in EvaluationPeriodType
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("performance/partials/periods_table.html")
    else:
        template = templates.get_template("performance/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def evaluation_periods_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Evaluation periods table partial."""
    return await evaluation_periods_list(
        request, response, user, csrf_token, db,
        q, status, period_type, page, per_page
    )


@router.get("/scorecards", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def scorecards_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Employee scorecards list page."""
    query = select(EmployeeScorecardInstance)

    if status:
        try:
            status_enum = ScorecardInstanceStatus(status)
            query = query.where(EmployeeScorecardInstance.status == status_enum)
        except ValueError:
            pass

    if period_id:
        query = query.where(EmployeeScorecardInstance.evaluation_period_id == period_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(EmployeeScorecardInstance.created_at.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    scorecards = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Employee Scorecards"
    context["scorecards"] = scorecards
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["period_id_filter"] = period_id

    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ScorecardInstanceStatus
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("performance/partials/scorecards_table.html")
    else:
        template = templates.get_template("performance/pages/scorecards_list.html")

    return HTMLResponse(template.render(context))


@router.get("/templates", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def scorecard_templates_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Scorecard templates list page."""
    query = select(ScorecardTemplate)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(ScorecardTemplate.name.asc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    scorecard_templates = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Scorecard Templates"
    context["templates"] = scorecard_templates
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("performance/pages/templates_list.html")
    return HTMLResponse(template.render(context))


@router.get("/kras", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def kra_definitions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """KRA definitions list page."""
    query = select(KRADefinition).where(KRADefinition.is_active == True)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(KRADefinition.name.asc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    kras = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Key Result Areas"
    context["kras"] = kras
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("performance/pages/kras_list.html")
    return HTMLResponse(template.render(context))


@router.get("/kpis", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def kpi_definitions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """KPI definitions list page."""
    query = select(KPIDefinition)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(KPIDefinition.name.asc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    kpis = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Key Performance Indicators"
    context["kpis"] = kpis
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    template = templates.get_template("performance/pages/kpis_list.html")
    return HTMLResponse(template.render(context))


@router.get("/{period_id}", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def evaluation_period_detail(
    period_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Evaluation period detail page."""
    query = select(EvaluationPeriod).where(EvaluationPeriod.id == period_id)
    result = db.execute(query)
    period = result.scalar_one_or_none()

    if not period:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Evaluation period not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get scorecards for this period
    scorecards_query = (
        select(EmployeeScorecardInstance)
        .where(EmployeeScorecardInstance.evaluation_period_id == period_id)
        .order_by(EmployeeScorecardInstance.created_at.desc())
        .limit(10)
    )
    scorecards_result = db.execute(scorecards_query)
    scorecards = scorecards_result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Period: {period.name}"
    context["period"] = period
    context["scorecards"] = scorecards

    template = templates.get_template("performance/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/scorecards/{scorecard_id}", response_class=HTMLResponse, dependencies=[RequirePerformanceRead])
async def scorecard_detail(
    scorecard_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Employee scorecard detail page."""
    query = (
        select(EmployeeScorecardInstance)
        .options(
            selectinload(EmployeeScorecardInstance.kpi_results),
            selectinload(EmployeeScorecardInstance.kra_results)
        )
        .where(EmployeeScorecardInstance.id == scorecard_id)
    )
    result = db.execute(query)
    scorecard = result.scalar_one_or_none()

    if not scorecard:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Scorecard not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Scorecard #{scorecard.id}"
    context["scorecard"] = scorecard

    template = templates.get_template("performance/pages/scorecard_detail.html")
    return HTMLResponse(template.render(context))
