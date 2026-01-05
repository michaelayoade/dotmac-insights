"""Payment Terms service.

This module contains business logic for payment terms templates and schedules.
All methods that mutate data do NOT commit. The caller (route handler)
is responsible for calling db.commit() after the operation succeeds.

Args:
    db: SQLAlchemy database session.
    principal: Authenticated user/service token (for audit fields).
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.payment_terms import PaymentTermsTemplate, PaymentTermsSchedule
from app.services.base import paginate, scoped_query
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginatedResult, PaginationParams

from .payment_terms_types import (
    PaymentTermsFilters,
    PaymentTermsCreateData,
    PaymentTermsUpdateData,
    ScheduleData,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["PaymentTermsService"]

# Allowed sort fields
ALLOWED_SORTS = {"template_name", "created_at", "id", "is_active"}


class PaymentTermsService:
    """Service for payment terms business logic.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    def list_payment_terms(
        self,
        filters: Optional[PaymentTermsFilters] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[PaymentTermsTemplate]:
        """List payment terms templates with filters and pagination.

        Args:
            filters: Optional filter criteria.
            pagination: Pagination parameters (offset, limit).

        Returns:
            PaginatedResult containing payment terms and total count.
        """
        if filters is None:
            filters = PaymentTermsFilters()
        if pagination is None:
            pagination = PaginationParams()

        query = self.db.query(PaymentTermsTemplate)
        query = scoped_query(query, self.principal)

        # Apply filters
        if filters.is_active is not None:
            query = query.filter(PaymentTermsTemplate.is_active == filters.is_active)

        if filters.company:
            query = query.filter(PaymentTermsTemplate.company == filters.company)

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    PaymentTermsTemplate.template_name.ilike(search_pattern),
                    PaymentTermsTemplate.description.ilike(search_pattern),
                )
            )

        # Apply sorting
        sort_field = filters.sort_by if filters.sort_by in ALLOWED_SORTS else "template_name"
        sort_column = getattr(PaymentTermsTemplate, sort_field, PaymentTermsTemplate.template_name)
        if filters.sort_dir == "desc":
            query = query.order_by(sort_column.desc(), PaymentTermsTemplate.id.desc())
        else:
            query = query.order_by(sort_column.asc(), PaymentTermsTemplate.id.asc())

        return paginate(query, pagination)

    def get_payment_terms(self, terms_id: int) -> PaymentTermsTemplate:
        """Get payment terms by ID.

        Args:
            terms_id: The payment terms ID.

        Returns:
            The PaymentTermsTemplate object with schedules loaded.

        Raises:
            NotFoundError: If payment terms not found.
        """
        terms = (
            self.db.query(PaymentTermsTemplate)
            .filter(PaymentTermsTemplate.id == terms_id)
            .first()
        )
        if not terms:
            raise NotFoundError(f"Payment terms {terms_id} not found")
        return terms

    def get_payment_terms_by_name(self, template_name: str) -> Optional[PaymentTermsTemplate]:
        """Get payment terms by template name.

        Args:
            template_name: The template name.

        Returns:
            The PaymentTermsTemplate object or None if not found.
        """
        return (
            self.db.query(PaymentTermsTemplate)
            .filter(PaymentTermsTemplate.template_name == template_name)
            .first()
        )

    def validate_schedules(self, schedules: list[ScheduleData]) -> None:
        """Validate that schedule percentages sum to 100%.

        Args:
            schedules: List of schedule data.

        Raises:
            ValidationError: If percentages don't sum to 100%.
        """
        if not schedules:
            return  # Empty schedules are allowed (simple terms with no schedule)

        total_pct = sum(s.payment_percentage for s in schedules)
        if abs(total_pct - Decimal("100")) > Decimal("0.01"):
            raise ValidationError(
                f"Payment percentages must sum to 100%, got {total_pct}%"
            )

    def create_payment_terms(self, data: PaymentTermsCreateData) -> PaymentTermsTemplate:
        """Create new payment terms.

        Validates that template name is unique and schedules sum to 100%.

        Args:
            data: Payment terms creation data.

        Returns:
            The created PaymentTermsTemplate (not yet committed).

        Raises:
            ValidationError: If template name exists or schedules invalid.
        """
        # Check for duplicate
        existing = self.get_payment_terms_by_name(data.template_name)
        if existing:
            raise ValidationError(
                f"Payment terms '{data.template_name}' already exists"
            )

        # Validate schedules
        self.validate_schedules(data.schedules)

        # Create template
        terms = PaymentTermsTemplate(
            template_name=data.template_name,
            description=data.description,
            company=data.company,
            created_by_id=self.principal.id if self.principal else None,
        )
        self.db.add(terms)
        self.db.flush()

        # Add schedules
        for idx, sched in enumerate(data.schedules):
            schedule = PaymentTermsSchedule(
                template_id=terms.id,
                credit_days=sched.credit_days,
                credit_months=sched.credit_months,
                day_of_month=sched.day_of_month,
                payment_percentage=sched.payment_percentage,
                discount_percentage=sched.discount_percentage,
                discount_days=sched.discount_days,
                description=sched.description,
                idx=idx,
            )
            self.db.add(schedule)

        return terms

    def update_payment_terms(
        self, terms_id: int, data: PaymentTermsUpdateData
    ) -> PaymentTermsTemplate:
        """Update payment terms.

        If schedules are provided, existing schedules are replaced atomically.

        Args:
            terms_id: The payment terms ID.
            data: Fields to update.

        Returns:
            The updated PaymentTermsTemplate (not yet committed).

        Raises:
            NotFoundError: If payment terms not found.
            ValidationError: If template name exists or schedules invalid.
        """
        terms = self.get_payment_terms(terms_id)

        if data.template_name is not None:
            # Check for duplicate
            existing = (
                self.db.query(PaymentTermsTemplate)
                .filter(
                    PaymentTermsTemplate.template_name == data.template_name,
                    PaymentTermsTemplate.id != terms_id,
                )
                .first()
            )
            if existing:
                raise ValidationError(
                    f"Payment terms '{data.template_name}' already exists"
                )
            terms.template_name = data.template_name

        if data.description is not None:
            terms.description = data.description

        if data.is_active is not None:
            terms.is_active = data.is_active

        if data.schedules is not None:
            # Validate new schedules
            self.validate_schedules(data.schedules)

            # Remove existing schedules
            self.db.query(PaymentTermsSchedule).filter(
                PaymentTermsSchedule.template_id == terms_id
            ).delete()

            # Add new schedules
            for idx, sched in enumerate(data.schedules):
                schedule = PaymentTermsSchedule(
                    template_id=terms.id,
                    credit_days=sched.credit_days,
                    credit_months=sched.credit_months,
                    day_of_month=sched.day_of_month,
                    payment_percentage=sched.payment_percentage,
                    discount_percentage=sched.discount_percentage,
                    discount_days=sched.discount_days,
                    description=sched.description,
                    idx=idx,
                )
                self.db.add(schedule)

        return terms

    def delete_payment_terms(self, terms_id: int) -> None:
        """Delete payment terms.

        This is a hard delete as payment terms are configuration data.
        Schedules are cascade deleted.

        Args:
            terms_id: The payment terms ID.

        Raises:
            NotFoundError: If payment terms not found.
        """
        terms = self.get_payment_terms(terms_id)
        self.db.delete(terms)

    def disable_payment_terms(self, terms_id: int) -> PaymentTermsTemplate:
        """Disable (soft delete) payment terms.

        Args:
            terms_id: The payment terms ID.

        Returns:
            The updated PaymentTermsTemplate.

        Raises:
            NotFoundError: If payment terms not found.
        """
        terms = self.get_payment_terms(terms_id)
        terms.is_active = False
        return terms

    def enable_payment_terms(self, terms_id: int) -> PaymentTermsTemplate:
        """Enable payment terms.

        Args:
            terms_id: The payment terms ID.

        Returns:
            The updated PaymentTermsTemplate.

        Raises:
            NotFoundError: If payment terms not found.
        """
        terms = self.get_payment_terms(terms_id)
        terms.is_active = True
        return terms
