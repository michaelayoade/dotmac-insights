from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, inspect
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.database import get_db
# Core models
from app.models.customer import Customer
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.conversation import Conversation, Message
from app.models.pop import Pop
from app.models.employee import Employee
from app.models.expense import Expense
from app.models.sync_log import SyncLog
from app.models.credit_note import CreditNote
from app.models.ticket import Ticket
from app.models.project import Project
# Splynx models
from app.models.tariff import Tariff
from app.models.router import Router
from app.models.customer_note import CustomerNote
from app.models.administrator import Administrator
from app.models.network_monitor import NetworkMonitor
from app.models.lead import Lead
from app.models.ipv4_address import IPv4Address
from app.models.ipv4_network import IPv4Network
from app.models.ipv6_network import IPv6Network
from app.models.ticket_message import TicketMessage
from app.models.transaction_category import TransactionCategory
from app.models.payment_method import PaymentMethod
# ERPNext accounting models
from app.models.accounting import (
    BankAccount,
    JournalEntry,
    PurchaseInvoice,
    GLEntry,
    Account,
    BankTransaction,
    Supplier,
    ModeOfPayment,
    CostCenter,
    FiscalYear,
)
# HR models
from app.models.hr import (
    Department,
    HDTeam,
    HDTeamMember,
    Designation,
    ERPNextUser,
)
# Sales models
from app.models.sales import (
    SalesOrder,
    Quotation,
    ERPNextLead,
    Item,
    CustomerGroup,
    Territory,
    SalesPerson,
    ItemGroup,
)

router = APIRouter()

# Available tables for exploration (organized by category)
TABLES = {
    # Core business data
    "customers": Customer,
    "subscriptions": Subscription,
    "invoices": Invoice,
    "payments": Payment,
    "credit_notes": CreditNote,
    "expenses": Expense,
    "projects": Project,
    "tickets": Ticket,
    # People
    "employees": Employee,
    "administrators": Administrator,
    "leads": Lead,
    # Network infrastructure (Splynx)
    "pops": Pop,
    "routers": Router,
    "tariffs": Tariff,
    "ipv4_networks": IPv4Network,
    "ipv6_networks": IPv6Network,
    "ipv4_addresses": IPv4Address,
    "network_monitors": NetworkMonitor,
    # Support
    "conversations": Conversation,
    "messages": Message,
    "ticket_messages": TicketMessage,
    "customer_notes": CustomerNote,
    # Accounting (ERPNext)
    "accounts": Account,
    "bank_accounts": BankAccount,
    "bank_transactions": BankTransaction,
    "journal_entries": JournalEntry,
    "gl_entries": GLEntry,
    "purchase_invoices": PurchaseInvoice,
    "suppliers": Supplier,
    "cost_centers": CostCenter,
    "fiscal_years": FiscalYear,
    "modes_of_payment": ModeOfPayment,
    # Reference data
    "transaction_categories": TransactionCategory,
    "payment_methods": PaymentMethod,
    # HR (ERPNext)
    "departments": Department,
    "designations": Designation,
    "hd_teams": HDTeam,
    "hd_team_members": HDTeamMember,
    "erpnext_users": ERPNextUser,
    # Sales (ERPNext)
    "sales_orders": SalesOrder,
    "quotations": Quotation,
    "erpnext_leads": ERPNextLead,
    "items": Item,
    "customer_groups": CustomerGroup,
    "territories": Territory,
    "sales_persons": SalesPerson,
    "item_groups": ItemGroup,
    # System
    "sync_logs": SyncLog,
}


