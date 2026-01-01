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


# =============================================================================
# UNIFIED CONTACT FACTORIES
# =============================================================================

def create_unified_contact(
    db: Session,
    name: str = None,
    contact_type: str = "customer",
    category: str = "business",
    email: str = None,
    phone: str = None,
    status: str = "active",
    company_name: str = None,
    **kwargs
) -> "UnifiedContact":
    """
    Create a unified contact for testing.

    Contact types: lead, prospect, customer, churned, person
    Categories: residential, business, enterprise, government, non_profit
    """
    from app.models.unified_contact import (
        UnifiedContact, ContactType, ContactCategory, ContactStatus
    )

    contact = UnifiedContact(
        name=name or f"Test Contact {random_string(6)}",
        contact_type=ContactType(contact_type),
        category=ContactCategory(category),
        status=ContactStatus(status),
        email=email or random_email(),
        phone=phone or random_phone(),
        company_name=company_name,
        city="Lagos",
        state="Lagos",
        country="Nigeria",
        first_contact_date=datetime.now(),
        **kwargs
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def create_person_contact(
    db: Session,
    parent_id: int,
    name: str = None,
    role: str = "Primary Contact",
    email: str = None,
    **kwargs
) -> "UnifiedContact":
    """Create a person contact linked to an organization."""
    from app.models.unified_contact import (
        UnifiedContact, ContactType, ContactCategory, ContactStatus
    )

    contact = UnifiedContact(
        name=name or f"Contact Person {random_string(6)}",
        contact_type=ContactType.PERSON,
        category=ContactCategory.BUSINESS,
        status=ContactStatus.ACTIVE,
        email=email or random_email(),
        phone=random_phone(),
        parent_id=parent_id,
        designation=role,
        is_primary_contact=True,
        first_contact_date=datetime.now(),
        **kwargs
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


# =============================================================================
# FIELD SERVICE FACTORIES
# =============================================================================

def create_service_zone(
    db: Session,
    name: str = None,
    code: str = None,
    coverage_areas: list = None,
    **kwargs
) -> "ServiceZone":
    """Create a service zone for field service testing."""
    from app.models.field_service import ServiceZone

    zone = ServiceZone(
        name=name or f"Zone {random_string(4)}",
        code=code or f"ZN-{random_string(4).upper()}",
        coverage_areas=coverage_areas or ["Lagos Island", "Victoria Island"],
        center_latitude=Decimal("6.4541"),
        center_longitude=Decimal("3.3947"),
        **kwargs
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


def create_service_order(
    db: Session,
    customer_id: int = None,
    order_type: str = "installation",
    status: str = "draft",
    priority: str = "medium",
    scheduled_date: date = None,
    technician_id: int = None,
    **kwargs
) -> "ServiceOrder":
    """
    Create a field service order for testing.

    Types: installation, repair, maintenance, inspection, relocation, upgrade, disconnection
    """
    from app.models.field_service import (
        ServiceOrder, ServiceOrderType, ServiceOrderStatus, ServiceOrderPriority
    )

    order = ServiceOrder(
        order_number=f"FSO-{random_string(8).upper()}",
        customer_id=customer_id,
        order_type=ServiceOrderType(order_type),
        status=ServiceOrderStatus(status),
        priority=ServiceOrderPriority(priority),
        scheduled_date=scheduled_date or date.today() + timedelta(days=1),
        description=f"Test service order - {order_type}",
        technician_id=technician_id,
        **kwargs
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# =============================================================================
# INVENTORY FACTORIES
# =============================================================================

def create_warehouse(
    db: Session,
    name: str = None,
    warehouse_type: str = "Stock",
    **kwargs
) -> "Warehouse":
    """Create a warehouse for inventory testing."""
    from app.models.inventory import Warehouse

    warehouse = Warehouse(
        warehouse_name=name or f"Warehouse {random_string(4)}",
        warehouse_type=warehouse_type,
        company="Test Company",
        is_group=False,
        disabled=False,
        origin_system="local",
        **kwargs
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def create_stock_item(
    db: Session,
    item_name: str = None,
    item_code: str = None,
    item_group: str = "Products",
    **kwargs
) -> "Item":
    """Create an inventory item for testing."""
    from app.models.inventory import Item

    item = Item(
        item_name=item_name or f"Test Item {random_string(6)}",
        item_code=item_code or f"ITM-{random_string(6).upper()}",
        item_group=item_group,
        stock_uom="Nos",
        is_stock_item=True,
        disabled=False,
        origin_system="local",
        **kwargs
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_stock_entry(
    db: Session,
    entry_type: str = "Material Receipt",
    from_warehouse: str = None,
    to_warehouse: str = None,
    total_amount: Decimal = None,
    **kwargs
) -> "StockEntry":
    """Create a stock entry (inventory transaction) for testing."""
    from app.models.inventory import StockEntry

    entry = StockEntry(
        stock_entry_type=entry_type,
        posting_date=datetime.now(),
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        total_amount=total_amount or Decimal("0"),
        company="Test Company",
        origin_system="local",
        **kwargs
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# =============================================================================
# EXPENSE MANAGEMENT FACTORIES
# =============================================================================

def create_expense_claim(
    db: Session,
    employee_id: int,
    claim_date: date = None,
    total_amount: Decimal = None,
    status: str = "draft",
    funding_method: str = "out_of_pocket",
    **kwargs
) -> "ExpenseClaim":
    """Create an expense claim for testing."""
    from app.models.expense_management import (
        ExpenseClaim, ExpenseClaimStatus, FundingMethod
    )

    claim = ExpenseClaim(
        claim_number=f"EXP-{random_string(8).upper()}",
        employee_id=employee_id,
        claim_date=claim_date or date.today(),
        total_claimed=total_amount or Decimal("50000"),
        total_approved=Decimal("0"),
        status=ExpenseClaimStatus(status),
        funding_method=FundingMethod(funding_method),
        description="Test expense claim",
        **kwargs
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def create_cash_advance(
    db: Session,
    employee_id: int,
    amount: Decimal = None,
    status: str = "draft",
    purpose: str = "Business Travel",
    **kwargs
) -> "CashAdvance":
    """Create a cash advance for testing."""
    from app.models.expense_management import CashAdvance, CashAdvanceStatus

    advance = CashAdvance(
        advance_number=f"ADV-{random_string(8).upper()}",
        employee_id=employee_id,
        amount_requested=amount or Decimal("100000"),
        amount_approved=Decimal("0"),
        amount_disbursed=Decimal("0"),
        amount_settled=Decimal("0"),
        status=CashAdvanceStatus(status),
        purpose=purpose,
        request_date=date.today(),
        **kwargs
    )
    db.add(advance)
    db.commit()
    db.refresh(advance)
    return advance


# =============================================================================
# PERFORMANCE MANAGEMENT FACTORIES
# =============================================================================

def create_evaluation_period(
    db: Session,
    period_type: str = "quarterly",
    status: str = "active",
    start_date: date = None,
    end_date: date = None,
    **kwargs
) -> "EvaluationPeriod":
    """Create an evaluation period for performance testing."""
    from app.models.performance import (
        EvaluationPeriod, EvaluationPeriodType, EvaluationPeriodStatus
    )

    current_year = datetime.now().year
    start = start_date or date(current_year, 1, 1)
    end = end_date or date(current_year, 3, 31)

    period = EvaluationPeriod(
        code=f"Q1-{current_year}-{random_string(4).upper()}",
        name=f"Q1 {current_year}",
        period_type=EvaluationPeriodType(period_type),
        status=EvaluationPeriodStatus(status),
        start_date=start,
        end_date=end,
        **kwargs
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def create_kpi_definition(
    db: Session,
    name: str = None,
    code: str = None,
    data_source: str = "manual",
    aggregation: str = "sum",
    **kwargs
) -> "KPIDefinition":
    """Create a KPI definition for performance testing."""
    from app.models.performance import KPIDefinition, KPIDataSource, KPIAggregation

    kpi = KPIDefinition(
        name=name or f"Test KPI {random_string(4)}",
        code=code or f"KPI-{random_string(4).upper()}",
        description="Test KPI for performance management",
        data_source=KPIDataSource(data_source),
        aggregation=KPIAggregation(aggregation),
        is_active=True,
        **kwargs
    )
    db.add(kpi)
    db.commit()
    db.refresh(kpi)
    return kpi


def create_employee_scorecard(
    db: Session,
    employee_id: int,
    period_id: int,
    template_id: int = None,
    status: str = "pending",
    **kwargs
) -> "EmployeeScorecardInstance":
    """Create an employee scorecard instance for testing."""
    from app.models.performance import (
        EmployeeScorecardInstance, ScorecardInstanceStatus
    )

    scorecard = EmployeeScorecardInstance(
        employee_id=employee_id,
        period_id=period_id,
        template_id=template_id,
        status=ScorecardInstanceStatus(status),
        overall_score=Decimal("0"),
        **kwargs
    )
    db.add(scorecard)
    db.commit()
    db.refresh(scorecard)
    return scorecard


# =============================================================================
# BANK RECONCILIATION FACTORIES
# =============================================================================

def create_bank_account(
    db: Session,
    account_name: str = None,
    bank_name: str = "Test Bank",
    account_number: str = None,
    **kwargs
) -> "BankAccount":
    """Create a bank account for reconciliation testing."""
    from app.models.accounting import BankAccount

    bank_account = BankAccount(
        account_name=account_name or f"Test Account {random_string(4)}",
        bank=bank_name,
        account_number=account_number or f"{random.randint(1000000000, 9999999999)}",
        company="Test Company",
        currency="NGN",
        disabled=False,
        **kwargs
    )
    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)
    return bank_account


def create_bank_statement(
    db: Session,
    bank_account_id: int,
    statement_date: date = None,
    opening_balance: Decimal = None,
    closing_balance: Decimal = None,
    **kwargs
) -> "BankStatement":
    """Create a bank statement for reconciliation testing."""
    from app.models.accounting_ext import BankStatement

    statement = BankStatement(
        bank_account_id=bank_account_id,
        statement_number=f"STMT-{random_string(8).upper()}",
        statement_date=statement_date or date.today(),
        opening_balance=opening_balance or Decimal("1000000"),
        closing_balance=closing_balance or Decimal("1200000"),
        status="pending",
        **kwargs
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)
    return statement


def create_bank_transaction(
    db: Session,
    bank_account_id: int,
    amount: Decimal = None,
    transaction_type: str = "credit",
    transaction_date: date = None,
    **kwargs
) -> "BankTransaction":
    """Create a bank transaction for reconciliation testing."""
    from app.models.accounting_ext import BankTransaction

    transaction = BankTransaction(
        bank_account_id=bank_account_id,
        transaction_ref=f"TXN-{random_string(10).upper()}",
        amount=amount or Decimal("50000"),
        transaction_type=transaction_type,
        transaction_date=transaction_date or date.today(),
        description="Test transaction",
        status="unreconciled",
        **kwargs
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


# =============================================================================
# NOTIFICATION FACTORIES
# =============================================================================

def create_notification(
    db: Session,
    user_id: int,
    notification_type: str = "info",
    title: str = None,
    message: str = None,
    **kwargs
) -> "Notification":
    """Create a notification for testing."""
    from app.models.notification import Notification

    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title or f"Test Notification {random_string(4)}",
        message=message or "This is a test notification",
        is_read=False,
        **kwargs
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# =============================================================================
# SCENARIO BUILDERS
# =============================================================================

def setup_accounting_period(db: Session) -> dict:
    """
    Setup a complete accounting period with fiscal year, periods, and chart of accounts.

    Returns dict with: fiscal_year, periods, accounts
    """
    from app.models.accounting import FiscalYear, Account, AccountType
    from app.models.accounting_ext import FiscalPeriod
    from app.services.period_manager import PeriodManager

    current_year = datetime.now().year

    # Create fiscal year
    fiscal_year = FiscalYear(
        year=str(current_year),
        year_start_date=date(current_year, 1, 1),
        year_end_date=date(current_year, 12, 31),
    )
    db.add(fiscal_year)
    db.commit()

    # Create fiscal periods
    PeriodManager(db).create_fiscal_periods_for_year(fiscal_year.id)
    db.commit()

    periods = db.query(FiscalPeriod).filter(
        FiscalPeriod.fiscal_year_id == fiscal_year.id
    ).all()

    # Create chart of accounts
    accounts = {}
    account_defs = [
        ("1000", "Cash", AccountType.ASSET),
        ("1100", "Accounts Receivable", AccountType.ASSET),
        ("1200", "Bank", AccountType.ASSET),
        ("2000", "Accounts Payable", AccountType.LIABILITY),
        ("2100", "Accrued Expenses", AccountType.LIABILITY),
        ("3000", "Retained Earnings", AccountType.EQUITY),
        ("4000", "Revenue", AccountType.INCOME),
        ("4100", "Service Revenue", AccountType.INCOME),
        ("5000", "Cost of Sales", AccountType.EXPENSE),
        ("6000", "Operating Expenses", AccountType.EXPENSE),
        ("6100", "Salaries Expense", AccountType.EXPENSE),
    ]

    for code, name, acc_type in account_defs:
        account = Account(
            account_number=code,
            account_name=name,
            root_type=acc_type,
            company="Test Company",
            is_group=False,
            disabled=False,
        )
        db.add(account)
        accounts[code] = account

    db.commit()

    return {
        "fiscal_year": fiscal_year,
        "periods": periods,
        "accounts": accounts,
    }


def setup_invoice_with_payments(
    db: Session,
    invoice_amount: Decimal = None,
    payment_amounts: list = None,
) -> dict:
    """
    Setup an invoice with partial/full payments for allocation testing.

    Returns dict with: customer, invoice, payments
    """
    amount = invoice_amount or Decimal("100000")
    payments_list = payment_amounts or [Decimal("30000"), Decimal("40000")]

    customer = create_customer(db, name="Invoice Test Customer")
    invoice = create_invoice(
        db,
        customer_id=customer.id,
        amount=amount,
        status="unpaid"
    )

    payments = []
    for pay_amount in payments_list:
        payment = create_payment(db, customer_id=customer.id, amount=pay_amount)
        payments.append(payment)

    return {
        "customer": customer,
        "invoice": invoice,
        "payments": payments,
    }


def setup_employee_with_leaves(
    db: Session,
    leave_days: Decimal = None,
) -> dict:
    """
    Setup an employee with leave allocations.

    Returns dict with: employee, allocation
    """
    employee = create_employee(db, name="Leave Test Employee")
    allocation = create_leave_allocation(
        db,
        employee_id=employee.id,
        employee_name=employee.name,
        new_leaves_allocated=leave_days or Decimal("20"),
    )

    return {
        "employee": employee,
        "allocation": allocation,
    }


def setup_support_queue(
    db: Session,
    agent_count: int = 3,
) -> dict:
    """
    Setup a support queue with agents and SLA policy.

    Returns dict with: team, agents, sla_policy
    """
    from app.models.agent import Agent, Team, TeamMembership
    from app.models.support_sla import SLAPolicy, SLATarget

    # Create team
    team = Team(
        name=f"Support Team {random_string(4)}",
        description="Test support team",
        is_active=True,
    )
    db.add(team)
    db.flush()

    # Create agents
    agents = []
    for i in range(agent_count):
        agent = Agent(
            email=random_email(),
            display_name=f"Agent {i + 1}",
            is_active=True,
            capacity=10,
        )
        db.add(agent)
        db.flush()

        membership = TeamMembership(
            team_id=team.id,
            agent_id=agent.id,
            is_active=True,
        )
        db.add(membership)
        agents.append(agent)

    # Create SLA policy
    sla_policy = SLAPolicy(
        name=f"Standard SLA {random_string(4)}",
        is_active=True,
        is_default=True,
        priority=100,
    )
    db.add(sla_policy)
    db.flush()

    # Add SLA targets
    targets = [
        SLATarget(policy_id=sla_policy.id, target_type="first_response", target_hours=Decimal("4")),
        SLATarget(policy_id=sla_policy.id, target_type="resolution", target_hours=Decimal("24")),
    ]
    for target in targets:
        db.add(target)

    db.commit()

    return {
        "team": team,
        "agents": agents,
        "sla_policy": sla_policy,
    }


def setup_field_service_dispatch(
    db: Session,
) -> dict:
    """
    Setup field service with zones, technicians, and service orders.

    Returns dict with: zone, technicians, service_orders
    """
    zone = create_service_zone(db, name="Lagos Zone")

    # Create technicians (employees with field service role)
    technicians = []
    for i in range(3):
        tech = create_employee(
            db,
            name=f"Technician {i + 1}",
            department="Field Operations",
            designation="Field Technician",
        )
        technicians.append(tech)

    # Create service orders
    customer = create_customer(db, name="Field Service Customer")
    orders = []
    for order_type in ["installation", "repair", "maintenance"]:
        order = create_service_order(
            db,
            customer_id=customer.id,
            order_type=order_type,
            technician_id=technicians[0].id if technicians else None,
        )
        orders.append(order)

    return {
        "zone": zone,
        "technicians": technicians,
        "customer": customer,
        "service_orders": orders,
    }


def setup_expense_workflow(
    db: Session,
    claim_amount: Decimal = None,
) -> dict:
    """
    Setup expense claim workflow with employee and claim.

    Returns dict with: employee, expense_claim
    """
    employee = create_employee(db, name="Expense Test Employee")
    claim = create_expense_claim(
        db,
        employee_id=employee.id,
        total_amount=claim_amount or Decimal("75000"),
        status="draft",
    )

    return {
        "employee": employee,
        "expense_claim": claim,
    }


def setup_performance_review(
    db: Session,
) -> dict:
    """
    Setup performance review with period, template, and scorecards.

    Returns dict with: period, employees, scorecards
    """
    period = create_evaluation_period(db, status="active")

    employees = []
    scorecards = []
    for i in range(3):
        emp = create_employee(db, name=f"Review Employee {i + 1}")
        employees.append(emp)

        scorecard = create_employee_scorecard(
            db,
            employee_id=emp.id,
            period_id=period.id,
            status="pending",
        )
        scorecards.append(scorecard)

    return {
        "period": period,
        "employees": employees,
        "scorecards": scorecards,
    }
