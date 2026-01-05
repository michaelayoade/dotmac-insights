"""
AR/AP Aging routes for accounting module.
"""
from fastapi import APIRouter
from typing import TypedDict

from ._deps import (
    Request, Response, HTMLResponse,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs,
    datetime, Decimal, date,
)
from app.services.accounting import AccountingSettingsService, PayablesService, ReceivablesService

router = APIRouter()


def _get_receivables_service(db: DB, user: SessionUser) -> ReceivablesService:
    settings_service = AccountingSettingsService(db, user)
    return ReceivablesService(db, settings_service, user)


def _get_payables_service(db: DB, user: SessionUser) -> PayablesService:
    settings_service = AccountingSettingsService(db, user)
    return PayablesService(db, settings_service, user)


class AgingBucket(TypedDict):
    count: int
    amount: Decimal


def calculate_aging_buckets(invoices, date_field: str = "due_date") -> dict[str, AgingBucket]:
    """Calculate aging buckets for invoices."""
    now = datetime.utcnow().date()
    buckets: dict[str, AgingBucket] = {
        "current": {"count": 0, "amount": Decimal("0")},
        "1_30": {"count": 0, "amount": Decimal("0")},
        "31_60": {"count": 0, "amount": Decimal("0")},
        "61_90": {"count": 0, "amount": Decimal("0")},
        "over_90": {"count": 0, "amount": Decimal("0")},
    }

    for inv in invoices:
        due_date = getattr(inv, date_field, None)
        raw_balance = getattr(inv, "balance", None) or getattr(inv, "outstanding_amount", None) or Decimal("0")
        balance = Decimal(str(raw_balance))

        if not due_date or balance <= 0:
            continue

        if isinstance(due_date, datetime):
            due_date = due_date.date()

        days_overdue = (now - due_date).days

        if days_overdue <= 0:
            buckets["current"]["count"] += 1
            buckets["current"]["amount"] += balance
        elif days_overdue <= 30:
            buckets["1_30"]["count"] += 1
            buckets["1_30"]["amount"] += balance
        elif days_overdue <= 60:
            buckets["31_60"]["count"] += 1
            buckets["31_60"]["amount"] += balance
        elif days_overdue <= 90:
            buckets["61_90"]["count"] += 1
            buckets["61_90"]["amount"] += balance
        else:
            buckets["over_90"]["count"] += 1
            buckets["over_90"]["amount"] += balance

    return buckets


async def _render_ar_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    breadcrumb_href: str,
):
    """Render Accounts Receivable Aging dashboard."""
    receivables_service = _get_receivables_service(db, user)
    outstanding_invoices = receivables_service.list_outstanding_invoices()

    today = date.today()
    for inv in outstanding_invoices:
        due_date = getattr(inv, "due_date", None)
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        inv.aging_days = (today - due_date).days if due_date else 0

    buckets = calculate_aging_buckets(outstanding_invoices)

    total_outstanding = sum(b["amount"] for b in buckets.values())
    total_overdue = buckets["1_30"]["amount"] + buckets["31_60"]["amount"] + buckets["61_90"]["amount"] + buckets["over_90"]["amount"]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Receivables Aging", "href": breadcrumb_href, "current": True},
    ])
    context["invoices"] = outstanding_invoices
    context["buckets"] = buckets
    context["total_outstanding"] = total_outstanding
    context["total_overdue"] = total_overdue
    context["today"] = today
    context["now_date"] = today

    template = templates.get_template("modules/accounting/templates/aging/pages/ar_aging.html")
    return HTMLResponse(template.render(context))


@router.get("/receivables", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def ar_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounts Receivable Aging dashboard."""
    return await _render_ar_aging(
        request,
        response,
        user,
        csrf_token,
        db,
        breadcrumb_href="/accounting/receivables",
    )


@router.get("/aging/ar", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def ar_aging_alias(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounts Receivable Aging dashboard (alias)."""
    return await _render_ar_aging(
        request,
        response,
        user,
        csrf_token,
        db,
        breadcrumb_href="/accounting/aging/ar",
    )


async def _render_ap_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    breadcrumb_href: str,
):
    """Render Accounts Payable Aging dashboard."""
    payables_service = _get_payables_service(db, user)
    outstanding_bills = payables_service.list_outstanding_bills()

    today = date.today()
    for bill in outstanding_bills:
        due_date = getattr(bill, "due_date", None)
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        bill.aging_days = (today - due_date).days if due_date else 0

    buckets = calculate_aging_buckets(outstanding_bills)

    total_outstanding = sum(b["amount"] for b in buckets.values())
    total_overdue = buckets["1_30"]["amount"] + buckets["31_60"]["amount"] + buckets["61_90"]["amount"] + buckets["over_90"]["amount"]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Payables Aging", "href": breadcrumb_href, "current": True},
    ])
    context["bills"] = outstanding_bills
    context["buckets"] = buckets
    context["total_outstanding"] = total_outstanding
    context["total_overdue"] = total_overdue
    context["today"] = today
    context["now_date"] = today

    template = templates.get_template("modules/accounting/templates/aging/pages/ap_aging.html")
    return HTMLResponse(template.render(context))


@router.get("/payables", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def ap_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounts Payable Aging dashboard."""
    return await _render_ap_aging(
        request,
        response,
        user,
        csrf_token,
        db,
        breadcrumb_href="/accounting/payables",
    )


@router.get("/aging/ap", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def ap_aging_alias(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounts Payable Aging dashboard (alias)."""
    return await _render_ap_aging(
        request,
        response,
        user,
        csrf_token,
        db,
        breadcrumb_href="/accounting/aging/ap",
    )
