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
    ApprovalWorkflow, ApprovalStep, DocumentApproval, ApprovalHistory, ApprovalStatus, ApprovalMode, AccountingControl,
    JournalEntry, Payment, Invoice, PurchaseInvoice, User,
    func, or_, datetime, Decimal, timedelta, selectinload,
)

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


def get_approval_stats(db, user_id: int) -> dict:
    """Get approval statistics for dashboard."""
    from datetime import date
    today = date.today()

    pending = db.query(func.count(DocumentApproval.id)).filter(
        DocumentApproval.status == ApprovalStatus.PENDING
    ).scalar() or 0

    approved_today = db.query(func.count(DocumentApproval.id)).filter(
        DocumentApproval.status == ApprovalStatus.APPROVED,
        func.date(DocumentApproval.approved_at) == today
    ).scalar() or 0

    rejected_today = db.query(func.count(DocumentApproval.id)).filter(
        DocumentApproval.status == ApprovalStatus.REJECTED,
        func.date(DocumentApproval.rejected_at) == today
    ).scalar() or 0

    overdue = db.query(func.count(DocumentApproval.id)).filter(
        DocumentApproval.status == ApprovalStatus.PENDING,
        DocumentApproval.submitted_at < datetime.utcnow() - timedelta(days=3)
    ).scalar() or 0

    return {
        "pending": pending,
        "approved_today": approved_today,
        "rejected_today": rejected_today,
        "overdue": overdue,
    }


