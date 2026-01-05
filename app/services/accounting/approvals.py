"""Approval workflows service for accounting module."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.accounting_ext import (
    AccountingControl,
    ApprovalHistory,
    ApprovalMode,
    ApprovalStatus,
    ApprovalStep,
    ApprovalWorkflow,
    DocumentApproval,
)
from app.models.accounting import JournalEntry, PurchaseInvoice
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.auth import User
from app.models.supplier_payment import SupplierPayment
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .approvals_types import (
    ApprovalListFilters,
    WorkflowFilters,
    WorkflowCreateData,
    WorkflowUpdateData,
    WorkflowStepCreateData,
    ControlsUpdateData,
)

__all__ = ["ApprovalsService"]


class ApprovalsService:
    """Service for approval workflows and pending approvals."""

    def __init__(self, db: Session, principal: Optional[object] = None) -> None:
        self.db = db
        self.principal = principal

    def get_stats(self) -> dict:
        """Get approval statistics for the dashboard."""
        today = date.today()

        pending = self.db.query(func.count(DocumentApproval.id)).filter(
            DocumentApproval.status == ApprovalStatus.PENDING
        ).scalar() or 0

        approved_today = self.db.query(func.count(DocumentApproval.id)).filter(
            DocumentApproval.status == ApprovalStatus.APPROVED,
            func.date(DocumentApproval.approved_at) == today,
        ).scalar() or 0

        rejected_today = self.db.query(func.count(DocumentApproval.id)).filter(
            DocumentApproval.status == ApprovalStatus.REJECTED,
            func.date(DocumentApproval.rejected_at) == today,
        ).scalar() or 0

        overdue = self.db.query(func.count(DocumentApproval.id)).filter(
            DocumentApproval.status == ApprovalStatus.PENDING,
            DocumentApproval.submitted_at < datetime.utcnow() - timedelta(days=3),
        ).scalar() or 0

        return {
            "pending": pending,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "overdue": overdue,
        }

    def list_pending_approvals(
        self,
        filters: ApprovalListFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[DocumentApproval]:
        """List pending approvals."""
        query = self.db.query(DocumentApproval).filter(
            DocumentApproval.status == ApprovalStatus.PENDING
        )

        if filters.doctype:
            query = query.filter(DocumentApproval.doctype == filters.doctype)

        query = query.order_by(DocumentApproval.submitted_at.desc())
        return paginate(query, pagination)

    def get_approval_detail(
        self,
        doctype: str,
        document_id: int,
    ) -> Tuple[DocumentApproval, Optional[object], list[ApprovalStep], list[ApprovalHistory]]:
        """Get approval detail data, including workflow steps and history."""
        approval = self.db.query(DocumentApproval).options(
            selectinload(DocumentApproval.approval_history)
        ).filter(
            DocumentApproval.doctype == doctype,
            DocumentApproval.document_id == document_id,
        ).first()

        if not approval:
            raise NotFoundError("Approval not found")

        document = self.get_document_for_approval(doctype, document_id)

        workflow_steps: list[ApprovalStep] = []
        if approval.workflow_id:
            workflow = self.db.query(ApprovalWorkflow).options(
                selectinload(ApprovalWorkflow.steps)
            ).filter(ApprovalWorkflow.id == approval.workflow_id).first()
            if workflow:
                workflow_steps = sorted(workflow.steps, key=lambda s: s.step_order)

        approval_history = sorted(
            approval.approval_history, key=lambda h: h.action_at
        ) if approval.approval_history else []

        return approval, document, workflow_steps, approval_history

    def approve_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        remarks: Optional[str] = None,
    ) -> DocumentApproval:
        """Approve a document approval request."""
        approval = self.db.query(DocumentApproval).filter(
            DocumentApproval.doctype == doctype,
            DocumentApproval.document_id == document_id,
            DocumentApproval.status == ApprovalStatus.PENDING,
        ).first()

        if not approval:
            raise NotFoundError("Pending approval not found")

        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=approval.current_step,
            action="APPROVED",
            user_id=user_id,
            remarks=remarks,
        )
        self.db.add(history)

        workflow = self.db.query(ApprovalWorkflow).options(
            selectinload(ApprovalWorkflow.steps)
        ).filter(ApprovalWorkflow.id == approval.workflow_id).first()

        next_step_exists = False
        if workflow:
            next_steps = [s for s in workflow.steps if s.step_order > approval.current_step]
            next_step_exists = len(next_steps) > 0

        if next_step_exists:
            approval.current_step += 1
            approval.step_approved_at = datetime.utcnow()
            approval.step_approved_by_id = user_id
        else:
            approval.status = ApprovalStatus.APPROVED
            approval.approved_at = datetime.utcnow()
            approval.approved_by_id = user_id

        self.db.flush()
        return approval

    def reject_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        remarks: Optional[str] = None,
    ) -> DocumentApproval:
        """Reject a document approval request."""
        approval = self.db.query(DocumentApproval).filter(
            DocumentApproval.doctype == doctype,
            DocumentApproval.document_id == document_id,
            DocumentApproval.status == ApprovalStatus.PENDING,
        ).first()

        if not approval:
            raise NotFoundError("Pending approval not found")

        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=approval.current_step,
            action="REJECTED",
            user_id=user_id,
            remarks=remarks,
        )
        self.db.add(history)

        approval.status = ApprovalStatus.REJECTED
        approval.rejected_at = datetime.utcnow()
        approval.rejected_by_id = user_id
        approval.rejection_reason = remarks

        self.db.flush()
        return approval

    def list_workflows(
        self,
        filters: WorkflowFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[ApprovalWorkflow]:
        """List approval workflows."""
        query = self.db.query(ApprovalWorkflow).options(
            selectinload(ApprovalWorkflow.steps)
        )

        if filters.query:
            query = query.filter(
                or_(
                    ApprovalWorkflow.workflow_name.ilike(f"%{filters.query}%"),
                    ApprovalWorkflow.description.ilike(f"%{filters.query}%"),
                )
            )

        if filters.doctype:
            query = query.filter(ApprovalWorkflow.doctype == filters.doctype)

        if filters.status == "active":
            query = query.filter(ApprovalWorkflow.is_active == True)
        elif filters.status == "inactive":
            query = query.filter(ApprovalWorkflow.is_active == False)

        query = query.order_by(ApprovalWorkflow.workflow_name)
        return paginate(query, pagination)

    def get_workflow(self, workflow_id: int, *, include_steps: bool = False) -> ApprovalWorkflow:
        """Get approval workflow by ID."""
        query = self.db.query(ApprovalWorkflow)
        if include_steps:
            query = query.options(selectinload(ApprovalWorkflow.steps))

        workflow = query.filter(ApprovalWorkflow.id == workflow_id).first()
        if not workflow:
            raise NotFoundError("Workflow not found")
        return workflow

    def create_workflow(self, data: WorkflowCreateData, user_id: int) -> ApprovalWorkflow:
        """Create a new approval workflow."""
        workflow = ApprovalWorkflow(
            workflow_name=data.workflow_name,
            doctype=data.doctype,
            description=data.description,
            is_active=data.is_active,
            is_mandatory=data.is_mandatory,
            escalation_enabled=data.escalation_enabled,
            escalation_hours=data.escalation_hours,
            created_by_id=user_id,
        )
        self.db.add(workflow)
        self.db.flush()
        return workflow

    def update_workflow(self, workflow_id: int, data: WorkflowUpdateData) -> ApprovalWorkflow:
        """Update an existing approval workflow."""
        workflow = self.get_workflow(workflow_id)
        workflow.workflow_name = data.workflow_name
        workflow.doctype = data.doctype
        workflow.description = data.description
        workflow.is_active = data.is_active
        workflow.is_mandatory = data.is_mandatory
        workflow.escalation_enabled = data.escalation_enabled
        workflow.escalation_hours = data.escalation_hours
        self.db.flush()
        return workflow

    def toggle_workflow(self, workflow_id: int) -> ApprovalWorkflow:
        """Toggle workflow active status."""
        workflow = self.get_workflow(workflow_id)
        workflow.is_active = not workflow.is_active
        self.db.flush()
        return workflow

    def add_step(self, workflow_id: int, data: WorkflowStepCreateData) -> ApprovalStep:
        """Add a step to a workflow."""
        self.get_workflow(workflow_id)
        try:
            approval_mode = ApprovalMode(data.approval_mode)
        except ValueError as exc:
            raise ValidationError(f"Invalid approval mode: {data.approval_mode}") from exc

        step = ApprovalStep(
            workflow_id=workflow_id,
            step_order=data.step_order,
            step_name=data.step_name,
            role_required=data.role_required,
            user_id=data.user_id,
            approval_mode=approval_mode,
            amount_threshold_min=data.amount_threshold_min,
            amount_threshold_max=data.amount_threshold_max,
        )
        self.db.add(step)
        self.db.flush()
        return step

    def delete_step(self, workflow_id: int, step_id: int) -> None:
        """Delete a step from a workflow."""
        step = self.db.query(ApprovalStep).filter(
            ApprovalStep.id == step_id,
            ApprovalStep.workflow_id == workflow_id,
        ).first()
        if not step:
            raise NotFoundError("Step not found")

        self.db.delete(step)
        self.db.flush()

    def list_active_users(self) -> list[User]:
        """List active users for workflow assignment."""
        return self.db.query(User).filter(User.is_active == True).order_by(User.name).all()

    def get_controls(self) -> Optional[AccountingControl]:
        """Get accounting controls configuration."""
        return self.db.query(AccountingControl).filter(
            AccountingControl.company == None
        ).first()

    def update_controls(self, data: ControlsUpdateData, user_id: int) -> AccountingControl:
        """Update or create accounting controls configuration."""
        controls = self.get_controls()
        if not controls:
            controls = AccountingControl(company=None)
            self.db.add(controls)

        controls.require_approval_journal_entry = data.require_approval_journal_entry
        controls.require_approval_payment = data.require_approval_payment
        controls.backdating_days_allowed = data.backdating_days_allowed
        controls.updated_by_id = user_id
        self.db.flush()
        return controls

    def get_document_for_approval(self, doctype: str, document_id: int) -> Optional[object]:
        """Fetch the underlying document for approval review."""
        if doctype == "journal_entry":
            return self.db.query(JournalEntry).options(
                selectinload(JournalEntry.items)
            ).filter(JournalEntry.id == document_id).first()
        if doctype == "supplier_payment":
            return self.db.query(SupplierPayment).filter(
                SupplierPayment.id == document_id
            ).first()
        if doctype == "purchase_invoice":
            return self.db.query(PurchaseInvoice).filter(
                PurchaseInvoice.id == document_id
            ).first()
        if doctype == "payment":
            return self.db.query(Payment).filter(Payment.id == document_id).first()
        if doctype == "invoice":
            return self.db.query(Invoice).filter(Invoice.id == document_id).first()
        return None
