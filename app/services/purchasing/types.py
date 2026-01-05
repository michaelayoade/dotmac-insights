"""Purchasing service types and data classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


@dataclass
class BillFilters:
    """Filters for bill listing."""
    status: Optional[str] = None
    supplier: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currency: Optional[str] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    overdue_only: bool = False
    sort_by: str = "posting_date"
    sort_order: str = "desc"


@dataclass
class BillCreateData:
    """Data for creating a purchase invoice."""
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    company: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    posting_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    grand_total: Decimal = field(default_factory=lambda: Decimal("0"))
    outstanding_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    paid_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    tax_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "NGN"
    status: Optional[str] = None
    docstatus: int = 0
    is_return: bool = False
    workflow_status: Optional[str] = None
    fiscal_period_id: Optional[int] = None
    journal_entry_id: Optional[int] = None


@dataclass
class BillUpdateData:
    """Data for updating a purchase invoice."""
    bill_number: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    supplier_name: Optional[str] = None
    company: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    supplier_address: Optional[str] = None
    posting_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    grand_total: Optional[Decimal] = None
    outstanding_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    docstatus: Optional[int] = None
    is_return: Optional[bool] = None
    workflow_status: Optional[str] = None
    fiscal_period_id: Optional[int] = None
    journal_entry_id: Optional[int] = None


@dataclass
class SupplierFilters:
    """Filters for supplier listing."""
    search: Optional[str] = None
    supplier_group: Optional[str] = None
    country: Optional[str] = None
    with_outstanding: bool = False


@dataclass
class SupplierCreateData:
    """Data for creating a supplier."""
    supplier_name: str
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: str = "NGN"
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None


@dataclass
class SupplierUpdateData:
    """Data for updating a supplier."""
    supplier_name: Optional[str] = None
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None
    disabled: Optional[bool] = None


@dataclass
class PaymentFilters:
    """Filters for vendor payments."""
    supplier: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class DebitNoteFilters:
    """Filters for debit notes."""
    supplier: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class ExpenseFilters:
    """Filters for GL expense entries."""
    account: Optional[str] = None
    cost_center: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[Decimal] = None


@dataclass
class AgingBucket:
    """AP aging bucket data."""
    count: int = 0
    total: Decimal = field(default_factory=lambda: Decimal("0"))
    invoices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DashboardMetrics:
    """Dashboard metrics data."""
    total_outstanding: Decimal
    total_overdue: Decimal
    overdue_percentage: float
    supplier_count: int
    status_breakdown: Dict[str, Dict[str, Any]]
    due_this_week: Dict[str, Any]
    top_suppliers: List[Dict[str, Any]]
