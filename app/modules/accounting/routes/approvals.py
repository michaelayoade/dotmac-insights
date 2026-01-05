"""
Approval Workflows routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    HTTPException, set_flash, validate_csrf, form_str, form_int, form_decimal,
    ApprovalStatus,
)
from app.services.accounting import ApprovalsService
from app.services.accounting.web_services import AccountingApprovalsWebService
from app.services.accounting.approvals_types import (
    ApprovalListFilters,
    ControlsUpdateData,
    WorkflowCreateData,
    WorkflowFilters,
    WorkflowStepCreateData,
    WorkflowUpdateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def get_approval_doctype_options():
    """Get document type options for approval workflows."""
    return [
        {"value": "journal_entry", "label": "Journal Entry"},
        {"value": "expense", "label": "Expense"},
        {"value": "payment", "label": "Payment"},
        {"value": "supplier_payment", "label": "Supplier Payment"},
        {"value": "invoice", "label": "Invoice"},
        {"value": "purchase_invoice", "label": "Purchase Invoice"},
        {"value": "credit_note", "label": "Credit Note"},
        {"value": "debit_note", "label": "Debit Note"},
        {"value": "bank_transaction", "label": "Bank Transaction"},
    ]


def _get_approvals_service(db: DB, user: SessionUser) -> ApprovalsService:
    return ApprovalsService(db, user)


def _get_approvals_web_service(db: DB, user: SessionUser) -> AccountingApprovalsWebService:
    return AccountingApprovalsWebService(db, _get_approvals_service(db, user))


# --- Pending Approvals ---

@router.get("/approvals", response_class=HTMLResponse)
async def approvals_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    doctype: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """Pending approvals list page."""
    service = _get_approvals_service(db, user)
    filters = ApprovalListFilters(doctype=doctype)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = service.list_pending_approvals(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["approvals"] = result.items
    context["stats"] = service.get_stats()
    context["doctype_options"] = get_approval_doctype_options()
    context["current_doctype"] = doctype
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/approvals/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/approvals/table", response_class=HTMLResponse)
async def approvals_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    doctype: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """Approvals table HTMX partial."""
    service = _get_approvals_service(db, user)
    filters = ApprovalListFilters(doctype=doctype)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = service.list_pending_approvals(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["approvals"] = result.items
    context["current_doctype"] = doctype
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/approvals/partials/approvals_table.html")
    return HTMLResponse(template.render(context))


@router.get("/approvals/{doctype}/{document_id}", response_class=HTMLResponse)
async def approval_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    doctype: str,
    document_id: int,
    _: None = RequireAccountingRead,
):
    """Document approval detail page."""
    service = _get_approvals_service(db, user)
    try:
        approval, document, workflow_steps, approval_history = service.get_approval_detail(
            doctype, document_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    can_approve = approval.status == ApprovalStatus.PENDING

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["approval"] = approval
    context["document"] = document
    context["doctype"] = doctype
    context["document_id"] = document_id
    context["workflow_steps"] = workflow_steps
    context["approval_history"] = approval_history
    context["can_approve"] = can_approve

    template = templates.get_template("modules/accounting/templates/approvals/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.post("/approvals/{doctype}/{document_id}/approve")
async def approve_document(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    doctype: str,
    document_id: int,
    _: None = RequireAccountingWrite,
):
    """Approve a document."""
    form_data = await request.form()
    await validate_csrf(request)

    remarks = form_str(form_data, "remarks")
    web_service = _get_approvals_web_service(db, user)
    try:
        web_service.approve_document(doctype, document_id, user.id, remarks)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    set_flash(response, "Document approved successfully", "success")
    return RedirectResponse(url="/accounting/approvals", status_code=303)


@router.post("/approvals/{doctype}/{document_id}/reject")
async def reject_document(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    doctype: str,
    document_id: int,
    _: None = RequireAccountingWrite,
):
    """Reject a document."""
    form_data = await request.form()
    await validate_csrf(request)

    remarks = form_str(form_data, "remarks")
    web_service = _get_approvals_web_service(db, user)
    try:
        web_service.reject_document(doctype, document_id, user.id, remarks)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    set_flash(response, "Document rejected", "warning")
    return RedirectResponse(url="/accounting/approvals", status_code=303)


# --- Workflow Configuration ---

@router.get("/workflows", response_class=HTMLResponse)
async def workflows_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    doctype: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """Workflow configuration list page."""
    web_service = _get_approvals_web_service(db, user)
    filters = WorkflowFilters(query=q, doctype=doctype, status=status)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = service.list_workflows(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["workflows"] = result.items
    context["doctype_options"] = get_approval_doctype_options()
    context["current_search"] = q
    context["current_doctype"] = doctype
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/workflows/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/workflows/table", response_class=HTMLResponse)
async def workflows_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    doctype: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """Workflows table HTMX partial."""
    service = _get_approvals_service(db, user)
    filters = WorkflowFilters(query=q, doctype=doctype, status=status)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)
    result = service.list_workflows(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["workflows"] = result.items
    context["current_search"] = q
    context["current_doctype"] = doctype
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/workflows/partials/workflows_table.html")
    return HTMLResponse(template.render(context))


@router.get("/workflows/new", response_class=HTMLResponse)
async def workflow_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """New workflow form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["workflow"] = None
    context["doctype_options"] = get_approval_doctype_options()

    template = templates.get_template("modules/accounting/templates/workflows/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/workflows")
