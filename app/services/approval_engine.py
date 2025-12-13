"""
Approval Engine Service

Provides a full workflow engine for document approvals with:
- Multi-step approval chains
- Role-based approval requirements
- Amount threshold conditions
- Escalation rules (timeout → escalate)
- Parallel approval support (all must approve)
- Document submit/approve/reject/post actions
- Pending approvals dashboard per user
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.accounting_ext import (
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalMode,
    DocumentApproval,
    ApprovalHistory,
    ApprovalStatus,
    AuditAction,
)
from app.models.auth import User, Role, UserRole
from app.models.notification import NotificationEventType
from app.services.audit_logger import AuditLogger, serialize_for_audit
from app.services.notification_service import NotificationService


class ApprovalError(Exception):
    """Base exception for approval-related errors."""
    pass


class WorkflowNotFoundError(ApprovalError):
    """Raised when no active workflow is found for a doctype."""
    pass


class ApprovalNotFoundError(ApprovalError):
    """Raised when document approval record is not found."""
    pass


class UnauthorizedApprovalError(ApprovalError):
    """Raised when user is not authorized to approve."""
    pass


class InvalidStateError(ApprovalError):
    """Raised when action is invalid for current document state."""
    pass


class ApprovalEngine:
    """Service for managing document approval workflows."""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.notification_service = NotificationService(db)

    # =========================================================================
    # WORKFLOW MANAGEMENT
    # =========================================================================

    def get_workflow_for_doctype(self, doctype: str) -> Optional[ApprovalWorkflow]:
        """
        Get the active workflow for a document type.

        Args:
            doctype: The document type (e.g., "journal_entry", "expense")

        Returns:
            Active ApprovalWorkflow or None
        """
        return (
            self.db.query(ApprovalWorkflow)
            .filter(
                and_(
                    ApprovalWorkflow.doctype == doctype,
                    ApprovalWorkflow.is_active == True,
                )
            )
            .first()
        )

    def get_workflow_steps(self, workflow_id: int) -> List[ApprovalStep]:
        """
        Get all steps for a workflow, ordered by step_order.

        Args:
            workflow_id: ID of the workflow

        Returns:
            List of ApprovalStep objects
        """
        return (
            self.db.query(ApprovalStep)
            .filter(ApprovalStep.workflow_id == workflow_id)
            .order_by(ApprovalStep.step_order)
            .all()
        )

    def create_workflow(
        self,
        workflow_name: str,
        doctype: str,
        user_id: int,
        description: Optional[str] = None,
        is_mandatory: bool = False,
        escalation_enabled: bool = False,
        escalation_hours: Optional[int] = None,
    ) -> ApprovalWorkflow:
        """
        Create a new approval workflow.

        Args:
            workflow_name: Name of the workflow
            doctype: Document type this workflow applies to
            user_id: ID of user creating the workflow
            description: Optional description
            is_mandatory: If True, all documents of this type require approval
            escalation_enabled: Enable automatic escalation on timeout
            escalation_hours: Hours before escalation triggers

        Returns:
            Created ApprovalWorkflow
        """
        # Deactivate any existing workflow for this doctype
        existing = (
            self.db.query(ApprovalWorkflow)
            .filter(
                and_(
                    ApprovalWorkflow.doctype == doctype,
                    ApprovalWorkflow.is_active == True,
                )
            )
            .all()
        )
        for wf in existing:
            wf.is_active = False

        workflow = ApprovalWorkflow(
            workflow_name=workflow_name,
            doctype=doctype,
            description=description,
            is_active=True,
            is_mandatory=is_mandatory,
            escalation_enabled=escalation_enabled,
            escalation_hours=escalation_hours,
            created_by_id=user_id,
        )
        self.db.add(workflow)
        self.db.flush()

        # Audit log
        self.audit_logger.log_create(
            doctype="approval_workflow",
            document_id=workflow.id,
            user_id=user_id,
            document_name=workflow_name,
            new_values=serialize_for_audit(workflow),
        )

        return workflow

    def add_workflow_step(
        self,
        workflow_id: int,
        step_order: int,
        step_name: str,
        role_required: Optional[str] = None,
        user_id: Optional[int] = None,
        approval_mode: ApprovalMode = ApprovalMode.ANY,
        amount_threshold_min: Optional[Decimal] = None,
        amount_threshold_max: Optional[Decimal] = None,
        auto_approve_below: Optional[Decimal] = None,
        escalation_user_id: Optional[int] = None,
        escalation_role: Optional[str] = None,
        can_reject: bool = True,
    ) -> ApprovalStep:
        """
        Add a step to an approval workflow.

        Args:
            workflow_id: ID of the workflow
            step_order: Order of this step (1, 2, 3...)
            step_name: Name/description of the step
            role_required: Role that can approve this step
            user_id: Specific user who can approve (alternative to role)
            approval_mode: ANY (one approver), ALL (all must approve), SEQUENTIAL
            amount_threshold_min: Only apply step if amount >= this
            amount_threshold_max: Only apply step if amount <= this
            auto_approve_below: Auto-approve if amount below this
            escalation_user_id: User to escalate to on timeout
            escalation_role: Role to escalate to on timeout
            can_reject: If True, approvers can reject at this step

        Returns:
            Created ApprovalStep
        """
        step = ApprovalStep(
            workflow_id=workflow_id,
            step_order=step_order,
            step_name=step_name,
            role_required=role_required,
            user_id=user_id,
            approval_mode=approval_mode,
            amount_threshold_min=amount_threshold_min,
            amount_threshold_max=amount_threshold_max,
            auto_approve_below=auto_approve_below,
            escalation_user_id=escalation_user_id,
            escalation_role=escalation_role,
            can_reject=can_reject,
        )
        self.db.add(step)
        self.db.flush()

        return step

    # =========================================================================
    # DOCUMENT SUBMISSION
    # =========================================================================

    def submit_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        amount: Optional[Decimal] = None,
        document_name: Optional[str] = None,
    ) -> DocumentApproval:
        """
        Submit a document for approval.

        Args:
            doctype: Document type
            document_id: ID of the document
            user_id: ID of user submitting
            amount: Document amount (for threshold-based routing)
            document_name: Human-readable document reference

        Returns:
            Created or updated DocumentApproval

        Raises:
            WorkflowNotFoundError: If no active workflow exists
            InvalidStateError: If document is already in approval
        """
        # Check for existing approval record
        existing = (
            self.db.query(DocumentApproval)
            .filter(
                and_(
                    DocumentApproval.doctype == doctype,
                    DocumentApproval.document_id == document_id,
                )
            )
            .first()
        )

        if existing:
            if existing.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED):
                raise InvalidStateError(
                    f"Document is already {existing.status.value}. "
                    "Cannot resubmit until rejected or cancelled."
                )
            # Resubmission after rejection - reset the approval
            approval = existing
            old_values = serialize_for_audit(approval)
        else:
            approval = None
            old_values = {}

        # Get active workflow
        workflow = self.get_workflow_for_doctype(doctype)
        if not workflow:
            raise WorkflowNotFoundError(
                f"No active approval workflow found for {doctype}. "
                "Document cannot be submitted for approval."
            )

        # Get applicable steps based on amount thresholds
        steps = self.get_workflow_steps(workflow.id)
        applicable_steps = self._filter_steps_by_amount(steps, amount)

        if not applicable_steps:
            # No steps apply - auto-approve
            if approval:
                approval.status = ApprovalStatus.APPROVED
                approval.approved_at = datetime.utcnow()
                approval.approved_by_id = user_id
            else:
                approval = DocumentApproval(
                    doctype=doctype,
                    document_id=document_id,
                    workflow_id=workflow.id,
                    current_step=0,
                    status=ApprovalStatus.APPROVED,
                    amount=amount,
                    submitted_at=datetime.utcnow(),
                    submitted_by_id=user_id,
                    approved_at=datetime.utcnow(),
                    approved_by_id=user_id,
                )
                self.db.add(approval)
        else:
            # Check for auto-approve based on amount
            first_step = applicable_steps[0]
            if first_step.auto_approve_below and amount and amount < first_step.auto_approve_below:
                if approval:
                    approval.status = ApprovalStatus.APPROVED
                    approval.approved_at = datetime.utcnow()
                    approval.approved_by_id = user_id
                else:
                    approval = DocumentApproval(
                        doctype=doctype,
                        document_id=document_id,
                        workflow_id=workflow.id,
                        current_step=0,
                        status=ApprovalStatus.APPROVED,
                        amount=amount,
                        submitted_at=datetime.utcnow(),
                        submitted_by_id=user_id,
                        approved_at=datetime.utcnow(),
                        approved_by_id=user_id,
                    )
                    self.db.add(approval)
            else:
                # Normal submission - set to pending at first step
                if approval:
                    approval.workflow_id = workflow.id
                    approval.current_step = first_step.step_order
                    approval.status = ApprovalStatus.PENDING
                    approval.amount = amount
                    approval.submitted_at = datetime.utcnow()
                    approval.submitted_by_id = user_id
                    approval.approved_at = None
                    approval.approved_by_id = None
                    approval.rejected_at = None
                    approval.rejected_by_id = None
                    approval.rejection_reason = None
                else:
                    approval = DocumentApproval(
                        doctype=doctype,
                        document_id=document_id,
                        workflow_id=workflow.id,
                        current_step=first_step.step_order,
                        status=ApprovalStatus.PENDING,
                        amount=amount,
                        submitted_at=datetime.utcnow(),
                        submitted_by_id=user_id,
                    )
                    self.db.add(approval)

        self.db.flush()

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=0,
            action="submit",
            user_id=user_id,
            remarks=f"Submitted for approval. Amount: {amount}",
        )
        self.db.add(history)

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log_submit(
            doctype=doctype,
            document_id=document_id,
            user_id=user_id,
            document_name=document_name,
            old_values=old_values,
            new_values=new_values,
        )

        # Emit notification to approvers if pending
        if approval.status == ApprovalStatus.PENDING:
            current_step = self._get_current_step(approval)
            if current_step:
                approver_ids = self._get_step_approver_ids(current_step)
                self._emit_approval_notification(
                    event_type=NotificationEventType.APPROVAL_REQUESTED,
                    doctype=doctype,
                    document_id=document_id,
                    user_ids=approver_ids,
                    payload={
                        "doctype": doctype,
                        "document_id": document_id,
                        "document_name": document_name,
                        "amount": float(amount) if amount else None,
                        "submitted_by_id": user_id,
                        "step_order": current_step.step_order,
                    },
                )

        self.db.flush()
        return approval

    # =========================================================================
    # APPROVAL ACTIONS
    # =========================================================================

    def approve_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        remarks: Optional[str] = None,
    ) -> DocumentApproval:
        """
        Approve a document at the current step.

        Args:
            doctype: Document type
            document_id: ID of the document
            user_id: ID of user approving
            remarks: Optional approval remarks

        Returns:
            Updated DocumentApproval

        Raises:
            ApprovalNotFoundError: If no approval record exists
            UnauthorizedApprovalError: If user cannot approve
            InvalidStateError: If document is not pending approval
        """
        approval = self._get_approval(doctype, document_id)
        old_values = serialize_for_audit(approval)

        if approval.status != ApprovalStatus.PENDING:
            raise InvalidStateError(
                f"Document is {approval.status.value}, not pending approval."
            )

        # Check authorization
        if not self.can_user_approve(doctype, document_id, user_id):
            raise UnauthorizedApprovalError(
                "You are not authorized to approve this document at the current step."
            )

        # Get current step
        current_step = self._get_current_step(approval)
        if not current_step:
            raise InvalidStateError("Current approval step not found.")

        # Record step approval
        approval.step_approved_at = datetime.utcnow()
        approval.step_approved_by_id = user_id
        approval.step_remarks = remarks

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=current_step.step_order,
            action="approve",
            user_id=user_id,
            remarks=remarks,
        )
        self.db.add(history)

        # Check if there are more steps
        next_step = self._get_next_step(approval, current_step)

        if next_step:
            # Move to next step
            approval.current_step = next_step.step_order
            approval.step_approved_at = None
            approval.step_approved_by_id = None
            approval.step_remarks = None
        else:
            # Final approval - mark as approved
            approval.status = ApprovalStatus.APPROVED
            approval.approved_at = datetime.utcnow()
            approval.approved_by_id = user_id

        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log_approve(
            doctype=doctype,
            document_id=document_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks,
        )

        # Emit notifications
        if approval.status == ApprovalStatus.APPROVED:
            # Notify submitter of final approval
            if approval.submitted_by_id:
                self._emit_approval_notification(
                    event_type=NotificationEventType.APPROVAL_APPROVED,
                    doctype=doctype,
                    document_id=document_id,
                    user_ids=[approval.submitted_by_id],
                    payload={
                        "doctype": doctype,
                        "document_id": document_id,
                        "approved_by_id": user_id,
                        "remarks": remarks,
                    },
                )
        elif next_step:
            # Notify next-step approvers
            next_approver_ids = self._get_step_approver_ids(next_step)
            self._emit_approval_notification(
                event_type=NotificationEventType.APPROVAL_REQUESTED,
                doctype=doctype,
                document_id=document_id,
                user_ids=next_approver_ids,
                payload={
                    "doctype": doctype,
                    "document_id": document_id,
                    "step_order": next_step.step_order,
                    "previous_approver_id": user_id,
                },
            )

        return approval

    def reject_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        reason: str,
    ) -> DocumentApproval:
        """
        Reject a document.

        Args:
            doctype: Document type
            document_id: ID of the document
            user_id: ID of user rejecting
            reason: Rejection reason (required)

        Returns:
            Updated DocumentApproval

        Raises:
            ApprovalNotFoundError: If no approval record exists
            UnauthorizedApprovalError: If user cannot reject
            InvalidStateError: If document is not pending approval
        """
        approval = self._get_approval(doctype, document_id)
        old_values = serialize_for_audit(approval)

        if approval.status != ApprovalStatus.PENDING:
            raise InvalidStateError(
                f"Document is {approval.status.value}, not pending approval."
            )

        # Check authorization and rejection permission
        current_step = self._get_current_step(approval)
        if not current_step:
            raise InvalidStateError("Current approval step not found.")

        if not current_step.can_reject:
            raise InvalidStateError(
                "Rejection is not allowed at this approval step."
            )

        if not self.can_user_approve(doctype, document_id, user_id):
            raise UnauthorizedApprovalError(
                "You are not authorized to reject this document at the current step."
            )

        # Update approval
        approval.status = ApprovalStatus.REJECTED
        approval.rejected_at = datetime.utcnow()
        approval.rejected_by_id = user_id
        approval.rejection_reason = reason

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=current_step.step_order,
            action="reject",
            user_id=user_id,
            remarks=reason,
        )
        self.db.add(history)
        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log_reject(
            doctype=doctype,
            document_id=document_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            remarks=reason,
        )

        # Notify submitter of rejection
        if approval.submitted_by_id:
            self._emit_approval_notification(
                event_type=NotificationEventType.APPROVAL_REJECTED,
                doctype=doctype,
                document_id=document_id,
                user_ids=[approval.submitted_by_id],
                payload={
                    "doctype": doctype,
                    "document_id": document_id,
                    "rejected_by_id": user_id,
                    "reason": reason,
                },
            )

        return approval

    def post_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        remarks: Optional[str] = None,
    ) -> DocumentApproval:
        """
        Post an approved document (e.g., post to GL).

        Args:
            doctype: Document type
            document_id: ID of the document
            user_id: ID of user posting
            remarks: Optional posting remarks

        Returns:
            Updated DocumentApproval

        Raises:
            ApprovalNotFoundError: If no approval record exists
            InvalidStateError: If document is not approved
        """
        approval = self._get_approval(doctype, document_id)
        old_values = serialize_for_audit(approval)

        if approval.status != ApprovalStatus.APPROVED:
            raise InvalidStateError(
                f"Document must be approved before posting. Current status: {approval.status.value}"
            )

        # Update approval
        approval.status = ApprovalStatus.POSTED
        approval.posted_at = datetime.utcnow()
        approval.posted_by_id = user_id

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=approval.current_step,
            action="post",
            user_id=user_id,
            remarks=remarks,
        )
        self.db.add(history)
        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log_post(
            doctype=doctype,
            document_id=document_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            remarks=remarks,
        )

        return approval

    def cancel_document(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
        reason: str,
    ) -> DocumentApproval:
        """
        Cancel a document approval.

        Args:
            doctype: Document type
            document_id: ID of the document
            user_id: ID of user cancelling
            reason: Cancellation reason

        Returns:
            Updated DocumentApproval
        """
        approval = self._get_approval(doctype, document_id)
        old_values = serialize_for_audit(approval)

        if approval.status == ApprovalStatus.POSTED:
            raise InvalidStateError(
                "Posted documents cannot be cancelled. Use reversal instead."
            )

        # Update approval
        approval.status = ApprovalStatus.CANCELLED

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=approval.current_step,
            action="cancel",
            user_id=user_id,
            remarks=reason,
        )
        self.db.add(history)
        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log_cancel(
            doctype=doctype,
            document_id=document_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            remarks=reason,
        )

        return approval

    # =========================================================================
    # AUTHORIZATION CHECKS
    # =========================================================================

    def can_user_approve(
        self,
        doctype: str,
        document_id: int,
        user_id: int,
    ) -> bool:
        """
        Check if a user can approve a document at its current step.

        Args:
            doctype: Document type
            document_id: Document ID
            user_id: User ID to check

        Returns:
            True if user can approve, False otherwise
        """
        try:
            approval = self._get_approval(doctype, document_id)
        except ApprovalNotFoundError:
            return False

        if approval.status != ApprovalStatus.PENDING:
            return False

        current_step = self._get_current_step(approval)
        if not current_step:
            return False

        return self._user_matches_step_requirements(user_id, current_step)

    def _user_matches_step_requirements(
        self,
        user_id: int,
        step: ApprovalStep,
    ) -> bool:
        """Check if user matches the requirements for an approval step."""
        # Check specific user requirement
        if step.user_id is not None:
            return user_id == step.user_id

        # Check role requirement
        if step.role_required:
            user_roles = (
                self.db.query(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .filter(UserRole.user_id == user_id)
                .all()
            )
            role_names = [r[0] for r in user_roles]
            return step.role_required in role_names

        # No requirements - anyone can approve
        return True

    def _get_step_approver_ids(self, step: ApprovalStep) -> List[int]:
        """Get list of user IDs who can approve at this step."""
        if step.user_id is not None:
            return [step.user_id]

        if step.role_required:
            users = (
                self.db.query(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .filter(Role.name == step.role_required)
                .all()
            )
            return [u[0] for u in users]

        return []

    def _emit_approval_notification(
        self,
        event_type: NotificationEventType,
        doctype: str,
        document_id: int,
        user_ids: List[int],
        payload: Dict[str, Any],
    ) -> None:
        """Emit approval-related notification to specified users."""
        if not user_ids:
            return

        self.notification_service.emit_event(
            event_type=event_type,
            payload=payload,
            entity_type="approval",
            entity_id=document_id,
            user_ids=user_ids,
        )

    def get_pending_approvals(
        self,
        user_id: int,
        doctype: Optional[str] = None,
    ) -> List[dict]:
        """
        Get documents pending approval by a specific user.

        Args:
            user_id: User ID
            doctype: Optional filter by document type

        Returns:
            List of pending approval dicts
        """
        # Get user's roles
        user_roles = (
            self.db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        role_names = [r[0] for r in user_roles]

        # Query pending approvals
        query = self.db.query(DocumentApproval).filter(
            DocumentApproval.status == ApprovalStatus.PENDING
        )

        if doctype:
            query = query.filter(DocumentApproval.doctype == doctype)

        pending = query.all()

        # Filter to those the user can approve
        results = []
        for approval in pending:
            current_step = self._get_current_step(approval)
            if not current_step:
                continue

            can_approve = False
            if current_step.user_id == user_id:
                can_approve = True
            elif current_step.role_required and current_step.role_required in role_names:
                can_approve = True
            elif not current_step.user_id and not current_step.role_required:
                can_approve = True

            if can_approve:
                results.append({
                    "approval_id": approval.id,
                    "doctype": approval.doctype,
                    "document_id": approval.document_id,
                    "amount": str(approval.amount) if approval.amount else None,
                    "current_step": approval.current_step,
                    "step_name": current_step.step_name,
                    "submitted_at": approval.submitted_at.isoformat() if approval.submitted_at else None,
                    "submitted_by_id": approval.submitted_by_id,
                    "workflow_id": approval.workflow_id,
                    "can_reject": current_step.can_reject,
                })

        return results

    def get_approval_status(
        self,
        doctype: str,
        document_id: int,
    ) -> Optional[dict]:
        """
        Get the approval status for a document.

        Args:
            doctype: Document type
            document_id: Document ID

        Returns:
            Dict with approval status or None if no approval exists
        """
        approval = (
            self.db.query(DocumentApproval)
            .filter(
                and_(
                    DocumentApproval.doctype == doctype,
                    DocumentApproval.document_id == document_id,
                )
            )
            .first()
        )

        if not approval:
            return None

        current_step = self._get_current_step(approval)

        # Get approval history
        history = (
            self.db.query(ApprovalHistory)
            .filter(ApprovalHistory.document_approval_id == approval.id)
            .order_by(ApprovalHistory.action_at)
            .all()
        )

        return {
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
            "current_step_name": current_step.step_name if current_step else None,
            "amount": str(approval.amount) if approval.amount else None,
            "submitted_at": approval.submitted_at.isoformat() if approval.submitted_at else None,
            "submitted_by_id": approval.submitted_by_id,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
            "approved_by_id": approval.approved_by_id,
            "rejected_at": approval.rejected_at.isoformat() if approval.rejected_at else None,
            "rejected_by_id": approval.rejected_by_id,
            "rejection_reason": approval.rejection_reason,
            "posted_at": approval.posted_at.isoformat() if approval.posted_at else None,
            "posted_by_id": approval.posted_by_id,
            "history": [
                {
                    "step_order": h.step_order,
                    "action": h.action,
                    "user_id": h.user_id,
                    "remarks": h.remarks,
                    "action_at": h.action_at.isoformat(),
                }
                for h in history
            ],
        }

    # =========================================================================
    # ESCALATION
    # =========================================================================

    def check_and_escalate(self) -> List[DocumentApproval]:
        """
        Check for pending approvals that need escalation and escalate them.

        This should be called periodically (e.g., by a scheduled task).

        Returns:
            List of escalated DocumentApproval objects
        """
        escalated = []

        # Get pending approvals
        pending = (
            self.db.query(DocumentApproval)
            .filter(DocumentApproval.status == ApprovalStatus.PENDING)
            .all()
        )

        for approval in pending:
            workflow = (
                self.db.query(ApprovalWorkflow)
                .filter(ApprovalWorkflow.id == approval.workflow_id)
                .first()
            )

            if not workflow or not workflow.escalation_enabled:
                continue

            # Check if escalation timeout exceeded
            step_start = approval.step_approved_at or approval.submitted_at
            if not step_start:
                continue

            hours_elapsed = (datetime.utcnow() - step_start).total_seconds() / 3600
            if workflow.escalation_hours and hours_elapsed >= workflow.escalation_hours:
                escalated_approval = self._escalate_approval(approval)
                if escalated_approval:
                    escalated.append(escalated_approval)

        return escalated

    def _escalate_approval(self, approval: DocumentApproval) -> Optional[DocumentApproval]:
        """Escalate an approval to the next level."""
        current_step = self._get_current_step(approval)
        if not current_step:
            return None

        # Check if step has escalation configured
        if not current_step.escalation_user_id and not current_step.escalation_role:
            return None

        old_values = serialize_for_audit(approval)

        # Mark as escalated
        approval.escalated_at = datetime.utcnow()
        approval.escalation_count = (approval.escalation_count or 0) + 1

        # Record history
        history = ApprovalHistory(
            document_approval_id=approval.id,
            step_order=current_step.step_order,
            action="escalate",
            user_id=0,  # System action
            remarks=f"Auto-escalated after timeout. Escalation #{approval.escalation_count}",
        )
        self.db.add(history)
        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(approval)
        self.audit_logger.log(
            doctype=approval.doctype,
            document_id=approval.document_id,
            action=AuditAction.UPDATE,
            user_id=None,
            old_values=old_values,
            new_values=new_values,
            remarks=f"Escalated to {current_step.escalation_role or current_step.escalation_user_id}",
        )

        return approval

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_approval(self, doctype: str, document_id: int) -> DocumentApproval:
        """Get approval record or raise ApprovalNotFoundError."""
        approval = (
            self.db.query(DocumentApproval)
            .filter(
                and_(
                    DocumentApproval.doctype == doctype,
                    DocumentApproval.document_id == document_id,
                )
            )
            .first()
        )

        if not approval:
            raise ApprovalNotFoundError(
                f"No approval record found for {doctype} #{document_id}"
            )

        return approval

    def _get_current_step(self, approval: DocumentApproval) -> Optional[ApprovalStep]:
        """Get the current approval step."""
        return (
            self.db.query(ApprovalStep)
            .filter(
                and_(
                    ApprovalStep.workflow_id == approval.workflow_id,
                    ApprovalStep.step_order == approval.current_step,
                )
            )
            .first()
        )

    def _get_next_step(
        self,
        approval: DocumentApproval,
        current_step: ApprovalStep,
    ) -> Optional[ApprovalStep]:
        """Get the next applicable step after the current one."""
        steps = self.get_workflow_steps(approval.workflow_id)
        applicable = self._filter_steps_by_amount(steps, approval.amount)

        for step in applicable:
            if step.step_order > current_step.step_order:
                return step

        return None

    def _filter_steps_by_amount(
        self,
        steps: List[ApprovalStep],
        amount: Optional[Decimal],
    ) -> List[ApprovalStep]:
        """Filter steps based on amount thresholds."""
        if amount is None:
            # No amount filtering - return all steps
            return steps

        applicable = []
        for step in steps:
            # Check min threshold
            if step.amount_threshold_min is not None and amount < step.amount_threshold_min:
                continue
            # Check max threshold
            if step.amount_threshold_max is not None and amount > step.amount_threshold_max:
                continue
            applicable.append(step)

        return applicable

    def get_workflow_by_id(self, workflow_id: int) -> Optional[ApprovalWorkflow]:
        """Get a workflow by its ID."""
        return (
            self.db.query(ApprovalWorkflow)
            .filter(ApprovalWorkflow.id == workflow_id)
            .first()
        )

    def update_workflow(
        self,
        workflow_id: int,
        user_id: int,
        **updates,
    ) -> ApprovalWorkflow:
        """Update a workflow's properties."""
        workflow = self.get_workflow_by_id(workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")

        old_values = serialize_for_audit(workflow)

        # Apply updates
        allowed_fields = [
            "workflow_name", "description", "is_active", "is_mandatory",
            "escalation_enabled", "escalation_hours"
        ]
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(workflow, field, value)

        workflow.updated_at = datetime.utcnow()
        self.db.flush()

        # Audit log
        new_values = serialize_for_audit(workflow)
        self.audit_logger.log_update(
            doctype="approval_workflow",
            document_id=workflow.id,
            user_id=user_id,
            document_name=workflow.workflow_name,
            old_values=old_values,
            new_values=new_values,
        )

        return workflow

    def deactivate_workflow(self, workflow_id: int, user_id: int) -> ApprovalWorkflow:
        """Deactivate a workflow."""
        return self.update_workflow(workflow_id, user_id, is_active=False)
