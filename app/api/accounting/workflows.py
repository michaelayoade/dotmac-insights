"""Workflows: Approval workflows, accounting controls, audit log, account CRUD."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import Require
from app.database import get_db
from app.models.accounting import Account, AccountType

from .helpers import parse_date, paginate

router = APIRouter()


# =============================================================================
# SUPPORTED DOCTYPES
# =============================================================================

SUPPORTED_WORKFLOW_DOCTYPES = [
    {"doctype": "journal_entry", "name": "Journal Entry", "description": "General ledger journal entries"},
    {"doctype": "expense", "name": "Expense", "description": "Expense claims and reimbursements"},
    {"doctype": "payment", "name": "Customer Payment", "description": "Payments received from customers"},
    {"doctype": "supplier_payment", "name": "Supplier Payment", "description": "Payments made to suppliers"},
    {"doctype": "invoice", "name": "Sales Invoice", "description": "Customer invoices (AR)"},
    {"doctype": "purchase_invoice", "name": "Purchase Invoice", "description": "Supplier bills (AP)"},
    {"doctype": "credit_note", "name": "Credit Note", "description": "Customer credit notes (AR)"},
    {"doctype": "debit_note", "name": "Debit Note", "description": "Supplier debit notes (AP)"},
    {"doctype": "bank_transaction", "name": "Bank Transaction", "description": "Bank transactions for reconciliation"},
]


@router.get("/doctypes", dependencies=[Depends(Require("books:read"))])
def list_workflow_doctypes() -> Dict[str, Any]:
    """List document types that support approval workflows.

    Returns:
        List of supported document types with descriptions
    """
    return {
        "total": len(SUPPORTED_WORKFLOW_DOCTYPES),
        "doctypes": SUPPORTED_WORKFLOW_DOCTYPES,
    }


# =============================================================================
# APPROVAL WORKFLOWS
# =============================================================================

@router.get("/workflows", dependencies=[Depends(Require("books:read"))])
def list_approval_workflows(
    doctype: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List approval workflows.

    Args:
        doctype: Filter by document type
        active_only: Only show active workflows

    Returns:
        List of approval workflows
    """
    from app.models.accounting_ext import ApprovalWorkflow

    query = db.query(ApprovalWorkflow)
    if doctype:
        query = query.filter(ApprovalWorkflow.doctype == doctype)
    if active_only:
        query = query.filter(ApprovalWorkflow.is_active == True)

    workflows = query.order_by(ApprovalWorkflow.doctype, ApprovalWorkflow.workflow_name).all()

    return {
        "total": len(workflows),
        "workflows": [
            {
                "id": w.id,
                "workflow_name": w.workflow_name,
                "doctype": w.doctype,
                "description": w.description,
                "is_active": w.is_active,
                "is_mandatory": w.is_mandatory,
                "escalation_enabled": w.escalation_enabled,
                "escalation_hours": w.escalation_hours,
            }
            for w in workflows
        ],
    }


