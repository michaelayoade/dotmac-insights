"""Type definitions for receivables service.

These dataclasses define the contract for AR operations.
They are framework-agnostic (no Pydantic, no FastAPI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

__all__ = [
    "ReceivablesFilters",
    "EnhancedAgingFilters",
    "InvoiceAgingDetail",
    "AgingBucket",
    "AgingReport",
    "OutstandingSummary",
    "PartyOutstanding",
    "PartyAgingDetail",
    "EnhancedAgingResult",
    "InvoiceStatsFilters",
    "InvoiceStats",
]


@dataclass
class ReceivablesFilters:
    """Filters for AR aging report."""

    as_of_date: Optional[date] = None
    party_id: Optional[int] = None
    customer_account_id: Optional[int] = None
    currency: Optional[str] = None


@dataclass
class EnhancedAgingFilters:
    """Filters for enhanced AR aging report."""

    currency: Optional[str] = None
    min_amount: Optional[Decimal] = None
    search: Optional[str] = None


@dataclass
class InvoiceAgingDetail:
    """Details of an invoice in an aging bucket."""

    id: int
    invoice_no: Optional[str]
    customer_account_id: Optional[int]
    party_id: Optional[int]
    party_name: str
    invoice_date: Optional[str]
    due_date: Optional[str]
    total_amount: float
    amount_paid: float
    outstanding: float
    days_overdue: int


@dataclass
class AgingBucket:
    """A single aging bucket with totals and invoices."""

    name: str
    count: int
    total: Decimal
    invoices: List[InvoiceAgingDetail] = field(default_factory=list)


@dataclass
class AgingReport:
    """Full AR aging report."""

    as_of_date: date
    total_receivable: Decimal
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
                        "customer_account_id": inv.customer_account_id,
                        "party_id": inv.party_id,
                        "party_name": inv.party_name,
                        "invoice_date": inv.invoice_date,
                        "due_date": inv.due_date,
                        "total_amount": inv.total_amount,
                        "amount_paid": inv.amount_paid,
                        "outstanding": inv.outstanding,
                        "days_overdue": inv.days_overdue,
                    }
                    for inv in bucket.invoices
                ],
            }
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "total_receivable": float(self.total_receivable),
            "total_invoices": self.total_invoices,
            "truncated": self.truncated,
            "max_invoices": self.max_invoices,
            "aging": aging,
        }


@dataclass
class PartyOutstanding:
    """Outstanding amount for a party."""

    party_id: Optional[int]
    party_name: Optional[str]
    customer_account_id: Optional[int]
    outstanding: Decimal


@dataclass
class OutstandingSummary:
    """Summary of outstanding receivables."""

    as_of_date: date
    currency: Optional[str]
    total_outstanding: Decimal
    total_invoices: int
    top_parties: List[PartyOutstanding]

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "currency": self.currency,
            "total_outstanding": float(self.total_outstanding),
            "total_invoices": self.total_invoices,
            "top_parties": [
                {
                    "party_id": p.party_id,
                    "party_name": p.party_name,
                    "customer_account_id": p.customer_account_id,
                    "outstanding": float(p.outstanding),
                }
                for p in self.top_parties
            ],
        }


@dataclass
class PartyAgingDetail:
    """Aging detail for a single party."""

    customer_account_id: Optional[int]
    party_id: Optional[int]
    party_name: Optional[str]
    name: str
    total_receivable: Decimal
    current: Decimal
    overdue_1_30: Decimal
    overdue_31_60: Decimal
    overdue_61_90: Decimal
    overdue_over_90: Decimal
    invoice_count: int
    oldest_invoice_date: Optional[str]


@dataclass
class EnhancedAgingResult:
    """Result of enhanced aging report."""

    total: int
    offset: int
    limit: int
    total_receivable: Decimal
    aging_totals: Dict[str, Decimal]
    parties: List[PartyAgingDetail]

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        return {
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "total_receivable": float(self.total_receivable),
            "aging": {k: float(v) for k, v in self.aging_totals.items()},
            "parties": [
                {
                    "customer_account_id": p.customer_account_id,
                    "party_id": p.party_id,
                    "party_name": p.party_name,
                    "name": p.name,
                    "total_receivable": float(p.total_receivable),
                    "current": float(p.current),
                    "overdue_1_30": float(p.overdue_1_30),
                    "overdue_31_60": float(p.overdue_31_60),
                    "overdue_61_90": float(p.overdue_61_90),
                    "overdue_over_90": float(p.overdue_over_90),
                    "invoice_count": p.invoice_count,
                    "oldest_invoice_date": p.oldest_invoice_date,
                }
                for p in self.parties
            ],
        }


@dataclass
class InvoiceStatsFilters:
    """Filters for invoice stats query."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currency: Optional[str] = None


@dataclass
class InvoiceStats:
    """Summary statistics for invoices.

    Used for dashboard widgets showing revenue and invoice counts.
    """

    period_start: date
    period_end: date
    total_revenue: Decimal
    pending_count: int
    pending_amount: Decimal

    def to_dict(self) -> Dict:
        """Convert to API-compatible dict."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_revenue": float(self.total_revenue),
            "pending_count": self.pending_count,
            "pending_amount": float(self.pending_amount),
        }
