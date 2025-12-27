"""
Workflow Verification Helpers for E2E Tests.

Provides utilities for verifying business workflow outcomes:
- GL entry verification
- Balance checks
- Status transition validation
- Document state verification
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session


# =============================================================================
# GL / ACCOUNTING VERIFICATION
# =============================================================================

def verify_gl_entry_exists(
    db: Session,
    document_type: str,
    document_id: int,
) -> Optional[Dict]:
    """
    Verify a GL entry was created for a document.

    Args:
        db: Database session
        document_type: Type of document (e.g., 'Invoice', 'Payment')
        document_id: ID of the document

    Returns:
        Dict with entry details or None if not found
    """
    from app.models.accounting import JournalEntry

    entry = db.query(JournalEntry).filter(
        JournalEntry.reference_type == document_type,
        JournalEntry.reference_id == document_id,
    ).first()

    if not entry:
        return None

    return {
        "id": entry.id,
        "entry_number": entry.entry_number,
        "posting_date": entry.posting_date,
        "total_debit": entry.total_debit,
        "total_credit": entry.total_credit,
        "is_posted": entry.is_posted,
        "description": entry.description,
    }


def verify_gl_balanced(
    db: Session,
    journal_entry_id: int,
) -> bool:
    """
    Verify a journal entry is balanced (debits = credits).

    Args:
        db: Database session
        journal_entry_id: ID of the journal entry

    Returns:
        True if balanced, False otherwise
    """
    from app.models.accounting import JournalEntry

    entry = db.query(JournalEntry).filter(
        JournalEntry.id == journal_entry_id
    ).first()

    if not entry:
        return False

    return entry.total_debit == entry.total_credit


def get_account_balance(
    db: Session,
    account_id: int,
    as_of_date: datetime = None,
) -> Decimal:
    """
    Get the balance of an account.

    Args:
        db: Database session
        account_id: ID of the account
        as_of_date: Optional date to get balance as of

    Returns:
        Account balance as Decimal
    """
    from sqlalchemy import func
    from app.models.accounting import GLEntry

    query = db.query(
        func.coalesce(func.sum(GLEntry.debit), Decimal("0")) -
        func.coalesce(func.sum(GLEntry.credit), Decimal("0"))
    ).filter(GLEntry.account_id == account_id)

    if as_of_date:
        query = query.filter(GLEntry.posting_date <= as_of_date)

    result = query.scalar()
    return result or Decimal("0")


def verify_ar_balance(
    db: Session,
    customer_id: int,
    expected_balance: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> bool:
    """
    Verify a customer's accounts receivable balance.

    Args:
        db: Database session
        customer_id: ID of the customer
        expected_balance: Expected AR balance
        tolerance: Acceptable difference

    Returns:
        True if balance matches within tolerance
    """
    from app.models.invoice import Invoice, InvoiceStatus

    # Sum unpaid invoice balances
    invoices = db.query(Invoice).filter(
        Invoice.customer_id == customer_id,
        Invoice.status.in_([
            InvoiceStatus.PENDING,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        ])
    ).all()

    actual_balance = sum(inv.balance or Decimal("0") for inv in invoices)

    return abs(actual_balance - expected_balance) <= tolerance


def verify_ap_balance(
    db: Session,
    supplier_id: int,
    expected_balance: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> bool:
    """
    Verify a supplier's accounts payable balance.

    Args:
        db: Database session
        supplier_id: ID of the supplier
        expected_balance: Expected AP balance
        tolerance: Acceptable difference

    Returns:
        True if balance matches within tolerance
    """
    from app.models.accounting_ext import PurchaseInvoice, PurchaseInvoiceStatus

    # Sum unpaid bill balances
    bills = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.supplier_id == supplier_id,
        PurchaseInvoice.status.in_([
            PurchaseInvoiceStatus.PENDING,
            PurchaseInvoiceStatus.PARTIALLY_PAID,
        ])
    ).all()

    actual_balance = sum(bill.balance or Decimal("0") for bill in bills)

    return abs(actual_balance - expected_balance) <= tolerance


# =============================================================================
# INVOICE / PAYMENT VERIFICATION
# =============================================================================

def verify_invoice_status(
    db: Session,
    invoice_id: int,
    expected_status: str,
) -> bool:
    """Verify an invoice has the expected status."""
    from app.models.invoice import Invoice, InvoiceStatus

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return False

    return invoice.status == InvoiceStatus(expected_status)


def verify_invoice_payment(
    db: Session,
    invoice_id: int,
    expected_paid: Decimal,
    expected_balance: Decimal,
) -> Dict[str, bool]:
    """
    Verify invoice payment amounts.

    Returns:
        Dict with 'paid_correct' and 'balance_correct' flags
    """
    from app.models.invoice import Invoice

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"paid_correct": False, "balance_correct": False}

    return {
        "paid_correct": invoice.amount_paid == expected_paid,
        "balance_correct": invoice.balance == expected_balance,
    }


def get_payment_allocations(
    db: Session,
    payment_id: int,
) -> List[Dict]:
    """Get all allocations for a payment."""
    from app.models.payment_allocation import PaymentAllocation

    allocations = db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_id == payment_id
    ).all()

    return [
        {
            "id": a.id,
            "document_type": a.allocation_type.value if a.allocation_type else None,
            "document_id": a.document_id,
            "amount": a.allocated_amount,
        }
        for a in allocations
    ]


# =============================================================================
# CRM VERIFICATION
# =============================================================================

def verify_lead_converted(
    db: Session,
    lead_id: int,
) -> Dict[str, Any]:
    """
    Verify a lead has been converted to a customer.

    Returns:
        Dict with conversion status and customer_id if converted
    """
    from app.models.lead import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"converted": False, "customer_id": None}

    return {
        "converted": lead.customer_id is not None,
        "customer_id": lead.customer_id,
        "conversion_date": lead.conversion_date,
        "status": lead.status,
    }


def verify_opportunity_stage(
    db: Session,
    opportunity_id: int,
    expected_stage: str,
) -> bool:
    """Verify an opportunity is at the expected pipeline stage."""
    from app.models.crm import Opportunity

    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return False

    return opp.stage == expected_stage


# =============================================================================
# HR VERIFICATION
# =============================================================================

def verify_leave_balance(
    db: Session,
    employee_id: int,
    leave_type: str,
    expected_remaining: Decimal,
    year: int = None,
) -> bool:
    """Verify an employee's remaining leave balance."""
    from app.models.hr_leave import LeaveAllocation
    from datetime import datetime

    year = year or datetime.now().year

    allocation = db.query(LeaveAllocation).filter(
        LeaveAllocation.employee_id == employee_id,
        LeaveAllocation.leave_type == leave_type,
        LeaveAllocation.year == year,
    ).first()

    if not allocation:
        return False

    remaining = allocation.total_days - allocation.used_days
    return remaining == expected_remaining


