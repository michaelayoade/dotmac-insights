"""Event handlers for automatic workflow task creation.

This module registers handlers for various events that should create
or complete workflow tasks. Handlers are registered via the @subscribe
decorator and executed asynchronously by the event bus.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.services.event_bus import subscribe, Event
from app.models.notification import NotificationEventType
from app.services.workflow_task_service import WorkflowTaskService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


# =============================================================================
# APPROVAL WORKFLOW HANDLERS
# =============================================================================

@subscribe(NotificationEventType.APPROVAL_REQUESTED)
def on_approval_requested(event: Event, db: "Session") -> None:
    """
    Create tasks for approvers when a document is submitted for approval.

    Expected payload:
        - approval_id: int
        - doctype: str (journal_entry, expense, etc.)
        - document_id: int
        - approver_user_ids: List[int]
        - amount: Optional[float]
        - submitted_by_id: int
    """
    service = WorkflowTaskService(db)
    payload = event.payload

    approval_id = payload.get("approval_id")
    doctype = payload.get("doctype", "document")
    document_id = payload.get("document_id")
    approver_user_ids = event.user_ids or payload.get("approver_user_ids", [])
    amount = payload.get("amount")
    submitted_by_id = payload.get("submitted_by_id")

    # Determine module based on doctype
    module = _get_module_for_doctype(doctype)

    # Format amount for display
    amount_str = f" (${amount:,.2f})" if amount else ""

    # Create task for each approver
    for user_id in approver_user_ids:
        service.create_task(
            source_type="approval",
            source_id=approval_id,
            title=f"Approve {_format_doctype(doctype)} #{document_id}{amount_str}",
            module=module,
            assignee_user_id=user_id,
            assigned_by_id=submitted_by_id,
            action_url=f"/accounting/approvals/{doctype}/{document_id}",
            priority="high" if amount and amount > 10000 else "medium",
            company=event.company,
            metadata={
                "doctype": doctype,
                "document_id": document_id,
                "amount": amount,
            },
        )

    logger.info(
        "approval_tasks_created",
        approval_id=approval_id,
        doctype=doctype,
        document_id=document_id,
        approver_count=len(approver_user_ids),
    )


@subscribe(NotificationEventType.APPROVAL_APPROVED)
def on_approval_approved(event: Event, db: "Session") -> None:
    """Complete approval task when document is approved."""
    service = WorkflowTaskService(db)
    payload = event.payload

    approval_id = payload.get("approval_id")
    approved_by_id = payload.get("approved_by_id")

    if approval_id and approved_by_id:
        service.complete_task(
            source_type="approval",
            source_id=approval_id,
            completed_by_id=approved_by_id,
            assignee_user_id=approved_by_id,
        )


@subscribe(NotificationEventType.APPROVAL_REJECTED)
def on_approval_rejected(event: Event, db: "Session") -> None:
    """Cancel all approval tasks when document is rejected."""
    service = WorkflowTaskService(db)
    payload = event.payload

    approval_id = payload.get("approval_id")

    if approval_id:
        service.cancel_tasks_for_source(
            source_type="approval",
            source_id=approval_id,
        )


# =============================================================================
# PERFORMANCE REVIEW HANDLERS
# =============================================================================

@subscribe(NotificationEventType.PERF_REVIEW_REQUESTED)
def on_perf_review_requested(event: Event, db: "Session") -> None:
    """
    Create task for manager when scorecard needs review.

    Expected payload:
        - scorecard_id: int
        - employee_name: str
        - period_name: str
        - reviewer_user_id: int
    """
    service = WorkflowTaskService(db)
    payload = event.payload

    scorecard_id = payload.get("scorecard_id")
    employee_name = payload.get("employee_name", "Employee")
    period_name = payload.get("period_name", "")
    reviewer_user_id = payload.get("reviewer_user_id")

    if not reviewer_user_id:
        reviewer_user_id = event.user_ids[0] if event.user_ids else None

    if not reviewer_user_id:
        logger.warning(
            "no_reviewer_for_scorecard",
            scorecard_id=scorecard_id,
        )
        return

    period_str = f" - {period_name}" if period_name else ""

    service.create_task(
        source_type="scorecard",
        source_id=scorecard_id,
        title=f"Review {employee_name}'s scorecard{period_str}",
        module="performance",
        assignee_user_id=reviewer_user_id,
        action_url=f"/performance/reviews/{scorecard_id}",
        priority="medium",
        company=event.company,
        metadata={
            "employee_name": employee_name,
            "period_name": period_name,
        },
    )


@subscribe(NotificationEventType.PERF_SCORECARD_APPROVED)
def on_perf_scorecard_approved(event: Event, db: "Session") -> None:
    """Complete scorecard review task when approved."""
    service = WorkflowTaskService(db)
    payload = event.payload

    scorecard_id = payload.get("scorecard_id")
    approved_by_id = payload.get("approved_by_id")

    if scorecard_id and approved_by_id:
        service.complete_task(
            source_type="scorecard",
            source_id=scorecard_id,
            completed_by_id=approved_by_id,
        )


@subscribe(NotificationEventType.PERF_SCORECARD_REJECTED)
def on_perf_scorecard_rejected(event: Event, db: "Session") -> None:
    """Cancel scorecard review task when rejected."""
    service = WorkflowTaskService(db)
    payload = event.payload

    scorecard_id = payload.get("scorecard_id")

    if scorecard_id:
        service.cancel_tasks_for_source(
            source_type="scorecard",
            source_id=scorecard_id,
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_module_for_doctype(doctype: str) -> str:
    """Map document type to module."""
    module_map = {
        "journal_entry": "accounting",
        "payment": "accounting",
        "supplier_payment": "accounting",
        "invoice": "accounting",
        "purchase_invoice": "accounting",
        "credit_note": "accounting",
        "debit_note": "accounting",
        "bank_transaction": "accounting",
        "expense": "expenses",
        "expense_claim": "expenses",
        "cash_advance": "expenses",
    }
    return module_map.get(doctype, "accounting")


def _format_doctype(doctype: str) -> str:
    """Format doctype for display."""
    return doctype.replace("_", " ").title()


# =============================================================================
# CUSTOM EVENT TYPES FOR TICKETS AND CONVERSATIONS
# (These would need to be added to NotificationEventType enum)
# =============================================================================

# Note: The following handlers are examples for future custom events.
# They require adding new event types to NotificationEventType enum.

# @subscribe(NotificationEventType.TICKET_ASSIGNED)
# def on_ticket_assigned(event: Event, db: "Session") -> None:
#     """Create task for agent when ticket is assigned."""
#     service = WorkflowTaskService(db)
#     payload = event.payload
#
#     ticket_id = payload.get("ticket_id")
#     subject = payload.get("subject", "Ticket")
#     assignee_user_id = payload.get("assignee_user_id")
#     priority = payload.get("priority", "medium")
#
#     if assignee_user_id:
#         service.create_task(
#             source_type="ticket",
#             source_id=ticket_id,
#             title=f"Resolve: {subject}",
#             module="support",
#             assignee_user_id=assignee_user_id,
#             action_url=f"/support/tickets/{ticket_id}",
#             priority=priority,
#             company=event.company,
#         )

# @subscribe(NotificationEventType.CONVERSATION_ASSIGNED)
# def on_conversation_assigned(event: Event, db: "Session") -> None:
#     """Create task for agent when conversation is assigned."""
#     service = WorkflowTaskService(db)
#     payload = event.payload
#
#     conversation_id = payload.get("conversation_id")
#     contact_name = payload.get("contact_name", "Customer")
#     assignee_user_id = payload.get("assignee_user_id")
#
#     if assignee_user_id:
#         service.create_task(
#             source_type="conversation",
#             source_id=conversation_id,
#             title=f"Respond to {contact_name}",
#             module="inbox",
#             assignee_user_id=assignee_user_id,
#             action_url=f"/inbox/conversations/{conversation_id}",
#             priority="medium",
#             company=event.company,
#         )
