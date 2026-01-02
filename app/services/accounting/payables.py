"""Payables service - business logic for accounts payable.

This service encapsulates AP-related business logic:
- AP aging reports with configurable buckets
- Outstanding payables with top suppliers
- Supplier CRUD operations

Uses AccountingSettingsService for configurable limits and buckets.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.accounting import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    Supplier,
)
from app.models.party import Party, SupplierAccount
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

from .payables_types import (
    AgingBucket,
    InvoiceAgingDetail,
    PayablesAgingReport,
    PayablesFilters,
    PayablesOutstandingSummary,
    SupplierCreateData,
    SupplierDetail,
    SupplierFilters,
    SupplierOutstanding,
    SupplierSummary,
    SupplierUpdateData,
)
from .settings import AccountingSettingsService

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["PayablesService"]


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


def _get_supplier_party_name(inv: PurchaseInvoice) -> Optional[str]:
    """Get party name from supplier account.

    Returns party name if supplier_account exists, otherwise falls back
    to legacy supplier_name or supplier fields.
    """
    if inv.supplier_account and inv.supplier_account.party:
        party = inv.supplier_account.party
        if party.name:
            return str(party.name)
        if party.legal_name:
            return str(party.legal_name)
        if party.trading_name:
            return str(party.trading_name)
    return inv.supplier_name or inv.supplier


class PayablesService:
    """Service for accounts payable business logic.

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
    # AP Aging Report
    # -------------------------------------------------------------------------

    def get_aging_report(
        self,
        filters: Optional[PayablesFilters] = None,
        company: Optional[str] = None,
    ) -> PayablesAgingReport:
        """Get AP aging report with configurable buckets.

        Args:
            filters: Filter criteria (date, supplier, currency).
            company: Company code for settings lookup.

        Returns:
            PayablesAgingReport with invoices grouped by aging bucket.

        Raises:
            ValidationError: If supplier filter is too short.
        """
        if filters is None:
            filters = PayablesFilters()

        cutoff = filters.as_of_date or date.today()

        # Get configurable limits from settings
        aging_config = self.settings.get_aging_config(company)
        query_limits = self.settings.get_query_limits(company)
        max_invoices = aging_config.max_invoices
        min_search_chars = query_limits.supplier_search_min_chars

        # Build query with eager loading for party-based data
        query = self.db.query(PurchaseInvoice).options(
            joinedload(PurchaseInvoice.supplier_account).joinedload(SupplierAccount.party),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ]),
        )

        # Legacy string filter
        if filters.supplier:
            # Require minimum characters to prevent ILIKE DoS
            if len(filters.supplier) < min_search_chars:
                raise ValidationError(
                    f"Supplier filter must be at least {min_search_chars} characters"
                )
            query = query.filter(
                PurchaseInvoice.supplier.ilike(f"%{filters.supplier}%")
            )

        # Party-based filters
        if filters.supplier_account_id:
            query = query.filter(PurchaseInvoice.supplier_account_id == filters.supplier_account_id)
        elif filters.party_id:
            query = query.join(
                SupplierAccount,
                SupplierAccount.id == PurchaseInvoice.supplier_account_id,
            ).filter(SupplierAccount.party_id == filters.party_id)

        if filters.currency:
            query = query.filter(PurchaseInvoice.currency == filters.currency)

        # Apply limit to prevent DoS
        invoices = query.order_by(PurchaseInvoice.due_date.asc()).limit(max_invoices).all()

        # Initialize buckets
        buckets: Dict[str, AgingBucket] = {
            "current": AgingBucket(name="current", count=0, total=Decimal("0"), invoices=[]),
            "1_30": AgingBucket(name="1-30", count=0, total=Decimal("0"), invoices=[]),
            "31_60": AgingBucket(name="31-60", count=0, total=Decimal("0"), invoices=[]),
            "61_90": AgingBucket(name="61-90", count=0, total=Decimal("0"), invoices=[]),
            "over_90": AgingBucket(name="90+", count=0, total=Decimal("0"), invoices=[]),
        }

        for inv in invoices:
            # Get due date with fallback to posting date
            if inv.due_date:
                due = inv.due_date.date() if hasattr(inv.due_date, 'date') else inv.due_date
            elif inv.posting_date:
                due = inv.posting_date.date() if hasattr(inv.posting_date, 'date') else inv.posting_date
            else:
                continue  # Skip invoices with no date

            days_overdue = (cutoff - due).days if cutoff > due else 0
            outstanding = Decimal(str(inv.outstanding_amount or 0))

            if outstanding <= 0:
                continue

            bucket_key = _get_bucket_key(days_overdue)
            bucket = buckets[bucket_key]

            bucket.count += 1
            bucket.total += outstanding

            # Get party info from supplier_account if available
            supplier_account_id = inv.supplier_account_id
            party_id = None
            party_name = None
            if inv.supplier_account:
                party_id = inv.supplier_account.party_id
                party_name = _get_supplier_party_name(inv)

            bucket.invoices.append(InvoiceAgingDetail(
                id=inv.id,
                invoice_no=inv.erpnext_id,
                supplier=inv.supplier_name or inv.supplier,
                posting_date=inv.posting_date.isoformat() if inv.posting_date else None,
                due_date=inv.due_date.isoformat() if inv.due_date else None,
                grand_total=float(inv.grand_total or 0),
                outstanding=float(outstanding),
                days_overdue=days_overdue,
                supplier_account_id=supplier_account_id,
                party_id=party_id,
                party_name=party_name,
            ))

        total_payable = sum(b.total for b in buckets.values())
        total_invoices = sum(b.count for b in buckets.values())

        return PayablesAgingReport(
            as_of_date=cutoff,
            total_payable=total_payable,
            total_invoices=total_invoices,
            truncated=len(invoices) >= max_invoices,
            max_invoices=max_invoices,
            buckets=buckets,
        )

    # -------------------------------------------------------------------------
    # Outstanding Summary
    # -------------------------------------------------------------------------

    def get_outstanding_summary(
        self,
        currency: Optional[str] = None,
        top_n: int = 5,
        company: Optional[str] = None,
    ) -> PayablesOutstandingSummary:
        """Get outstanding payables with top suppliers.

        Args:
            currency: Currency filter.
            top_n: Number of top suppliers to return.
            company: Company code for settings lookup.

        Returns:
            PayablesOutstandingSummary with total and top suppliers.
        """
        as_of = date.today()

        # Get configurable limits
        query_limits = self.settings.get_query_limits(company)
        max_top = query_limits.max_top_items
        top_n = min(top_n, max_top)

        # Total outstanding
        pi_query = self.db.query(
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.count(PurchaseInvoice.id).label("invoice_count"),
        ).filter(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ]),
        )
        if currency:
            pi_query = pi_query.filter(PurchaseInvoice.currency == currency)

        pi_totals = pi_query.first()
        total_outstanding = Decimal(str(pi_totals.outstanding or 0)) if pi_totals else Decimal("0")
        total_invoices = int(pi_totals.invoice_count or 0) if pi_totals else 0

        # Top suppliers by outstanding (with party info when available)
        by_supplier_query = (
            self.db.query(
                PurchaseInvoice.supplier,
                PurchaseInvoice.supplier_account_id,
                SupplierAccount.party_id,
                Party.name.label("party_name"),
                func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            )
            .outerjoin(SupplierAccount, SupplierAccount.id == PurchaseInvoice.supplier_account_id)
            .outerjoin(Party, Party.id == SupplierAccount.party_id)
            .filter(
                PurchaseInvoice.outstanding_amount > 0,
                PurchaseInvoice.status.in_([
                    PurchaseInvoiceStatus.SUBMITTED,
                    PurchaseInvoiceStatus.UNPAID,
                    PurchaseInvoiceStatus.OVERDUE,
                ]),
            )
        )
        if currency:
            by_supplier_query = by_supplier_query.filter(PurchaseInvoice.currency == currency)

        by_supplier = (
            by_supplier_query.group_by(
                PurchaseInvoice.supplier,
                PurchaseInvoice.supplier_account_id,
                SupplierAccount.party_id,
                Party.name,
            )
            .order_by(func.sum(PurchaseInvoice.outstanding_amount).desc())
            .limit(top_n)
            .all()
        )

        top_suppliers = [
            SupplierOutstanding(
                supplier=row.supplier,
                outstanding=Decimal(str(row.outstanding or 0)),
                supplier_account_id=row.supplier_account_id,
                party_id=row.party_id,
                party_name=row.party_name,
            )
            for row in by_supplier
        ]

        return PayablesOutstandingSummary(
            as_of_date=as_of,
            currency=currency,
            total_outstanding=total_outstanding,
            total_invoices=total_invoices,
            top_suppliers=top_suppliers,
        )

    # -------------------------------------------------------------------------
    # Supplier CRUD
    # -------------------------------------------------------------------------

    def list_suppliers(
        self,
        filters: Optional[SupplierFilters] = None,
        pagination: Optional[PaginationParams] = None,
        company: Optional[str] = None,
    ) -> Tuple[int, List[SupplierSummary]]:
        """List suppliers with filters and pagination.

        Args:
            filters: Filter criteria (search, group).
            pagination: Pagination parameters.
            company: Company code for settings lookup.

        Returns:
            Tuple of (total_count, list of SupplierSummary).
        """
        if filters is None:
            filters = SupplierFilters()
        if pagination is None:
            pagination = PaginationParams()

        # Get configurable limits
        query_limits = self.settings.get_query_limits(company)
        limit = min(pagination.limit or query_limits.default_pagination_limit,
                    query_limits.max_pagination_limit)
        offset = pagination.offset or 0

        query = self.db.query(Supplier).filter(Supplier.disabled.is_(False))

        if filters.search:
            query = query.filter(Supplier.supplier_name.ilike(f"%{filters.search}%"))

        if filters.supplier_group:
            query = query.filter(Supplier.supplier_group == filters.supplier_group)

        # Get total count
        total = query.count()

        # Apply pagination
        suppliers = (
            query.order_by(Supplier.supplier_name)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return total, [
            SupplierSummary(
                id=s.id,
                erpnext_id=s.erpnext_id,
                name=s.supplier_name,
                group=s.supplier_group,
                type=s.supplier_type,
                country=s.country,
                currency=s.default_currency,
                email=s.email_id,
                mobile=s.mobile_no,
            )
            for s in suppliers
        ]

    def get_supplier(self, supplier_id: int) -> SupplierDetail:
        """Get supplier detail by ID.

        Args:
            supplier_id: Supplier primary key.

        Returns:
            SupplierDetail with full supplier information.

        Raises:
            NotFoundError: If supplier not found.
        """
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise NotFoundError(f"Supplier {supplier_id} not found")

        return SupplierDetail(
            id=supplier.id,
            erpnext_id=supplier.erpnext_id,
            supplier_name=supplier.supplier_name,
            supplier_group=supplier.supplier_group,
            supplier_type=supplier.supplier_type,
            country=supplier.country,
            default_currency=supplier.default_currency,
            default_bank_account=supplier.default_bank_account,
            tax_id=supplier.tax_id,
            tax_withholding_category=supplier.tax_withholding_category,
            supplier_primary_contact=supplier.supplier_primary_contact,
            supplier_primary_address=supplier.supplier_primary_address,
            email_id=supplier.email_id,
            mobile_no=supplier.mobile_no,
            default_price_list=supplier.default_price_list,
            payment_terms=supplier.payment_terms,
            is_transporter=supplier.is_transporter or False,
            is_internal_supplier=supplier.is_internal_supplier or False,
            disabled=supplier.disabled or False,
            is_frozen=supplier.is_frozen or False,
            on_hold=supplier.on_hold or False,
        )

    def create_supplier(
        self,
        data: SupplierCreateData,
        company: Optional[str] = None,
    ) -> Supplier:
        """Create a new supplier.

        Args:
            data: Supplier creation data.
            company: Company code for default settings.

        Returns:
            Created Supplier model instance.
        """
        # Get default currency from settings if not provided
        query_limits = self.settings.get_query_limits(company)
        default_currency = data.default_currency or query_limits.default_currency

        supplier = Supplier(
            supplier_name=data.supplier_name,
            supplier_group=data.supplier_group,
            supplier_type=data.supplier_type,
            country=data.country,
            default_currency=default_currency,
            default_bank_account=data.default_bank_account,
            tax_id=data.tax_id,
            tax_withholding_category=data.tax_withholding_category,
            supplier_primary_contact=data.supplier_primary_contact,
            supplier_primary_address=data.supplier_primary_address,
            email_id=data.email_id,
            mobile_no=data.mobile_no,
            default_price_list=data.default_price_list,
            payment_terms=data.payment_terms,
            is_transporter=data.is_transporter,
            is_internal_supplier=data.is_internal_supplier,
            disabled=data.disabled,
            is_frozen=data.is_frozen,
            on_hold=data.on_hold,
        )

        self.db.add(supplier)
        self.db.flush()
        return supplier

    def update_supplier(
        self,
        supplier_id: int,
        data: SupplierUpdateData,
    ) -> Supplier:
        """Update an existing supplier.

        Args:
            supplier_id: Supplier primary key.
            data: Fields to update (only non-None values applied).

        Returns:
            Updated Supplier model instance.

        Raises:
            NotFoundError: If supplier not found.
        """
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise NotFoundError(f"Supplier {supplier_id} not found")

        # Apply updates (only non-None values)
        update_fields = [
            "supplier_name", "supplier_group", "supplier_type", "country",
            "default_currency", "default_bank_account", "tax_id",
            "tax_withholding_category", "supplier_primary_contact",
            "supplier_primary_address", "email_id", "mobile_no",
            "default_price_list", "payment_terms", "is_transporter",
            "is_internal_supplier", "disabled", "is_frozen", "on_hold",
        ]

        for field_name in update_fields:
            value = getattr(data, field_name, None)
            if value is not None:
                setattr(supplier, field_name, value)

        self.db.flush()
        return supplier

    def disable_supplier(self, supplier_id: int) -> None:
        """Disable a supplier (soft delete).

        Args:
            supplier_id: Supplier primary key.

        Raises:
            NotFoundError: If supplier not found.
        """
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise NotFoundError(f"Supplier {supplier_id} not found")

        supplier.disabled = True
        self.db.flush()