def verify_payslip_generated(
    db: Session,
    employee_id: int,
    payroll_entry_id: int,
) -> Dict[str, Any]:
    """Verify a payslip was generated for an employee."""
    from app.models.hr_payroll import PayrollSlip

    slip = db.query(PayrollSlip).filter(
        PayrollSlip.employee_id == employee_id,
        PayrollSlip.payroll_entry_id == payroll_entry_id,
    ).first()

    if not slip:
        return {"exists": False}

    return {
        "exists": True,
        "id": slip.id,
        "gross_pay": slip.gross_pay,
        "net_pay": slip.net_pay,
        "status": slip.status.value if slip.status else None,
    }


# =============================================================================
# SUPPORT VERIFICATION
# =============================================================================

def verify_ticket_status(
    db: Session,
    ticket_id: int,
    expected_status: str,
) -> bool:
    """Verify a ticket has the expected status."""
    from app.models.ticket import Ticket, TicketStatus

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return False

    return ticket.status == TicketStatus(expected_status)


def verify_ticket_assigned(
    db: Session,
    ticket_id: int,
    expected_employee_id: int,
) -> bool:
    """Verify a ticket is assigned to the expected employee."""
    from app.models.ticket import Ticket

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return False

    return ticket.assigned_employee_id == expected_employee_id


def get_ticket_activity_log(
    db: Session,
    ticket_id: int,
) -> List[Dict]:
    """Get activity log entries for a ticket."""
    from app.models.ticket import HDTicketActivity

    activities = db.query(HDTicketActivity).filter(
        HDTicketActivity.ticket_id == ticket_id
    ).order_by(HDTicketActivity.activity_date.desc()).all()

    return [
        {
            "id": a.id,
            "activity_type": a.activity_type,
            "from_status": a.from_status,
            "to_status": a.to_status,
            "owner": a.owner,
            "activity_date": a.activity_date,
        }
        for a in activities
    ]


def verify_sla_met(
    db: Session,
    ticket_id: int,
) -> Dict[str, bool]:
    """Check if SLA targets were met for a ticket."""
    from app.models.ticket import Ticket
    from app.utils.datetime_utils import utc_now

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"response_sla_met": False, "resolution_sla_met": False}

    now = utc_now()

    response_met = True
    if ticket.response_by and ticket.first_responded_on:
        response_met = ticket.first_responded_on <= ticket.response_by

    resolution_met = True
    if ticket.resolution_by and ticket.resolution_date:
        resolution_met = ticket.resolution_date <= ticket.resolution_by

    return {
        "response_sla_met": response_met,
        "resolution_sla_met": resolution_met,
    }


# =============================================================================
# PROJECT VERIFICATION
# =============================================================================

def verify_project_status(
    db: Session,
    project_id: int,
    expected_status: str,
) -> bool:
    """Verify a project has the expected status."""
    from app.models.project import Project, ProjectStatus

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False

    return project.status == ProjectStatus(expected_status)


def verify_project_completion(
    db: Session,
    project_id: int,
    expected_percent: Decimal,
    tolerance: Decimal = Decimal("1"),
) -> bool:
    """Verify project completion percentage."""
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False

    return abs(project.percent_complete - expected_percent) <= tolerance


def get_project_task_summary(
    db: Session,
    project_id: int,
) -> Dict[str, int]:
    """Get summary of task statuses for a project."""
    from app.models.task import Task
    from sqlalchemy import func

    results = db.query(
        Task.status,
        func.count(Task.id)
    ).filter(
        Task.project_id == project_id
    ).group_by(Task.status).all()

    return {str(status.value): count for status, count in results}


def verify_milestone_completed(
    db: Session,
    milestone_id: int,
) -> bool:
    """Verify a project milestone is completed."""
    from app.models.project import Milestone, MilestoneStatus

    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        return False

    return milestone.status == MilestoneStatus.COMPLETED
