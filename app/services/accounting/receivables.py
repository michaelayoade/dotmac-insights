"""Receivables service - business logic for accounts receivable.

This service encapsulates AR-related business logic:
- AR aging reports with configurable buckets
- Outstanding receivables with top parties
- Enhanced aging grouped by party

Uses AccountingSettingsService for configurable limits and buckets.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.invoice import Invoice, InvoiceStatus
from app.models.party import CustomerAccount, Party
from app.services.types import PaginationParams

from .receivables_types import (
    AgingBucket,
    AgingReport,
    EnhancedAgingFilters,
    EnhancedAgingResult,
    InvoiceAgingDetail,
    InvoiceStats,
    InvoiceStatsFilters,
    OutstandingSummary,
    PartyAgingDetail,
    PartyOutstanding,
    ReceivablesFilters,
)
from .settings import AccountingSettingsService

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ReceivablesService"]


def _get_party_name(inv: Invoice) -> str:
    """Get name from party via customer account."""
    if inv.customer_account and inv.customer_account.party:
        party = inv.customer_account.party
        if party.name:
            return str(party.name)
        full_name = f"{party.first_name or ''} {party.last_name or ''}".strip()
        if full_name:
            return full_name
        if party.legal_name:
            return str(party.legal_name)
        if party.trading_name:
            return str(party.trading_name)
    return "Unknown"


def _get_bucket_key(days_overdue: int) -> str:
    """Map days overdue to bucket key."""
    if days_overdue <= 0:
        return "current"
    elif days_overdue <= 30:
        return "1_30"
    elif days_overdue <= 60:
        return "31_60"
    elif days_overdue <= 90:
        return "61_90"
    else:
        return "over_90"


class ReceivablesService:
    """Service for accounts receivable business logic.

    All methods that access settings use AccountingSettingsService
    to get configurable limits instead of hardcoded values.

    Args:
        db: SQLAlchemy database session.
        settings_service: Accounting settings service for configuration.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(
        self,
        db: Session,
        settings_service: AccountingSettingsService,
        principal: Optional["Principal"] = None,
    ) -> None:
        self.db = db
        self.settings = settings_service
        self.principal = principal

    # -------------------------------------------------------------------------
    # AR Aging Report
    # -------------------------------------------------------------------------

    def get_aging_report(
        self,
        filters: Optional[ReceivablesFilters] = None,
        company: Optional[str] = None,
    ) -> AgingReport:
        """Get AR aging report with configurable buckets.

        Args:
            filters: Filter criteria (date, party, currency).
            company: Company code for settings lookup.

        Returns:
            AgingReport with invoices grouped by aging bucket.
        """
        if filters is None:
            filters = ReceivablesFilters()

        cutoff = filters.as_of_date or date.today()

        # Get configurable limits from settings
        aging_config = self.settings.get_aging_config(company)
        max_invoices = aging_config.max_invoices

        # Build query
        query = self.db.query(Invoice).options(
            joinedload(Invoice.customer_account).joinedload(CustomerAccount.party),
        ).filter(
            Invoice.status.in_([
                InvoiceStatus.PENDING,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PARTIALLY_PAID,
            ]),
            Invoice.is_deleted == False,
        )

        if filters.customer_account_id:
            query = query.filter(Invoice.customer_account_id == filters.customer_account_id)
        elif filters.party_id:
            query = query.join(
                CustomerAccount,
                CustomerAccount.id == Invoice.customer_account_id,
            ).filter(CustomerAccount.party_id == filters.party_id)

        if filters.currency:
            query = query.filter(Invoice.currency == filters.currency)

        # Apply limit to prevent DoS
        invoices = query.order_by(Invoice.due_date.asc()).limit(max_invoices).all()

        # Initialize buckets
        buckets: Dict[str, AgingBucket] = {
            "current": AgingBucket(name="current", count=0, total=Decimal("0"), invoices=[]),
            "1_30": AgingBucket(name="1-30", count=0, total=Decimal("0"), invoices=[]),
            "31_60": AgingBucket(name="31-60", count=0, total=Decimal("0"), invoices=[]),
            "61_90": AgingBucket(name="61-90", count=0, total=Decimal("0"), invoices=[]),
            "over_90": AgingBucket(name="90+", count=0, total=Decimal("0"), invoices=[]),
        }

        for inv in invoices:
            # Get due date with fallback to invoice date
            if inv.due_date:
                due = inv.due_date.date() if hasattr(inv.due_date, 'date') else inv.due_date
            elif inv.invoice_date:
                due = inv.invoice_date.date() if hasattr(inv.invoice_date, 'date') else inv.invoice_date
            else:
                continue  # Skip invoices with no date

            days_overdue = (cutoff - due).days if cutoff > due else 0
            if inv.balance is not None:
                outstanding = Decimal(str(inv.balance))
            else:
                outstanding = Decimal(str(inv.total_amount - (inv.amount_paid or 0)))

            if outstanding <= 0:
                continue

            bucket_key = _get_bucket_key(days_overdue)
            bucket = buckets[bucket_key]

            bucket.count += 1
            bucket.total += outstanding
            bucket.invoices.append(InvoiceAgingDetail(
                id=inv.id,
                invoice_no=inv.invoice_number,
                customer_account_id=inv.customer_account_id,
                party_id=inv.customer_account.party_id if inv.customer_account else None,
                party_name=_get_party_name(inv),
                invoice_date=inv.invoice_date.isoformat() if inv.invoice_date else None,
                due_date=inv.due_date.isoformat() if inv.due_date else None,
                total_amount=float(inv.total_amount),
                amount_paid=float(inv.amount_paid or 0),
                outstanding=float(outstanding),
                days_overdue=days_overdue,
            ))

        total_receivable = sum(b.total for b in buckets.values())
        total_invoices = sum(b.count for b in buckets.values())

        return AgingReport(
            as_of_date=cutoff,
            total_receivable=total_receivable,
            total_invoices=total_invoices,
            truncated=len(invoices) >= max_invoices,
            max_invoices=max_invoices,
            buckets=buckets,
        )

    def list_customer_accounts(self) -> List[CustomerAccount]:
        """List customer accounts ordered by party name."""
        return (
            self.db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .all()
        )

    # -------------------------------------------------------------------------
    # Outstanding Summary
    # -------------------------------------------------------------------------

    def get_outstanding_summary(
        self,
        currency: Optional[str] = None,
        top_n: int = 5,
        company: Optional[str] = None,
    ) -> OutstandingSummary:
        """Get outstanding receivables with top parties.

        Args:
            currency: Currency filter.
            top_n: Number of top parties to return.
            company: Company code for settings lookup.

        Returns:
            OutstandingSummary with total and top parties.
        """
        as_of = date.today()

        # Get configurable limits
        query_limits = self.settings.get_query_limits(company)
        max_top = query_limits.max_top_items
        top_n = min(top_n, max_top)

        # Total outstanding
        inv_query = self.db.query(
            func.sum(func.coalesce(Invoice.balance, Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0))).label("outstanding"),
            func.count(Invoice.id).label("invoice_count"),
        ).filter(
            Invoice.status.in_([
                InvoiceStatus.PENDING,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PARTIALLY_PAID,
            ]),
            Invoice.is_deleted == False,
            func.coalesce(Invoice.balance, Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0)) > 0,
        )
        if currency:
            inv_query = inv_query.filter(Invoice.currency == currency)

        inv_totals = inv_query.first()
        total_outstanding = Decimal(str(inv_totals.outstanding or 0)) if inv_totals else Decimal("0")
        total_invoices = int(inv_totals.invoice_count or 0) if inv_totals else 0

        # Top parties by outstanding amount
        inv_by_party_query = (
            self.db.query(
                Party.id.label("party_id"),
                Party.name.label("party_name"),
                Invoice.customer_account_id.label("customer_account_id"),
                func.sum(func.coalesce(Invoice.balance, Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0))).label("outstanding"),
            )
            .join(CustomerAccount, CustomerAccount.id == Invoice.customer_account_id)
            .join(Party, Party.id == CustomerAccount.party_id)
            .filter(
                Invoice.status.in_([
                    InvoiceStatus.PENDING,
                    InvoiceStatus.OVERDUE,
                    InvoiceStatus.PARTIALLY_PAID,
                ]),
                Invoice.customer_account_id.isnot(None),
                Invoice.is_deleted == False,
                func.coalesce(Invoice.balance, Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0)) > 0,
            )
        )
        if currency:
            inv_by_party_query = inv_by_party_query.filter(Invoice.currency == currency)

        inv_by_party = (
            inv_by_party_query
            .group_by(Party.id, Party.name, Invoice.customer_account_id)
            .order_by(func.sum(func.coalesce(Invoice.balance, Invoice.total_amount - func.coalesce(Invoice.amount_paid, 0))).desc())
            .limit(top_n)
            .all()
        )

        top_parties = [
            PartyOutstanding(
                party_id=row.party_id,
                party_name=row.party_name,
                customer_account_id=row.customer_account_id,
                outstanding=Decimal(str(row.outstanding or 0)),
            )
            for row in inv_by_party
        ]

        return OutstandingSummary(
            as_of_date=as_of,
            currency=currency,
            total_outstanding=total_outstanding,
            total_invoices=total_invoices,
            top_parties=top_parties,
        )

    # -------------------------------------------------------------------------
    # Enhanced Aging (grouped by party)
    # -------------------------------------------------------------------------

    def get_enhanced_aging(
        self,
        filters: Optional[EnhancedAgingFilters] = None,
        pagination: Optional[PaginationParams] = None,
        company: Optional[str] = None,
    ) -> EnhancedAgingResult:
        """Get enhanced AR aging grouped by party.

        Args:
            filters: Filter criteria (currency, min_amount, search).
            pagination: Pagination parameters (offset, limit).
            company: Company code for settings lookup.

        Returns:
            EnhancedAgingResult with party-level aging details.
        """
        if filters is None:
            filters = EnhancedAgingFilters()
        if pagination is None:
            pagination = PaginationParams()

        cutoff = date.today()

        # Get configurable limits
        aging_config = self.settings.get_aging_config(company)
        max_invoices = aging_config.max_invoices

        # Build query
        query = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.customer_account).joinedload(CustomerAccount.party))
            .filter(
                and_(
                    Invoice.status.in_([
                        InvoiceStatus.PENDING,
                        InvoiceStatus.PARTIALLY_PAID,
                        InvoiceStatus.OVERDUE,
                    ]),
                    Invoice.is_deleted == False,
                    Invoice.invoice_date <= cutoff,
                )
            )
        )

        if filters.currency:
            query = query.filter(Invoice.currency == filters.currency)

        invoices = query.order_by(Invoice.due_date.asc()).limit(max_invoices).all()

        # Aggregate by party
        totals: Dict[str, Decimal] = {
            "current": Decimal("0"),
            "1_30": Decimal("0"),
            "31_60": Decimal("0"),
            "61_90": Decimal("0"),
            "over_90": Decimal("0"),
        }
        entities: Dict[tuple, Dict] = {}

        for inv in invoices:
            if inv.balance is not None:
                outstanding = Decimal(str(inv.balance))
            else:
                outstanding = Decimal(str(inv.total_amount - (inv.amount_paid or 0)))
            if outstanding <= 0:
                continue

            # Get due date with fallback to invoice date
            if inv.due_date:
                due = inv.due_date.date() if hasattr(inv.due_date, 'date') else inv.due_date
            elif inv.invoice_date:
                due = inv.invoice_date.date() if hasattr(inv.invoice_date, 'date') else inv.invoice_date
            else:
                continue  # Skip invoices with no date

            days_overdue = (cutoff - due).days if cutoff > due else 0
            bucket_key = _get_bucket_key(days_overdue)

            customer_account_id = inv.customer_account_id
            party_id = inv.customer_account.party_id if inv.customer_account else None
            entity_key = (customer_account_id, party_id)
            entity_name = _get_party_name(inv)

            if entity_key not in entities:
                entities[entity_key] = {
                    "customer_account_id": customer_account_id,
                    "party_id": party_id,
                    "party_name": inv.customer_account.party.name if inv.customer_account and inv.customer_account.party else None,
                    "name": entity_name,
                    "total_receivable": Decimal("0"),
                    "current": Decimal("0"),
                    "overdue_1_30": Decimal("0"),
                    "overdue_31_60": Decimal("0"),
                    "overdue_61_90": Decimal("0"),
                    "overdue_over_90": Decimal("0"),
                    "invoice_count": 0,
                    "oldest_invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                }

            ent = entities[entity_key]
            ent["total_receivable"] += outstanding
            ent["invoice_count"] += 1
            if ent["oldest_invoice_date"] is None and inv.invoice_date:
                ent["oldest_invoice_date"] = inv.invoice_date.isoformat()

            # Map bucket key to entity field
            bucket_field_map = {
                "current": "current",
                "1_30": "overdue_1_30",
                "31_60": "overdue_31_60",
                "61_90": "overdue_61_90",
                "over_90": "overdue_over_90",
            }
            ent[bucket_field_map[bucket_key]] += outstanding
            totals[bucket_key] += outstanding

        # Convert to list
        entity_list = list(entities.values())

        # Apply filters
        if filters.search:
            search_lower = filters.search.lower()
            entity_list = [
                e for e in entity_list
                if search_lower in (e["name"] or "").lower()
            ]
        if filters.min_amount:
            entity_list = [
                e for e in entity_list
                if e["total_receivable"] >= filters.min_amount
            ]

        # Sort by total descending
        entity_list.sort(key=lambda e: e["total_receivable"], reverse=True)

        # Paginate
        total_count = len(entity_list)
        offset = pagination.offset or 0
        limit = pagination.limit or 50
        paged = entity_list[offset:offset + limit]

        # Convert to typed objects
        parties = [
            PartyAgingDetail(
                customer_account_id=e["customer_account_id"],
                party_id=e["party_id"],
                party_name=e["party_name"],
                name=e["name"],
                total_receivable=e["total_receivable"],
                current=e["current"],
                overdue_1_30=e["overdue_1_30"],
                overdue_31_60=e["overdue_31_60"],
                overdue_61_90=e["overdue_61_90"],
                overdue_over_90=e["overdue_over_90"],
                invoice_count=e["invoice_count"],
                oldest_invoice_date=e["oldest_invoice_date"],
            )
            for e in paged
        ]

        return EnhancedAgingResult(
            total=total_count,
            offset=offset,
            limit=limit,
            total_receivable=sum(totals.values()),
            aging_totals=totals,
            parties=parties,
        )

    # -------------------------------------------------------------------------
    # Invoice Stats (Dashboard Widget)
    # -------------------------------------------------------------------------

    def get_invoice_stats(
        self,
        filters: Optional[InvoiceStatsFilters] = None,
    ) -> InvoiceStats:
        """Get invoice statistics for dashboard widgets.

        Returns revenue totals and pending invoice counts for the specified period.

        Args:
            filters: Date range and currency filters. Defaults to MTD.

        Returns:
            InvoiceStats with revenue and pending invoice data.
        """
        if filters is None:
            filters = InvoiceStatsFilters()

        today = date.today()
        end_dt = filters.end_date or today
        start_dt = filters.start_date or date(today.year, today.month, 1)  # MTD default

        # Revenue: sum of total_amount for invoices in period with billable statuses
        revenue_statuses = [
            InvoiceStatus.PAID,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PENDING,
            InvoiceStatus.OVERDUE,
        ]

        revenue_query = self.db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
            Invoice.status.in_(revenue_statuses),
        )
        if filters.currency:
            revenue_query = revenue_query.filter(Invoice.currency == filters.currency)

        total_revenue = revenue_query.scalar() or Decimal("0")

        # Pending invoices: count and amount for unpaid invoices
        pending_statuses = [
            InvoiceStatus.PENDING,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERDUE,
        ]

        pending_base = self.db.query(Invoice).filter(
            Invoice.status.in_(pending_statuses),
            Invoice.is_deleted == False,
        )
        if filters.currency:
            pending_base = pending_base.filter(Invoice.currency == filters.currency)

        pending_count = pending_base.with_entities(func.count(Invoice.id)).scalar() or 0
        pending_amount = (
            pending_base.with_entities(func.sum(Invoice.balance)).scalar()
            or Decimal("0")
        )

        return InvoiceStats(
            period_start=start_dt,
            period_end=end_dt,
            total_revenue=Decimal(str(total_revenue)),
            pending_count=int(pending_count),
            pending_amount=Decimal(str(pending_amount)),
        )

    def get_invoice_list_stats(self) -> Dict[str, Decimal]:
        """Get stats for invoice list view."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_count = self.db.query(func.count(Invoice.id)).filter(
            Invoice.is_deleted == False,
        ).scalar() or 0

        outstanding = self.db.query(func.sum(Invoice.balance)).filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
            Invoice.is_deleted == False,
        ).scalar() or Decimal("0")

        overdue = self.db.query(func.sum(Invoice.balance)).filter(
            Invoice.status == InvoiceStatus.OVERDUE,
            Invoice.is_deleted == False,
        ).scalar() or Decimal("0")

        paid_this_month = self.db.query(func.sum(Invoice.amount_paid)).filter(
            Invoice.paid_date >= month_start,
            Invoice.is_deleted == False,
        ).scalar() or Decimal("0")

        return {
            "total_count": total_count,
            "outstanding": outstanding,
            "overdue": overdue,
            "paid_this_month": paid_this_month,
        }

    def list_outstanding_invoices(self) -> List[Invoice]:
        """List outstanding invoices for aging dashboards."""
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.status.in_(
                    [
                        InvoiceStatus.PENDING,
                        InvoiceStatus.PARTIALLY_PAID,
                        InvoiceStatus.OVERDUE,
                    ]
                ),
                Invoice.is_deleted == False,
                Invoice.balance > 0,
            )
            .order_by(Invoice.due_date)
            .all()
        )

    def list_outstanding_invoices_for_customer(
        self,
        customer_account_id: int,
    ) -> List[Invoice]:
        """List outstanding invoices for a specific customer account."""
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.customer_account_id == customer_account_id,
                Invoice.status.in_(
                    [
                        InvoiceStatus.PENDING,
                        InvoiceStatus.PARTIALLY_PAID,
                        InvoiceStatus.OVERDUE,
                    ]
                ),
                Invoice.is_deleted == False,
                Invoice.balance > 0,
            )
            .order_by(Invoice.due_date)
            .all()
        )