@router.get("/tables")
async def list_tables(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all available tables with record counts."""
    tables = {}

    for name, model in TABLES.items():
        count = db.query(model).count()
        tables[name] = {
            "count": count,
            "columns": [c.key for c in inspect(model).mapper.column_attrs],
        }

    return tables


@router.get("/tables/{table_name}")
async def explore_table(
    table_name: str,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    order_by: Optional[str] = None,
    order_dir: str = Query(default="desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explore data in a specific table."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]
    query = db.query(model)

    # Apply ordering
    if order_by:
        column = getattr(model, order_by, None)
        if column is None:
            raise HTTPException(status_code=400, detail=f"Invalid column: {order_by}")
        if order_dir == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        # Default order by id desc
        if hasattr(model, "id"):
            query = query.order_by(model.id.desc())

    total = query.count()
    records = query.offset(offset).limit(limit).all()

    # Convert to dict
    data = []
    for record in records:
        row = {}
        for column in inspect(model).mapper.column_attrs:
            value = getattr(record, column.key)
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            # Handle enums
            elif hasattr(value, "value"):
                value = value.value
            row[column.key] = value
        data.append(row)

    return {
        "table": table_name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data,
    }


@router.get("/tables/{table_name}/stats")
async def get_table_stats(
    table_name: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get statistics for a table."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]

    stats = {
        "table": table_name,
        "total_records": db.query(model).count(),
    }

    # Add specific stats based on table
    if table_name == "customers":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Customer.status, func.count(Customer.id).label("count"))
            .group_by(Customer.status)
            .all()
        }
        stats["by_type"] = {
            row.customer_type.value: row.count
            for row in db.query(Customer.customer_type, func.count(Customer.id).label("count"))
            .group_by(Customer.customer_type)
            .all()
        }

    elif table_name == "subscriptions":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Subscription.status, func.count(Subscription.id).label("count"))
            .group_by(Subscription.status)
            .all()
        }
        stats["by_plan"] = {
            row.plan_name: row.count
            for row in db.query(Subscription.plan_name, func.count(Subscription.id).label("count"))
            .group_by(Subscription.plan_name)
            .order_by(func.count(Subscription.id).desc())
            .limit(20)
            .all()
        }

    elif table_name == "invoices":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Invoice.status, func.count(Invoice.id).label("count"))
            .group_by(Invoice.status)
            .all()
        }
        total_amount = db.query(func.sum(Invoice.total_amount)).scalar()
        total_paid = db.query(func.sum(Invoice.amount_paid)).scalar()
        stats["total_invoiced"] = float(total_amount or 0)
        stats["total_paid"] = float(total_paid or 0)
    elif table_name == "credit_notes":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(CreditNote.status, func.count(CreditNote.id).label("count"))
            .group_by(CreditNote.status)
            .all()
        }
        total_amount = db.query(func.sum(CreditNote.amount)).scalar()
        stats["total_credit_notes"] = float(total_amount or 0)

    elif table_name == "payments":
        stats["by_method"] = {
            row.payment_method.value: row.count
            for row in db.query(Payment.payment_method, func.count(Payment.id).label("count"))
            .group_by(Payment.payment_method)
            .all()
        }
        total = db.query(func.sum(Payment.amount)).scalar()
        stats["total_payments"] = float(total or 0)

    elif table_name == "conversations":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Conversation.status, func.count(Conversation.id).label("count"))
            .group_by(Conversation.status)
            .all()
        }
        stats["by_channel"] = {
            row.channel: row.count
            for row in db.query(Conversation.channel, func.count(Conversation.id).label("count"))
            .group_by(Conversation.channel)
            .all()
            if row.channel
        }

    elif table_name == "pops":
        stats["active"] = db.query(Pop).filter(Pop.is_active.is_(True)).count()
        stats["inactive"] = db.query(Pop).filter(Pop.is_active.is_(False)).count()

    elif table_name == "employees":
        stats["by_department"] = {
            row.department: row.count
            for row in db.query(Employee.department, func.count(Employee.id).label("count"))
            .group_by(Employee.department)
            .all()
            if row.department
        }
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Employee.status, func.count(Employee.id).label("count"))
            .group_by(Employee.status)
            .all()
        }

    elif table_name == "tickets":
        stats["by_status"] = {
            row.status.value: row.count
            for row in db.query(Ticket.status, func.count(Ticket.id).label("count"))
            .group_by(Ticket.status)
            .all()
        }
        stats["by_priority"] = {
            row.priority.value: row.count
            for row in db.query(Ticket.priority, func.count(Ticket.id).label("count"))
            .group_by(Ticket.priority)
            .all()
        }
        stats["by_source"] = {
            row.source.value: row.count
            for row in db.query(Ticket.source, func.count(Ticket.id).label("count"))
            .group_by(Ticket.source)
            .all()
        }

    elif table_name == "projects":
        stats["by_status"] = {
            row.status.value if hasattr(row.status, 'value') else row.status: row.count
            for row in db.query(Project.status, func.count(Project.id).label("count"))
            .group_by(Project.status)
            .all()
            if row.status
        }
        stats["with_customer"] = db.query(Project).filter(Project.customer_id.isnot(None)).count()
        stats["with_manager"] = db.query(Project).filter(Project.project_manager_id.isnot(None)).count()

    elif table_name == "tariffs":
        stats["by_type"] = {
            row.tariff_type.value: row.count
            for row in db.query(Tariff.tariff_type, func.count(Tariff.id).label("count"))
            .group_by(Tariff.tariff_type)
            .all()
        }
        stats["enabled"] = db.query(Tariff).filter(Tariff.enabled.is_(True)).count()

    elif table_name == "routers":
        stats["by_nas_type"] = {
            str(row.nas_type): row.count
            for row in db.query(Router.nas_type, func.count(Router.id).label("count"))
            .group_by(Router.nas_type)
            .all()
            if row.nas_type is not None
        }
        stats["with_pop"] = db.query(Router).filter(Router.pop_id.isnot(None)).count()

    elif table_name == "leads":
        stats["by_status"] = {
            row.status: row.count
            for row in db.query(Lead.status, func.count(Lead.id).label("count"))
            .group_by(Lead.status)
            .all()
            if row.status
        }
        stats["converted"] = db.query(Lead).filter(Lead.customer_id.isnot(None)).count()

    elif table_name == "network_monitors":
        stats["by_ping_state"] = {
            row.ping_state.value: row.count
            for row in db.query(NetworkMonitor.ping_state, func.count(NetworkMonitor.id).label("count"))
            .group_by(NetworkMonitor.ping_state)
            .all()
        }
        stats["active"] = db.query(NetworkMonitor).filter(NetworkMonitor.active.is_(True)).count()

    elif table_name == "ipv4_networks":
        stats["by_type"] = {
            row.network_type: row.count
            for row in db.query(IPv4Network.network_type, func.count(IPv4Network.id).label("count"))
            .group_by(IPv4Network.network_type)
            .all()
            if row.network_type
        }
        stats["by_usage"] = {
            row.type_of_usage: row.count
            for row in db.query(IPv4Network.type_of_usage, func.count(IPv4Network.id).label("count"))
            .group_by(IPv4Network.type_of_usage)
            .all()
            if row.type_of_usage
        }

    elif table_name == "ipv4_addresses":
        stats["used"] = db.query(IPv4Address).filter(IPv4Address.is_used.is_(True)).count()
        stats["available"] = db.query(IPv4Address).filter(IPv4Address.is_used.is_(False)).count()
        stats["assigned_to_customer"] = db.query(IPv4Address).filter(IPv4Address.customer_id.isnot(None)).count()

    elif table_name == "accounts":
        stats["by_account_type"] = {
            row.account_type: row.count
            for row in db.query(Account.account_type, func.count(Account.id).label("count"))
            .group_by(Account.account_type)
            .all()
            if row.account_type
        }
        stats["by_root_type"] = {
            row.root_type: row.count
            for row in db.query(Account.root_type, func.count(Account.id).label("count"))
            .group_by(Account.root_type)
            .all()
            if row.root_type
        }

    elif table_name == "journal_entries":
        total_debit = db.query(func.sum(JournalEntry.total_debit)).scalar()
        total_credit = db.query(func.sum(JournalEntry.total_credit)).scalar()
        stats["total_debit"] = float(total_debit or 0)
        stats["total_credit"] = float(total_credit or 0)

    elif table_name == "gl_entries":
        total_debit = db.query(func.sum(GLEntry.debit)).scalar()
        total_credit = db.query(func.sum(GLEntry.credit)).scalar()
        stats["total_debit"] = float(total_debit or 0)
        stats["total_credit"] = float(total_credit or 0)

    elif table_name == "purchase_invoices":
        stats["by_status"] = {
            row.status: row.count
            for row in db.query(PurchaseInvoice.status, func.count(PurchaseInvoice.id).label("count"))
            .group_by(PurchaseInvoice.status)
            .all()
            if row.status
        }
        total = db.query(func.sum(PurchaseInvoice.grand_total)).scalar()
        stats["total_amount"] = float(total or 0)

    elif table_name == "administrators":
        stats["by_role"] = {
            row.role_name: row.count
            for row in db.query(Administrator.role_name, func.count(Administrator.id).label("count"))
            .group_by(Administrator.role_name)
            .all()
            if row.role_name
        }

    return stats


@router.get("/data-quality")
async def check_data_quality(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Check data quality and completeness across all tables."""
    report = {}

    # Customers
    total_customers = db.query(Customer).count()
    customers_with_email = db.query(Customer).filter(Customer.email.isnot(None)).count()
    customers_with_phone = db.query(Customer).filter(Customer.phone.isnot(None)).count()
    customers_with_pop = db.query(Customer).filter(Customer.pop_id.isnot(None)).count()
    customers_linked_splynx = db.query(Customer).filter(Customer.splynx_id.isnot(None)).count()
    customers_linked_erpnext = db.query(Customer).filter(Customer.erpnext_id.isnot(None)).count()
    customers_linked_chatwoot = db.query(Customer).filter(Customer.chatwoot_contact_id.isnot(None)).count()

    report["customers"] = {
        "total": total_customers,
        "completeness": {
            "has_email": customers_with_email,
            "has_phone": customers_with_phone,
            "has_pop": customers_with_pop,
        },
        "linkage": {
            "linked_to_splynx": customers_linked_splynx,
            "linked_to_erpnext": customers_linked_erpnext,
            "linked_to_chatwoot": customers_linked_chatwoot,
        },
        "quality_score": round(
            (customers_with_email + customers_with_phone + customers_with_pop)
            / (total_customers * 3)
            * 100
            if total_customers > 0
            else 0,
            2,
        ),
    }

    # Invoices
    total_invoices = db.query(Invoice).count()
    invoices_with_customer = db.query(Invoice).filter(Invoice.customer_id.isnot(None)).count()

    report["invoices"] = {
        "total": total_invoices,
        "linked_to_customer": invoices_with_customer,
        "unlinked": total_invoices - invoices_with_customer,
    }

    # Conversations
    total_conversations = db.query(Conversation).count()
    conversations_with_customer = db.query(Conversation).filter(Conversation.customer_id.isnot(None)).count()

    report["conversations"] = {
        "total": total_conversations,
        "linked_to_customer": conversations_with_customer,
        "unlinked": total_conversations - conversations_with_customer,
    }

    # Overall data health
    total_records = sum([
        total_customers,
        db.query(Subscription).count(),
        total_invoices,
        db.query(Payment).count(),
        total_conversations,
    ])

    report["summary"] = {
        "total_records": total_records,
        "last_sync_check": datetime.utcnow().isoformat(),
    }

    return report


@router.get("/search")
async def search_all(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Search across all major tables."""
    results = {}
    search_term = f"%{q}%"

    # Search customers
    customers = (
        db.query(Customer)
        .filter(
            Customer.name.ilike(search_term)
            | Customer.email.ilike(search_term)
            | Customer.phone.ilike(search_term)
            | Customer.account_number.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["customers"] = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "status": c.status.value,
        }
        for c in customers
    ]

    # Search invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.ilike(search_term))
        .limit(limit)
        .all()
    )
    results["invoices"] = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "total_amount": str(inv.total_amount),
            "status": inv.status.value,
        }
        for inv in invoices
    ]

    # Search employees
    employees = (
        db.query(Employee)
        .filter(
            Employee.name.ilike(search_term)
            | Employee.email.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["employees"] = [
        {
            "id": e.id,
            "name": e.name,
            "email": e.email,
            "department": e.department,
        }
        for e in employees
    ]

    # Search POPs
    pops = (
        db.query(Pop)
        .filter(
            Pop.name.ilike(search_term)
            | Pop.code.ilike(search_term)
        )
        .limit(limit)
        .all()
    )
    results["pops"] = [
        {
            "id": p.id,
            "name": p.name,
            "code": p.code,
        }
        for p in pops
    ]

    return results


def _apply_filters(query: Any, model: Any, filters: Optional[Dict[str, Any]]) -> Any:
    """Apply filters to a query, handling both simple values and operator dicts."""
    if not filters:
        return query

    for column_name, value in filters.items():
        column = getattr(model, column_name, None)
        if column is None:
            continue

        if isinstance(value, dict):
            # Handle operators: {"gt": 100, "lt": 500}
            for op, val in value.items():
                if op == "gt":
                    query = query.filter(column > val)
                elif op == "gte":
                    query = query.filter(column >= val)
                elif op == "lt":
                    query = query.filter(column < val)
                elif op == "lte":
                    query = query.filter(column <= val)
                elif op == "eq":
                    query = query.filter(column == val)
                elif op == "ne":
                    query = query.filter(column != val)
                elif op == "like":
                    query = query.filter(column.ilike(f"%{val}%"))
                elif op == "in":
                    query = query.filter(column.in_(val))
        else:
            # Simple equality
            query = query.filter(column == value)

    return query


@router.post("/query")
async def run_custom_query(
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    group_by: Optional[List[str]] = None,
    aggregate: Optional[Dict[str, str]] = None,  # {"column": "sum|count|avg|min|max"}
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run a custom query with filters, grouping, and aggregation."""
    if table not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table}")

    model = TABLES[table]

    # Handle grouping and aggregation
    if group_by and aggregate:
        select_columns = []
        for col_name in group_by:
            column = getattr(model, col_name, None)
            if column:
                select_columns.append(column)

        for col_name, agg_func in aggregate.items():
            column = getattr(model, col_name, None)
            if column:
                if agg_func == "count":
                    select_columns.append(func.count(column).label(f"{col_name}_count"))
                elif agg_func == "sum":
                    select_columns.append(func.sum(column).label(f"{col_name}_sum"))
                elif agg_func == "avg":
                    select_columns.append(func.avg(column).label(f"{col_name}_avg"))
                elif agg_func == "min":
                    select_columns.append(func.min(column).label(f"{col_name}_min"))
                elif agg_func == "max":
                    select_columns.append(func.max(column).label(f"{col_name}_max"))

        query = db.query(*select_columns)

        # Apply ALL filters (including operator filters) to the aggregation query
        query = _apply_filters(query, model, filters)

        for col_name in group_by:
            column = getattr(model, col_name, None)
            if column:
                query = query.group_by(column)

        results = query.limit(limit).all()

        # Convert results to dict
        data = []
        for row in results:
            row_dict = {}
            for i, col_name in enumerate(group_by):
                value = row[i]
                if hasattr(value, "value"):
                    value = value.value
                row_dict[col_name] = value

            for j, (col_name, agg_func) in enumerate(aggregate.items()):
                row_dict[f"{col_name}_{agg_func}"] = float(row[len(group_by) + j] or 0)
            data.append(row_dict)

        return {"data": data, "grouped": True}

    # Regular query (no aggregation)
    query = db.query(model)
    query = _apply_filters(query, model, filters)

    total = query.count()
    records = query.limit(limit).all()

    data = []
    for record in records:
        row = {}
        for column in inspect(model).mapper.column_attrs:
            value = getattr(record, column.key)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, "value"):
                value = value.value
            row[column.key] = value
        data.append(row)

    return {"total": total, "limit": limit, "data": data, "grouped": False}
