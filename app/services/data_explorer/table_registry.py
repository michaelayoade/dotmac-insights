"""Table registry for data explorer.

Defines available tables, categories, and helper functions.
"""
from __future__ import annotations

from typing import Any, List, Dict, TYPE_CHECKING

from sqlalchemy import inspect
from sqlalchemy.types import DateTime, Date

# Core models
from app.models.party import Party, CustomerAccount
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


# Table categories for organization
# Note: "auth" category excluded for security - contains sensitive auth data
TABLE_CATEGORIES: Dict[str, str] = {
    "core_business": "Core Business Data",
    "people": "People & Contacts",
    "network": "Network Infrastructure",
    "support": "Support & Communication",
    "accounting": "Accounting & Finance",
    "hr": "HR & Teams",
    "sales": "Sales & CRM",
    "system": "System & Logs",
}

# Available tables for exploration (organized by category)
TABLES: Dict[str, Any] = {
    # Core business data
    "customer_accounts": CustomerAccount,
    "parties": Party,
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
    # Note: Auth/RBAC tables excluded for security
    # System
    "sync_logs": SyncLog,
}

# Map tables to categories
TABLE_TO_CATEGORY: Dict[str, str] = {
    "customer_accounts": "core_business",
    "parties": "people",
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
    # Note: Auth tables excluded for security
    "sync_logs": "system",
}


def get_date_columns(model: Any) -> List[str]:
    """Get list of date/datetime columns for a model."""
    date_columns = []
    for column in inspect(model).mapper.column_attrs:
        col = getattr(model, column.key)
        if hasattr(col, 'type'):
            if isinstance(col.type, (DateTime, Date)):
                date_columns.append(column.key)
    return date_columns


def get_model_columns(model: Any) -> List[str]:
    """Get list of all columns for a model."""
    return [c.key for c in inspect(model).mapper.column_attrs]


def get_table_model(table_name: str) -> Any:
    """Get the SQLAlchemy model for a table name."""
    return TABLES.get(table_name)


def is_valid_table(table_name: str) -> bool:
    """Check if a table name is valid."""
    return table_name in TABLES
