from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, inspect, and_, or_
from sqlalchemy.types import DateTime, Date
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
import csv
import io
import json

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
# Auth/RBAC models
from app.models.auth import (
    User,
    Role,
    Permission,
    UserRole,
    RolePermission,
    ServiceToken,
    TokenDenylist,
)
from app.auth import Require

router = APIRouter()

# Table categories for organization
TABLE_CATEGORIES = {
    "core_business": "Core Business Data",
    "people": "People & Contacts",
    "network": "Network Infrastructure",
    "support": "Support & Communication",
    "accounting": "Accounting & Finance",
    "hr": "HR & Teams",
    "sales": "Sales & CRM",
    "auth": "Authentication & RBAC",
    "system": "System & Logs",
}

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
    # Auth/RBAC
    "auth_users": User,
    "auth_roles": Role,
    "auth_permissions": Permission,
    "auth_user_roles": UserRole,
    "auth_role_permissions": RolePermission,
    "auth_service_tokens": ServiceToken,
    "auth_token_denylist": TokenDenylist,
    # System
    "sync_logs": SyncLog,
}

# Map tables to categories
TABLE_TO_CATEGORY = {
    "customers": "core_business",
    "subscriptions": "core_business",
    "invoices": "core_business",
    "payments": "core_business",
    "credit_notes": "core_business",
    "expenses": "core_business",
    "projects": "core_business",
    "tickets": "core_business",
    "employees": "people",
    "administrators": "people",
    "leads": "people",
    "pops": "network",
    "routers": "network",
    "tariffs": "network",
    "ipv4_networks": "network",
    "ipv6_networks": "network",
    "ipv4_addresses": "network",
    "network_monitors": "network",
    "conversations": "support",
    "messages": "support",
    "ticket_messages": "support",
    "customer_notes": "support",
    "accounts": "accounting",
    "bank_accounts": "accounting",
    "bank_transactions": "accounting",
    "journal_entries": "accounting",
    "gl_entries": "accounting",
    "purchase_invoices": "accounting",
    "suppliers": "accounting",
    "cost_centers": "accounting",
    "fiscal_years": "accounting",
    "modes_of_payment": "accounting",
    "transaction_categories": "accounting",
    "payment_methods": "accounting",
    "departments": "hr",
    "designations": "hr",
    "hd_teams": "hr",
    "hd_team_members": "hr",
    "erpnext_users": "hr",
    "sales_orders": "sales",
    "quotations": "sales",
    "erpnext_leads": "sales",
    "items": "sales",
    "customer_groups": "sales",
    "territories": "sales",
    "sales_persons": "sales",
    "item_groups": "sales",
    "auth_users": "auth",
    "auth_roles": "auth",
    "auth_permissions": "auth",
    "auth_user_roles": "auth",
    "auth_role_permissions": "auth",
    "auth_service_tokens": "auth",
    "auth_token_denylist": "auth",
    "sync_logs": "system",
}


def _get_date_columns(model: Any) -> List[str]:
    """Get list of date/datetime columns for a model."""
    date_columns = []
    for column in inspect(model).mapper.column_attrs:
        col = getattr(model, column.key)
        if hasattr(col, 'type'):
            if isinstance(col.type, (DateTime, Date)):
                date_columns.append(column.key)
    return date_columns


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON output."""
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif hasattr(value, "value"):  # Enum
        return value.value
    return value


@router.get("/tables", dependencies=[Depends(Require("explorer:read"))])
async def list_tables(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all available tables with record counts, organized by category."""
    tables = {}
    by_category: Dict[str, List[Dict[str, Any]]] = {}

    for name, model in TABLES.items():
        count = db.query(model).count()
        columns = [c.key for c in inspect(model).mapper.column_attrs]
        date_columns = _get_date_columns(model)
        category = TABLE_TO_CATEGORY.get(name, "other")

        table_info = {
            "name": name,
            "count": count,
            "columns": columns,
            "date_columns": date_columns,
            "category": category,
            "category_label": TABLE_CATEGORIES.get(category, "Other"),
        }
        tables[name] = table_info

        if category not in by_category:
            by_category[category] = []
        by_category[category].append(table_info)

    return {
        "tables": tables,
        "categories": TABLE_CATEGORIES,
        "by_category": by_category,
        "total_tables": len(tables),
        "total_records": sum(t["count"] for t in tables.values()),
    }


