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
    Invoice, InvoiceStatus, PurchaseInvoice, PurchaseInvoiceStatus,
    datetime, Decimal, date,
)

router = APIRouter()


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


@router.get("/receivables", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def ar_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounts Receivable Aging dashboard."""
    # Get outstanding invoices
    outstanding_invoices = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
        Invoice.balance > 0,
    ).order_by(Invoice.due_date).all()

    buckets = calculate_aging_buckets(outstanding_invoices)

    total_outstanding = sum(b["amount"] for b in buckets.values())
    total_overdue = buckets["1_30"]["amount"] + buckets["31_60"]["amount"] + buckets["61_90"]["amount"] + buckets["over_90"]["amount"]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Receivables Aging", "href": "/accounting/receivables", "current": True},
    ])
    context["invoices"] = outstanding_invoices
    context["buckets"] = buckets
    context["total_outstanding"] = total_outstanding
    context["total_overdue"] = total_overdue

    template = templates.get_template("modules/accounting/templates/aging/pages/ar_aging.html")
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
    # Get outstanding purchase invoices
    outstanding_bills = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.status.in_([PurchaseInvoiceStatus.SUBMITTED, PurchaseInvoiceStatus.UNPAID, PurchaseInvoiceStatus.OVERDUE]),
        PurchaseInvoice.outstanding_amount > 0,
    ).order_by(PurchaseInvoice.due_date).all()

    buckets = calculate_aging_buckets(outstanding_bills)

    total_outstanding = sum(b["amount"] for b in buckets.values())
    total_overdue = buckets["1_30"]["amount"] + buckets["31_60"]["amount"] + buckets["61_90"]["amount"] + buckets["over_90"]["amount"]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Payables Aging", "href": "/accounting/payables", "current": True},
    ])
    context["bills"] = outstanding_bills
    context["buckets"] = buckets
    context["total_outstanding"] = total_outstanding
    context["total_overdue"] = total_overdue
    context["today"] = date.today()
    context["now_date"] = date.today()

    template = templates.get_template("modules/accounting/templates/aging/pages/ap_aging.html")
    return HTMLResponse(template.render(context))
