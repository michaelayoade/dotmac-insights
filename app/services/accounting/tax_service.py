"""Tax service for tax filing and payment management.

This module handles:
- Tax filing period CRUD
- Tax filing workflow (file, pay)
- Tax dashboard summary

Note: Tax templates, categories, and rules are read-only lookups and remain in the API layer.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.tax import (
    TaxCode,
    TaxFilingPeriod,
    TaxFilingStatus,
    TaxFilingType,
    TaxPayment,
    TaxType,
    RoundingMethod,
)
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams
from app.services.validation.soft_validation_service import SoftValidationService
from app.services.validation.soft_validation_service import SoftValidationService

from .tax_types import (
    TaxCodeFilters,
    TaxCodeCreateData,
    TaxCodeUpdateData,
    TaxDashboardSummary,
    TaxFilingCreateData,
    TaxFilingFilters,
    TaxPaymentCreateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["TaxService"]


class TaxService:
    """Service for tax filing and payment management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # ============= TAX CODES =============

    def list_tax_codes(
        self,
        filters: TaxCodeFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[TaxCode]:
        """List tax codes with filters."""
        query = self.db.query(TaxCode)

        if filters.query:
            query = query.filter(
                or_(
                    TaxCode.code.ilike(f"%{filters.query}%"),
                    TaxCode.name.ilike(f"%{filters.query}%"),
                )
            )

        if filters.tax_type:
            try:
                tax_type_enum = TaxType(filters.tax_type.lower())
                query = query.filter(TaxCode.tax_type == tax_type_enum)
            except ValueError:
                raise ValidationError(f"Invalid tax type: {filters.tax_type}")

        if filters.is_active is not None:
            query = query.filter(TaxCode.is_active == filters.is_active)

        query = query.order_by(TaxCode.code)
        return paginate(query, pagination)

    def get_tax_code(self, tax_code_id: int) -> TaxCode:
        """Get a tax code by ID."""
        tax_code = self.db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
        if not tax_code:
            raise NotFoundError("Tax code not found")
        return tax_code

    def get_tax_code_stats(self) -> Dict[str, int]:
        """Get tax code statistics."""
        total = self.db.query(func.count(TaxCode.id)).scalar() or 0
        active = self.db.query(func.count(TaxCode.id)).filter(TaxCode.is_active == True).scalar() or 0
        sales = self.db.query(func.count(TaxCode.id)).filter(
            TaxCode.tax_type.in_([TaxType.SALES, TaxType.BOTH])
        ).scalar() or 0
        purchase = self.db.query(func.count(TaxCode.id)).filter(
            TaxCode.tax_type.in_([TaxType.PURCHASE, TaxType.BOTH])
        ).scalar() or 0

        return {
            "total": total,
            "active": active,
            "sales": sales,
            "purchase": purchase,
        }

    def create_tax_code(
        self,
        data: TaxCodeCreateData,
        user_id: Optional[int] = None,
    ) -> TaxCode:
        """Create a new tax code."""
        existing = self.db.query(TaxCode).filter(TaxCode.code == data.code).first()
        if existing:
            raise ValidationError(f"Tax code '{data.code}' already exists")

        try:
            tax_type_enum = TaxType(data.tax_type.lower())
        except ValueError:
            raise ValidationError(f"Invalid tax type: {data.tax_type}")

        try:
            rounding_enum = RoundingMethod(data.rounding_method.lower())
        except ValueError:
            raise ValidationError(f"Invalid rounding method: {data.rounding_method}")

        tc = TaxCode(
            code=data.code,
            name=data.name,
            description=data.description,
            rate=data.rate,
            tax_type=tax_type_enum,
            is_tax_inclusive=data.is_tax_inclusive,
            rounding_method=rounding_enum,
            rounding_precision=data.rounding_precision,
            jurisdiction=data.jurisdiction,
            country=data.country,
            account_head=data.account_head,
            cost_center=data.cost_center,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            company=data.company,
            created_by_id=user_id,
        )
        self.db.add(tc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(tc)
        return tc

    def update_tax_code(self, tax_code_id: int, data: TaxCodeUpdateData) -> TaxCode:
        """Update a tax code."""
        tc = self.db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
        if not tc:
            raise NotFoundError("Tax code not found")

        if data.name is not None:
            tc.name = data.name
        if data.description is not None:
            tc.description = data.description
        if data.rate is not None:
            tc.rate = data.rate
        if data.tax_type is not None:
            try:
                tc.tax_type = TaxType(data.tax_type.lower())
            except ValueError:
                raise ValidationError(f"Invalid tax type: {data.tax_type}")
        if data.is_tax_inclusive is not None:
            tc.is_tax_inclusive = data.is_tax_inclusive
        if data.rounding_method is not None:
            try:
                tc.rounding_method = RoundingMethod(data.rounding_method.lower())
            except ValueError:
                raise ValidationError(f"Invalid rounding method: {data.rounding_method}")
        if data.rounding_precision is not None:
            tc.rounding_precision = data.rounding_precision
        if data.jurisdiction is not None:
            tc.jurisdiction = data.jurisdiction
        if data.country is not None:
            tc.country = data.country
        if data.account_head is not None:
            tc.account_head = data.account_head
        if data.cost_center is not None:
            tc.cost_center = data.cost_center
        if data.valid_from is not None:
            tc.valid_from = data.valid_from
        if data.valid_to is not None:
            tc.valid_to = data.valid_to
        if data.company is not None:
            tc.company = data.company
        if data.is_active is not None:
            tc.is_active = data.is_active

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(tc)
        return tc

    def deactivate_tax_code(self, tax_code_id: int) -> TaxCode:
        """Deactivate (soft delete) a tax code."""
        tc = self.db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()
        if not tc:
            raise NotFoundError("Tax code not found")
        tc.is_active = False
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(tc)
        return tc

    # ============= TAX FILING PERIODS =============

    # ============= TAX FILING PERIODS =============

    def list_filing_periods(
        self,
        filters: TaxFilingFilters,
        pagination: PaginationParams,
    ) -> PaginatedResult[TaxFilingPeriod]:
        """List tax filing periods with filtering.

        Args:
            filters: Filing period filters
            pagination: Pagination parameters

        Returns:
            Paginated filing period results
        """
        query = self.db.query(TaxFilingPeriod)

        if filters.tax_type:
            try:
                tax_type_enum = TaxFilingType(filters.tax_type.lower())
                query = query.filter(TaxFilingPeriod.tax_type == tax_type_enum)
            except ValueError:
                raise ValidationError(f"Invalid tax type: {filters.tax_type}")

        if filters.status:
            try:
                status_enum = TaxFilingStatus(filters.status.lower())
                query = query.filter(TaxFilingPeriod.status == status_enum)
            except ValueError:
                raise ValidationError(f"Invalid status: {filters.status}")

        if filters.year:
            query = query.filter(
                func.extract("year", TaxFilingPeriod.period_start) == filters.year
            )

        query = query.order_by(TaxFilingPeriod.due_date.desc())
        return paginate(query, pagination)

    def list_filing_years(self) -> list[int]:
        """List available filing years (descending)."""
        years_query = self.db.query(
            func.distinct(func.extract("year", TaxFilingPeriod.period_start))
        ).all()
        years = sorted([int(y[0]) for y in years_query if y[0]], reverse=True)
        return years

    def get_filing_period(self, period_id: int) -> TaxFilingPeriod:
        """Get a tax filing period by ID.

        Args:
            period_id: Filing period ID

        Returns:
            TaxFilingPeriod model instance

        Raises:
            NotFoundError: If period not found
        """
        period = self.db.query(TaxFilingPeriod).filter(
            TaxFilingPeriod.id == period_id
        ).first()
        if not period:
            raise NotFoundError("Tax filing period not found")
        return period

    def get_period_payments(self, period_id: int) -> List[TaxPayment]:
        """Get payments for a tax filing period.

        Args:
            period_id: Filing period ID

        Returns:
            List of TaxPayment instances
        """
        return self.db.query(TaxPayment).filter(
            TaxPayment.filing_period_id == period_id
        ).order_by(TaxPayment.payment_date.desc()).all()

    def get_filing_stats(self) -> Dict[str, int]:
        """Get filing period statistics for the dashboard."""
        today = date.today()
        month_start = date(today.year, today.month, 1)

        filed_this_month = self.db.query(func.count(TaxFilingPeriod.id)).filter(
            TaxFilingPeriod.filed_at >= month_start
        ).scalar() or 0

        return {
            "filed_this_month": filed_this_month,
        }

    def create_filing_period(
        self,
        data: TaxFilingCreateData,
        user_id: Optional[int] = None,
    ) -> TaxFilingPeriod:
        """Create a new tax filing period.

        Args:
            data: Filing period creation data
            user_id: ID of user creating the period

        Returns:
            Created TaxFilingPeriod

        Raises:
            ValidationError: If tax type is invalid
        """
        try:
            tax_type_enum = TaxFilingType(data.tax_type.lower())
        except ValueError:
            raise ValidationError(f"Invalid tax type: {data.tax_type}")

        period = TaxFilingPeriod(
            tax_type=tax_type_enum,
            period_name=data.period_name,
            period_start=data.period_start,
            period_end=data.period_end,
            due_date=data.due_date,
            tax_base=data.tax_base,
            tax_amount=data.tax_amount,
            created_by_id=user_id,
        )
        self.db.add(period)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(period)
        return period

    # ============= FILING WORKFLOW =============

    def file_period(
        self,
        period_id: int,
        filing_reference: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> TaxFilingPeriod:
        """Mark a tax filing period as filed.

        Args:
            period_id: Filing period ID
            filing_reference: Reference number from filing
            user_id: ID of user filing

        Returns:
            Updated TaxFilingPeriod

        Raises:
            NotFoundError: If period not found
            ValidationError: If period is already filed
        """
        period = self.get_filing_period(period_id)

        if period.status != TaxFilingStatus.OPEN:
            raise ValidationError(f"Period is already {period.status.value}")

        period.status = TaxFilingStatus.FILED
        period.filed_at = datetime.now(timezone.utc)
        period.filed_by_id = user_id
        period.filing_reference = filing_reference

        self.db.flush()
        SoftValidationService(self.db).validate_and_store(period)
        return period

    def record_payment(
        self,
        period_id: int,
        data: TaxPaymentCreateData,
        user_id: Optional[int] = None,
    ) -> TaxPayment:
        """Record a tax payment for a filing period.

        Args:
            period_id: Filing period ID
            data: Payment data
            user_id: ID of user recording payment

        Returns:
            Created TaxPayment

        Raises:
            NotFoundError: If period not found
        """
        period = self.get_filing_period(period_id)

        payment = TaxPayment(
            filing_period_id=period_id,
            payment_date=data.payment_date,
            amount=data.amount,
            payment_reference=data.payment_reference,
            payment_method=data.payment_method,
            bank_account=data.bank_account,
            created_by_id=user_id,
        )
        self.db.add(payment)

        # Update period totals
        period.amount_paid += data.amount
        if period.amount_paid >= period.tax_amount:
            period.status = TaxFilingStatus.PAID

        self.db.flush()
        validator = SoftValidationService(self.db)
        validator.validate_and_store(payment)
        validator.validate_and_store(period)
        return payment

    # ============= TAX DASHBOARD =============

    def get_dashboard_summary(self) -> TaxDashboardSummary:
        """Get tax obligations dashboard summary.

        Returns:
            Dashboard summary with tax obligations by type
        """
        today = date.today()

        # Get summary by tax type
        summary_by_type: Dict[str, Any] = {}
        for tax_type in TaxFilingType:
            open_periods = self.db.query(TaxFilingPeriod).filter(
                and_(
                    TaxFilingPeriod.tax_type == tax_type,
                    TaxFilingPeriod.status.in_([
                        TaxFilingStatus.OPEN,
                        TaxFilingStatus.FILED,
                    ]),
                )
            ).all()

            total_outstanding = sum(p.outstanding_amount for p in open_periods)
            overdue_count = sum(1 for p in open_periods if p.is_overdue)

            if open_periods or total_outstanding > 0:
                summary_by_type[tax_type.value] = {
                    "open_periods": len(open_periods),
                    "total_outstanding": float(total_outstanding),
                    "overdue_count": overdue_count,
                }

        # Get upcoming due dates
        upcoming = self.db.query(TaxFilingPeriod).filter(
            and_(
                TaxFilingPeriod.status == TaxFilingStatus.OPEN,
                TaxFilingPeriod.due_date >= today,
            )
        ).order_by(TaxFilingPeriod.due_date).limit(5).all()

        # Get overdue filings
        overdue = self.db.query(TaxFilingPeriod).filter(
            and_(
                TaxFilingPeriod.status == TaxFilingStatus.OPEN,
                TaxFilingPeriod.due_date < today,
            )
        ).order_by(TaxFilingPeriod.due_date).all()

        return TaxDashboardSummary(
            as_of_date=today,
            summary_by_type=summary_by_type,
            total_outstanding=sum(
                s["total_outstanding"] for s in summary_by_type.values()
            ),
            total_overdue_count=sum(
                s["overdue_count"] for s in summary_by_type.values()
            ),
            upcoming_due=[
                {
                    "id": p.id,
                    "tax_type": p.tax_type.value,
                    "period_name": p.period_name,
                    "due_date": p.due_date.isoformat(),
                    "outstanding": float(p.outstanding_amount),
                }
                for p in upcoming
            ],
            overdue=[
                {
                    "id": p.id,
                    "tax_type": p.tax_type.value,
                    "period_name": p.period_name,
                    "due_date": p.due_date.isoformat(),
                    "days_overdue": (today - p.due_date).days,
                    "outstanding": float(p.outstanding_amount),
                }
                for p in overdue
            ],
        )
