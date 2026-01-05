"""Fiscal service for fiscal years and cost centers.

This module handles:
- Fiscal Year CRUD
- Cost Center CRUD with expense breakdown

Note: Fiscal periods are handled by PeriodManager service.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import (
    Account,
    AccountType,
    CostCenter,
    FiscalYear,
    GLEntry,
)
from app.models.accounting_ext import FiscalPeriod, FiscalPeriodStatus
from app.services.base import paginate
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .fiscal_types import (
    CostCenterCreateData,
    CostCenterExpenseBreakdown,
    CostCenterUpdateData,
    ExpenseByAccount,
    FiscalPeriodFilters,
    FiscalYearCreateData,
    FiscalYearUpdateData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["FiscalService"]


class FiscalService:
    """Service for fiscal year and cost center management."""

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # ============= FISCAL YEARS =============

    def list_fiscal_years(self, include_disabled: bool = False) -> List[FiscalYear]:
        """List fiscal years.

        Args:
            include_disabled: Include disabled years

        Returns:
            List of fiscal years ordered by most recent first
        """
        query = self.db.query(FiscalYear)
        if not include_disabled:
            query = query.filter(FiscalYear.disabled == False)
        return query.order_by(FiscalYear.year.desc()).all()

    def get_fiscal_year(self, year_id: int) -> FiscalYear:
        """Get a fiscal year by ID.

        Args:
            year_id: Fiscal year ID

        Returns:
            FiscalYear model instance

        Raises:
            NotFoundError: If year not found
        """
        year = self.db.query(FiscalYear).filter(FiscalYear.id == year_id).first()
        if not year:
            raise NotFoundError("Fiscal year not found")
        return year

    def create_fiscal_year(self, data: FiscalYearCreateData) -> FiscalYear:
        """Create a new fiscal year.

        Args:
            data: Fiscal year creation data

        Returns:
            Created FiscalYear
        """
        fiscal_year = FiscalYear(
            year=data.year,
            year_start_date=data.year_start_date,
            year_end_date=data.year_end_date,
            is_short_year=data.is_short_year,
            disabled=data.disabled,
            auto_created=data.auto_created,
        )
        self.db.add(fiscal_year)
        self.db.flush()
        return fiscal_year

    def update_fiscal_year(
        self,
        year_id: int,
        data: FiscalYearUpdateData,
    ) -> FiscalYear:
        """Update a fiscal year.

        Args:
            year_id: Fiscal year ID
            data: Update data

        Returns:
            Updated FiscalYear

        Raises:
            NotFoundError: If year not found
        """
        fiscal_year = self.get_fiscal_year(year_id)

        if data.year is not None:
            fiscal_year.year = data.year
        if data.year_start_date is not None:
            fiscal_year.year_start_date = data.year_start_date
        if data.year_end_date is not None:
            fiscal_year.year_end_date = data.year_end_date
        if data.is_short_year is not None:
            fiscal_year.is_short_year = data.is_short_year
        if data.disabled is not None:
            fiscal_year.disabled = data.disabled
        if data.auto_created is not None:
            fiscal_year.auto_created = data.auto_created

        self.db.flush()
        return fiscal_year

    def disable_fiscal_year(self, year_id: int) -> None:
        """Disable a fiscal year (soft delete).

        Args:
            year_id: Fiscal year ID

        Raises:
            NotFoundError: If year not found
        """
        fiscal_year = self.get_fiscal_year(year_id)
        fiscal_year.disabled = True
        self.db.flush()

    def get_fiscal_year_by_year(self, year: str) -> Optional[FiscalYear]:
        """Get a fiscal year by its year value."""
        return self.db.query(FiscalYear).filter(FiscalYear.year == year).first()

    # ============= FISCAL PERIODS =============

    def list_fiscal_periods(self, filters: FiscalPeriodFilters) -> List[FiscalPeriod]:
        """List fiscal periods with optional filters."""
        query = self.db.query(FiscalPeriod)

        if filters.year:
            fiscal_year = self.get_fiscal_year_by_year(filters.year)
            if fiscal_year:
                query = query.filter(FiscalPeriod.fiscal_year_id == fiscal_year.id)

        if filters.status:
            try:
                period_status = FiscalPeriodStatus(filters.status)
                query = query.filter(FiscalPeriod.status == period_status)
            except ValueError:
                raise ValidationError(f"Invalid fiscal period status: {filters.status}")

        return query.order_by(FiscalPeriod.start_date.desc()).all()

    def get_fiscal_period(self, period_id: int) -> FiscalPeriod:
        """Get a fiscal period by ID."""
        period = self.db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
        if not period:
            raise NotFoundError("Fiscal period not found")
        return period

    def get_fiscal_period_stats(self) -> Dict[str, Any]:
        """Get fiscal period statistics for the list view."""
        now = date.today()

        total_periods = self.db.query(func.count(FiscalPeriod.id)).scalar() or 0
        open_periods = self.db.query(func.count(FiscalPeriod.id)).filter(
            FiscalPeriod.status == FiscalPeriodStatus.OPEN
        ).scalar() or 0
        closed_periods = self.db.query(func.count(FiscalPeriod.id)).filter(
            FiscalPeriod.status.in_([
                FiscalPeriodStatus.SOFT_CLOSED,
                FiscalPeriodStatus.HARD_CLOSED,
            ])
        ).scalar() or 0

        current_period = self.db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= now,
            FiscalPeriod.end_date >= now,
        ).first()

        return {
            "total_periods": total_periods,
            "open_periods": open_periods,
            "closed_periods": closed_periods,
            "current_period": current_period,
        }

    def get_fiscal_period_totals(self, period: FiscalPeriod) -> Dict[str, Any]:
        """Get GL totals and entry counts for a fiscal period."""
        gl_count = self.db.query(func.count(GLEntry.id)).filter(
            GLEntry.posting_date >= period.start_date,
            GLEntry.posting_date <= period.end_date,
            GLEntry.is_cancelled == False,
        ).scalar() or 0

        period_debit = self.db.query(func.sum(GLEntry.debit)).filter(
            GLEntry.posting_date >= period.start_date,
            GLEntry.posting_date <= period.end_date,
            GLEntry.is_cancelled == False,
        ).scalar() or Decimal("0")

        period_credit = self.db.query(func.sum(GLEntry.credit)).filter(
            GLEntry.posting_date >= period.start_date,
            GLEntry.posting_date <= period.end_date,
            GLEntry.is_cancelled == False,
        ).scalar() or Decimal("0")

        return {
            "gl_count": gl_count,
            "period_debit": period_debit,
            "period_credit": period_credit,
        }

    # ============= COST CENTERS =============

    def list_cost_centers(self, include_disabled: bool = False) -> List[CostCenter]:
        """List cost centers.

        Args:
            include_disabled: Include disabled cost centers

        Returns:
            List of cost centers
        """
        query = self.db.query(CostCenter)
        if not include_disabled:
            query = query.filter(CostCenter.disabled == False)
        return query.all()

    def list_cost_centers_paginated(
        self,
        search: Optional[str] = None,
        include_disabled: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[CostCenter]:
        """List cost centers with optional search and pagination."""
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(CostCenter)
        if not include_disabled:
            query = query.filter(CostCenter.disabled == False)

        if search:
            if len(search) < 2:
                raise ValidationError("Search query must be at least 2 characters")
            query = query.filter(
                CostCenter.cost_center_name.ilike(f"%{search}%")
                | CostCenter.cost_center_number.ilike(f"%{search}%")
            )

        query = query.order_by(CostCenter.cost_center_name)
        return paginate(query, pagination)

    def list_parent_cost_centers(self, exclude_id: Optional[int] = None) -> List[CostCenter]:
        """List active parent cost centers (groups)."""
        query = self.db.query(CostCenter).filter(
            CostCenter.disabled == False,
            CostCenter.is_group == True,
        )
        if exclude_id:
            query = query.filter(CostCenter.id != exclude_id)
        return query.order_by(CostCenter.cost_center_name).all()

    def get_cost_center_stats(self) -> Dict[str, int]:
        """Get summary stats for cost centers list view."""
        total = self.db.query(func.count(CostCenter.id)).scalar() or 0
        active = (
            self.db.query(func.count(CostCenter.id))
            .filter(CostCenter.disabled == False)
            .scalar()
            or 0
        )
        inactive = total - active
        return {"total": total, "active": active, "inactive": inactive}

    def get_cost_center(self, center_id: int) -> CostCenter:
        """Get a cost center by ID.

        Args:
            center_id: Cost center ID

        Returns:
            CostCenter model instance

        Raises:
            NotFoundError: If cost center not found
        """
        center = self.db.query(CostCenter).filter(CostCenter.id == center_id).first()
        if not center:
            raise NotFoundError("Cost center not found")
        return center

    def get_cost_center_expenses(
        self,
        center_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> CostCenterExpenseBreakdown:
        """Get cost center with expense breakdown.

        Args:
            center_id: Cost center ID
            start_date: Filter from date
            end_date: Filter to date

        Returns:
            Cost center with expense breakdown

        Raises:
            NotFoundError: If cost center not found
        """
        cc = self.get_cost_center(center_id)

        # Get expenses by account for this cost center
        query = self.db.query(
            GLEntry.account,
            func.sum(GLEntry.debit).label("debit"),
            func.sum(GLEntry.credit).label("credit"),
        ).filter(
            GLEntry.cost_center == cc.erpnext_id,
            GLEntry.is_cancelled == False,
        )

        if start_date:
            query = query.filter(GLEntry.posting_date >= start_date)
        if end_date:
            query = query.filter(GLEntry.posting_date <= end_date)

        results = query.group_by(GLEntry.account).all()

        # Get account info for names and filtering by expense type
        accounts = {
            a.erpnext_id: a
            for a in self.db.query(Account).filter(
                Account.erpnext_id.in_([r.account for r in results])
            ).all()
        }

        breakdown = []
        total = Decimal("0")

        for row in results:
            acc = accounts.get(row.account)
            amount = (row.debit or Decimal("0")) - (row.credit or Decimal("0"))
            if acc and acc.root_type == AccountType.EXPENSE:
                breakdown.append(ExpenseByAccount(
                    account=row.account,
                    account_name=acc.account_name if acc else row.account,
                    amount=float(amount),
                ))
                total += amount

        # Sort by absolute amount descending
        breakdown.sort(key=lambda x: -abs(x.amount))

        return CostCenterExpenseBreakdown(
            id=cc.id,
            erpnext_id=cc.erpnext_id,
            name=cc.cost_center_name,
            number=cc.cost_center_number,
            parent=cc.parent_cost_center,
            company=cc.company,
            start_date=start_date,
            end_date=end_date,
            total_expenses=float(total),
            breakdown=breakdown,
        )

    def create_cost_center(self, data: CostCenterCreateData) -> CostCenter:
        """Create a new cost center.

        Args:
            data: Cost center creation data

        Returns:
            Created CostCenter
        """
        center = CostCenter(
            cost_center_name=data.cost_center_name,
            cost_center_number=data.cost_center_number,
            parent_cost_center=data.parent_cost_center,
            company=data.company,
            is_group=data.is_group,
            disabled=data.disabled,
            lft=data.lft,
            rgt=data.rgt,
        )
        self.db.add(center)
        self.db.flush()
        return center

    def update_cost_center(
        self,
        center_id: int,
        data: CostCenterUpdateData,
    ) -> CostCenter:
        """Update a cost center.

        Args:
            center_id: Cost center ID
            data: Update data

        Returns:
            Updated CostCenter

        Raises:
            NotFoundError: If cost center not found
        """
        center = self.get_cost_center(center_id)

        if data.cost_center_name is not None:
            center.cost_center_name = data.cost_center_name
        if data.cost_center_number is not None:
            center.cost_center_number = data.cost_center_number
        if data.parent_cost_center is not None:
            center.parent_cost_center = data.parent_cost_center
        if data.company is not None:
            center.company = data.company
        if data.is_group is not None:
            center.is_group = data.is_group
        if data.disabled is not None:
            center.disabled = data.disabled
        if data.lft is not None:
            center.lft = data.lft
        if data.rgt is not None:
            center.rgt = data.rgt

        self.db.flush()
        return center

    def disable_cost_center(self, center_id: int) -> None:
        """Disable a cost center (soft delete).

        Args:
            center_id: Cost center ID

        Raises:
            NotFoundError: If cost center not found
        """
        center = self.get_cost_center(center_id)
        center.disabled = True
        self.db.flush()