@router.get("/tables/{table_name}", dependencies=[Depends(Require("explorer:read"))])
async def explore_table(
    table_name: str,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    order_by: Optional[str] = None,
    order_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_column: Optional[str] = Query(default=None, description="Column to filter by date"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(default=None, description="Search text in string columns"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explore data in a specific table with date filtering and search."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]
    query = db.query(model)

    # Apply date filtering
    if date_column and start_date and end_date:
        col = getattr(model, date_column, None)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Invalid date column: {date_column}")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        query = query.filter(col >= start_dt, col <= end_dt)

    # Apply search (search in string columns)
    if search:
        search_conditions = []
        for column in inspect(model).mapper.column_attrs:
            col = getattr(model, column.key)
            if hasattr(col, 'type') and hasattr(col.type, 'python_type'):
                if col.type.python_type == str:
                    search_conditions.append(col.ilike(f"%{search}%"))
        if search_conditions:
            query = query.filter(or_(*search_conditions))

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
            row[column.key] = _serialize_value(value)
        data.append(row)

    return {
        "table": table_name,
        "total": total,
        "limit": limit,
        "offset": offset,
        "date_columns": _get_date_columns(model),
        "columns": [c.key for c in inspect(model).mapper.column_attrs],
        "filters_applied": {
            "date_column": date_column,
            "start_date": start_date,
            "end_date": end_date,
            "search": search,
        },
        "data": data,
    }


@router.get("/tables/{table_name}/stats", dependencies=[Depends(Require("explorer:read"))])
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


@router.get("/tables/{table_name}/export", dependencies=[Depends(Require("explorer:read"))])
async def export_table(
    table_name: str,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    date_column: Optional[str] = Query(default=None, description="Column to filter by date"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(default=None, description="Search text in string columns"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export table data as CSV or JSON with optional filtering."""
    if table_name not in TABLES:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    model = TABLES[table_name]
    query = db.query(model)

    # Apply date filtering
    if date_column and start_date and end_date:
        col = getattr(model, date_column, None)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Invalid date column: {date_column}")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        query = query.filter(col >= start_dt, col <= end_dt)

    # Apply search (search in string columns)
    if search:
        search_conditions = []
        for column in inspect(model).mapper.column_attrs:
            col = getattr(model, column.key)
            if hasattr(col, 'type') and hasattr(col.type, 'python_type'):
                if col.type.python_type == str:
                    search_conditions.append(col.ilike(f"%{search}%"))
        if search_conditions:
            query = query.filter(or_(*search_conditions))

    # Default order by id desc
    if hasattr(model, "id"):
        query = query.order_by(model.id.desc())

    # Limit to 10000 records for export to prevent memory issues
    records = query.limit(10000).all()

    # Get column names
    columns = [c.key for c in inspect(model).mapper.column_attrs]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for record in records:
            row = []
            for col in columns:
                value = getattr(record, col)
                row.append(_serialize_value(value))
            writer.writerow(row)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={table_name}_export.csv"
            },
        )
    else:  # json
        data = []
        for record in records:
            row = {}
            for col in columns:
                value = getattr(record, col)
                row[col] = _serialize_value(value)
            data.append(row)

        output = json.dumps(data, indent=2, default=str)
        return StreamingResponse(
            iter([output]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={table_name}_export.json"
            },
        )


@router.get("/data-quality", dependencies=[Depends(Require("explorer:read"))])
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


@router.get("/search", dependencies=[Depends(Require("explorer:read"))])
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


@router.post("/query", dependencies=[Depends(Require("explorer:read"))])
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