@router.get("/workflows/{workflow_id}", dependencies=[Depends(Require("books:read"))])
def get_workflow_detail(
    workflow_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get workflow detail with all steps.

    Args:
        workflow_id: Workflow ID

    Returns:
        Workflow details with steps
    """
    from app.models.accounting_ext import ApprovalWorkflow, ApprovalStep

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps = db.query(ApprovalStep).filter(
        ApprovalStep.workflow_id == workflow_id
    ).order_by(ApprovalStep.step_order).all()

    return {
        "id": workflow.id,
        "workflow_name": workflow.workflow_name,
        "doctype": workflow.doctype,
        "description": workflow.description,
        "is_active": workflow.is_active,
        "is_mandatory": workflow.is_mandatory,
        "escalation_enabled": workflow.escalation_enabled,
        "escalation_hours": workflow.escalation_hours,
        "steps": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "step_name": s.step_name,
                "role_required": s.role_required,
                "user_id": s.user_id,
                "approval_mode": s.approval_mode.value,
                "amount_threshold_min": str(s.amount_threshold_min) if s.amount_threshold_min else None,
                "amount_threshold_max": str(s.amount_threshold_max) if s.amount_threshold_max else None,
                "auto_approve_below": str(s.auto_approve_below) if s.auto_approve_below else None,
                "can_reject": s.can_reject,
            }
            for s in steps
        ],
    }


@router.post("/workflows", dependencies=[Depends(Require("books:admin"))])
def create_workflow(
    workflow_name: str = Query(...),
    doctype: str = Query(...),
    description: Optional[str] = None,
    is_mandatory: bool = False,
    escalation_enabled: bool = False,
    escalation_hours: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new approval workflow.

    Args:
        workflow_name: Name of the workflow
        doctype: Document type this workflow applies to
        description: Workflow description
        is_mandatory: Whether approval is mandatory
        escalation_enabled: Whether to escalate after timeout
        escalation_hours: Hours before escalation

    Returns:
        Created workflow info
    """
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    workflow = engine.create_workflow(
        workflow_name=workflow_name,
        doctype=doctype,
        user_id=user.id,
        description=description,
        is_mandatory=is_mandatory,
        escalation_enabled=escalation_enabled,
        escalation_hours=escalation_hours,
    )
    db.commit()

    return {
        "message": "Workflow created",
        "id": workflow.id,
        "workflow_name": workflow.workflow_name,
        "doctype": workflow.doctype,
    }


@router.post("/workflows/{workflow_id}/steps", dependencies=[Depends(Require("books:admin"))])
def add_workflow_step(
    workflow_id: int,
    step_order: int = Query(...),
    step_name: str = Query(...),
    role_required: Optional[str] = None,
    user_id: Optional[int] = None,
    approval_mode: str = "any",
    amount_threshold_min: Optional[float] = None,
    amount_threshold_max: Optional[float] = None,
    auto_approve_below: Optional[float] = None,
    can_reject: bool = True,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a step to a workflow.

    Args:
        workflow_id: Workflow ID
        step_order: Order of this step
        step_name: Name of the step
        role_required: Role required for approval
        user_id: Specific user for approval
        approval_mode: Approval mode (any, all)
        amount_threshold_min: Minimum amount for this step
        amount_threshold_max: Maximum amount for this step
        auto_approve_below: Auto-approve amounts below this
        can_reject: Whether this step can reject

    Returns:
        Created step info
    """
    from app.models.accounting_ext import ApprovalWorkflow, ApprovalMode, ApprovalStep
    from app.services.approval_engine import ApprovalEngine

    workflow = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        mode = ApprovalMode(approval_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid approval mode: {approval_mode}")

    # Prevent duplicate step_order
    dup_step = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.workflow_id == workflow_id, ApprovalStep.step_order == step_order)
        .first()
    )
    if dup_step:
        raise HTTPException(status_code=400, detail=f"Step order {step_order} already exists in this workflow")

    # Prevent overlapping amount thresholds within the same workflow
    if amount_threshold_min is not None or amount_threshold_max is not None:
        existing_steps = db.query(ApprovalStep).filter(ApprovalStep.workflow_id == workflow_id).all()
        new_min = Decimal(str(amount_threshold_min)) if amount_threshold_min is not None else None
        new_max = Decimal(str(amount_threshold_max)) if amount_threshold_max is not None else None

        for s in existing_steps:
            s_min = s.amount_threshold_min
            s_max = s.amount_threshold_max
            # Overlap if ranges intersect (treat None as unbounded)
            if (
                (new_min is None or s_max is None or new_min <= s_max)
                and (new_max is None or s_min is None or new_max >= s_min)
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Amount range overlaps with existing step '{s.step_name}' (min={s_min}, max={s_max})",
                )

    engine = ApprovalEngine(db)
    step = engine.add_workflow_step(
        workflow_id=workflow_id,
        step_order=step_order,
        step_name=step_name,
        role_required=role_required,
        user_id=user_id,
        approval_mode=mode,
        amount_threshold_min=Decimal(str(amount_threshold_min)) if amount_threshold_min else None,
        amount_threshold_max=Decimal(str(amount_threshold_max)) if amount_threshold_max else None,
        auto_approve_below=Decimal(str(auto_approve_below)) if auto_approve_below else None,
        can_reject=can_reject,
    )
    db.commit()

    return {
        "message": "Step added",
        "step_id": step.id,
        "step_order": step.step_order,
        "step_name": step.step_name,
    }


@router.patch("/workflows/{workflow_id}", dependencies=[Depends(Require("books:admin"))])
def update_workflow(
    workflow_id: int,
    workflow_name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_mandatory: Optional[bool] = None,
    escalation_enabled: Optional[bool] = None,
    escalation_hours: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update a workflow.

    Args:
        workflow_id: Workflow ID
        workflow_name: New name
        description: New description
        is_active: Active status
        is_mandatory: Mandatory status
        escalation_enabled: Escalation status
        escalation_hours: Hours before escalation

    Returns:
        Updated workflow info
    """
    from app.services.approval_engine import ApprovalEngine, WorkflowNotFoundError

    updates: Dict[str, Any] = {}
    if workflow_name is not None:
        updates["workflow_name"] = workflow_name
    if description is not None:
        updates["description"] = description
    if is_active is not None:
        updates["is_active"] = is_active
    if is_mandatory is not None:
        updates["is_mandatory"] = is_mandatory
    if escalation_enabled is not None:
        updates["escalation_enabled"] = escalation_enabled
    if escalation_hours is not None:
        updates["escalation_hours"] = escalation_hours

    engine = ApprovalEngine(db)
    try:
        workflow = engine.update_workflow(workflow_id, user.id, **updates)
        db.commit()
        return {
            "message": "Workflow updated",
            "id": workflow.id,
            "workflow_name": workflow.workflow_name,
            "is_active": workflow.is_active,
        }
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/workflows/{workflow_id}", dependencies=[Depends(Require("books:admin"))])
def deactivate_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Deactivate a workflow (soft delete).

    Args:
        workflow_id: Workflow ID

    Returns:
        Deactivation confirmation
    """
    from app.services.approval_engine import ApprovalEngine, WorkflowNotFoundError

    engine = ApprovalEngine(db)
    try:
        workflow = engine.deactivate_workflow(workflow_id, user.id)
        db.commit()
        return {
            "message": "Workflow deactivated",
            "id": workflow.id,
            "workflow_name": workflow.workflow_name,
        }
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# PENDING APPROVALS
# =============================================================================

@router.get("/approvals/pending", dependencies=[Depends(Require("books:approve"))])
def get_pending_approvals(
    doctype: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:approve")),
) -> Dict[str, Any]:
    """Get documents pending approval for the current user.

    Args:
        doctype: Filter by document type

    Returns:
        List of pending approvals
    """
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    pending = engine.get_pending_approvals(user.id, doctype)

    return {
        "total": len(pending),
        "pending": pending,
    }


@router.get("/approvals/{doctype}/{document_id}", dependencies=[Depends(Require("books:read"))])
def get_approval_status(
    doctype: str,
    document_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get approval status for a specific document.

    Args:
        doctype: Document type
        document_id: Document ID

    Returns:
        Approval status details
    """
    from app.services.approval_engine import ApprovalEngine

    engine = ApprovalEngine(db)
    status = engine.get_approval_status(doctype, document_id)

    if not status:
        raise HTTPException(status_code=404, detail="No approval record found")

    return status


# =============================================================================
# ACCOUNTING CONTROLS
# =============================================================================

@router.get("/controls", dependencies=[Depends(Require("books:read"))])
def get_accounting_controls(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get accounting control settings.

    Returns:
        Accounting control configuration
    """
    from app.models.accounting_ext import AccountingControl

    controls = db.query(AccountingControl).filter(
        AccountingControl.company.is_(None)
    ).first()

    if not controls:
        return {"message": "No controls configured", "controls": None}

    return {
        "controls": {
            "id": controls.id,
            "base_currency": controls.base_currency,
            "backdating_days_allowed": controls.backdating_days_allowed,
            "future_posting_days_allowed": controls.future_posting_days_allowed,
            "auto_voucher_numbering": controls.auto_voucher_numbering,
            "voucher_prefix_format": controls.voucher_prefix_format,
            "require_attachment_journal_entry": controls.require_attachment_journal_entry,
            "require_attachment_expense": controls.require_attachment_expense,
            "require_attachment_payment": controls.require_attachment_payment,
            "require_attachment_invoice": controls.require_attachment_invoice,
            "require_attachment_supplier_payment": controls.require_attachment_supplier_payment,
            "require_attachment_purchase_invoice": controls.require_attachment_purchase_invoice,
            "require_attachment_credit_note": controls.require_attachment_credit_note,
            "require_attachment_debit_note": controls.require_attachment_debit_note,
            "require_attachment_bank_transaction": controls.require_attachment_bank_transaction,
            "require_approval_journal_entry": controls.require_approval_journal_entry,
            "require_approval_expense": controls.require_approval_expense,
            "require_approval_payment": controls.require_approval_payment,
            "require_approval_supplier_payment": controls.require_approval_supplier_payment,
            "require_approval_purchase_invoice": controls.require_approval_purchase_invoice,
            "require_approval_credit_note": controls.require_approval_credit_note,
            "require_approval_debit_note": controls.require_approval_debit_note,
            "auto_create_fiscal_periods": controls.auto_create_fiscal_periods,
            "default_period_type": controls.default_period_type,
            "retained_earnings_account": controls.retained_earnings_account,
            "fx_gain_account": controls.fx_gain_account,
            "fx_loss_account": controls.fx_loss_account,
        }
    }


@router.patch("/controls", dependencies=[Depends(Require("books:admin"))])
def update_accounting_controls(
    backdating_days_allowed: Optional[int] = None,
    future_posting_days_allowed: Optional[int] = None,
    auto_voucher_numbering: Optional[bool] = None,
    require_attachment_journal_entry: Optional[bool] = None,
    require_attachment_expense: Optional[bool] = None,
    require_attachment_payment: Optional[bool] = None,
    require_attachment_invoice: Optional[bool] = None,
    require_attachment_supplier_payment: Optional[bool] = None,
    require_attachment_purchase_invoice: Optional[bool] = None,
    require_attachment_credit_note: Optional[bool] = None,
    require_attachment_debit_note: Optional[bool] = None,
    require_attachment_bank_transaction: Optional[bool] = None,
    require_approval_journal_entry: Optional[bool] = None,
    require_approval_expense: Optional[bool] = None,
    require_approval_payment: Optional[bool] = None,
    require_approval_supplier_payment: Optional[bool] = None,
    require_approval_purchase_invoice: Optional[bool] = None,
    require_approval_credit_note: Optional[bool] = None,
    require_approval_debit_note: Optional[bool] = None,
    retained_earnings_account: Optional[str] = None,
    fx_gain_account: Optional[str] = None,
    fx_loss_account: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update accounting control settings.

    Args:
        backdating_days_allowed: Days of backdating allowed
        future_posting_days_allowed: Days of future posting allowed
        auto_voucher_numbering: Auto-number vouchers
        require_attachment_*: Require attachments on various doc types
        require_approval_*: Require approval for various doc types
        retained_earnings_account: Retained earnings account
        fx_gain_account: FX gain account
        fx_loss_account: FX loss account

    Returns:
        Update confirmation
    """
    from app.models.accounting_ext import AccountingControl
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    controls = db.query(AccountingControl).filter(
        AccountingControl.company.is_(None)
    ).first()

    if not controls:
        controls = AccountingControl()
        db.add(controls)
        old_values = {}
    else:
        old_values = serialize_for_audit(controls)

    # Apply updates - posting controls
    if backdating_days_allowed is not None:
        controls.backdating_days_allowed = backdating_days_allowed
    if future_posting_days_allowed is not None:
        controls.future_posting_days_allowed = future_posting_days_allowed
    if auto_voucher_numbering is not None:
        controls.auto_voucher_numbering = auto_voucher_numbering

    # Attachment requirements
    if require_attachment_journal_entry is not None:
        controls.require_attachment_journal_entry = require_attachment_journal_entry
    if require_attachment_expense is not None:
        controls.require_attachment_expense = require_attachment_expense
    if require_attachment_payment is not None:
        controls.require_attachment_payment = require_attachment_payment
    if require_attachment_invoice is not None:
        controls.require_attachment_invoice = require_attachment_invoice
    if require_attachment_supplier_payment is not None:
        controls.require_attachment_supplier_payment = require_attachment_supplier_payment
    if require_attachment_purchase_invoice is not None:
        controls.require_attachment_purchase_invoice = require_attachment_purchase_invoice
    if require_attachment_credit_note is not None:
        controls.require_attachment_credit_note = require_attachment_credit_note
    if require_attachment_debit_note is not None:
        controls.require_attachment_debit_note = require_attachment_debit_note
    if require_attachment_bank_transaction is not None:
        controls.require_attachment_bank_transaction = require_attachment_bank_transaction

    # Approval requirements
    if require_approval_journal_entry is not None:
        controls.require_approval_journal_entry = require_approval_journal_entry
    if require_approval_expense is not None:
        controls.require_approval_expense = require_approval_expense
    if require_approval_payment is not None:
        controls.require_approval_payment = require_approval_payment
    if require_approval_supplier_payment is not None:
        controls.require_approval_supplier_payment = require_approval_supplier_payment
    if require_approval_purchase_invoice is not None:
        controls.require_approval_purchase_invoice = require_approval_purchase_invoice
    if require_approval_credit_note is not None:
        controls.require_approval_credit_note = require_approval_credit_note
    if require_approval_debit_note is not None:
        controls.require_approval_debit_note = require_approval_debit_note

    # Special accounts
    if retained_earnings_account is not None:
        controls.retained_earnings_account = retained_earnings_account
    if fx_gain_account is not None:
        controls.fx_gain_account = fx_gain_account
    if fx_loss_account is not None:
        controls.fx_loss_account = fx_loss_account

    controls.updated_at = datetime.utcnow()
    controls.updated_by_id = user.id

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="accounting_control",
        document_id=controls.id,
        user_id=user.id,
        old_values=old_values,
        new_values=serialize_for_audit(controls),
    )

    db.commit()

    return {"message": "Controls updated"}


# =============================================================================
# AUDIT LOG
# =============================================================================

@router.get("/audit-log", dependencies=[Depends(Require("books:read"))])
def list_audit_logs(
    doctype: Optional[str] = None,
    document_id: Optional[int] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Query audit logs.

    Args:
        doctype: Filter by document type
        document_id: Filter by document ID
        action: Filter by action type
        user_id: Filter by user
        start_date: Filter from date
        end_date: Filter to date
        limit: Max results
        offset: Pagination offset

    Returns:
        Paginated audit logs
    """
    from app.models.accounting_ext import AuditLog, AuditAction

    query = db.query(AuditLog)

    if doctype:
        query = query.filter(AuditLog.doctype == doctype)
    if document_id:
        query = query.filter(AuditLog.document_id == document_id)
    if action:
        try:
            action_enum = AuditAction(action)
            query = query.filter(AuditLog.action == action_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if start_date:
        query = query.filter(AuditLog.timestamp >= parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(AuditLog.timestamp <= parse_date(end_date, "end_date"))

    query = query.order_by(AuditLog.timestamp.desc())
    total, logs = paginate(query, offset, limit)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "doctype": log.doctype,
                "document_id": log.document_id,
                "document_name": log.document_name,
                "action": log.action.value,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "user_name": log.user_name,
                "changed_fields": log.changed_fields,
                "remarks": log.remarks,
            }
            for log in logs
        ],
    }


@router.get("/audit-log/{doctype}/{document_id}", dependencies=[Depends(Require("books:read"))])
def get_document_audit_history(
    doctype: str,
    document_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get full audit history for a specific document.

    Args:
        doctype: Document type
        document_id: Document ID

    Returns:
        Full audit history for the document
    """
    from app.services.audit_logger import AuditLogger

    audit = AuditLogger(db)
    history = audit.get_document_history(doctype, document_id)

    return {
        "doctype": doctype,
        "document_id": document_id,
        "total": len(history),
        "history": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action.value,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "user_name": log.user_name,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "changed_fields": log.changed_fields,
                "remarks": log.remarks,
            }
            for log in history
        ],
    }


# =============================================================================
# ACCOUNT CRUD
# =============================================================================

@router.post("/accounts", dependencies=[Depends(Require("books:admin"))])
def create_account(
    account_name: str = Query(...),
    root_type: str = Query(..., description="Asset, Liability, Equity, Income, or Expense"),
    account_number: Optional[str] = None,
    account_type: Optional[str] = None,
    parent_account: Optional[str] = None,
    is_group: bool = False,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Create a new account in the chart of accounts.

    Args:
        account_name: Account name
        root_type: Root type (Asset, Liability, Equity, Income, Expense)
        account_number: Account number
        account_type: Account type
        parent_account: Parent account reference
        is_group: Whether this is a group account
        company: Company this account belongs to

    Returns:
        Created account info
    """
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    try:
        root_type_enum = AccountType(root_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid root type: {root_type}. Must be Asset, Liability, Equity, Income, or Expense"
        )

    account_data = {
        "account_name": account_name,
        "root_type": root_type_enum,
        "account_number": account_number,
        "account_type": account_type,
        "parent_account": parent_account,
        "is_group": is_group,
        "company": company,
    }

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_create(account_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    account = Account(
        account_name=account_name,
        root_type=root_type_enum,
        account_number=account_number,
        account_type=account_type,
        parent_account=parent_account,
        is_group=is_group,
        company=company,
        disabled=False,
    )
    db.add(account)
    db.flush()

    # Audit log
    audit = AuditLogger(db)
    audit.log_create(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account_name,
        new_values=serialize_for_audit(account),
    )

    db.commit()

    return {
        "message": "Account created",
        "id": account.id,
        "account_name": account.account_name,
        "account_number": account.account_number,
        "root_type": account.root_type.value if account.root_type else None,
    }


@router.patch("/accounts/{account_id}", dependencies=[Depends(Require("books:admin"))])
def update_account(
    account_id: int,
    account_name: Optional[str] = None,
    account_number: Optional[str] = None,
    account_type: Optional[str] = None,
    disabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Update an account.

    Args:
        account_id: Account ID
        account_name: New account name
        account_number: New account number
        account_type: New account type
        disabled: Disable/enable the account

    Returns:
        Updated account info
    """
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    updates: Dict[str, Any] = {}
    if account_name is not None:
        updates["account_name"] = account_name
    if account_number is not None:
        updates["account_number"] = account_number
    if account_type is not None:
        updates["account_type"] = account_type
    if disabled is not None:
        updates["disabled"] = disabled

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_update(account, updates)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    old_values = serialize_for_audit(account)

    # Apply updates
    for field, value in updates.items():
        setattr(account, field, value)
    account.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account.account_name,
        old_values=old_values,
        new_values=serialize_for_audit(account),
    )

    db.commit()

    return {
        "message": "Account updated",
        "id": account.id,
        "account_name": account.account_name,
    }


@router.delete("/accounts/{account_id}", dependencies=[Depends(Require("books:admin"))])
def disable_account(
    account_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("books:admin")),
) -> Dict[str, Any]:
    """Disable an account (soft delete).

    Args:
        account_id: Account ID

    Returns:
        Disable confirmation
    """
    from app.services.je_validator import AccountValidator
    from app.services.audit_logger import AuditLogger, serialize_for_audit

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    validator = AccountValidator(db)
    is_valid, errors = validator.validate_disable(account)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    old_values = serialize_for_audit(account)
    account.disabled = True
    account.updated_at = datetime.utcnow()

    # Audit log
    audit = AuditLogger(db)
    audit.log_update(
        doctype="account",
        document_id=account.id,
        user_id=user.id,
        document_name=account.account_name,
        old_values=old_values,
        new_values=serialize_for_audit(account),
        remarks="Account disabled",
    )

    db.commit()

    return {
        "message": "Account disabled",
        "id": account.id,
        "account_name": account.account_name,
    }
