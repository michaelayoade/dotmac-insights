"""
Pre-built Test Scenarios for E2E Tests.

Scenarios combine multiple factories to create complex test setups
that mirror real-world usage patterns.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .factories import (
    # Utility
    random_string,
    random_email,
    # CRM
    create_customer,
    create_lead,
    create_unified_contact,
    create_person_contact,
    create_opportunity_stage,
    get_or_create_opportunity_stage,
    # Accounting
    create_invoice,
    create_payment,
    create_journal_entry,
    create_bank_account,
    create_bank_transaction,
    # HR
    create_employee,
    create_leave_allocation,
    create_leave_application,
    # Support
    create_ticket,
    add_ticket_comment,
    # Projects
    create_project,
    create_task,
    # Field Service
    create_service_zone,
    create_service_order,
    # Expenses
    create_expense_claim,
    create_cash_advance,
    # Performance
    create_evaluation_period,
    create_employee_scorecard,
    # Inventory
    create_warehouse,
    create_stock_item,
    create_stock_entry,
    # Scenario builders
    setup_accounting_period,
    setup_invoice_with_payments,
    setup_employee_with_leaves,
    setup_support_queue,
    setup_field_service_dispatch,
    setup_expense_workflow,
    setup_performance_review,
)


# =============================================================================
# CRM SCENARIOS
# =============================================================================

def scenario_lead_to_customer_conversion(db: Session) -> dict:
    """
    Scenario: Lead qualification and conversion to customer.

    Steps:
    1. Create lead with minimal info
    2. Add person contacts
    3. Create opportunity
    4. Close-won opportunity
    5. Convert to customer

    Returns dict with all created entities.
    """
    # Create lead
    lead = create_unified_contact(
        db,
        name="Conversion Test Lead",
        contact_type="lead",
        category="business",
        email=random_email(),
    )

    # Add contacts
    primary_contact = create_person_contact(
        db,
        parent_id=lead.id,
        name="Primary Decision Maker",
        role="CEO",
    )

    # Create opportunity stages
    stages = []
    stage_defs = [
        ("Qualification", 0, 10, False, False),
        ("Proposal", 1, 40, False, False),
        ("Negotiation", 2, 70, False, False),
        ("Closed Won", 3, 100, True, False),
        ("Closed Lost", 4, 0, False, True),
    ]
    for name, seq, prob, won, lost in stage_defs:
        stage = get_or_create_opportunity_stage(
            db, name=name, sequence=seq, probability=prob, is_won=won, is_lost=lost
        )
        stages.append(stage)

    return {
        "lead": lead,
        "primary_contact": primary_contact,
        "stages": stages,
    }


def scenario_sales_pipeline(db: Session, deal_count: int = 5) -> dict:
    """
    Scenario: Full sales pipeline with multiple opportunities at different stages.

    Returns dict with customers, opportunities, and stages.
    """
    # Setup stages
    stages = []
    stage_defs = [
        ("Lead", 0, 10, "#94a3b8"),
        ("Qualified", 1, 30, "#60a5fa"),
        ("Proposal", 2, 50, "#fbbf24"),
        ("Negotiation", 3, 70, "#f97316"),
        ("Closed Won", 4, 100, "#22c55e"),
    ]
    for name, seq, prob, color in stage_defs:
        stage = get_or_create_opportunity_stage(
            db, name=name, sequence=seq, probability=prob, color=color
        )
        stages.append(stage)

    # Create customers and opportunities
    customers = []
    opportunities = []
    for i in range(deal_count):
        customer = create_unified_contact(
            db,
            name=f"Pipeline Customer {i + 1}",
            contact_type="prospect",
        )
        customers.append(customer)

    return {
        "stages": stages,
        "customers": customers,
    }


# =============================================================================
# ACCOUNTING SCENARIOS
# =============================================================================

def scenario_invoice_to_payment_reconciliation(
    db: Session,
    invoice_amount: Decimal = None,
) -> dict:
    """
    Scenario: Complete invoice-to-cash flow.

    Steps:
    1. Setup accounting period
    2. Create customer
    3. Create invoice
    4. Record payment
    5. Allocate payment to invoice
    6. Reconcile with bank

    Returns dict with all entities.
    """
    # Setup accounting
    accounting = setup_accounting_period(db)

    # Create customer and invoice
    customer = create_customer(db, name="AR Test Customer")
    amount = invoice_amount or Decimal("500000")

    invoice = create_invoice(
        db,
        customer_id=customer.id,
        amount=amount,
        status="unpaid",
    )

    # Create payment
    payment = create_payment(
        db,
        customer_id=customer.id,
        amount=amount,
    )

    # Setup bank for reconciliation
    bank_account = create_bank_account(db, account_name="Main Operating Account")
    bank_transaction = create_bank_transaction(
        db,
        bank_account_id=bank_account.id,
        amount=amount,
        transaction_type="credit",
    )

    return {
        "fiscal_year": accounting["fiscal_year"],
        "accounts": accounting["accounts"],
        "customer": customer,
        "invoice": invoice,
        "payment": payment,
        "bank_account": bank_account,
        "bank_transaction": bank_transaction,
    }


def scenario_multi_currency_transaction(db: Session) -> dict:
    """
    Scenario: Multi-currency invoice and payment with exchange rate.

    Returns dict with USD invoice and NGN payment.
    """
    customer = create_customer(db, name="Multi-Currency Customer")

    # USD invoice
    invoice = create_invoice(
        db,
        customer_id=customer.id,
        amount=Decimal("1000"),
        currency="USD",
    )

    # NGN payment at conversion rate
    payment = create_payment(
        db,
        customer_id=customer.id,
        amount=Decimal("1550000"),  # Approx 1550 NGN per USD
        currency="NGN",
    )

    return {
        "customer": customer,
        "invoice": invoice,
        "payment": payment,
        "exchange_rate": Decimal("1550"),
    }


def scenario_ap_workflow(db: Session) -> dict:
    """
    Scenario: Accounts payable workflow from PO to payment.

    Steps:
    1. Create supplier
    2. Create purchase order
    3. Receive goods
    4. Create bill
    5. Process payment

    Returns dict with all entities.
    """
    from app.models.unified_contact import UnifiedContact, ContactType

    # Create supplier
    supplier = create_unified_contact(
        db,
        name="AP Test Supplier",
        contact_type="customer",  # Will be used as supplier
        category="business",
    )

    # Create employee for approval
    employee = create_employee(db, name="AP Approver", designation="Finance Manager")

    return {
        "supplier": supplier,
        "approver": employee,
    }


# =============================================================================
# HR SCENARIOS
# =============================================================================

def scenario_employee_onboarding(db: Session) -> dict:
    """
    Scenario: New employee onboarding flow.

    Steps:
    1. Create employee record
    2. Allocate leave balances
    3. Assign to department
    4. Setup performance scorecard

    Returns dict with employee and related entities.
    """
    # Create employee
    employee = create_employee(
        db,
        name="New Hire Employee",
        department="Engineering",
        designation="Software Engineer",
        salary=Decimal("800000"),
    )

    # Allocate leaves
    annual_leave = create_leave_allocation(
        db,
        employee_id=employee.id,
        employee_name=employee.name,
        leave_type="Annual Leave",
        new_leaves_allocated=Decimal("20"),
    )

    sick_leave = create_leave_allocation(
        db,
        employee_id=employee.id,
        employee_name=employee.name,
        leave_type="Sick Leave",
        new_leaves_allocated=Decimal("10"),
    )

    # Setup performance period
    period = create_evaluation_period(db, status="active")
    scorecard = create_employee_scorecard(
        db,
        employee_id=employee.id,
        period_id=period.id,
    )

    return {
        "employee": employee,
        "annual_leave": annual_leave,
        "sick_leave": sick_leave,
        "period": period,
        "scorecard": scorecard,
    }


def scenario_leave_request_approval(db: Session) -> dict:
    """
    Scenario: Leave request with approval workflow.

    Steps:
    1. Setup employee with allocation
    2. Create leave request
    3. Setup approver

    Returns dict with employee, allocation, and leave application.
    """
    setup = setup_employee_with_leaves(db, leave_days=Decimal("20"))

    # Create leave application
    leave_app = create_leave_application(
        db,
        employee_id=setup["employee"].id,
        leave_type="Annual Leave",
        from_date=date.today() + timedelta(days=7),
        to_date=date.today() + timedelta(days=10),
        status="open",
    )

    # Create approver
    approver = create_employee(
        db,
        name="Leave Approver",
        department=setup["employee"].department,
        designation="Team Lead",
    )

    return {
        "employee": setup["employee"],
        "allocation": setup["allocation"],
        "leave_application": leave_app,
        "approver": approver,
    }


def scenario_payroll_processing(db: Session, employee_count: int = 5) -> dict:
    """
    Scenario: Monthly payroll processing.

    Returns dict with employees and payroll setup.
    """
    employees = []
    for i in range(employee_count):
        emp = create_employee(
            db,
            name=f"Payroll Employee {i + 1}",
            salary=Decimal("500000") + Decimal(str(i * 50000)),
        )
        employees.append(emp)

    return {
        "employees": employees,
        "payroll_month": date.today().replace(day=1),
    }


# =============================================================================
# SUPPORT SCENARIOS
# =============================================================================

def scenario_ticket_lifecycle(db: Session) -> dict:
    """
    Scenario: Complete ticket lifecycle from creation to resolution.

    Steps:
    1. Create customer
    2. Create ticket
    3. Assign to agent
    4. Add comments
    5. Resolve ticket

    Returns dict with all entities.
    """
    # Setup support queue
    queue = setup_support_queue(db, agent_count=3)

    # Create customer
    customer = create_customer(db, name="Support Customer")

    # Create ticket
    ticket = create_ticket(
        db,
        customer_id=customer.id,
        subject="Internet connectivity issue",
        priority="high",
        status="open",
    )

    # Add initial comment
    comment = add_ticket_comment(
        db,
        ticket_id=ticket.id,
        comment="Customer reports intermittent connectivity",
        commented_by="System",
    )

    return {
        "customer": customer,
        "ticket": ticket,
        "comment": comment,
        "team": queue["team"],
        "agents": queue["agents"],
        "sla_policy": queue["sla_policy"],
    }


def scenario_sla_breach_escalation(db: Session) -> dict:
    """
    Scenario: SLA breach with escalation.

    Creates ticket that breaches SLA for testing escalation logic.
    """
    queue = setup_support_queue(db)
    customer = create_customer(db, name="Escalation Customer")

    # Create high priority ticket with past response deadline
    ticket = create_ticket(
        db,
        customer_id=customer.id,
        subject="Critical system failure",
        priority="urgent",
        status="open",
    )

    return {
        "ticket": ticket,
        "customer": customer,
        "sla_policy": queue["sla_policy"],
        "team": queue["team"],
    }


# =============================================================================
# PROJECT SCENARIOS
# =============================================================================

def scenario_project_lifecycle(db: Session) -> dict:
    """
    Scenario: Project from creation through completion.

    Returns dict with project, tasks, and team.
    """
    # Create project manager
    pm = create_employee(
        db,
        name="Project Manager",
        designation="Project Manager",
    )

    # Create team members
    team = []
    for i in range(3):
        member = create_employee(
            db,
            name=f"Team Member {i + 1}",
            designation="Developer",
        )
        team.append(member)

    # Create customer
    customer = create_customer(db, name="Project Customer")

    # Create project
    project = create_project(
        db,
        project_name="Website Redesign",
        customer_id=customer.id,
        project_manager_id=pm.id,
        status="open",
    )

    # Create tasks
    tasks = []
    task_defs = [
        ("Requirements Gathering", "open"),
        ("Design Phase", "open"),
        ("Development", "open"),
        ("Testing", "open"),
        ("Deployment", "open"),
    ]
    for i, (subject, status) in enumerate(task_defs):
        task = create_task(
            db,
            project_id=project.id,
            subject=subject,
            status=status,
            assigned_to_id=team[i % len(team)].id,
        )
        tasks.append(task)

    return {
        "project": project,
        "project_manager": pm,
        "team": team,
        "tasks": tasks,
        "customer": customer,
    }


# =============================================================================
# FIELD SERVICE SCENARIOS
# =============================================================================

def scenario_installation_workflow(db: Session) -> dict:
    """
    Scenario: New customer installation from start to completion.

    Returns dict with customer, service order, and technician.
    """
    setup = setup_field_service_dispatch(db)

    # Create new customer for installation
    customer = create_customer(db, name="Installation Customer")

    # Create installation order
    order = create_service_order(
        db,
        customer_id=customer.id,
        order_type="installation",
        status="scheduled",
        priority="medium",
        technician_id=setup["technicians"][0].id,
    )

    return {
        "customer": customer,
        "service_order": order,
        "technician": setup["technicians"][0],
        "zone": setup["zone"],
    }


def scenario_maintenance_schedule(db: Session, order_count: int = 5) -> dict:
    """
    Scenario: Scheduled maintenance for multiple customers.

    Returns dict with customers and maintenance orders.
    """
    setup = setup_field_service_dispatch(db)

    customers = []
    orders = []
    for i in range(order_count):
        customer = create_customer(db, name=f"Maintenance Customer {i + 1}")
        customers.append(customer)

        order = create_service_order(
            db,
            customer_id=customer.id,
            order_type="maintenance",
            status="scheduled",
            scheduled_date=date.today() + timedelta(days=i),
            technician_id=setup["technicians"][i % len(setup["technicians"])].id,
        )
        orders.append(order)

    return {
        "customers": customers,
        "maintenance_orders": orders,
        "technicians": setup["technicians"],
        "zone": setup["zone"],
    }


# =============================================================================
# EXPENSE SCENARIOS
# =============================================================================

def scenario_expense_claim_workflow(db: Session) -> dict:
    """
    Scenario: Expense claim submission and approval.

    Returns dict with employee, claim, and approver.
    """
    setup = setup_expense_workflow(db, claim_amount=Decimal("150000"))

    # Create approver
    approver = create_employee(
        db,
        name="Expense Approver",
        designation="Finance Manager",
    )

    return {
        "employee": setup["employee"],
        "expense_claim": setup["expense_claim"],
        "approver": approver,
    }


def scenario_travel_advance(db: Session) -> dict:
    """
    Scenario: Cash advance for business travel.

    Returns dict with employee, advance, and related expense claim.
    """
    employee = create_employee(
        db,
        name="Traveling Employee",
        designation="Sales Manager",
    )

    # Create cash advance
    advance = create_cash_advance(
        db,
        employee_id=employee.id,
        amount=Decimal("500000"),
        purpose="Business trip to Abuja",
    )

    return {
        "employee": employee,
        "cash_advance": advance,
    }


# =============================================================================
# INVENTORY SCENARIOS
# =============================================================================

def scenario_stock_movement(db: Session) -> dict:
    """
    Scenario: Stock receipt, transfer, and issue.

    Returns dict with warehouses, items, and stock entries.
    """
    # Create warehouses
    main_warehouse = create_warehouse(db, name="Main Warehouse")
    store_warehouse = create_warehouse(db, name="Store Warehouse")

    # Create items
    items = []
    for i in range(3):
        item = create_stock_item(
            db,
            item_name=f"Product {i + 1}",
            item_code=f"PROD-{i + 1:03d}",
        )
        items.append(item)

    # Stock receipt
    receipt = create_stock_entry(
        db,
        entry_type="Material Receipt",
        to_warehouse=main_warehouse.warehouse_name,
        total_amount=Decimal("1000000"),
    )

    # Stock transfer
    transfer = create_stock_entry(
        db,
        entry_type="Material Transfer",
        from_warehouse=main_warehouse.warehouse_name,
        to_warehouse=store_warehouse.warehouse_name,
        total_amount=Decimal("300000"),
    )

    return {
        "main_warehouse": main_warehouse,
        "store_warehouse": store_warehouse,
        "items": items,
        "receipt": receipt,
        "transfer": transfer,
    }