def get_document_for_approval(db, doctype: str, document_id: int):
    """Fetch the actual document for approval review."""
    document = None
    if doctype == "journal_entry":
        document = db.query(JournalEntry).options(
            selectinload(JournalEntry.items)
        ).filter(JournalEntry.id == document_id).first()
    elif doctype == "supplier_payment":
        from app.models.supplier_payment import SupplierPayment
        document = db.query(SupplierPayment).filter(SupplierPayment.id == document_id).first()
    elif doctype == "purchase_invoice":
        document = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == document_id).first()
    elif doctype == "payment":
        document = db.query(Payment).filter(Payment.id == document_id).first()
    elif doctype == "invoice":
        document = db.query(Invoice).filter(Invoice.id == document_id).first()
    return document


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
    query = db.query(DocumentApproval).filter(
        DocumentApproval.status == ApprovalStatus.PENDING
    )

    if doctype:
        query = query.filter(DocumentApproval.doctype == doctype)

    total = query.count()
    approvals = query.order_by(DocumentApproval.submitted_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["approvals"] = approvals
    context["stats"] = get_approval_stats(db, user.id)
    context["doctype_options"] = get_approval_doctype_options()
    context["current_doctype"] = doctype
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    query = db.query(DocumentApproval).filter(
        DocumentApproval.status == ApprovalStatus.PENDING
    )

    if doctype:
        query = query.filter(DocumentApproval.doctype == doctype)

    total = query.count()
    approvals = query.order_by(DocumentApproval.submitted_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["approvals"] = approvals
    context["current_doctype"] = doctype
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    approval = db.query(DocumentApproval).options(
        selectinload(DocumentApproval.approval_history)
    ).filter(
        DocumentApproval.doctype == doctype,
        DocumentApproval.document_id == document_id
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Get the actual document
    document = get_document_for_approval(db, doctype, document_id)

    # Get workflow steps
    workflow_steps = []
    if approval.workflow_id:
        workflow = db.query(ApprovalWorkflow).options(
            selectinload(ApprovalWorkflow.steps)
        ).filter(ApprovalWorkflow.id == approval.workflow_id).first()
        if workflow:
            workflow_steps = sorted(workflow.steps, key=lambda s: s.step_order)

    # Check if current user can approve
    can_approve = approval.status == ApprovalStatus.PENDING

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["approval"] = approval
    context["document"] = document
    context["doctype"] = doctype
    context["document_id"] = document_id
    context["workflow_steps"] = workflow_steps
    context["approval_history"] = sorted(
        approval.approval_history, key=lambda h: h.action_at
    ) if approval.approval_history else []
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

    approval = db.query(DocumentApproval).filter(
        DocumentApproval.doctype == doctype,
        DocumentApproval.document_id == document_id,
        DocumentApproval.status == ApprovalStatus.PENDING
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Pending approval not found")

    remarks = form_str(form_data, "remarks")

    # Record approval history
    history = ApprovalHistory(
        document_approval_id=approval.id,
        step_order=approval.current_step,
        action="APPROVED",
        user_id=user.id,
        remarks=remarks
    )
    db.add(history)

    # Get workflow to check if more steps needed
    workflow = db.query(ApprovalWorkflow).options(
        selectinload(ApprovalWorkflow.steps)
    ).filter(ApprovalWorkflow.id == approval.workflow_id).first()

    next_step_exists = False
    if workflow:
        next_steps = [s for s in workflow.steps if s.step_order > approval.current_step]
        next_step_exists = len(next_steps) > 0

    if next_step_exists:
        # Move to next step
        approval.current_step += 1
        approval.step_approved_at = datetime.utcnow()
        approval.step_approved_by_id = user.id
    else:
        # Final approval
        approval.status = ApprovalStatus.APPROVED
        approval.approved_at = datetime.utcnow()
        approval.approved_by_id = user.id

    db.commit()

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

    approval = db.query(DocumentApproval).filter(
        DocumentApproval.doctype == doctype,
        DocumentApproval.document_id == document_id,
        DocumentApproval.status == ApprovalStatus.PENDING
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Pending approval not found")

    remarks = form_str(form_data, "remarks")

    # Record rejection history
    history = ApprovalHistory(
        document_approval_id=approval.id,
        step_order=approval.current_step,
        action="REJECTED",
        user_id=user.id,
        remarks=remarks
    )
    db.add(history)

    # Update approval status
    approval.status = ApprovalStatus.REJECTED
    approval.rejected_at = datetime.utcnow()
    approval.rejected_by_id = user.id
    approval.rejection_reason = remarks

    db.commit()

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
    query = db.query(ApprovalWorkflow).options(
        selectinload(ApprovalWorkflow.steps)
    )

    if q:
        query = query.filter(
            or_(
                ApprovalWorkflow.workflow_name.ilike(f"%{q}%"),
                ApprovalWorkflow.description.ilike(f"%{q}%")
            )
        )

    if doctype:
        query = query.filter(ApprovalWorkflow.doctype == doctype)

    if status == "active":
        query = query.filter(ApprovalWorkflow.is_active == True)
    elif status == "inactive":
        query = query.filter(ApprovalWorkflow.is_active == False)

    total = query.count()
    workflows = query.order_by(ApprovalWorkflow.workflow_name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["workflows"] = workflows
    context["doctype_options"] = get_approval_doctype_options()
    context["current_search"] = q
    context["current_doctype"] = doctype
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    query = db.query(ApprovalWorkflow).options(
        selectinload(ApprovalWorkflow.steps)
    )

    if q:
        query = query.filter(
            or_(
                ApprovalWorkflow.workflow_name.ilike(f"%{q}%"),
                ApprovalWorkflow.description.ilike(f"%{q}%")
            )
        )

    if doctype:
        query = query.filter(ApprovalWorkflow.doctype == doctype)

    if status == "active":
        query = query.filter(ApprovalWorkflow.is_active == True)
    elif status == "inactive":
        query = query.filter(ApprovalWorkflow.is_active == False)

    total = query.count()
    workflows = query.order_by(ApprovalWorkflow.workflow_name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["workflows"] = workflows
    context["current_search"] = q
    context["current_doctype"] = doctype
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

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

    workflow = ApprovalWorkflow(
        workflow_name=form_str(form_data, "workflow_name"),
        doctype=form_str(form_data, "doctype"),
        description=form_str(form_data, "description") or None,
        is_active=bool(form_str(form_data, "is_active")),
        is_mandatory=bool(form_str(form_data, "is_mandatory")),
        escalation_enabled=bool(form_str(form_data, "escalation_enabled")),
        escalation_hours=form_int(form_data, "escalation_hours", 24) or 24,
        created_by_id=user.id,
    )
    db.add(workflow)
    db.commit()

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
    workflow = db.query(ApprovalWorkflow).options(
        selectinload(ApprovalWorkflow.steps)
    ).filter(ApprovalWorkflow.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get available roles and users for step configuration
    users = db.query(User).filter(User.is_active == True).order_by(User.name).all()

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
    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

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

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.workflow_name = form_str(form_data, "workflow_name")
    workflow.doctype = form_str(form_data, "doctype")
    workflow.description = form_str(form_data, "description") or None
    workflow.is_active = bool(form_str(form_data, "is_active"))
    workflow.is_mandatory = bool(form_str(form_data, "is_mandatory"))
    workflow.escalation_enabled = bool(form_str(form_data, "escalation_enabled"))
    workflow.escalation_hours = form_int(form_data, "escalation_hours", 24) or 24

    db.commit()

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

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.is_active = not workflow.is_active
    db.commit()

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

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    step = ApprovalStep(
        workflow_id=workflow_id,
        step_order=form_int(form_data, "step_order", 1) or 1,
        step_name=form_str(form_data, "step_name"),
        role_required=form_str(form_data, "role_required") or None,
        user_id=form_int(form_data, "user_id"),
        approval_mode=ApprovalMode(form_str(form_data, "approval_mode", "any")),
        amount_threshold_min=form_decimal(form_data, "amount_threshold_min"),
        amount_threshold_max=form_decimal(form_data, "amount_threshold_max"),
    )
    db.add(step)
    db.commit()

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

    step = db.query(ApprovalStep).filter(
        ApprovalStep.id == step_id,
        ApprovalStep.workflow_id == workflow_id
    ).first()

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    db.delete(step)
    db.commit()

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
    controls = db.query(AccountingControl).filter(
        AccountingControl.company == None  # Global controls
    ).first()

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

    controls = db.query(AccountingControl).filter(
        AccountingControl.company == None
    ).first()

    if not controls:
        controls = AccountingControl(company=None)
        db.add(controls)

    # Update controls based on form data
    controls.require_approval_journal_entry = bool(form_str(form_data, "require_je_approval"))
    controls.require_approval_payment = bool(form_str(form_data, "require_payment_approval"))
    controls.backdating_days_allowed = form_int(form_data, "max_backdate_days", 30) or 30
    controls.updated_by_id = user.id

    db.commit()

    set_flash(response, "Accounting controls updated", "success")
    return RedirectResponse(url="/accounting/controls", status_code=303)