async def workflow_create(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """Create a new workflow."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_approvals_service(db, user)
    data = WorkflowCreateData(
        workflow_name=form_str(form_data, "workflow_name"),
        doctype=form_str(form_data, "doctype"),
        description=form_str(form_data, "description") or None,
        is_active=bool(form_str(form_data, "is_active")),
        is_mandatory=bool(form_str(form_data, "is_mandatory")),
        escalation_enabled=bool(form_str(form_data, "escalation_enabled")),
        escalation_hours=form_int(form_data, "escalation_hours", 24) or 24,
    )
    workflow = web_service.create_workflow(data, user.id)

    set_flash(response, f"Workflow '{workflow.workflow_name}' created", "success")
    return RedirectResponse(url=f"/accounting/workflows/{workflow.id}", status_code=303)


@router.get("/workflows/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    workflow_id: int,
    _: None = RequireAccountingRead,
):
    """Workflow detail page."""
    web_service = _get_approvals_web_service(db, user)
    try:
        workflow = service.get_workflow(workflow_id, include_steps=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    users = service.list_active_users()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["workflow"] = workflow
    context["users"] = users
    context["roles"] = [
        {"name": "accounting:read", "label": "Accounting Reader"},
        {"name": "accounting:write", "label": "Accounting Writer"},
        {"name": "books:approve", "label": "Books Approver"},
        {"name": "books:close", "label": "Books Closer"},
        {"name": "admin", "label": "Administrator"},
    ]

    template = templates.get_template("modules/accounting/templates/workflows/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/workflows/{workflow_id}/edit", response_class=HTMLResponse)
async def workflow_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    workflow_id: int,
    _: None = RequireAccountingWrite,
):
    """Edit workflow form."""
    service = _get_approvals_service(db, user)
    try:
        workflow = service.get_workflow(workflow_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["workflow"] = workflow
    context["doctype_options"] = get_approval_doctype_options()

    template = templates.get_template("modules/accounting/templates/workflows/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/workflows/{workflow_id}")
async def workflow_update(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    workflow_id: int,
    _: None = RequireAccountingWrite,
):
    """Update a workflow."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_approvals_service(db, user)
    data = WorkflowUpdateData(
        workflow_name=form_str(form_data, "workflow_name"),
        doctype=form_str(form_data, "doctype"),
        description=form_str(form_data, "description") or None,
        is_active=bool(form_str(form_data, "is_active")),
        is_mandatory=bool(form_str(form_data, "is_mandatory")),
        escalation_enabled=bool(form_str(form_data, "escalation_enabled")),
        escalation_hours=form_int(form_data, "escalation_hours", 24) or 24,
    )
    try:
        workflow = web_service.update_workflow(workflow_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    set_flash(response, f"Workflow '{workflow.workflow_name}' updated", "success")
    return RedirectResponse(url=f"/accounting/workflows/{workflow.id}", status_code=303)


@router.post("/workflows/{workflow_id}/toggle")
async def workflow_toggle(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    workflow_id: int,
    _: None = RequireAccountingWrite,
):
    """Toggle workflow active status."""
    form_data = await request.form()
    await validate_csrf(request)

    web_service = _get_approvals_web_service(db, user)
    try:
        workflow = web_service.toggle_workflow(workflow_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    status = "activated" if workflow.is_active else "deactivated"
    set_flash(response, f"Workflow {status}", "success")
    return RedirectResponse(url=f"/accounting/workflows/{workflow.id}", status_code=303)


@router.post("/workflows/{workflow_id}/steps")
async def workflow_add_step(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    workflow_id: int,
    _: None = RequireAccountingWrite,
):
    """Add a step to a workflow."""
    form_data = await request.form()
    await validate_csrf(request)

    web_service = _get_approvals_web_service(db, user)
    data = WorkflowStepCreateData(
        step_order=form_int(form_data, "step_order", 1) or 1,
        step_name=form_str(form_data, "step_name"),
        role_required=form_str(form_data, "role_required") or None,
        user_id=form_int(form_data, "user_id"),
        approval_mode=form_str(form_data, "approval_mode", "any"),
        amount_threshold_min=form_decimal(form_data, "amount_threshold_min"),
        amount_threshold_max=form_decimal(form_data, "amount_threshold_max"),
    )
    try:
        step = web_service.add_step(workflow_id, data)
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    set_flash(response, f"Step '{step.step_name}' added", "success")
    return RedirectResponse(url=f"/accounting/workflows/{workflow_id}", status_code=303)


@router.post("/workflows/{workflow_id}/steps/{step_id}/delete")
async def workflow_delete_step(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    workflow_id: int,
    step_id: int,
    _: None = RequireAccountingWrite,
):
    """Delete a step from a workflow."""
    form_data = await request.form()
    await validate_csrf(request)

    web_service = _get_approvals_web_service(db, user)
    try:
        web_service.delete_step(workflow_id, step_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    set_flash(response, "Step deleted", "success")
    return RedirectResponse(url=f"/accounting/workflows/{workflow_id}", status_code=303)


# --- Accounting Controls ---

@router.get("/controls", response_class=HTMLResponse)
async def controls_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """Accounting controls configuration form."""
    web_service = _get_approvals_web_service(db, user)
    controls = service.get_controls()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["controls"] = controls

    template = templates.get_template("modules/accounting/templates/controls/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/controls")
async def controls_update(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """Update accounting controls."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_approvals_service(db, user)
    data = ControlsUpdateData(
        require_approval_journal_entry=bool(form_str(form_data, "require_je_approval")),
        require_approval_payment=bool(form_str(form_data, "require_payment_approval")),
        backdating_days_allowed=form_int(form_data, "max_backdate_days", 30) or 30,
    )
    web_service.update_controls(data, user.id)

    set_flash(response, "Accounting controls updated", "success")
    return RedirectResponse(url="/accounting/controls", status_code=303)
