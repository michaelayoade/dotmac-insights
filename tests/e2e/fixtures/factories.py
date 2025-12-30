"""
Test Data Factories for E2E Tests.

Factory functions for creating test entities with sensible defaults.
Each factory returns the created database model instance.

Factory patterns:
- create_X() - Always creates a new instance
- get_or_create_X() - Returns existing or creates new (for shared resources)
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
import random
import string

from sqlalchemy.orm import Session


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def random_string(length: int = 8) -> str:
    """Generate a random alphanumeric string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_email() -> str:
    """Generate a random email address."""
    return f"test_{random_string(8)}@example.com"


def random_phone() -> str:
    """Generate a random phone number."""
    return f"+234{random.randint(7000000000, 9999999999)}"


def calculate_working_days(start: date, end: date) -> Decimal:
    """
    Calculate working days excluding weekends.

    Args:
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Number of working days (Mon-Fri)
    """
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri (0-4)
            days += 1
        current += timedelta(days=1)
    return Decimal(days)


# =============================================================================
# CRM FACTORIES
# =============================================================================

def create_lead(
    db: Session,
    name: str = None,
    email: str = None,
    phone: str = None,
    status: str = "new",
    splynx_id: int = None,
    **kwargs
) -> "Lead":
    """Create a lead record for testing."""
    from app.models.lead import Lead

    lead = Lead(
        splynx_id=splynx_id or random.randint(10000, 99999),
        name=name or f"Test Lead {random_string(6)}",
        email=email or random_email(),
        phone=phone or random_phone(),
        status=status,
        category="business",
        city="Lagos",
        **kwargs
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def create_opportunity_stage(
    db: Session,
    name: str = None,
    sequence: int = 0,
    probability: int = 0,
    is_won: bool = False,
    is_lost: bool = False,
    color: str = None,
    **kwargs
) -> "OpportunityStage":
    """
    Always create a new opportunity stage.

    Use get_or_create_opportunity_stage() for idempotent creation.
    """
    from app.models.crm import OpportunityStage

    stage = OpportunityStage(
        name=name or f"Stage {random_string(4)}",
        sequence=sequence,
        probability=probability,
        is_won=is_won,
        is_lost=is_lost,
        color=color,
        **kwargs
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def get_or_create_opportunity_stage(
    db: Session,
    name: str,
    sequence: int = 0,
    probability: int = 0,
    is_won: bool = False,
    is_lost: bool = False,
    color: str = None,
    **kwargs
) -> "OpportunityStage":
    """
    Get existing opportunity stage by name or create new one.

    Use this for shared pipeline stages that shouldn't be duplicated.
    """
    from app.models.crm import OpportunityStage

    existing = db.query(OpportunityStage).filter(OpportunityStage.name == name).first()
    if existing:
        return existing

    return create_opportunity_stage(
        db,
        name=name,
        sequence=sequence,
        probability=probability,
        is_won=is_won,
        is_lost=is_lost,
        color=color,
        **kwargs
    )


def create_customer(
    db: Session,
    name: str = None,
    email: str = None,
    phone: str = None,
    status: str = None,
    customer_type: str = None,
    **kwargs
) -> "Customer":
    """Create a customer record for testing."""
    from app.models.customer import Customer, CustomerStatus, CustomerType

    customer = Customer(
        name=name or f"Test Customer {random_string(6)}",
        email=email or random_email(),
        phone=phone or random_phone(),
        status=CustomerStatus(status) if status else CustomerStatus.ACTIVE,
        customer_type=CustomerType(customer_type) if customer_type else CustomerType.BUSINESS,
        address="123 Test Street",
        city="Lagos",
        state="Lagos",
        country="Nigeria",
        **kwargs
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def create_opportunity(
    db: Session,
    client,
    name: str = None,
    customer_id: int = None,
    stage_id: int = None,
    deal_value: Decimal = None,
    **kwargs
) -> dict:
    """Create an opportunity via API."""
    payload = {
        "name": name or f"Test Opportunity {random_string(6)}",
        "expected_close_date": (date.today() + timedelta(days=30)).isoformat(),
        "deal_value": float(deal_value or Decimal("500000")),
        "probability": 50,
        **kwargs
    }
    if customer_id:
        payload["customer_id"] = customer_id
    if stage_id:
        payload["stage_id"] = stage_id

    response = client.post("/api/crm/opportunities/", json=payload)
    assert response.status_code in [200, 201], f"Failed to create opportunity: {response.text}"
    return response.json()


# =============================================================================
# ACCOUNTING FACTORIES
# =============================================================================

def create_invoice(
    db: Session,
    customer_id: int = None,
    contact_id: int = None,
    amount: Decimal = None,
    status: str = "pending",
    invoice_date: date = None,
    due_date: date = None,
    company: str = "Test Company",
    **kwargs
) -> "Invoice":
    """Create an invoice record for testing."""
    from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource

    inv_date = invoice_date or date.today()
    total_amount = amount or Decimal("100000")

    invoice = Invoice(
        source=InvoiceSource.INTERNAL,
        customer_id=customer_id,
        contact_id=contact_id,
        invoice_number=f"INV-{random_string(8).upper()}",
        invoice_date=datetime.combine(inv_date, datetime.min.time()),
        due_date=datetime.combine(due_date or inv_date + timedelta(days=30), datetime.min.time()),
        amount=total_amount,
        tax_amount=Decimal("0"),
        total_amount=total_amount,
        amount_paid=Decimal("0"),
        balance=total_amount,
        currency="NGN",
        base_amount=total_amount,
        base_total_amount=total_amount,
        status=InvoiceStatus(status),
        docstatus=0 if status == "draft" else 1,
        company=company,
        **kwargs
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_payment(
    db: Session,
    customer_id: int = None,
    amount: Decimal = None,
    payment_date: datetime = None,
    **kwargs
) -> "Payment":
    """Create a payment record for testing."""
    from app.models.payment import Payment, PaymentStatus, PaymentSource, PaymentMethod

    if customer_id is None:
        customer = create_customer(db, name="Payment Customer")
        customer_id = customer.id

    payment_amount = amount or Decimal("50000")

    payment = Payment(
        source=PaymentSource.INTERNAL,
        customer_id=customer_id,
        receipt_number=f"PAY-{random_string(8).upper()}",
        amount=payment_amount,
        currency="NGN",
        payment_date=payment_date or datetime.utcnow(),
        payment_method=PaymentMethod.BANK_TRANSFER,
        status=PaymentStatus.COMPLETED,
        conversion_rate=Decimal("1"),
        base_currency="NGN",
        base_amount=payment_amount,
        total_allocated=Decimal("0"),
        unallocated_amount=payment_amount,
        workflow_status="completed",
        write_back_status="pending",
        origin_system="local",  # Required field for audit tracking
        **kwargs
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def create_journal_entry(
    db: Session,
    lines: list = None,
    posting_date: date = None,
    description: str = None,
    validate_balance: bool = True,
    **kwargs
) -> "JournalEntry":
    """
    Create a journal entry for testing.

    Args:
        db: Database session
        lines: List of line dicts with account_id, debit, credit
        posting_date: Posting date (default: today)
        description: Entry description
        validate_balance: If True, raises error if debits != credits
        **kwargs: Additional fields

    Raises:
        ValueError: If validate_balance=True and entry doesn't balance
    """
    from app.models.accounting import JournalEntry, JournalEntryLine

    # Pre-validate balance before creating
    if lines and validate_balance:
        total_debit = sum(Decimal(str(l.get("debit", 0))) for l in lines)
        total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lines)
        if total_debit != total_credit:
            raise ValueError(
                f"Journal entry must balance: total_debit={total_debit}, "
                f"total_credit={total_credit}, difference={total_debit - total_credit}"
            )

    je = JournalEntry(
        entry_number=f"JE-{random_string(8).upper()}",
        posting_date=posting_date or date.today(),
        description=description or "Test journal entry",
        total_debit=Decimal("0"),
        total_credit=Decimal("0"),
        is_posted=False,
        **kwargs
    )
    db.add(je)
    db.flush()

    if lines:
        for line_data in lines:
            line = JournalEntryLine(
                journal_entry_id=je.id,
                **line_data
            )
            db.add(line)
            if line_data.get("debit"):
                je.total_debit += Decimal(str(line_data["debit"]))
            if line_data.get("credit"):
                je.total_credit += Decimal(str(line_data["credit"]))

    db.commit()
    db.refresh(je)
    return je


# =============================================================================
# HR FACTORIES
# =============================================================================

def create_employee(
    db: Session,
    name: str = None,
    email: str = None,
    department: str = None,
    designation: str = None,
    salary: Decimal = None,
    status: str = "active",
    **kwargs
) -> "Employee":
    """Create an employee record for testing."""
    from app.models.employee import Employee, EmploymentStatus

    employee = Employee(
        employee_number=f"EMP-{random_string(6).upper()}",
        name=name or f"Test Employee {random_string(6)}",
        email=email or random_email(),
        phone=random_phone(),
        department=department or "Engineering",
        designation=designation or "Software Engineer",
        salary=salary or Decimal("500000"),
        status=EmploymentStatus(status),
        date_of_joining=datetime.utcnow() - timedelta(days=365),
        **kwargs
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def create_leave_allocation(
    db: Session,
    employee_id: int,
    employee_name: str = None,
    leave_type: str = "Annual Leave",
    new_leaves_allocated: Decimal = None,
    from_date: date = None,
    to_date: date = None,
    **kwargs
) -> "LeaveAllocation":
    """Create a leave allocation for an employee."""
    from app.models.hr_leave import LeaveAllocation

    current_year = datetime.now().year
    start = from_date or date(current_year, 1, 1)
    end = to_date or date(current_year, 12, 31)
    leaves = new_leaves_allocated or Decimal("20")

    allocation = LeaveAllocation(
        employee=f"EMP-{employee_id}",
        employee_id=employee_id,
        employee_name=employee_name or f"Employee {employee_id}",
        leave_type=leave_type,
        from_date=start,
        to_date=end,
        new_leaves_allocated=leaves,
        total_leaves_allocated=leaves,
        **kwargs
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


def create_leave_application(
    db: Session,
    employee_id: int,
    leave_type: str = "Annual Leave",
    from_date: date = None,
    to_date: date = None,
    status: str = "open",
    **kwargs
) -> "LeaveApplication":
    """
    Create a leave application for testing.

    Args:
        db: Database session
        employee_id: Employee ID
        leave_type: Type of leave (default: Annual Leave)
        from_date: Start date (default: 7 days from now)
        to_date: End date (default: 2 days after start)
        status: Must be a valid LeaveApplicationStatus value (open, approved, rejected, cancelled)
        **kwargs: Additional fields

    Note:
        - Uses working days calculation (excludes weekends)
        - Status "pending" is not valid - use "open" instead
    """
    from app.models.employee import Employee
    from app.models.hr_leave import LeaveApplication, LeaveApplicationStatus

    start = from_date or date.today() + timedelta(days=7)
    end = to_date or start + timedelta(days=2)

    # Validate status - don't silently convert
    valid_statuses = [s.value for s in LeaveApplicationStatus]
    if status not in valid_statuses:
        raise ValueError(
            f"Invalid status '{status}'. Valid values: {valid_statuses}. "
            f"Note: Use 'open' instead of 'pending'."
        )

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    employee_number = employee.employee_number if employee else f"EMP-{employee_id}"
    employee_name = employee.name if employee else f"Employee {employee_id}"

    # Calculate working days (excludes weekends)
    working_days = calculate_working_days(start, end)

    application = LeaveApplication(
        employee=employee_number,
        employee_id=employee_id,
        employee_name=employee_name,
        leave_type=leave_type,
        from_date=start,
        to_date=end,
        posting_date=start,
        total_leave_days=working_days,
        description="Test leave request",
        status=LeaveApplicationStatus(status),
        **kwargs
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


# =============================================================================
# SUPPORT FACTORIES
# =============================================================================

def create_ticket(
    db: Session,
    customer_id: int = None,
    subject: str = None,
    status: str = "open",
    priority: str = "medium",
    assigned_employee_id: int = None,
    **kwargs
) -> "Ticket":
    """Create a support ticket for testing."""
    from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketSource

    ticket = Ticket(
        source=TicketSource.ERPNEXT,
        customer_id=customer_id,
        ticket_number=f"TKT-{random_string(8).upper()}",
        subject=subject or f"Test Ticket {random_string(6)}",
        description="This is a test ticket for E2E testing",
        status=TicketStatus(status),
        priority=TicketPriority(priority),
        assigned_employee_id=assigned_employee_id,
        opening_date=datetime.utcnow(),
        **kwargs
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def add_ticket_comment(
    db: Session,
    ticket_id: int,
    comment: str,
    commented_by: str = "Test User",
    is_public: bool = True,
) -> "HDTicketComment":
    """Add a comment to a ticket."""
    from app.models.ticket import HDTicketComment

    ticket_comment = HDTicketComment(
        ticket_id=ticket_id,
        comment=comment,
        commented_by=commented_by,
        commented_by_name=commented_by,
        is_public=is_public,
        comment_date=datetime.utcnow(),
    )
    db.add(ticket_comment)
    db.commit()
    db.refresh(ticket_comment)
    return ticket_comment


# =============================================================================
# PROJECT FACTORIES
# =============================================================================

def create_project(
    db: Session,
    project_name: str = None,
    customer_id: int = None,
    project_manager_id: int = None,
    status: str = "open",
    priority: str = "medium",
    **kwargs
) -> "Project":
    """Create a project for testing."""
    from app.models.project import Project, ProjectStatus, ProjectPriority

    project = Project(
        project_name=project_name or f"Test Project {random_string(6)}",
        customer_id=customer_id,
        project_manager_id=project_manager_id,
        status=ProjectStatus(status),
        priority=ProjectPriority(priority),
        expected_start_date=datetime.utcnow(),
        expected_end_date=datetime.utcnow() + timedelta(days=30),
        estimated_costing=Decimal("1000000"),
        **kwargs
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_task(
    db: Session,
    project_id: int,
    subject: str = None,
    status: str = "open",
    assigned_to_id: int = None,
    **kwargs
) -> "Task":
    """Create a task for a project."""
    from app.models.task import Task, TaskStatus

    task = Task(
        project_id=project_id,
        subject=subject or f"Test Task {random_string(6)}",
        status=TaskStatus(status),
        assigned_to_id=assigned_to_id,
        exp_start_date=datetime.utcnow(),
        exp_end_date=datetime.utcnow() + timedelta(days=7),
        **kwargs
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# =============================================================================
# PURCHASING FACTORIES
# =============================================================================

def create_supplier(
    db: Session,
    name: str = None,
    email: str = None,
    **kwargs
) -> "Contact":
    """Create a supplier contact for testing."""
    from app.models.contact import Contact, ContactType

    supplier = Contact(
        name=name or f"Test Supplier {random_string(6)}",
        email=email or random_email(),
        phone=random_phone(),
        contact_type=ContactType.SUPPLIER,
        is_active=True,
        **kwargs
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def create_bill(
    db: Session,
    supplier_id: int = None,
    amount: Decimal = None,
    bill_date: date = None,
    due_date: date = None,
    status: str = "pending",
    **kwargs
) -> dict:
    """Create a bill (purchase invoice) via API helper."""
    # Similar to invoice but for AP
    from app.models.accounting_ext import PurchaseInvoice, PurchaseInvoiceStatus

    bill = PurchaseInvoice(
        supplier_id=supplier_id,
        invoice_number=f"BILL-{random_string(8).upper()}",
        invoice_date=bill_date or date.today(),
        due_date=due_date or date.today() + timedelta(days=30),
        total_amount=amount or Decimal("75000"),
        amount_paid=Decimal("0"),
        balance=amount or Decimal("75000"),
        currency="NGN",
        status=PurchaseInvoiceStatus(status),
        **kwargs
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill
