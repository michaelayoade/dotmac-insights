"""
Audit Log routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request,
    AuditLog, AuditAction,
    func, or_, datetime,
)

router = APIRouter()


def get_audit_doc_type_options() -> list:
    """Get document type options for audit log filter."""
    return [
        {"value": "JournalEntry", "label": "Journal Entry"},
        {"value": "Invoice", "label": "Invoice"},
        {"value": "Payment", "label": "Payment"},
        {"value": "PurchaseInvoice", "label": "Purchase Invoice"},
        {"value": "BankTransaction", "label": "Bank Transaction"},
        {"value": "BankReconciliation", "label": "Bank Reconciliation"},
        {"value": "Account", "label": "Account"},
        {"value": "FiscalPeriod", "label": "Fiscal Period"},
    ]


def get_audit_action_options() -> list:
    """Get action options for audit log filter."""
    return [
        {"value": action.value, "label": action.value.replace("_", " ").title()}
        for action in AuditAction
    ]


@router.get("/audit-log", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def audit_log_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Audit log list page."""
    query = db.query(AuditLog)

    if q:
        query = query.filter(
            or_(
                AuditLog.document_name.ilike(f"%{q}%"),
                AuditLog.user_name.ilike(f"%{q}%"),
                AuditLog.user_email.ilike(f"%{q}%"),
            )
        )

    if doc_type:
        query = query.filter(AuditLog.doctype == doc_type)

    if action:
        query = query.filter(AuditLog.action == AuditAction(action))

    if date_from:
        try:
            from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(AuditLog.timestamp >= from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.timestamp <= to_dt)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Audit Log", "href": "/accounting/audit-log", "current": True},
    ])
    context["entries"] = entries
    context["current_search"] = q
    context["current_doc_type"] = doc_type
    context["current_action"] = action
    context["current_date_from"] = date_from
    context["current_date_to"] = date_to
    context["doc_type_options"] = get_audit_doc_type_options()
    context["action_options"] = get_audit_action_options()
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/audit_log/partials/audit_log_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/audit_log/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/audit-log/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def audit_log_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Audit log table HTMX partial."""
    query = db.query(AuditLog)

    if q:
        query = query.filter(
            or_(
                AuditLog.document_name.ilike(f"%{q}%"),
                AuditLog.user_name.ilike(f"%{q}%"),
                AuditLog.user_email.ilike(f"%{q}%"),
            )
        )

    if doc_type:
        query = query.filter(AuditLog.doctype == doc_type)

    if action:
        query = query.filter(AuditLog.action == AuditAction(action))

    if date_from:
        try:
            from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(AuditLog.timestamp >= from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.timestamp <= to_dt)
        except ValueError:
            pass

    total = query.count()
    entries = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["entries"] = entries
    context["current_search"] = q
    context["current_doc_type"] = doc_type
    context["current_action"] = action
    context["current_date_from"] = date_from
    context["current_date_to"] = date_to
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/audit_log/partials/audit_log_table.html")
    return HTMLResponse(template.render(context))
