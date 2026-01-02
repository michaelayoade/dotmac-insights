"""Type definitions for payables service.

These dataclasses define the contract for AP operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

__all__ = [
    "PayablesFilters",
    "SupplierFilters",
    "SupplierCreateData",
    "SupplierUpdateData",
    "InvoiceAgingDetail",
    "AgingBucket",
    "PayablesAgingReport",
    "SupplierOutstanding",
    "PayablesOutstandingSummary",
    "SupplierSummary",
    "SupplierDetail",
]


@dataclass
class PayablesFilters:
    """Filters for AP aging report."""

    as_of_date: Optional[date] = None
    supplier: Optional[str] = None  # Legacy string filter
    supplier_account_id: Optional[int] = None  # Party-based filter
    party_id: Optional[int] = None  # Party-based filter
    currency: Optional[str] = None


@dataclass
class SupplierFilters:
    """Filters for listing suppliers."""

    search: Optional[str] = None
    supplier_group: Optional[str] = None


@dataclass
class SupplierCreateData:
    """Data for creating a supplier."""

    supplier_name: str
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    default_bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    tax_withholding_category: Optional[str] = None
    supplier_primary_contact: Optional[str] = None
    supplier_primary_address: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    default_price_list: Optional[str] = None
    payment_terms: Optional[str] = None
    is_transporter: bool = False
    is_internal_supplier: bool = False
    disabled: bool = False
    is_frozen: bool = False
    on_hold: bool = False


@dataclass
class SupplierUpdateData:
    """Data for updating a supplier (all fields optional)."""

    supplier_name: Optional[str] = None
    supplier_group: Optional[str] = None
    supplier_type: Optional[str] = None
    country: Optional[str] = None
    default_currency: Optional[str] = None
    default_bank_account: Optional[str] = None
    tax_id: Optional[str] = None
    tax_withholding_category: Optional[str] = None
    supplier_primary_contact: Optional[str] = None
    supplier_primary_address: Optional[str] = None
    email_id: Optional[str] = None
    mobile_no: Optional[str] = None
    default_price_list: Optional[str] = None
    payment_terms: Optional[str] = None
    is_transporter: Optional[bool] = None
    is_internal_supplier: Optional[bool] = None
    disabled: Optional[bool] = None
    is_frozen: Optional[bool] = None
    on_hold: Optional[bool] = None


@dataclass
class InvoiceAgingDetail:
    """Details of a purchase invoice in an aging bucket."""

    id: int
    invoice_no: Optional[str]
    supplier: Optional[str]  # Legacy supplier string
    posting_date: Optional[str]
    due_date: Optional[str]
    grand_total: float
    outstanding: float
    days_overdue: int
    # Party-based fields (populated when supplier_account exists)
    supplier_account_id: Optional[int] = None
    party_id: Optional[int] = None
    party_name: Optional[str] = None


@dataclass
class AgingBucket:
    """A single aging bucket with totals and invoices."""

    name: str
    count: int
    total: Decimal
    invoices: List[InvoiceAgingDetail] = field(default_factory=list)


@dataclass
class PayablesAgingReport:
    """Full AP aging report."""

    as_of_date: date
    total_payable: Decimal
    total_invoices: int
    truncated: bool
    max_invoices: int
    buckets: Dict[str, AgingBucket]

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        aging = {}
        for key, bucket in self.buckets.items():
            aging[key] = {
                "count": bucket.count,
                "total": float(bucket.total),
                "invoices": [
                    {
                        "id": inv.id,
                        "invoice_no": inv.invoice_no,
                        "supplier": inv.supplier,
                        "supplier_account_id": inv.supplier_account_id,
                        "party_id": inv.party_id,
                        "party_name": inv.party_name,
                        "posting_date": inv.posting_date,
                        "due_date": inv.due_date,
                        "grand_total": inv.grand_total,
                        "outstanding": inv.outstanding,
                        "days_overdue": inv.days_overdue,
                    }
                    for inv in bucket.invoices
                ],
            }
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "total_payable": float(self.total_payable),
            "total_invoices": self.total_invoices,
            "truncated": self.truncated,
            "max_invoices": self.max_invoices,
            "aging": aging,
        }


@dataclass
class SupplierOutstanding:
    """Outstanding amount for a supplier."""

    supplier: Optional[str]  # Legacy supplier string
    outstanding: Decimal
    # Party-based fields (populated when supplier_account exists)
    supplier_account_id: Optional[int] = None
    party_id: Optional[int] = None
    party_name: Optional[str] = None


@dataclass
class PayablesOutstandingSummary:
    """Summary of outstanding payables."""

    as_of_date: date
    currency: Optional[str]
    total_outstanding: Decimal
    total_invoices: int
    top_suppliers: List[SupplierOutstanding]

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "currency": self.currency,
            "total_outstanding": float(self.total_outstanding),
            "total_invoices": self.total_invoices,
            "top_suppliers": [
                {
                    "supplier": s.supplier,
                    "supplier_account_id": s.supplier_account_id,
                    "party_id": s.party_id,
                    "party_name": s.party_name,
                    "outstanding": float(s.outstanding),
                }
                for s in self.top_suppliers
            ],
        }


@dataclass
class SupplierSummary:
    """Summary of a supplier for list views."""

    id: int
    erpnext_id: Optional[str]
    name: Optional[str]
    group: Optional[str]
    type: Optional[str]
    country: Optional[str]
    currency: Optional[str]
    email: Optional[str]
    mobile: Optional[str]


@dataclass
class SupplierDetail:
    """Full supplier details."""

    id: int
    erpnext_id: Optional[str]
    supplier_name: Optional[str]
    supplier_group: Optional[str]
    supplier_type: Optional[str]
    country: Optional[str]
    default_currency: Optional[str]
    default_bank_account: Optional[str]
    tax_id: Optional[str]
    tax_withholding_category: Optional[str]
    supplier_primary_contact: Optional[str]
    supplier_primary_address: Optional[str]
    email_id: Optional[str]
    mobile_no: Optional[str]
    default_price_list: Optional[str]
    payment_terms: Optional[str]
    is_transporter: bool
    is_internal_supplier: bool
    disabled: bool
    is_frozen: bool
    on_hold: bool

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        return {
            "id": self.id,
            "erpnext_id": self.erpnext_id,
            "supplier_name": self.supplier_name,
            "supplier_group": self.supplier_group,
            "supplier_type": self.supplier_type,
            "country": self.country,
            "default_currency": self.default_currency,
            "default_bank_account": self.default_bank_account,
            "tax_id": self.tax_id,
            "tax_withholding_category": self.tax_withholding_category,
            "supplier_primary_contact": self.supplier_primary_contact,
            "supplier_primary_address": self.supplier_primary_address,
            "email_id": self.email_id,
            "mobile_no": self.mobile_no,
            "default_price_list": self.default_price_list,
            "payment_terms": self.payment_terms,
            "is_transporter": self.is_transporter,
            "is_internal_supplier": self.is_internal_supplier,
            "disabled": self.disabled,
            "is_frozen": self.is_frozen,
            "on_hold": self.on_hold,
        }
