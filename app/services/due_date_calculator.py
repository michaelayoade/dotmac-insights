"""Due Date Calculator service for payment terms calculations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.payment_terms import PaymentTermsTemplate, PaymentTermsSchedule


@dataclass
class PaymentScheduleItem:
    """A single payment schedule item."""
    due_date: date
    percentage: Decimal
    amount: Decimal
    discount_percentage: Decimal
    discount_amount: Decimal
    discount_deadline: Optional[date]


@dataclass
class DueDateResult:
    """Result of due date calculation."""
    due_date: date
    payment_terms_name: Optional[str]


class DueDateCalculator:
    """
    Service for calculating due dates and payment schedules.

    Supports:
    - Simple net terms (Net 30, Net 60, etc.)
    - Day of month terms (Due on 15th of following month)
    - Split payment schedules (50% now, 50% in 30 days)
    - Early payment discounts (2/10 Net 30)
    """

    def __init__(self, db: Session):
        self.db = db

    def get_payment_terms(self, terms_id: int) -> Optional[PaymentTermsTemplate]:
        """Get payment terms template by ID."""
        return self.db.query(PaymentTermsTemplate).filter(
            PaymentTermsTemplate.id == terms_id
        ).first()

    def calculate_due_date(
        self,
        doc_date: date,
        payment_terms_id: Optional[int] = None,
        credit_days: int = 0,
    ) -> DueDateResult:
        """
        Calculate the due date for a document.

        Args:
            doc_date: Document date (invoice date, bill date, etc.)
            payment_terms_id: ID of payment terms template
            credit_days: Fallback credit days if no terms provided

        Returns:
            DueDateResult with calculated due date
        """
        terms_name = None

        if payment_terms_id:
            terms = self.get_payment_terms(payment_terms_id)
            if terms and terms.schedules:
                terms_name = terms.template_name
                # For simple due date, use the last schedule (typically 100% payment)
                # Find the schedule with the longest credit period
                max_schedule = max(
                    terms.schedules,
                    key=lambda s: self._calculate_days_from_schedule(s)
                )
                due_date = self._apply_schedule_to_date(doc_date, max_schedule)
                return DueDateResult(due_date=due_date, payment_terms_name=terms_name)

        # Fallback to simple credit days
        due_date = doc_date + timedelta(days=credit_days)
        return DueDateResult(due_date=due_date, payment_terms_name=terms_name)

    def calculate_payment_schedule(
        self,
        doc_date: date,
        total_amount: Decimal,
        payment_terms_id: int,
    ) -> List[PaymentScheduleItem]:
        """
        Calculate a complete payment schedule for a document.

        Args:
            doc_date: Document date
            total_amount: Total document amount
            payment_terms_id: ID of payment terms template

        Returns:
            List of PaymentScheduleItem for each payment
        """
        terms = self.get_payment_terms(payment_terms_id)
        if not terms or not terms.schedules:
            # Return single payment due immediately
            return [
                PaymentScheduleItem(
                    due_date=doc_date,
                    percentage=Decimal("100"),
                    amount=total_amount,
                    discount_percentage=Decimal("0"),
                    discount_amount=Decimal("0"),
                    discount_deadline=None,
                )
            ]

        schedule_items = []
        for schedule in sorted(terms.schedules, key=lambda s: s.idx):
            due_date = self._apply_schedule_to_date(doc_date, schedule)
            percentage = schedule.payment_percentage
            amount = total_amount * percentage / Decimal("100")

            # Calculate discount
            discount_percentage = schedule.discount_percentage
            discount_amount = Decimal("0")
            discount_deadline = None

            if discount_percentage > 0 and schedule.discount_days > 0:
                discount_amount = amount * discount_percentage / Decimal("100")
                discount_deadline = doc_date + timedelta(days=schedule.discount_days)

            schedule_items.append(
                PaymentScheduleItem(
                    due_date=due_date,
                    percentage=percentage,
                    amount=amount,
                    discount_percentage=discount_percentage,
                    discount_amount=discount_amount,
                    discount_deadline=discount_deadline,
                )
            )

        return schedule_items

    def get_early_payment_discount(
        self,
        payment_terms_id: int,
        pay_date: date,
        doc_date: date,
        amount: Decimal,
    ) -> Decimal:
        """
        Calculate early payment discount if applicable.

        Args:
            payment_terms_id: ID of payment terms template
            pay_date: Actual payment date
            doc_date: Original document date
            amount: Amount being paid

        Returns:
            Discount amount (0 if not eligible)
        """
        terms = self.get_payment_terms(payment_terms_id)
        if not terms or not terms.schedules:
            return Decimal("0")

        total_discount = Decimal("0")

        for schedule in terms.schedules:
            if schedule.discount_percentage <= 0 or schedule.discount_days <= 0:
                continue

            discount_deadline = doc_date + timedelta(days=schedule.discount_days)
            if pay_date <= discount_deadline:
                # Eligible for discount on this portion
                portion_amount = amount * schedule.payment_percentage / Decimal("100")
                discount = portion_amount * schedule.discount_percentage / Decimal("100")
                total_discount += discount

        return total_discount

    def _apply_schedule_to_date(
        self,
        doc_date: date,
        schedule: PaymentTermsSchedule,
    ) -> date:
        """Apply schedule rules to calculate due date."""
        result_date = doc_date

        # Add months
        if schedule.credit_months > 0:
            # Add months, handling month boundaries
            month = result_date.month + schedule.credit_months
            year = result_date.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1

            # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
            day = min(result_date.day, self._days_in_month(year, month))
            result_date = date(year, month, day)

        # Add days
        if schedule.credit_days > 0:
            result_date = result_date + timedelta(days=schedule.credit_days)

        # Override to specific day of month if set
        if schedule.day_of_month:
            day = min(schedule.day_of_month, self._days_in_month(result_date.year, result_date.month))
            result_date = result_date.replace(day=day)

            # If day has already passed this month, move to next month
            if result_date < doc_date + timedelta(days=schedule.credit_days):
                month = result_date.month + 1
                year = result_date.year
                if month > 12:
                    month = 1
                    year += 1
                day = min(schedule.day_of_month, self._days_in_month(year, month))
                result_date = date(year, month, day)

        return result_date

    def _calculate_days_from_schedule(self, schedule: PaymentTermsSchedule) -> int:
        """Calculate approximate days from a schedule for comparison."""
        days = schedule.credit_days
        days += schedule.credit_months * 30  # Approximate
        return days

    def _days_in_month(self, year: int, month: int) -> int:
        """Get the number of days in a month."""
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - date(year, month, 1)).days
